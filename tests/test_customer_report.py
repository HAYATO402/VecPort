import json
import sys

import pytest

from vecport.cli import main
from vecport.core.code_migration import (
    SearchCodeFinding,
    SearchCodeMigrationReport,
    code_migration_report_to_dict,
)
from vecport.core.customer_report import (
    determine_production_recommendation,
    load_customer_report_artifacts,
    render_customer_migration_report,
    render_metadata_mapping,
)
from vecport.core.filter_compatibility import (
    FilterRequirements,
    assess_filter_compatibility,
    filter_report_to_dict,
)
from vecport.core.models import Capabilities
from vecport.core.search_comparison import (
    LatencySummary,
    QueryComparisonResult,
    SearchComparisonReport,
    search_comparison_report_to_dict,
)


def _project_config(
    *,
    secret: str = "local-credential-value",
):
    return {
        "project": {
            "name": "customer-demo",
        },
        "source": {
            "driver": "qdrant",
            "connection": (
                "vecport://qdrant?url="
                "http://localhost:6333"
            ),
            "collection": "documents",
            "private_note": secret,
        },
        "target": {
            "driver": "milvus",
            "connection": (
                "vecport://milvus?uri="
                "http://localhost:19530"
            ),
            "collection": "documents_migrated",
        },
        "data": {
            "estimated_records": 100,
            "dimension": 3,
        },
        "metadata_transform": {
            "rename": {
                "old_category": "category",
            },
            "drop": ["debug"],
            "defaults": {
                "source": "legacy",
            },
            "cast": {
                "price": "int",
            },
        },
        "application": {
            "language": "python",
            "framework": "native",
        },
    }


def _verification(
    *,
    passed: bool = True,
):
    return {
        "type": "migration",
        "migration": {
            "source_collection": "documents",
            "target_collection": "documents_migrated",
            "scanned": 100,
            "migrated": 100,
        },
        "verification": {
            "source_count": 100,
            "target_count": 100,
            "matched_ids": 100,
            "missing_ids": 0,
            "extra_records": 0,
            "dimensions_ok": passed,
            "vectors_ok": passed,
            "metadata_ok": passed,
            "passed": passed,
        },
    }


def _filter_report(
    *,
    recommendation: str = "READY",
):
    passed = recommendation == "READY"
    return {
        "type": "filter_compatibility",
        "source_driver": "qdrant",
        "target_driver": "milvus",
        "passed": passed,
        "recommendation": recommendation,
        "unsupported_operators": (
            [] if passed else ["$text"]
        ),
        "checks": [
            {
                "operator": "$eq" if passed else "$text",
                "description": "equals",
                "source_supported": True,
                "target_supported": passed,
                "in_vecport_dsl": passed,
                "passed": passed,
            }
        ],
    }


def _code_report(
    *,
    status: str = "READY_FOR_PATCH",
):
    return {
        "type": "search_code_migration",
        "source_driver": "qdrant",
        "target_driver": "milvus",
        "target_framework": "native",
        "status": status,
        "requires_manual_review": (
            status != "READY_FOR_PATCH"
        ),
        "findings": [
            {
                "file_name": (
                    "C:\\Users\\customer\\private\\search.py"
                ),
                "framework": "native",
                "detected_driver": "qdrant",
                "operations": ["search"],
                "filter_keywords": ["query_filter"],
            }
        ],
        "notes": [],
    }


def _search_report(
    *,
    recommendation: str = "SEARCH_QUALITY_PRESERVED",
):
    passed = recommendation == "SEARCH_QUALITY_PRESERVED"
    return {
        "type": "search_comparison",
        "source_driver": "qdrant",
        "target_driver": "milvus",
        "top_k": 10,
        "queries_compared": 5,
        "recall_at_k": 1.0 if passed else 0.5,
        "top1_match_rate": 1.0 if passed else 0.4,
        "average_overlap": 1.0 if passed else 0.5,
        "quality_passed": passed,
        "recommendation": recommendation,
        "source_latency": {
            "p50_ms": 10.0,
            "p95_ms": 12.0,
            "p99_ms": 13.0,
            "average_ms": 10.5,
        },
        "target_latency": {
            "p50_ms": 5.0,
            "p95_ms": 6.0,
            "p99_ms": 7.0,
            "average_ms": 5.5,
        },
    }


