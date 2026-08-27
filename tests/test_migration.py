from types import SimpleNamespace

import pytest

from vecport.core.errors import MigrationError
from vecport.core.migration import (
    migrate_collection,
    plan_migration,
    verify_migration,
)
from vecport.core.models import (
    Capabilities,
    CollectionInfo,
    VectorRecord,
)
from vecport.core.transforms import (
    MetadataTransformer,
    MetadataTransformSpec,
)


class FakeDriver:

    def __init__(self):

        self.records = {}
        self.dimension = None

    def delete_collection(
        self,
        collection,
    ):

        self.records[collection] = []

    def create_collection(
        self,
        collection,
        dimension,
    ):

        self.dimension = dimension
        self.records[collection] = []

    def collection_info(
        self,
        name: str,
    ) -> CollectionInfo:

        if name not in self.records:
            return CollectionInfo(
                name=name,
                exists=False,
            )

        return CollectionInfo(
            name=name,
            exists=True,
            dimension=self.dimension,
            distance_metric="cosine",
            index_type=None,
            index_params=None,
            metadata_schema=None,
        )

    def create_collection_from_info(
        self,
        name: str,
        info: CollectionInfo,
    ) -> None:

        if info.dimension is None:
            raise ValueError(
                "Collection dimension is required."
            )

        self.create_collection(
            name,
            info.dimension,
        )

    def upsert(
        self,
        collection,
        records,
    ):

        stored_records = self.records.setdefault(
            collection,
            [],
        )

        records_by_id = {
            record.id: record
            for record in stored_records
        }

        for record in records:
            records_by_id[record.id] = record

        self.records[collection] = list(
            records_by_id.values()
        )

    def scan(
        self,
        collection,
        *,
        batch_size=100,
    ):

        yield from self.records.get(
            collection,
            []
        )

    def get(
        self,
        collection,
        ids,
    ):

        wanted = set(ids)

        return [
            record
            for record
            in self.records.get(
                collection,
                [],
            )
            if record.id in wanted
        ]

class PlanTargetDatabase(FakeDriver):

    def __init__(self):
        super().__init__()
        self.write_calls = 0

    def capabilities(
        self,
    ):
        return Capabilities(
            dense_vector=True,
            metadata_filter=True,
            filter_operators=(
                "$eq",
                "$ne",
                "$gt",
                "$gte",
                "$lt",
                "$lte",
                "$in",
                "$and",
                "$or",
            ),
            sparse_vector=True,
            hybrid_search=True,
            namespaces=False,
            named_vectors=False,
        )

    def delete_collection(
        self,
        *args,
        **kwargs,
    ):
        self.write_calls += 1

    def create_collection(
        self,
        *args,
        **kwargs,
    ):
        self.write_calls += 1

    def upsert(
        self,
        *args,
        **kwargs,
    ):
        self.write_calls += 1

class PlanSourceDatabase:

    def __init__(
        self,
        records,
    ):
        self.records = records

    def scan(
        self,
        collection,
        batch_size=100,
    ):
        yield from self.records

    def capabilities(
        self,
    ):
        return Capabilities(
            dense_vector=True,
            metadata_filter=True,
            filter_operators=(
                "$eq",
                "$ne",
                "$gt",
                "$gte",
                "$lt",
                "$lte",
                "$in",
                "$and",
                "$or",
            ),
            sparse_vector=True,
            hybrid_search=True,
            namespaces=False,
            named_vectors=False,
        )

    def collection_info(
        self,
        name: str,
    ) -> CollectionInfo:

        if not self.records:
            return CollectionInfo(
                name=name,
                exists=True,
                dimension=None,
                distance_metric="cosine",
                index_type="HNSW",
                index_params=None,
                metadata_schema=None,
            )

        return CollectionInfo(
            name=name,
            exists=True,
            dimension=len(
                self.records[0].vector
            ),
            distance_metric="cosine",
            index_type="HNSW",
            index_params=None,
            metadata_schema=None,
        )

