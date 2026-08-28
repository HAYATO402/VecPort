import json
import sys

import pytest

from vecport.cli import main
from vecport.core.models import SearchResult
from vecport.core.search_comparison import (
    SearchComparisonConfig,
    SearchQuery,
    compare_search_results,
    load_search_queries,
    render_search_comparison_report,
    summarize_latency,
    validate_query_dimensions,
)


class FakeSearchDB:
    def __init__(
        self,
        result_ids,
    ):
        self.result_ids = result_ids
        self.calls = []
        self.closed = False

    def search(
        self,
        collection,
        vector,
        top_k=10,
        filters=None,
    ):
        self.calls.append(
            (
                collection,
                list(vector),
                top_k,
                filters,
            )
        )
        return [
            SearchResult(
                id=record_id,
                score=1.0,
                metadata={},
            )
            for record_id in self.result_ids[:top_k]
        ]

    def close(self):
        self.closed = True


def _query():
    return SearchQuery(
        id="q1",
        vector=(1.0, 0.0),
    )


def _compare(
    source_ids,
    target_ids,
    *,
    config=None,
):
    return compare_search_results(
        source_db=FakeSearchDB(source_ids),
        target_db=FakeSearchDB(target_ids),
        source_driver="qdrant",
        target_driver="milvus",
        source_collection="source_docs",
        target_collection="target_docs",
        queries=(_query(),),
        config=(
            config
            or SearchComparisonConfig(
                top_k=3,
                warmup=0,
            )
        ),
    )


def test_identical_rankings_pass():
    report = _compare(
        ["a", "b", "c"],
        ["a", "b", "c"],
    )

    assert report.recall_at_k == 1.0
    assert report.top1_match_rate == 1.0
    assert report.average_overlap == 1.0
    assert report.quality_passed
    assert (
        report.recommendation
        == "SEARCH_QUALITY_PRESERVED"
    )


def test_partial_overlap():
    report = _compare(
        ["a", "b", "c"],
        ["a", "x", "c"],
        config=SearchComparisonConfig(
            top_k=3,
            warmup=0,
            minimum_recall_at_k=0.5,
        ),
    )
    result = report.query_results[0]

    assert result.overlap_count == 2
    assert result.recall_at_k == 2 / 3
    assert report.average_overlap == 2 / 3


def test_top1_mismatch_requires_review():
    report = _compare(
        ["a", "b"],
        ["b", "a"],
        config=SearchComparisonConfig(
            top_k=2,
            warmup=0,
        ),
    )

    assert report.recall_at_k == 1.0
    assert report.top1_match_rate == 0.0
    assert not report.quality_passed
    assert report.recommendation == "MANUAL_REVIEW"


def test_warmup_is_not_counted_as_query_result():
    source = FakeSearchDB(["a"])
    target = FakeSearchDB(["a"])
    report = compare_search_results(
        source_db=source,
        target_db=target,
        source_driver="qdrant",
        target_driver="milvus",
        source_collection="source_docs",
        target_collection="target_docs",
        queries=(_query(),),
        config=SearchComparisonConfig(
            top_k=1,
            warmup=2,
        ),
    )

    assert report.queries_compared == 1
    assert len(source.calls) == 3
    assert len(target.calls) == 3


def test_latency_summary_uses_interpolation():
    summary = summarize_latency(
        [1.0, 2.0, 3.0, 4.0]
    )

    assert summary.p50_ms == 2.5
    assert summary.p95_ms == pytest.approx(3.85)
    assert summary.p99_ms == pytest.approx(3.97)
    assert summary.average_ms == 2.5


def test_load_search_queries(
    tmp_path,
):
    path = tmp_path / "queries.jsonl"
    path.write_text(
        (
            '{"id":"q1","vector":[1,0]}\n'
            '\n'
            '{"id":"q2","vector":[0,1]}\n'
        ),
        encoding="utf-8",
    )

    queries = load_search_queries(path)

    assert len(queries) == 2
    assert queries[0].id == "q1"
    assert queries[0].vector == (1.0, 0.0)


