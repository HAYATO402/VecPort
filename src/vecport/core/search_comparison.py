from __future__ import annotations

import json
import math
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def _validate_ratio(
    value: float,
    *,
    name: str,
) -> None:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
        or not 0.0 <= float(value) <= 1.0
    ):
        raise ValueError(
            f"{name} must be between 0.0 and 1.0."
        )


@dataclass(frozen=True)
class SearchQuery:
    """One stable query vector used against both databases."""

    id: str
    vector: tuple[float, ...]


@dataclass(frozen=True)
class SearchComparisonConfig:
    """Quality thresholds and timing options for a comparison."""

    top_k: int = 10
    warmup: int = 3
    minimum_recall_at_k: float = 0.90
    minimum_top1_match_rate: float = 0.80

    def __post_init__(self) -> None:
        if (
            isinstance(self.top_k, bool)
            or not isinstance(self.top_k, int)
            or self.top_k <= 0
        ):
            raise ValueError(
                "top_k must be greater than 0."
            )

        if (
            isinstance(self.warmup, bool)
            or not isinstance(self.warmup, int)
            or self.warmup < 0
        ):
            raise ValueError(
                "warmup cannot be negative."
            )

        _validate_ratio(
            self.minimum_recall_at_k,
            name="minimum_recall_at_k",
        )
        _validate_ratio(
            self.minimum_top1_match_rate,
            name="minimum_top1_match_rate",
        )


@dataclass(frozen=True)
class QueryComparisonResult:
    """Internal result for one query comparison."""

    query_id: str = field(repr=False)
    source_ids: tuple[str, ...] = field(
        repr=False
    )
    target_ids: tuple[str, ...] = field(
        repr=False
    )
    overlap_count: int
    recall_at_k: float
    top1_match: bool
    source_latency_ms: float
    target_latency_ms: float


@dataclass(frozen=True)
class LatencySummary:
    p50_ms: float
    p95_ms: float
    p99_ms: float
    average_ms: float


@dataclass(frozen=True)
class SearchComparisonReport:
    """Aggregate source-versus-target search comparison."""

    source_driver: str
    target_driver: str
    top_k: int
    queries_compared: int
    recall_at_k: float
    top1_match_rate: float
    average_overlap: float
    source_latency: LatencySummary
    target_latency: LatencySummary
    query_results: tuple[
        QueryComparisonResult,
        ...,
    ] = field(repr=False)
    minimum_recall_at_k: float
    minimum_top1_match_rate: float

    @property
    def quality_passed(self) -> bool:
        return (
            self.recall_at_k
            >= self.minimum_recall_at_k
            and self.top1_match_rate
            >= self.minimum_top1_match_rate
        )

    @property
    def recommendation(self) -> str:
        if self.quality_passed:
            return "SEARCH_QUALITY_PRESERVED"

        return "MANUAL_REVIEW"


def search_comparison_report_to_dict(
    report: SearchComparisonReport,
) -> dict[str, Any]:
    """Return aggregate metrics without query or document identifiers."""

    return {
        "type": "search_comparison",
        "source_driver": report.source_driver,
        "target_driver": report.target_driver,
        "top_k": report.top_k,
        "queries_compared": report.queries_compared,
        "recall_at_k": report.recall_at_k,
        "top1_match_rate": report.top1_match_rate,
        "average_overlap": report.average_overlap,
        "quality_passed": report.quality_passed,
        "recommendation": report.recommendation,
        "source_latency": {
            "p50_ms": report.source_latency.p50_ms,
            "p95_ms": report.source_latency.p95_ms,
            "p99_ms": report.source_latency.p99_ms,
            "average_ms": (
                report.source_latency.average_ms
            ),
        },
        "target_latency": {
            "p50_ms": report.target_latency.p50_ms,
            "p95_ms": report.target_latency.p95_ms,
            "p99_ms": report.target_latency.p99_ms,
            "average_ms": (
                report.target_latency.average_ms
            ),
        },
    }


def _validate_query(
    *,
    query_id: Any,
    vector: Any,
) -> SearchQuery:
    if (
        not isinstance(query_id, str)
        or not query_id.strip()
    ):
        raise ValueError(
            "Search query ID must be a non-empty string."
        )

    if not isinstance(vector, (list, tuple)):
        raise ValueError(  # noqa: TRY004
            f"Query '{query_id}' vector must be a list."
        )

    if not vector:
        raise ValueError(
            f"Query '{query_id}' vector cannot be empty."
        )

    converted: list[float] = []

    for value in vector:
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
        ):
            raise ValueError(  # noqa: TRY004
                f"Query '{query_id}' contains a "
                "non-numeric vector value."
            )

        number = float(value)

        if not math.isfinite(number):
            raise ValueError(
                f"Query '{query_id}' contains a "
                "non-finite vector value."
            )

        converted.append(number)

    return SearchQuery(
        id=query_id.strip(),
        vector=tuple(converted),
    )


