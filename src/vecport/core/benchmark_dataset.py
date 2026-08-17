import logging
import math
import random
import time
import uuid
from dataclasses import dataclass

from vecport import VectorRecord

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BenchmarkDatasetReport:
    collection: str
    count: int
    dimension: int
    batch_size: int
    elapsed_seconds: float
    records_per_second: float

def _make_vector(
    rng: random.Random,
    dimension: int,
) -> list[float]:

    values = [
        rng.random()
        for _ in range(dimension)
    ]

    norm = math.sqrt(
        sum(
            value * value
            for value in values
        )
    )

    if norm == 0:
        return values

    return [
        value / norm
        for value in values
    ]

def iter_benchmark_batches(
    *,
    count: int,
    dimension: int,
    batch_size: int = 500,
    seed: int = 42,
):

    if count <= 0:
        raise ValueError(
            "count must be greater than 0"
        )

    if dimension <= 0:
        raise ValueError(
            "dimension must be greater than 0"
        )

    if batch_size <= 0:
        raise ValueError(
            "batch_size must be greater than 0"
        )

    rng = random.Random(
        seed
    )

    batch = []

    for index in range(count):

        record_id = str(
            uuid.uuid5(
                uuid.NAMESPACE_URL,
                (
                    f"vecport-benchmark-"
                    f"{seed}-{index}"
                ),
            )
        )

        record = VectorRecord(
            id=record_id,
            vector=_make_vector(
                rng,
                dimension,
            ),
            metadata={
                "benchmark_index": index,
                "benchmark_seed": seed,
            },
        )

        batch.append(
            record
        )

        if len(batch) >= batch_size:

            yield batch

            batch = []

    if batch:
        yield batch

def load_benchmark_dataset(
    db,
    *,
    collection: str,
    count: int,
    dimension: int,
    batch_size: int = 500,
    seed: int = 42,
    recreate: bool = True,
) -> BenchmarkDatasetReport:

    if recreate:

        try:
            db.delete_collection(
                collection
            )

        except Exception as exc:  # noqa: BLE001
            logger.debug(
                "Could not delete benchmark collection %s: %s",
                collection,
                exc,
            )

    db.create_collection(
        collection,
        dimension=dimension,
    )

    started = time.perf_counter()

    inserted = 0

    for batch in iter_benchmark_batches(
        count=count,
        dimension=dimension,
        batch_size=batch_size,
        seed=seed,
    ):

        db.upsert(
            collection,
            batch,
        )

        inserted += len(batch)

    elapsed = (
        time.perf_counter()
        - started
    )

    throughput = (
        inserted / elapsed
        if elapsed > 0
        else 0.0
    )

    return BenchmarkDatasetReport(
        collection=collection,
        count=inserted,
        dimension=dimension,
        batch_size=batch_size,
        elapsed_seconds=elapsed,
        records_per_second=throughput,
    )

def make_benchmark_query(
    *,
    dimension: int,
    seed: int = 999,
) -> list[float]:

    if dimension <= 0:
        raise ValueError(
            "dimension must be greater than 0"
        )

    rng = random.Random(
        seed
    )

    return _make_vector(
        rng,
        dimension,
    )