def test_plan_migration_reports_collection_info():

    records = [
        SimpleNamespace(
            id=str(index),
            vector=[
                0.1,
                0.2,
                0.3,
            ],
            metadata={},
        )
        for index in range(10)
    ]

    source = PlanSourceDatabase(
        records
    )

    target = PlanTargetDatabase()

    plan = plan_migration(
        source,
        target,
        source_collection="source",
        target_collection="target",
        batch_size=4,
    )

    assert plan.source_count == 10
    assert plan.dimension == 3
    assert plan.batch_size == 4
    assert plan.estimated_batches == 3

    assert plan.dimensions_ok is True
    assert plan.dense_vector_ok is True
    assert plan.ready is True

    assert len(plan.compatibility) == 7

    checks = {
        check.name: check
        for check in plan.compatibility
    }

    assert (
        checks["Dense vectors"].status
        == "OK"
    )

    assert (
        checks["Metadata filters"].status
        == "OK"
    )

    assert (
        checks["Namespaces"].status
        == "N/A"
    )

    assert target.write_calls == 0

    assert (
        plan.source_info.exists
        is True
    )

    assert (
        plan.source_info.dimension
        == 3
    )

    assert (
        plan.source_info.distance_metric
        == "cosine"
    )

    assert (
        plan.target_info.exists
        is False
    )

    assert (
        plan.target_dimension_ok
        is None
    )

    assert (
        plan.distance_metric_ok
        is None
    )

def test_migration_dry_run():

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
            )
        ],
    )

    report = migrate_collection(
        source,
        target,
        collection="documents",
        dry_run=True,
    )

    assert report.scanned == 1
    assert report.migrated == 0
    assert report.dry_run is True

    assert (
        "documents"
        not in target.records
    )

def test_verify_migration():

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
                metadata={
                    "category": "AI",
                },
            ),
            VectorRecord(
                id="2",
                vector=[
                    0.9,
                    0.1,
                    0.0,
                ],
                metadata={
                    "category": "Finance",
                },
            ),
        ],
    )

    migrate_collection(
        source,
        target,
        collection="documents",
    )

    report = verify_migration(
        source,
        target,
        source_collection="documents",
    )

    assert report.source_count == 2
    assert report.target_count == 2
    assert report.matched_ids == 2
    assert report.missing_ids == 0
    assert report.dimensions_ok is True
    assert report.vectors_ok is True
    assert report.metadata_ok is True
    assert report.passed is True

def test_verify_detects_metadata_mismatch():
    source = FakeDriver()
    target = FakeDriver()

    source.create_collection(
        "documents",
        dimension=3,
    )

    target.create_collection(
        "documents",
        dimension=3,
    )

    source.upsert(
        "documents",
        [
            VectorRecord(
                id="1",
                vector=[1.0, 0.0, 0.0],
                metadata={"category": "AI"},
            )
        ],
    )

    target.upsert(
        "documents",
        [
            VectorRecord(
                id="1",
                vector=[1.0, 0.0, 0.0],
                metadata={"category": "Sports"},
            )
        ],
    )

    report = verify_migration(
        source,
        target,
        source_collection="documents",
    )

    assert report.metadata_ok is False
    assert report.passed is False

def test_plan_migration():

    records = [
        SimpleNamespace(
            id=str(index),
            vector=[
                0.1,
                0.2,
                0.3,
            ],
            metadata={},
        )
        for index in range(10)
    ]

    source = PlanSourceDatabase(
        records
    )

    target = PlanTargetDatabase()

    plan = plan_migration(
        source,
        target,
        source_collection="source",
        target_collection="target",
        batch_size=4,
    )

    assert plan.source_count == 10
    assert plan.dimension == 3
    assert plan.batch_size == 4
    assert plan.estimated_batches == 3

    assert plan.dimensions_ok is True
    assert plan.dense_vector_ok is True
    assert plan.ready is True

    # Compatibility Matrix
    assert len(plan.compatibility) == 7

    checks = {
        check.name: check
        for check in plan.compatibility
    }

    assert (
        checks["Dense vectors"].status
        == "OK"
    )

    assert (
        checks["Metadata filters"].status
        == "OK"
    )

    assert (
        checks["Namespaces"].status
        == "N/A"
    )

    # PlanではTargetに書き込んではいけない
    assert target.write_calls == 0