def load_search_queries(
    path: str | Path,
) -> tuple[SearchQuery, ...]:
    """Load a local JSONL dataset without retaining raw rows."""

    file_path = Path(path)
    queries: list[SearchQuery] = []
    seen_ids: set[str] = set()

    try:
        lines = file_path.read_text(
            encoding="utf-8"
        ).splitlines()

    except (OSError, UnicodeError) as error:
        raise ValueError(
            "Failed to read search query dataset: "
            f"{file_path.name}"
        ) from error

    for line_number, raw_line in enumerate(
        lines,
        start=1,
    ):
        if not raw_line.strip():
            continue

        try:
            payload = json.loads(raw_line)

        except json.JSONDecodeError as error:
            raise ValueError(
                "Invalid JSON in search query dataset "
                f"at line {line_number}."
            ) from error

        if not isinstance(payload, dict):
            raise ValueError(  # noqa: TRY004
                "Each search query row must be a JSON object."
            )

        query = _validate_query(
            query_id=payload.get("id"),
            vector=payload.get("vector"),
        )

        if query.id in seen_ids:
            raise ValueError(
                "Duplicate search query ID: "
                f"{query.id}"
            )

        seen_ids.add(query.id)
        queries.append(query)

    if not queries:
        raise ValueError(
            "Search query dataset contains no queries."
        )

    return tuple(queries)


def validate_query_dimensions(
    queries: Sequence[SearchQuery],
    *,
    expected_dimension: int | None = None,
) -> int:
    """Ensure every query uses the same expected dimension."""

    dimensions = {
        len(query.vector)
        for query in queries
    }

    if len(dimensions) != 1:
        raise ValueError(
            "Search query vectors do not all use "
            "the same dimension."
        )

    dimension = next(iter(dimensions))

    if (
        expected_dimension is not None
        and dimension != expected_dimension
    ):
        raise ValueError(
            "Search query dimension "
            f"{dimension} does not match project "
            f"dimension {expected_dimension}."
        )

    return dimension


def _percentile(
    values: Sequence[float],
    percentile: float,
) -> float:
    if not values:
        return 0.0

    ordered = sorted(values)

    if len(ordered) == 1:
        return ordered[0]

    position = (len(ordered) - 1) * percentile
    lower = math.floor(position)
    upper = math.ceil(position)

    if lower == upper:
        return ordered[lower]

    fraction = position - lower

    return (
        ordered[lower]
        + (ordered[upper] - ordered[lower])
        * fraction
    )


def summarize_latency(
    values: Sequence[float],
) -> LatencySummary:
    if not values:
        return LatencySummary(
            p50_ms=0.0,
            p95_ms=0.0,
            p99_ms=0.0,
            average_ms=0.0,
        )

    return LatencySummary(
        p50_ms=_percentile(values, 0.50),
        p95_ms=_percentile(values, 0.95),
        p99_ms=_percentile(values, 0.99),
        average_ms=sum(values) / len(values),
    )


def _timed_search(
    db: Any,
    *,
    collection: str,
    vector: Sequence[float],
    top_k: int,
) -> tuple[tuple[str, ...], float]:
    started = time.perf_counter()
    results = db.search(
        collection=collection,
        vector=list(vector),
        top_k=top_k,
    )
    latency_ms = max(
        (time.perf_counter() - started) * 1000.0,
        0.0,
    )
    ids = tuple(
        str(result.id)
        for result in results
    )
    return ids, latency_ms


def _recall_at_k(
    source_ids: Sequence[str],
    target_ids: Sequence[str],
) -> tuple[int, float]:
    source_set = set(source_ids)
    target_set = set(target_ids)
    overlap = len(source_set & target_set)
    denominator = len(source_set)

    if denominator == 0:
        return (
            overlap,
            1.0 if not target_set else 0.0,
        )

    return overlap, overlap / denominator


def compare_query(
    *,
    source_db: Any,
    target_db: Any,
    source_collection: str,
    target_collection: str,
    query: SearchQuery,
    top_k: int,
) -> QueryComparisonResult:
    source_ids, source_latency = _timed_search(
        source_db,
        collection=source_collection,
        vector=query.vector,
        top_k=top_k,
    )
    target_ids, target_latency = _timed_search(
        target_db,
        collection=target_collection,
        vector=query.vector,
        top_k=top_k,
    )
    overlap_count, recall = _recall_at_k(
        source_ids,
        target_ids,
    )
    top1_match = (
        bool(source_ids)
        and bool(target_ids)
        and source_ids[0] == target_ids[0]
    )

    return QueryComparisonResult(
        query_id=query.id,
        source_ids=source_ids,
        target_ids=target_ids,
        overlap_count=overlap_count,
        recall_at_k=recall,
        top1_match=top1_match,
        source_latency_ms=source_latency,
        target_latency_ms=target_latency,
    )