@pytest.mark.parametrize(
    (
        "verification_ok",
        "filter_status",
        "code_status",
        "search_status",
        "expected",
    ),
    [
        (
            False,
            "READY",
            "READY_FOR_PATCH",
            "SEARCH_QUALITY_PRESERVED",
            "NOT_READY",
        ),
        (
            True,
            "READY",
            "READY_FOR_PATCH",
            "MANUAL_REVIEW",
            "CONDITIONAL",
        ),
        (
            True,
            "CONDITIONAL",
            "READY_FOR_PATCH",
            "SEARCH_QUALITY_PRESERVED",
            "CONDITIONAL",
        ),
        (
            True,
            "READY",
            "MANUAL_REVIEW",
            "SEARCH_QUALITY_PRESERVED",
            "CONDITIONAL",
        ),
        (
            True,
            "READY",
            "READY_FOR_PATCH",
            "SEARCH_QUALITY_PRESERVED",
            "READY",
        ),
    ],
)
def test_production_recommendation(
    verification_ok,
    filter_status,
    code_status,
    search_status,
    expected,
):
    assert determine_production_recommendation(
        verification_passed=verification_ok,
        filter_status=filter_status,
        code_status=code_status,
        search_status=search_status,
    ) == expected


def test_report_contains_customer_sections():
    markdown = render_customer_migration_report(
        project=_project_config(),
        verification=_verification(),
        filter_report=_filter_report(),
        code_report=_code_report(),
        search_report=_search_report(),
    )

    for heading in (
        "Executive Summary",
        "Migration Assessment",
        "Schema / Metadata Mapping",
        "Filter Compatibility",
        "Application Code Migration",
        "Data Verification",
        "Search Quality",
        "Latency Comparison",
        "Risks",
        "Remaining Manual Work",
        "Production Migration Recommendation",
        "Scope Note",
    ):
        assert heading in markdown

    assert "PoC Results: PASSED" in markdown
    assert "Recall@10 (source-as-reference): 1.000" in markdown
    assert "Top-1 Match Rate: 100.0%" in markdown
    assert "\nREADY\n" in markdown


def test_customer_report_does_not_leak_private_inputs():
    secret = "super-secret-password-value"
    verification = _verification()
    verification["connection"] = secret
    filter_report = _filter_report()
    filter_report["api_key"] = secret
    code_report = _code_report()
    code_report["source_code"] = secret
    search_report = _search_report()
    search_report["query_results"] = [
        {
            "query_id": secret,
            "source_ids": [secret],
            "target_ids": [secret],
        }
    ]

    markdown = render_customer_migration_report(
        project=_project_config(secret=secret),
        verification=verification,
        filter_report=filter_report,
        code_report=code_report,
        search_report=search_report,
    )

    assert secret not in markdown
    assert "localhost" not in markdown
    assert "C:\\Users\\" not in markdown
    assert "query_id" not in markdown
    assert "source_ids" not in markdown
    assert "target_ids" not in markdown
    assert "search.py" in markdown


def test_metadata_mapping_renderer():
    markdown = render_metadata_mapping(
        _project_config()["metadata_transform"]
    )

    assert "`old_category` → `category`" in markdown
    assert "`debug`" in markdown
    assert "`source`: configured value omitted" in markdown
    assert "legacy" not in markdown
    assert "`price` → `int`" in markdown


def test_filter_payload_contains_only_report_fields():
    capabilities = Capabilities(
        metadata_filter=True,
        filter_operators=("$eq",),
    )
    report = assess_filter_compatibility(
        source_driver="qdrant",
        target_driver="milvus",
        requirements=FilterRequirements(
            required_operators=("$eq",)
        ),
        source_capabilities=capabilities,
        target_capabilities=capabilities,
    )

    payload = filter_report_to_dict(report)

    assert payload["type"] == "filter_compatibility"
    assert "connection" not in payload
    assert "api_key" not in payload


def test_code_payload_excludes_code_and_paths():
    secret = "super-secret-api-key-value"
    report = SearchCodeMigrationReport(
        source_driver="qdrant",
        target_driver="milvus",
        findings=(
            SearchCodeFinding(
                file_name="search.py",
                framework="native",
                detected_driver="qdrant",
                imports=(secret,),
                operations=("search",),
                filter_keywords=("query_filter",),
            ),
        ),
        target_framework="native",
        target_example=secret,
        notes=(),
    )

    payload = code_migration_report_to_dict(report)
    serialized = json.dumps(payload)

    assert payload["type"] == "search_code_migration"
    assert "target_example" not in payload
    assert "imports" not in serialized
    assert secret not in serialized


