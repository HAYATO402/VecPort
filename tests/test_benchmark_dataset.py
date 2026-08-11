from vecport.core.benchmark_dataset import (
    iter_benchmark_batches,
    load_benchmark_dataset,
)


class FakeDatasetDriver:

    def __init__(self):
        self.records = {}
        self.dimension = None

    def delete_collection(
        self,
        collection,
    ):
        self.records.pop(
            collection,
            None,
        )

    def create_collection(
        self,
        collection,
        dimension,
    ):
        self.dimension = dimension
        self.records[
            collection
        ] = []

    def upsert(
        self,
        collection,
        records,
    ):
        self.records[
            collection
        ].extend(
            records
        )


def test_benchmark_dataset_generator():

    batches = list(
        iter_benchmark_batches(
            count=5,
            dimension=3,
            batch_size=2,
            seed=42,
        )
    )

    assert len(batches) == 3

    records = [
        record
        for batch in batches
        for record in batch
    ]

    assert len(records) == 5

    for record in records:
        assert len(
            record.vector
        ) == 3


def test_benchmark_dataset_is_deterministic():

    first = list(
        iter_benchmark_batches(
            count=3,
            dimension=3,
            seed=42,
        )
    )

    second = list(
        iter_benchmark_batches(
            count=3,
            dimension=3,
            seed=42,
        )
    )

    first_records = [
        record
        for batch in first
        for record in batch
    ]

    second_records = [
        record
        for batch in second
        for record in batch
    ]

    assert (
        first_records[0].id
        == second_records[0].id
    )

    assert (
        first_records[0].vector
        == second_records[0].vector
    )


def test_load_benchmark_dataset():

    db = FakeDatasetDriver()

    report = load_benchmark_dataset(
        db,
        collection="benchmark",
        count=5,
        dimension=3,
        batch_size=2,
    )

    assert report.count == 5
    assert report.dimension == 3

    assert len(
        db.records["benchmark"]
    ) == 5