@pytest.mark.parametrize(
    "row",
    [
        {"id": "", "vector": [1, 0]},
        {"id": None, "vector": [1, 0]},
        {"id": 1, "vector": [1, 0]},
        {"id": "q1", "vector": []},
        {"id": "q1", "vector": "1,0"},
        {"id": "q1", "vector": [True, 0]},
        {"id": "q1", "vector": ["1", 0]},
        {"id": "q1", "vector": [float("nan"), 0]},
        {"id": "q1", "vector": [float("inf"), 0]},
    ],
)
def test_invalid_query_rows_fail(
    tmp_path,
    row,
):
    path = tmp_path / "queries.jsonl"
    path.write_text(
        json.dumps(row),
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        load_search_queries(path)


def test_invalid_json_reports_line_only(
    tmp_path,
):
    private_dir = tmp_path / "private-customer"
    private_dir.mkdir()
    path = private_dir / "queries.jsonl"
    path.write_text(
        '{"id":',
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="line 1",
    ) as captured:
        load_search_queries(path)

    assert str(private_dir) not in str(
        captured.value
    )


def test_duplicate_query_ids_fail(
    tmp_path,
):
    path = tmp_path / "queries.jsonl"
    path.write_text(
        (
            '{"id":"q1","vector":[1,0]}\n'
            '{"id":"q1","vector":[0,1]}\n'
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="Duplicate search query ID",
    ):
        load_search_queries(path)


def test_empty_query_dataset_fails(
    tmp_path,
):
    path = tmp_path / "queries.jsonl"
    path.write_text("\n", encoding="utf-8")

    with pytest.raises(
        ValueError,
        match="contains no queries",
    ):
        load_search_queries(path)


def test_query_dimension_mismatch():
    queries = (
        SearchQuery(
            id="q1",
            vector=(1.0, 0.0),
        ),
        SearchQuery(
            id="q2",
            vector=(1.0, 0.0, 0.0),
        ),
    )

    with pytest.raises(ValueError):
        validate_query_dimensions(queries)


def test_query_dimension_must_match_project():
    with pytest.raises(
        ValueError,
        match="project dimension 3",
    ):
        validate_query_dimensions(
            (_query(),),
            expected_dimension=3,
        )


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"top_k": 0}, "top_k"),
        ({"top_k": True}, "top_k"),
        ({"warmup": -1}, "warmup"),
        ({"warmup": False}, "warmup"),
        (
            {"minimum_recall_at_k": 1.1},
            "minimum_recall_at_k",
        ),
        (
            {"minimum_top1_match_rate": -0.1},
            "minimum_top1_match_rate",
        ),
    ],
)
def test_invalid_comparison_config_fails(
    kwargs,
    message,
):
    with pytest.raises(
        ValueError,
        match=message,
    ):
        SearchComparisonConfig(**kwargs)


def test_empty_comparison_fails():
    with pytest.raises(
        ValueError,
        match="At least one",
    ):
        compare_search_results(
            source_db=FakeSearchDB([]),
            target_db=FakeSearchDB([]),
            source_driver="qdrant",
            target_driver="milvus",
            source_collection="source_docs",
            target_collection="target_docs",
            queries=(),
            config=SearchComparisonConfig(
                warmup=0
            ),
        )


def test_render_report_omits_customer_ids():
    report = _compare(
        ["private-source-a", "private-source-b"],
        ["private-source-a", "private-target-c"],
        config=SearchComparisonConfig(
            top_k=2,
            warmup=0,
            minimum_recall_at_k=0.5,
            minimum_top1_match_rate=0.5,
        ),
    )

    markdown = render_search_comparison_report(
        report
    )

    assert (
        "# Search Quality / Performance Report"
        in markdown
    )
    assert "source-as-reference" in markdown
    assert "SEARCH_QUALITY_PRESERVED" in markdown
    assert "private-source-a" not in markdown
    assert "private-source-b" not in markdown
    assert "private-target-c" not in markdown
    assert "P50" in markdown
    assert "P95" in markdown
    assert "P99" in markdown


def _write_cli_project(
    path,
    *,
    dimension=2,
    enabled=True,
):
    path.write_text(
        f'''
project:
  name: customer-demo
source:
  driver: qdrant
  connection: "vecport://qdrant?url=http://localhost:6333"
  collection: source_docs
target:
  driver: milvus
  connection: "vecport://milvus?uri=http://localhost:19530"
  collection: target_docs
data:
  estimated_records: 10
  dimension: {dimension}
search_comparison:
  enabled: {str(enabled).lower()}
  top_k: 2
  warmup: 0
  minimum_recall_at_k: 0.5
  minimum_top1_match_rate: 0.5
''',
        encoding="utf-8",
    )


def _write_cli_queries(
    path,
    *,
    vector=(1, 0),
):
    path.write_text(
        json.dumps(
            {
                "id": "private-query-id",
                "vector": list(vector),
            }
        ),
        encoding="utf-8",
    )