class ExistingCompatibleTarget(
    PlanTargetDatabase
):

    def collection_info(
        self,
        name: str,
    ) -> CollectionInfo:

        return CollectionInfo(
            name=name,
            exists=True,
            dimension=3,
            distance_metric="cosine",
            index_type="AUTOINDEX",
            index_params=None,
            metadata_schema=None,
        )

def test_plan_existing_target_is_compatible():

    records = [
        SimpleNamespace(
            id="1",
            vector=[
                0.1,
                0.2,
                0.3,
            ],
            metadata={},
        )
    ]

    source = PlanSourceDatabase(
        records
    )

    target = (
        ExistingCompatibleTarget()
    )

    plan = plan_migration(
        source,
        target,
        source_collection="source",
        target_collection="target",
    )

    assert (
        plan.target_dimension_ok
        is True
    )

    assert (
        plan.distance_metric_ok
        is True
    )

    assert plan.ready is True

    assert target.write_calls == 0

class IncompatibleTarget(
    PlanTargetDatabase
):

    def collection_info(
        self,
        name: str,
    ) -> CollectionInfo:

        return CollectionInfo(
            name=name,
            exists=True,
            dimension=384,
            distance_metric="dot",
            index_type="AUTOINDEX",
            index_params=None,
            metadata_schema=None,
        )

def test_plan_detects_target_incompatibility():

    records = [
        SimpleNamespace(
            id="1",
            vector=[
                0.1,
                0.2,
                0.3,
            ],
            metadata={},
        )
    ]

    source = PlanSourceDatabase(
        records
    )

    target = IncompatibleTarget()

    plan = plan_migration(
        source,
        target,
        source_collection="source",
        target_collection="target",
    )

    assert (
        plan.target_dimension_ok
        is False
    )

    assert (
        plan.distance_metric_ok
        is False
    )

    assert plan.ready is False

    assert target.write_calls == 0

def test_migration_resume_repairs_mismatch():

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
                metadata={
                    "version": "new",
                },
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
                vector=[
                    0.0,
                    1.0,
                    0.0,
                ],
                metadata={
                    "version": "old",
                },
            ),
        ],
    )

    report = migrate_collection(
        source,
        target,
        collection="documents",
        resume=True,
        existing_policy="repair",
    )

    assert report.migrated == 1
    assert report.repaired_existing == 1
    assert report.skipped_existing == 0
    assert report.existing_policy == "repair"

    result = target.get(
        "documents",
        ["1"],
    )

    assert len(result) == 1

    assert result[0].vector == [
        1.0,
        0.0,
        0.0,
    ]

    assert result[0].metadata == {
        "version": "new",
    }

def test_migration_resume_repair_skips_matching():

    source = FakeDriver()
    target = FakeDriver()

    record = VectorRecord(
        id="1",
        vector=[
            1.0,
            0.0,
            0.0,
        ],
        metadata={
            "version": "same",
        },
    )

    source.create_collection(
        "documents",
        dimension=3,
    )

    target.create_collection(
        "documents",
        dimension=3,
    )

    source.upsert(
        "documents",
        [record],
    )

    target.upsert(
        "documents",
        [record],
    )

    report = migrate_collection(
        source,
        target,
        collection="documents",
        resume=True,
        existing_policy="repair",
    )

    assert report.migrated == 0
    assert report.repaired_existing == 0
    assert report.skipped_existing == 1
    assert report.existing_policy == "repair"

def test_migration_resume_errors_on_mismatch():

    source = FakeDriver()
    target = FakeDriver()

    source.create_collection(
        "documents",
        dimension=3,
    )

    target.create_collection(
        "documents",
        dimension=3,
    )

    source.upsert(
        "documents",
        [
            VectorRecord(
                id="1",
                vector=[1.0, 0.0, 0.0],
                metadata={},
            ),
        ],
    )

    target.upsert(
        "documents",
        [
            VectorRecord(
                id="1",
                vector=[0.0, 1.0, 0.0],
                metadata={},
            ),
        ],
    )

    with pytest.raises(
        MigrationError,
        match="Resume conflict",
    ):
        migrate_collection(
            source,
            target,
            collection="documents",
            resume=True,
            existing_policy="error",
        )

