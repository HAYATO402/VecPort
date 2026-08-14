from vecport import VectorRecord

from vecport.core.migration import (
    migrate_collection,
    plan_migration,
    verify_migration,
)

from types import SimpleNamespace

from vecport.core.models import (
    Capabilities,
    VectorRecord,
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

    def upsert(
        self,
        collection,
        records,
    ):

        self.records.setdefault(
            collection,
            [],
        )

        self.records[
            collection
        ].extend(records)

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
                    vector=[
                        1.0,
                        0.0,
                        0.0,
                    ],
                    metadata={
                        "category": "AI",
                    },
                )
            ],
        )

        target.upsert(
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
                        "category": "Sports",
                    },
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