def test_search_report_cli_writes_aggregate_report(
    tmp_path,
    monkeypatch,
    capsys,
):
    config_path = tmp_path / "migration-intake.yml"
    query_path = tmp_path / "customer-data" / "queries.jsonl"
    output_path = tmp_path / "reports" / "search.md"
    json_path = tmp_path / "reports" / "search.json"
    query_path.parent.mkdir()
    _write_cli_project(config_path)
    _write_cli_queries(query_path)
    source = FakeSearchDB(
        ["private-doc-a", "private-doc-b"]
    )
    target = FakeSearchDB(
        ["private-doc-a", "private-doc-b"]
    )

    def connect(url, **overrides):
        assert overrides == {}
        if "qdrant" in url:
            return source
        return target

    monkeypatch.setattr(
        "vecport.cli.connect_url",
        connect,
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "vecport",
            "project",
            "search-report",
            "--config",
            str(config_path),
            "--queries",
            str(query_path),
            "--output",
            str(output_path),
            "--json-output",
            str(json_path),
        ],
    )

    result = main()
    captured = capsys.readouterr()
    markdown = output_path.read_text(
        encoding="utf-8"
    )
    payload = json.loads(
        json_path.read_text(encoding="utf-8")
    )

    assert result == 0
    assert source.closed
    assert target.closed
    assert "SEARCH_QUALITY_PRESERVED" in captured.out
    assert "source-as-reference" in markdown
    assert "private-query-id" not in markdown
    assert "private-doc-a" not in markdown
    assert "localhost" not in markdown
    assert "localhost" not in captured.out
    assert payload["type"] == "search_comparison"
    assert "query_results" not in payload
    assert "private-query-id" not in json.dumps(payload)
    assert "private-doc-a" not in json.dumps(payload)


def test_search_report_cli_missing_queries_fails_before_connect(
    tmp_path,
    monkeypatch,
    capsys,
):
    config_path = tmp_path / "migration-intake.yml"
    missing_path = tmp_path / "private" / "missing.jsonl"
    output_path = tmp_path / "report.md"
    _write_cli_project(config_path)

    def unexpected_connection(*args, **kwargs):
        raise AssertionError(
            "invalid query input must not connect"
        )

    monkeypatch.setattr(
        "vecport.cli.connect_url",
        unexpected_connection,
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "vecport",
            "project",
            "search-report",
            "--config",
            str(config_path),
            "--queries",
            str(missing_path),
            "--output",
            str(output_path),
        ],
    )

    result = main()
    captured = capsys.readouterr()

    assert result == 1
    assert "missing.jsonl" in captured.out
    assert str(missing_path.parent) not in captured.out
    assert not output_path.exists()


def test_search_report_cli_dimension_fails_before_connect(
    tmp_path,
    monkeypatch,
    capsys,
):
    config_path = tmp_path / "migration-intake.yml"
    query_path = tmp_path / "queries.jsonl"
    output_path = tmp_path / "report.md"
    _write_cli_project(
        config_path,
        dimension=3,
    )
    _write_cli_queries(query_path)

    def unexpected_connection(*args, **kwargs):
        raise AssertionError(
            "dimension mismatch must not connect"
        )

    monkeypatch.setattr(
        "vecport.cli.connect_url",
        unexpected_connection,
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "vecport",
            "project",
            "search-report",
            "--config",
            str(config_path),
            "--queries",
            str(query_path),
            "--output",
            str(output_path),
        ],
    )

    result = main()
    captured = capsys.readouterr()

    assert result == 1
    assert "project dimension 3" in captured.out
    assert not output_path.exists()


def test_search_report_cli_manual_review_is_success(
    tmp_path,
    monkeypatch,
    capsys,
):
    config_path = tmp_path / "migration-intake.yml"
    query_path = tmp_path / "queries.jsonl"
    output_path = tmp_path / "report.md"
    _write_cli_project(config_path)
    _write_cli_queries(query_path)
    source = FakeSearchDB(["a", "b"])
    target = FakeSearchDB(["x", "y"])
    connections = iter((source, target))
    monkeypatch.setattr(
        "vecport.cli.connect_url",
        lambda *args, **kwargs: next(connections),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "vecport",
            "project",
            "search-report",
            "--config",
            str(config_path),
            "--queries",
            str(query_path),
            "--output",
            str(output_path),
        ],
    )

    result = main()
    captured = capsys.readouterr()

    assert result == 0
    assert "Recommendation: MANUAL_REVIEW" in captured.out
    assert "MANUAL_REVIEW" in output_path.read_text(
        encoding="utf-8"
    )


def test_search_report_cli_hides_backend_error(
    tmp_path,
    monkeypatch,
    capsys,
):
    class FailingSearchDB(FakeSearchDB):
        def search(self, *args, **kwargs):
            raise RuntimeError(
                "password=customer-private-value"
            )

    config_path = tmp_path / "migration-intake.yml"
    query_path = tmp_path / "queries.jsonl"
    output_path = tmp_path / "report.md"
    _write_cli_project(config_path)
    _write_cli_queries(query_path)
    source = FailingSearchDB([])
    target = FakeSearchDB([])
    connections = iter((source, target))
    monkeypatch.setattr(
        "vecport.cli.connect_url",
        lambda *args, **kwargs: next(connections),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "vecport",
            "project",
            "search-report",
            "--config",
            str(config_path),
            "--queries",
            str(query_path),
            "--output",
            str(output_path),
        ],
    )

    result = main()
    captured = capsys.readouterr()

    assert result == 1
    assert source.closed
    assert target.closed
    assert "source or target search failed" in captured.out
    assert "customer-private-value" not in captured.out
    assert not output_path.exists()
