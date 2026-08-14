import math
from dataclasses import dataclass


@dataclass(frozen=True)
class MigrationReport:

    source_collection: str
    target_collection: str

    scanned: int
    migrated: int

    dimension: int | None

    dry_run: bool

from itertools import chain

from vecport.core.errors import (
    MigrationError,
)

@dataclass(frozen=True)
class MigrationPlan:
    source_collection: str
    target_collection: str

    source_count: int
    dimension: int | None

    batch_size: int
    estimated_batches: int

    dimensions_ok: bool
    dense_vector_ok: bool

    capability_gaps: tuple[str, ...]

    ready: bool


def _migration_capability_gaps(
    source_capabilities,
    target_capabilities,
) -> tuple[str, ...]:

    gaps = []

    capability_fields = (
        (
            "metadata_filter",
            "metadata filtering",
        ),
        (
            "sparse_vector",
            "sparse vectors",
        ),
        (
            "hybrid_search",
            "hybrid search",
        ),
        (
            "namespaces",
            "namespaces",
        ),
        (
            "named_vectors",
            "named vectors",
        ),
    )

    for attribute, label in capability_fields:

        source_supports = getattr(
            source_capabilities,
            attribute,
        )

        target_supports = getattr(
            target_capabilities,
            attribute,
        )

        if (
            source_supports
            and not target_supports
        ):
            gaps.append(
                label
            )

    source_operators = set(
        source_capabilities.filter_operators
    )

    target_operators = set(
        target_capabilities.filter_operators
    )

    missing_operators = sorted(
        source_operators
        - target_operators
    )

    if missing_operators:

        gaps.append(
            "filter operators: "
            + ", ".join(
                missing_operators
            )
        )

    return tuple(
        gaps
    )

def plan_migration(
    source,
    target,
    *,
    source_collection: str,
    target_collection: str | None = None,
    batch_size: int = 100,
) -> MigrationPlan:

    if batch_size <= 0:
        raise MigrationError(
            "batch_size must be greater than 0"
        )

    destination = (
        target_collection
        or source_collection
    )

    source_capabilities = (
        source.capabilities()
    )

    target_capabilities = (
        target.capabilities()
    )

    source_records = iter(
        source.scan(
            source_collection,
            batch_size=batch_size,
        )
    )

    first_record = next(
        source_records,
        None,
    )

    if first_record is None:

        capability_gaps = (
            _migration_capability_gaps(
                source_capabilities,
                target_capabilities,
            )
        )

        return MigrationPlan(
            source_collection=source_collection,
            target_collection=destination,
            source_count=0,
            dimension=None,
            batch_size=batch_size,
            estimated_batches=0,
            dimensions_ok=True,
            dense_vector_ok=(
                source_capabilities.dense_vector
                and target_capabilities.dense_vector
            ),
            capability_gaps=capability_gaps,
            ready=False,
        )

    dimension = len(
        first_record.vector
    )

    source_count = 1
    dimensions_ok = True

    for record in source_records:

        source_count += 1

        if (
            len(record.vector)
            != dimension
        ):
            dimensions_ok = False

    estimated_batches = (
        source_count
        + batch_size
        - 1
    ) // batch_size

    dense_vector_ok = (
        source_capabilities.dense_vector
        and target_capabilities.dense_vector
    )

    capability_gaps = (
        _migration_capability_gaps(
            source_capabilities,
            target_capabilities,
        )
    )

    ready = (
        source_count > 0
        and dimensions_ok
        and dense_vector_ok
    )

    return MigrationPlan(
        source_collection=source_collection,
        target_collection=destination,
        source_count=source_count,
        dimension=dimension,
        batch_size=batch_size,
        estimated_batches=estimated_batches,
        dimensions_ok=dimensions_ok,
        dense_vector_ok=dense_vector_ok,
        capability_gaps=capability_gaps,
        ready=ready,
    )

