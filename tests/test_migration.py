from vecport import VectorRecord

from vecport.core.migration import (
    migrate_collection,
    verify_migration,
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


def test_migrate_collection():

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
                metadata={"type": "AI"},
            ),
            VectorRecord(
                id="2",
                vector=[0.9, 0.1, 0.0],
                metadata={"type": "Finance"},
            ),
        ],
    )

    report = migrate_collection(
        source,
        target,
        collection="documents",
        batch_size=1,
    )

    assert report.scanned == 2
    assert report.migrated == 2
    assert report.dimension == 3

    assert len(
        target.records[
            "documents"
        ]
    ) == 2

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