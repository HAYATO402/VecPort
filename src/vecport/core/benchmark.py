import math
import time

from dataclasses import dataclass


@dataclass(frozen=True)
class BenchmarkReport:
    label: str
    requests: int
    successes: int
    failures: int

    average_ms: float
    p50_ms: float
    p95_ms: float
    p99_ms: float

    success_rate: float


def _percentile(
    values: list[float],
    percentile: float,
) -> float:

    if not values:
        return 0.0

    ordered = sorted(values)

    index = math.ceil(
        percentile
        / 100
        * len(ordered)
    ) - 1

    index = max(
        0,
        min(
            index,
            len(ordered) - 1,
        ),
    )

    return ordered[index]


def benchmark_search(
    db,
    *,
    label: str,
    collection: str,
    vector: list[float],
    top_k: int = 10,
    iterations: int = 20,
    warmup: int = 3,
) -> BenchmarkReport:

    if iterations <= 0:
        raise ValueError(
            "iterations must be greater than 0"
        )

    if top_k <= 0:
        raise ValueError(
            "top_k must be greater than 0"
        )

    if warmup < 0:
        raise ValueError(
            "warmup cannot be negative"
        )

    if not vector:
        raise ValueError(
            "vector cannot be empty"
        )

    for _ in range(warmup):
        db.search(
            collection,
            vector,
            top_k=top_k,
        )

    latencies = []
    successes = 0
    failures = 0

    for _ in range(iterations):

        started = time.perf_counter()

        try:

            db.search(
                collection,
                vector,
                top_k=top_k,
            )

            successes += 1

        except Exception:
            failures += 1

        elapsed_ms = (
            time.perf_counter()
            - started
        ) * 1000

        latencies.append(
            elapsed_ms
        )

    average_ms = (
        sum(latencies)
        / len(latencies)
    )

    return BenchmarkReport(
        label=label,
        requests=iterations,
        successes=successes,
        failures=failures,
        average_ms=average_ms,
        p50_ms=_percentile(
            latencies,
            50,
        ),
        p95_ms=_percentile(
            latencies,
            95,
        ),
        p99_ms=_percentile(
            latencies,
            99,
        ),
        success_rate=(
            successes
            / iterations
            * 100
        ),
    )