def test_search_payload_excludes_query_and_record_ids():
    secret = "private-record-id"
    report = SearchComparisonReport(
        source_driver="qdrant",
        target_driver="milvus",
        top_k=1,
        queries_compared=1,
        recall_at_k=1.0,
        top1_match_rate=1.0,
        average_overlap=1.0,
        source_latency=LatencySummary(1.0, 1.0, 1.0, 1.0),
        target_latency=LatencySummary(1.0, 1.0, 1.0, 1.0),
        query_results=(
            QueryComparisonResult(
                query_id=secret,
                source_ids=(secret,),
                target_ids=(secret,),
                overlap_count=1,
                recall_at_k=1.0,
                top1_match=True,
                source_latency_ms=1.0,
                target_latency_ms=1.0,
            ),
        ),
        minimum_recall_at_k=0.9,
        minimum_top1_match_rate=0.8,
    )

    payload = search_comparison_report_to_dict(report)
    serialized = json.dumps(payload)

    assert "query_results" not in payload
    assert "source_ids" not in serialized
    assert "target_ids" not in serialized
    assert secret not in serialized


def _write_artifacts(tmp_path):
    payloads = {
        "verification": _verification(),
        "filter": _filter_report(),
        "code": _code_report(),
        "search": _search_report(),
    }
    paths = {}
    for name, payload in payloads.items():
        path = tmp_path / f"{name}.json"
        path.write_text(
            json.dumps(payload),
            encoding="utf-8",
        )
        paths[name] = path
    return paths


def test_load_customer_report_artifacts(tmp_path):
    paths = _write_artifacts(tmp_path)

    artifacts = load_customer_report_artifacts(
        verification_path=paths["verification"],
        filter_report_path=paths["filter"],
        code_report_path=paths["code"],
        search_report_path=paths["search"],
    )

    assert artifacts.verification["type"] == "migration"
    assert artifacts.filter_report["type"] == "filter_compatibility"


def test_loader_rejects_wrong_type_without_echoing_value(
    tmp_path,
):
    secret = "password=private-value"
    paths = _write_artifacts(tmp_path)
    paths["search"].write_text(
        json.dumps({"type": secret}),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="expected 'search_comparison'",
    ) as captured:
        load_customer_report_artifacts(
            verification_path=paths["verification"],
            filter_report_path=paths["filter"],
            code_report_path=paths["code"],
            search_report_path=paths["search"],
        )

    assert secret not in str(captured.value)


def test_loader_error_hides_parent_path(tmp_path):
    private = tmp_path / "customer-private"
    private.mkdir()
    paths = _write_artifacts(tmp_path)
    missing = private / "verification.json"

    with pytest.raises(
        ValueError,
        match="verification.json",
    ) as captured:
        load_customer_report_artifacts(
            verification_path=missing,
            filter_report_path=paths["filter"],
            code_report_path=paths["code"],
            search_report_path=paths["search"],
        )

    assert str(private) not in str(captured.value)


def _write_project_yaml(path):
    path.write_text(
        """
project:
  name: customer-demo
source:
  driver: qdrant
  connection: "vecport://qdrant?url=http://localhost:6333"
  collection: documents
target:
  driver: milvus
  connection: "vecport://milvus?uri=http://localhost:19530"
  collection: documents_migrated
data:
  estimated_records: 100
  dimension: 3
metadata_transform:
  rename:
    old_category: category
application:
  language: python
  framework: native
""",
        encoding="utf-8",
    )


def test_customer_report_cli_is_read_only(
    tmp_path,
    monkeypatch,
    capsys,
):
    config_path = tmp_path / "migration-intake.yml"
    output_path = tmp_path / "reports" / "migration-report.md"
    _write_project_yaml(config_path)
    paths = _write_artifacts(tmp_path)

    def unexpected_connection(*args, **kwargs):
        raise AssertionError(
            "customer-report must not connect to databases"
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
            "customer-report",
            "--config",
            str(config_path),
            "--verification",
            str(paths["verification"]),
            "--filter-report",
            str(paths["filter"]),
            "--code-report",
            str(paths["code"]),
            "--search-report",
            str(paths["search"]),
            "--output",
            str(output_path),
        ],
    )

    result = main()
    captured = capsys.readouterr()
    markdown = output_path.read_text(
        encoding="utf-8"
    )

    assert result == 0
    assert "Customer migration PoC report generated" in captured.out
    assert "Production Migration Recommendation" in markdown
    assert "localhost" not in markdown


def test_customer_report_cli_rejects_wrong_artifact(
    tmp_path,
    monkeypatch,
    capsys,
):
    config_path = tmp_path / "migration-intake.yml"
    output_path = tmp_path / "migration-report.md"
    _write_project_yaml(config_path)
    paths = _write_artifacts(tmp_path)

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "vecport",
            "project",
            "customer-report",
            "--config",
            str(config_path),
            "--verification",
            str(paths["verification"]),
            "--filter-report",
            str(paths["search"]),
            "--code-report",
            str(paths["code"]),
            "--search-report",
            str(paths["search"]),
            "--output",
            str(output_path),
        ],
    )

    result = main()
    captured = capsys.readouterr()

    assert result == 1
    assert "expected 'filter_compatibility'" in captured.out
    assert not output_path.exists()