def migrate_collection(
    source,
    target,
    *,
    collection: str,
    target_collection: str | None = None,
    batch_size: int = 100,
    recreate_target: bool = False,
    dry_run: bool = False,
) -> MigrationReport:

    if batch_size <= 0:
        raise MigrationError(
            "batch_size must be greater than 0"
        )

    destination = (
        target_collection
        or collection
    )

    source_records = iter(
        source.scan(
            collection,
            batch_size=batch_size,
        )
    )

    first_record = next(
        source_records,
        None,
    )

    if first_record is None:

        return MigrationReport(
            source_collection=collection,
            target_collection=destination,
            scanned=0,
            migrated=0,
            dimension=None,
            dry_run=dry_run,
        )

    dimension = len(
        first_record.vector
    )

    records = chain(
        [first_record],
        source_records,
    )

    if dry_run:

        scanned = sum(
            1
            for _ in records
        )

        return MigrationReport(
            source_collection=collection,
            target_collection=destination,
            scanned=scanned,
            migrated=0,
            dimension=dimension,
            dry_run=True,
        )

    if recreate_target:

        target.delete_collection(
            destination
        )

    target.create_collection(
        destination,
        dimension=dimension,
    )

    buffer = []
    scanned = 0
    migrated = 0

    for record in records:

        scanned += 1

        if len(record.vector) != dimension:
            raise MigrationError(
                "Source collection contains vectors "
                "with inconsistent dimensions"
            )

        buffer.append(record)

        if len(buffer) >= batch_size:

            target.upsert(
                destination,
                buffer,
            )

            migrated += len(buffer)

            buffer = []

    if buffer:

        target.upsert(
            destination,
            buffer,
        )

        migrated += len(buffer)

    return MigrationReport(
        source_collection=collection,
        target_collection=destination,
        scanned=scanned,
        migrated=migrated,
        dimension=dimension,
        dry_run=False,
    )

def verify_migration(
    source,
    target,
    *,
    source_collection: str,
    target_collection: str | None = None,
    batch_size: int = 100,
    rel_tol: float = 1e-6,
    abs_tol: float = 1e-6,
) -> VerificationReport:

    if batch_size <= 0:
        raise MigrationError(
            "batch_size must be greater than 0"
        )

    destination = (
        target_collection
        or source_collection
    )

    source_count = 0
    matched_ids = 0

    dimensions_ok = True
    vectors_ok = True
    metadata_ok = True

    source_batch = []

    def verify_batch(records):

        nonlocal matched_ids
        nonlocal dimensions_ok
        nonlocal vectors_ok
        nonlocal metadata_ok

        ids = [
            record.id
            for record in records
        ]

        target_records = target.get(
            destination,
            ids,
        )

        target_by_id = {
            record.id: record
            for record in target_records
        }

        for source_record in records:

            target_record = target_by_id.get(
                source_record.id
            )

            if target_record is None:
                continue

            matched_ids += 1

            if (
                len(source_record.vector)
                != len(target_record.vector)
            ):
                dimensions_ok = False
                vectors_ok = False
                continue

            for source_value, target_value in zip(
                source_record.vector,
                target_record.vector,
            ):

                if not math.isclose(
                    float(source_value),
                    float(target_value),
                    rel_tol=rel_tol,
                    abs_tol=abs_tol,
                ):
                    vectors_ok = False
                    break

            if (
                source_record.metadata
                != target_record.metadata
            ):
                metadata_ok = False

    for record in source.scan(
        source_collection,
        batch_size=batch_size,
    ):

        source_count += 1
        source_batch.append(record)

        if len(source_batch) >= batch_size:

            verify_batch(
                source_batch
            )

            source_batch = []

    if source_batch:

        verify_batch(
            source_batch
        )

    target_count = sum(
        1
        for _ in target.scan(
            destination,
            batch_size=batch_size,
        )
    )

    missing_ids = (
        source_count
        - matched_ids
    )

    extra_records = max(
        target_count
        - matched_ids,
        0,
    )

    passed = (
        source_count == target_count
        and matched_ids == source_count
        and dimensions_ok
        and vectors_ok
        and metadata_ok
    )

    return VerificationReport(
        source_count=source_count,
        target_count=target_count,
        matched_ids=matched_ids,
        missing_ids=missing_ids,
        extra_records=extra_records,
        dimensions_ok=dimensions_ok,
        vectors_ok=vectors_ok,
        metadata_ok=metadata_ok,
        passed=passed,
    )

@dataclass(frozen=True)
class VerificationReport:
    source_count: int
    target_count: int
    matched_ids: int
    missing_ids: int
    extra_records: int
    dimensions_ok: bool
    vectors_ok: bool
    metadata_ok: bool
    passed: bool