def test_migration_reports_progress():

    source = FakeDriver()
    target = FakeDriver()

    source.create_collection(
        "documents",
        dimension=3,
    )

    records = [
        VectorRecord(
            id=str(index),
            vector=[
                1.0,
                0.0,
                0.0,
            ],
            metadata={},
        )
        for index in range(5)
    ]

    source.upsert(
        "documents",
        records,
    )

    events = []

    migrate_collection(
        source,
        target,
        collection="documents",
        batch_size=2,
        total_records=5,
        progress_callback=events.append,
    )

    assert len(events) == 3

    assert [
        event.scanned
        for event in events
    ] == [
        2,
        4,
        5,
    ]

    final = events[-1]

    assert final.total_records == 5
    assert final.percent == 100.0
    assert final.batches_completed == 3

    assert (
        final.records_per_second
        >= 0
    )

    assert (
        final.eta_seconds
        is not None
    )


def test_migration_applies_record_transform():
    source = FakeDriver()
    target = FakeDriver()
    source.create_collection(
        "documents",
        dimension=2,
    )
    source.upsert(
        "documents",
        [
            VectorRecord(
                id="1",
                vector=[1.0, 0.0],
                metadata={
                    "old_category": "AI",
                    "price": "5000",
                },
            )
        ],
    )
    transformer = MetadataTransformer(
        MetadataTransformSpec(
            rename={
                "old_category": "category",
            },
            cast={
                "price": "int",
            },
        )
    )

    migrate_collection(
        source,
        target,
        collection="documents",
        record_transform=transformer,
    )

    migrated = target.get(
        "documents",
        ["1"],
    )
    assert migrated[0].metadata == {
        "category": "AI",
        "price": 5000,
    }
    assert source.get(
        "documents",
        ["1"],
    )[0].metadata == {
        "old_category": "AI",
        "price": "5000",
    }


def test_resume_compares_transformed_metadata():
    source = FakeDriver()
    target = FakeDriver()
    source.create_collection(
        "documents",
        dimension=2,
    )
    source.upsert(
        "documents",
        [
            VectorRecord(
                id="1",
                vector=[1.0, 0.0],
                metadata={"old": "value"},
            )
        ],
    )
    target.create_collection(
        "documents",
        dimension=2,
    )
    target.upsert(
        "documents",
        [
            VectorRecord(
                id="1",
                vector=[1.0, 0.0],
                metadata={"new": "value"},
            )
        ],
    )
    transformer = MetadataTransformer(
        MetadataTransformSpec(
            rename={"old": "new"}
        )
    )

    report = migrate_collection(
        source,
        target,
        collection="documents",
        resume=True,
        existing_policy="repair",
        record_transform=transformer,
    )

    assert report.migrated == 0
    assert report.skipped_existing == 1
    assert report.repaired_existing == 0


def test_migration_resume_skips_existing():
    source = FakeDriver()
    target = FakeDriver()

    source.create_collection("documents", dimension=3)
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
    target.create_collection("documents", dimension=3)
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
    assert report.skipped_existing == 1
    assert report.resumed is True
    assert len(list(target.scan("documents"))) == 2


def test_migration_resume_rejects_dimension_mismatch():
    source = FakeDriver()
    target = FakeDriver()
    source.create_collection("documents", dimension=3)
    source.upsert(
        "documents",
        [
            VectorRecord(
                id="1",
                vector=[1.0, 0.0, 0.0],
                metadata={},
            ),
        ],
    )
    target.create_collection("documents", dimension=2)

    with pytest.raises(MigrationError):
        migrate_collection(
            source,
            target,
            collection="documents",
            resume=True,
        )


def test_migration_resume_rejects_recreate():
    source = FakeDriver()
    target = FakeDriver()

    with pytest.raises(MigrationError):
        migrate_collection(
            source,
            target,
            collection="documents",
            resume=True,
            recreate_target=True,
        )
