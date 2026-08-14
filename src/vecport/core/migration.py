import math
from dataclasses import (
    dataclass,
    replace,
)


@dataclass(frozen=True)
class MigrationReport:

    source_collection: str
    target_collection: str

    scanned: int
    migrated: int

    dimension: int | None

    dry_run: bool

    resumed: bool = False
    skipped_existing: int = 0

from itertools import chain

from vecport.core.errors import (
    MigrationError,
)

from vecport.core.models import (
    CollectionInfo,
)

@dataclass(frozen=True)
class CompatibilityCheck:
    name: str
    source_supported: bool
    target_supported: bool
    status: str
    detail: str | None = None

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
    compatibility: tuple[CompatibilityCheck, ...]

    source_info: CollectionInfo
    target_info: CollectionInfo

    target_dimension_ok: bool | None
    distance_metric_ok: bool | None

    ready: bool

def _compatibility_status(
    source_supported: bool,
    target_supported: bool,
) -> str:

    if (
        source_supported
        and target_supported
    ):
        return "OK"

    if (
        source_supported
        and not target_supported
    ):
        return "WARN"

    return "N/A"

def _build_compatibility_checks(
    source_capabilities,
    target_capabilities,
) -> tuple[CompatibilityCheck, ...]:

    checks = []

    capability_fields = (
        (
            "dense_vector",
            "Dense vectors",
        ),
        (
            "metadata_filter",
            "Metadata filters",
        ),
        (
            "sparse_vector",
            "Sparse vectors",
        ),
        (
            "hybrid_search",
            "Hybrid search",
        ),
        (
            "namespaces",
            "Namespaces",
        ),
        (
            "named_vectors",
            "Named vectors",
        ),
    )

    for attribute, label in capability_fields:

        source_supported = getattr(
            source_capabilities,
            attribute,
        )

        target_supported = getattr(
            target_capabilities,
            attribute,
        )

        status = _compatibility_status(
            source_supported,
            target_supported,
        )

        detail = None

        if status == "WARN":
            detail = (
                "Supported by source driver "
                "but not target driver."
            )

        checks.append(
            CompatibilityCheck(
                name=label,
                source_supported=source_supported,
                target_supported=target_supported,
                status=status,
                detail=detail,
            )
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

        operator_status = "WARN"

        operator_detail = (
            "Missing on target: "
            + ", ".join(
                missing_operators
            )
        )

    else:
        operator_status = "OK"
        operator_detail = None

    checks.append(
        CompatibilityCheck(
            name="Filter operators",
            source_supported=bool(
                source_operators
            ),
            target_supported=bool(
                target_operators
            ),
            status=operator_status,
            detail=operator_detail,
        )
    )

    return tuple(
        checks
    )


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

def _target_dimension_compatible(
    source_dimension: int | None,
    target_info: CollectionInfo,
) -> bool | None:

    if target_info.exists is not True:
        return None

    if (
        source_dimension is None
        or target_info.dimension is None
    ):
        return None

    return (
        source_dimension
        == target_info.dimension
    )

def _distance_metric_compatible(
    source_info: CollectionInfo,
    target_info: CollectionInfo,
) -> bool | None:

    if target_info.exists is not True:
        return None

    if (
        source_info.distance_metric is None
        or target_info.distance_metric is None
    ):
        return None

    return (
        source_info.distance_metric
        == target_info.distance_metric
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

    compatibility = (
        _build_compatibility_checks(
            source_capabilities,
            target_capabilities,
        )
    )

    source_info = (
        source.collection_info(
            source_collection
        )
    )

    target_info = (
        target.collection_info(
            destination
        )
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
            compatibility=compatibility,
            source_info=source_info,
            target_info=target_info,
            target_dimension_ok=None,
            distance_metric_ok=(
                _distance_metric_compatible(
                    source_info,
                    target_info,
                )
            ),
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

    target_dimension_ok = (
        _target_dimension_compatible(
            dimension,
            target_info,
        )
    )

    distance_metric_ok = (
        _distance_metric_compatible(
            source_info,
            target_info,
        )
    )

    ready = (
        source_count > 0
        and dimensions_ok
        and dense_vector_ok
        and target_dimension_ok is not False
        and distance_metric_ok is not False
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
        compatibility=compatibility,
        source_info=source_info,
        target_info=target_info,
        target_dimension_ok=target_dimension_ok,
        distance_metric_ok=distance_metric_ok,
        ready=ready,
    )

def _filter_existing_records(
    target,
    collection: str,
    records,
):
    ids = [
        record.id
        for record in records
    ]

    existing_records = target.get(
        collection,
        ids,
    )

    existing_ids = {
        record.id
        for record in existing_records
    }

    pending_records = [
        record
        for record in records
        if record.id not in existing_ids
    ]

    skipped = (
        len(records)
        - len(pending_records)
    )

    return (
        pending_records,
        skipped,
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
    resume: bool = False,
) -> MigrationReport:

    if batch_size <= 0:
        raise MigrationError(
            "batch_size must be greater than 0"
        )

    if (
        resume
        and recreate_target
    ):
        raise MigrationError(
            "resume cannot be used "
            "with recreate_target"
        )

    if (
        resume
        and dry_run
    ):
        raise MigrationError(
            "resume cannot be used "
            "with dry_run"
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

    source_info = (
        source.collection_info(
            collection
        )
    )

    creation_info = replace(
        source_info,
        name=destination,
        dimension=(
            source_info.dimension
            or dimension
        ),
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

    target_info = (
        target.collection_info(
            destination
        )
    )

    if resume:

        if target_info.exists is None:
            raise MigrationError(
                "Resume requires target "
                "collection existence "
                "to be detectable."
            )

        if target_info.exists is True:

            dimension_ok = (
                _target_dimension_compatible(
                    dimension,
                    target_info,
                )
            )

            metric_ok = (
                _distance_metric_compatible(
                    source_info,
                    target_info,
                )
            )

            if dimension_ok is False:
                raise MigrationError(
                    "Cannot resume migration: "
                    "target dimension differs "
                    "from source."
                )

            if metric_ok is False:
                raise MigrationError(
                    "Cannot resume migration: "
                    "target distance metric "
                    "differs from source."
                )

    if resume:

        if target_info.exists is False:
            target.create_collection_from_info(
                destination,
                creation_info,
            )

    else:

        if recreate_target:
            target.delete_collection(
                destination
            )

        target.create_collection_from_info(
            destination,
            creation_info,
        )

    buffer = []
    scanned = 0
    migrated = 0
    skipped_existing = 0

    for record in records:

        scanned += 1

        if len(record.vector) != dimension:
            raise MigrationError(
                "Source collection contains vectors "
                "with inconsistent dimensions"
            )

        buffer.append(record)

        if len(buffer) >= batch_size:

            records_to_write = buffer

            if resume:

                (
                    records_to_write,
                    skipped,
                ) = _filter_existing_records(
                    target,
                    destination,
                    buffer,
                )

                skipped_existing += skipped

            if records_to_write:

                target.upsert(
                    destination,
                    records_to_write,
                )

                migrated += len(
                    records_to_write
                )

            buffer = []

    if buffer:

        records_to_write = buffer

        if resume:

            (
                records_to_write,
                skipped,
            ) = _filter_existing_records(
                target,
                destination,
                buffer,
            )

            skipped_existing += skipped

        if records_to_write:

            target.upsert(
                destination,
                records_to_write,
            )

            migrated += len(
                records_to_write
            )

    return MigrationReport(
        source_collection=collection,
        target_collection=destination,
        scanned=scanned,
        migrated=migrated,
        dimension=dimension,
        dry_run=False,
        resumed=resume,
        skipped_existing=skipped_existing,
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

def test_migration_resume_skips_existing():

    source = FakeDriver()
    target = FakeDriver()

    source.create_collection(
        "documents",
        dimension=3,
    )

    source.upsert(
        "documents",
        [
            VectorRecord(
                id="1",
                vector=[1.0, 0.0, 0.0],
                metadata={"value": 1},
            ),
            VectorRecord(
                id="2",
                vector=[0.0, 1.0, 0.0],
                metadata={"value": 2},
            ),
        ],
    )

    target.create_collection(
        "documents",
        dimension=3,
    )

    target.upsert(
        "documents",
        [
            VectorRecord(
                id="1",
                vector=[1.0, 0.0, 0.0],
                metadata={"value": 1},
            ),
        ],
    )

    report = migrate_collection(
        source,
        target,
        collection="documents",
        resume=True,
    )

    assert report.scanned == 2
    assert report.migrated == 1

    assert (
        report.skipped_existing
        == 1
    )

    assert report.resumed is True

    records = target.scan(
        "documents"
    )

    assert len(
        list(records)
    ) == 2

def test_migration_resume_rejects_dimension_mismatch():

    source = FakeDriver()
    target = FakeDriver()

    source.create_collection(
        "documents",
        dimension=3,
    )

    source.upsert(
        "documents",
        [
            VectorRecord(
                id="1",
                vector=[
                    1.0,
                    0.0,
                    0.0,
                ],
                metadata={},
            ),
        ],
    )

    target.create_collection(
        "documents",
        dimension=2,
    )

    with pytest.raises(
        MigrationError
    ):
        migrate_collection(
            source,
            target,
            collection="documents",
            resume=True,
        )

def test_migration_resume_rejects_recreate():

    source = FakeDriver()
    target = FakeDriver()

    with pytest.raises(
        MigrationError
    ):
        migrate_collection(
            source,
            target,
            collection="documents",
            resume=True,
            recreate_target=True,
        )