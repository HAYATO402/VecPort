import pytest

from vecport.core.benchmark import (
    benchmark_search,
    compare_benchmarks,
)


class FakeBenchmarkDriver:

    def search(
        self,
        collection,
        vector,
        top_k=10,
        filters=None,
    ):
        return []


def test_benchmark_search():

    db = FakeBenchmarkDriver()

    report = benchmark_search(
        db,
        label="fake",
        collection="documents",
        vector=[
            1.0,
            0.0,
            0.0,
        ],
        iterations=5,
        warmup=0,
    )

    assert report.requests == 5
    assert report.successes == 5
    assert report.failures == 0
    assert report.success_rate == 100
    assert report.average_ms >= 0
    assert report.p50_ms >= 0
    assert report.p95_ms >= 0
    assert report.p99_ms >= 0

class FailingBenchmarkDriver:

    def search(
        self,
        collection,
        vector,
        top_k=10,
        filters=None,
    ):
        raise RuntimeError(
            "Search failed"
        )


def test_benchmark_counts_failures():

    db = FailingBenchmarkDriver()

    report = benchmark_search(
        db,
        label="failing",
        collection="documents",
        vector=[
            1.0,
            0.0,
            0.0,
        ],
        iterations=3,
        warmup=0,
    )

    assert report.requests == 3
    assert report.successes == 0
    assert report.failures == 3
    assert report.success_rate == 0

def test_benchmark_rejects_invalid_iterations():

    db = FakeBenchmarkDriver()

    with pytest.raises(
        ValueError
    ):
        benchmark_search(
            db,
            label="fake",
            collection="documents",
            vector=[
                1.0,
                0.0,
                0.0,
            ],
            iterations=0,
        )


def test_compare_benchmarks():
    first = FakeBenchmarkDriver()
    second = FakeBenchmarkDriver()

    comparison = compare_benchmarks(
        [
            ("first", first),
            ("second", second),
        ],
        collection="documents",
        vector=[1.0, 0.0, 0.0],
        iterations=3,
        warmup=0,
    )

    assert len(comparison.reports) == 2
    assert comparison.reports[0].label == "first"
    assert comparison.reports[1].label == "second"