def _run_warmup(
    *,
    source_db: Any,
    target_db: Any,
    source_collection: str,
    target_collection: str,
    query: SearchQuery,
    top_k: int,
    warmup: int,
) -> None:
    for _ in range(warmup):
        source_db.search(
            collection=source_collection,
            vector=list(query.vector),
            top_k=top_k,
        )
        target_db.search(
            collection=target_collection,
            vector=list(query.vector),
            top_k=top_k,
        )


def compare_search_results(
    *,
    source_db: Any,
    target_db: Any,
    source_driver: str,
    target_driver: str,
    source_collection: str,
    target_collection: str,
    queries: Sequence[SearchQuery],
    config: SearchComparisonConfig,
) -> SearchComparisonReport:
    """Compare ranking overlap and latency for identical vectors."""

    if not queries:
        raise ValueError(
            "At least one search query is required."
        )

    validate_query_dimensions(queries)

    if config.warmup:
        _run_warmup(
            source_db=source_db,
            target_db=target_db,
            source_collection=source_collection,
            target_collection=target_collection,
            query=queries[0],
            top_k=config.top_k,
            warmup=config.warmup,
        )

    comparisons = tuple(
        compare_query(
            source_db=source_db,
            target_db=target_db,
            source_collection=source_collection,
            target_collection=target_collection,
            query=query,
            top_k=config.top_k,
        )
        for query in queries
    )
    average_recall = sum(
        item.recall_at_k
        for item in comparisons
    ) / len(comparisons)
    top1_match_rate = sum(
        item.top1_match
        for item in comparisons
    ) / len(comparisons)
    average_overlap = sum(
        item.overlap_count
        for item in comparisons
    ) / (len(comparisons) * config.top_k)
    source_latencies = [
        item.source_latency_ms
        for item in comparisons
    ]
    target_latencies = [
        item.target_latency_ms
        for item in comparisons
    ]

    return SearchComparisonReport(
        source_driver=source_driver,
        target_driver=target_driver,
        top_k=config.top_k,
        queries_compared=len(comparisons),
        recall_at_k=average_recall,
        top1_match_rate=top1_match_rate,
        average_overlap=average_overlap,
        source_latency=summarize_latency(
            source_latencies
        ),
        target_latency=summarize_latency(
            target_latencies
        ),
        query_results=comparisons,
        minimum_recall_at_k=(
            config.minimum_recall_at_k
        ),
        minimum_top1_match_rate=(
            config.minimum_top1_match_rate
        ),
    )


def _percent(value: float) -> str:
    return f"{value * 100:.1f}%"


def _latency_delta(
    source_ms: float,
    target_ms: float,
) -> str:
    if source_ms == 0:
        return "N/A"

    delta = (
        (target_ms - source_ms)
        / source_ms
    ) * 100.0
    return f"{delta:+.1f}%"


def _markdown_text(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("`", "\\`")
        .replace("\r", " ")
        .replace("\n", " ")
    )


def render_search_comparison_report(
    report: SearchComparisonReport,
) -> str:
    """Render aggregate metrics without exposing query/document IDs."""

    lines = [
        "# Search Quality / Performance Report",
        "",
        (
            "Source DB: "
            f"{_markdown_text(report.source_driver)}"
        ),
        (
            "Target DB: "
            f"{_markdown_text(report.target_driver)}"
        ),
        f"Queries: {report.queries_compared}",
        f"Top K: {report.top_k}",
        "",
        "## Search Quality",
        "",
        (
            f"Recall@{report.top_k} "
            "(source-as-reference): "
            f"{report.recall_at_k:.3f}"
        ),
        (
            "Top-1 Match Rate: "
            f"{_percent(report.top1_match_rate)}"
        ),
        (
            "Average Top-K Overlap: "
            f"{_percent(report.average_overlap)}"
        ),
        "",
        "## Latency",
        "",
        "| Metric | Source | Target | Delta |",
        "| --- | ---: | ---: | ---: |",
    ]

    latency_metrics = (
        ("P50", "p50_ms"),
        ("P95", "p95_ms"),
        ("P99", "p99_ms"),
        ("Average", "average_ms"),
    )

    for display_name, field_name in latency_metrics:
        source_value = getattr(
            report.source_latency,
            field_name,
        )
        target_value = getattr(
            report.target_latency,
            field_name,
        )
        lines.append(
            "| "
            f"{display_name} | "
            f"{source_value:.2f} ms | "
            f"{target_value:.2f} ms | "
            f"{_latency_delta(source_value, target_value)} |"
        )

    lines.extend(
        [
            "",
            "## Recommendation",
            "",
            report.recommendation,
            "",
            "## Interpretation",
            "",
            (
                "Recall@K in this report uses the source "
                "database Top-K results as the reference "
                "set. It is not a relevance-labeled "
                "information-retrieval recall metric."
            ),
            "",
            (
                "Latency values represent this test "
                "environment and query dataset only and "
                "are not universal database performance "
                "guarantees."
            ),
            "",
        ]
    )
    return "\n".join(lines)
