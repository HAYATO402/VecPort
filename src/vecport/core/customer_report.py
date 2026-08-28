"""Consolidated, customer-facing migration PoC reports."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from vecport.core.project import parse_migration_project


@dataclass(frozen=True)
class CustomerReportSummary:
    """The decision-driving fields shown in the executive summary."""

    project_name: str
    source_driver: str
    target_driver: str
    source_collection: str
    target_collection: str
    estimated_records: int | None
    dimension: int | None
    verification_passed: bool
    filter_status: str
    code_status: str
    search_status: str
    recommendation: str


@dataclass(frozen=True)
class CustomerReportArtifacts:
    """Validated structured artifacts used by the final report."""

    verification: dict[str, Any]
    filter_report: dict[str, Any]
    code_report: dict[str, Any]
    search_report: dict[str, Any]


def determine_production_recommendation(
    *,
    verification_passed: bool,
    filter_status: str,
    code_status: str,
    search_status: str,
) -> str:
    """Apply the fixed Small Migration PoC recommendation rules."""

    if not verification_passed:
        return "NOT_READY"

    if search_status != "SEARCH_QUALITY_PRESERVED":
        return "CONDITIONAL"

    if filter_status != "READY":
        return "CONDITIONAL"

    if code_status != "READY_FOR_PATCH":
        return "CONDITIONAL"

    return "READY"


def _load_json_object(
    path: str | Path,
) -> dict[str, Any]:
    file_path = Path(path)

    try:
        payload = json.loads(
            file_path.read_text(
                encoding="utf-8"
            )
        )
    except (
        OSError,
        json.JSONDecodeError,
    ) as error:
        raise ValueError(
            "Failed to load report artifact: "
            f"{file_path.name}"
        ) from error

    if not isinstance(payload, dict):
        raise TypeError(
            "Report artifact must contain a JSON object: "
            f"{file_path.name}"
        )

    return payload


def _require_artifact_type(
    payload: Mapping[str, Any],
    expected: str,
) -> None:
    if payload.get("type") != expected:
        raise ValueError(
            "Unexpected report artifact type; "
            f"expected {expected!r}."
        )


def _verification_details(
    payload: Mapping[str, Any],
) -> Mapping[str, Any]:
    details = payload.get("verification")

    if not isinstance(details, Mapping):
        raise TypeError(
            "Migration artifact does not contain "
            "a verification object."
        )

    return details


def verification_passed(
    payload: Mapping[str, Any],
) -> bool:
    value = payload.get("passed")

    if not isinstance(value, bool):
        raise TypeError(
            "Verification report does not contain "
            "a valid 'passed' field."
        )

    return value


def load_customer_report_artifacts(
    *,
    verification_path: str | Path,
    filter_report_path: str | Path,
    code_report_path: str | Path,
    search_report_path: str | Path,
) -> CustomerReportArtifacts:
    """Load and type-check every local report artifact."""

    verification = _load_json_object(
        verification_path
    )
    filter_report = _load_json_object(
        filter_report_path
    )
    code_report = _load_json_object(
        code_report_path
    )
    search_report = _load_json_object(
        search_report_path
    )

    _require_artifact_type(
        verification,
        "migration",
    )
    _require_artifact_type(
        filter_report,
        "filter_compatibility",
    )
    _require_artifact_type(
        code_report,
        "search_code_migration",
    )
    _require_artifact_type(
        search_report,
        "search_comparison",
    )
    _verification_details(verification)

    return CustomerReportArtifacts(
        verification=verification,
        filter_report=filter_report,
        code_report=code_report,
        search_report=search_report,
    )


def _markdown_text(value: Any) -> str:
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace("`", "\\`")
        .replace("|", "\\|")
        .replace("\r", " ")
        .replace("\n", " ")
    )


def _safe_file_name(value: Any) -> str:
    return _markdown_text(
        str(value).replace("\\", "/").rsplit("/", 1)[-1]
    )


def _mapping(
    payload: Mapping[str, Any],
    key: str,
) -> Mapping[str, Any]:
    value = payload.get(key)

    if not isinstance(value, Mapping):
        raise TypeError(
            f"Report artifact field {key!r} must be an object."
        )

    return value


def _sequence(
    payload: Mapping[str, Any],
    key: str,
) -> Sequence[Any]:
    value = payload.get(key, [])

    if (
        not isinstance(value, Sequence)
        or isinstance(value, (str, bytes))
    ):
        raise TypeError(
            f"Report artifact field {key!r} must be a list."
        )

    return value


def _integer(
    payload: Mapping[str, Any],
    key: str,
) -> int:
    value = payload.get(key)

    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or value < 0
    ):
        raise ValueError(
            f"Report artifact field {key!r} must be "
            "a non-negative integer."
        )

    return value


def _number(
    payload: Mapping[str, Any],
    key: str,
) -> float:
    value = payload.get(key)

    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
    ):
        raise TypeError(
            f"Report artifact field {key!r} must be numeric."
        )

    return float(value)


def _status(
    payload: Mapping[str, Any],
    key: str,
    *,
    allowed: frozenset[str],
    fallback: str,
) -> str:
    value = payload.get(key)

    if isinstance(value, str) and value in allowed:
        return value

    return fallback


def render_metadata_mapping(
    transform_config: Mapping[str, Any] | None,
) -> str:
    """Render only declarative metadata rules from project config."""

    if not transform_config:
        return "No metadata transformations configured."

    lines: list[str] = []
    rename = transform_config.get("rename", {})
    drop = transform_config.get("drop", [])
    defaults = transform_config.get("defaults", {})
    cast = transform_config.get("cast", {})

    if isinstance(rename, Mapping) and rename:
        lines.extend(["### Rename", ""])
        for source, target in rename.items():
            lines.append(
                f"- `{_markdown_text(source)}` → "
                f"`{_markdown_text(target)}`"
            )
        lines.append("")

    if (
        isinstance(drop, Sequence)
        and not isinstance(drop, (str, bytes))
        and drop
    ):
        lines.extend(["### Drop", ""])
        for field_name in drop:
            lines.append(
                f"- `{_markdown_text(field_name)}`"
            )
        lines.append("")

    if isinstance(defaults, Mapping) and defaults:
        lines.extend(["### Defaults", ""])
        for field_name in defaults:
            lines.append(
                f"- `{_markdown_text(field_name)}`: "
                "configured value omitted"
            )
        lines.append("")

    if isinstance(cast, Mapping) and cast:
        lines.extend(["### Cast", ""])
        for field_name, cast_type in cast.items():
            lines.append(
                f"- `{_markdown_text(field_name)}` → "
                f"`{_markdown_text(cast_type)}`"
            )

    return (
        "\n".join(lines).strip()
        or "No metadata transformations configured."
    )


def _percent(value: float) -> str:
    return f"{value * 100.0:.1f}%"


def _pass_fail(value: Any) -> str:
    return "PASS" if value is True else "FAIL"


def _summary(
    *,
    project_config: Mapping[str, Any],
    verification: Mapping[str, Any],
    filter_report: Mapping[str, Any],
    code_report: Mapping[str, Any],
    search_report: Mapping[str, Any],
) -> CustomerReportSummary:
    project = parse_migration_project(
        dict(project_config)
    )
    verification_ok = verification_passed(
        verification
    )
    filter_status = _status(
        filter_report,
        "recommendation",
        allowed=frozenset({"READY", "CONDITIONAL"}),
        fallback="CONDITIONAL",
    )
    code_status = _status(
        code_report,
        "status",
        allowed=frozenset(
            {"READY_FOR_PATCH", "MANUAL_REVIEW"}
        ),
        fallback="MANUAL_REVIEW",
    )
    search_status = _status(
        search_report,
        "recommendation",
        allowed=frozenset(
            {
                "SEARCH_QUALITY_PRESERVED",
                "MANUAL_REVIEW",
            }
        ),
        fallback="MANUAL_REVIEW",
    )
    recommendation = determine_production_recommendation(
        verification_passed=verification_ok,
        filter_status=filter_status,
        code_status=code_status,
        search_status=search_status,
    )

    return CustomerReportSummary(
        project_name=project.project.name,
        source_driver=project.source.driver,
        target_driver=project.target.driver,
        source_collection=project.source.collection,
        target_collection=project.target.collection,
        estimated_records=project.data.estimated_records,
        dimension=project.data.dimension,
        verification_passed=verification_ok,
        filter_status=filter_status,
        code_status=code_status,
        search_status=search_status,
        recommendation=recommendation,
    )


def render_customer_migration_report(
    *,
    project: Mapping[str, Any],
    verification: Mapping[str, Any],
    filter_report: Mapping[str, Any],
    code_report: Mapping[str, Any],
    search_report: Mapping[str, Any],
) -> str:
    """Render one customer artifact without credentials or raw IDs."""

    _require_artifact_type(verification, "migration")
    _require_artifact_type(
        filter_report,
        "filter_compatibility",
    )
    _require_artifact_type(
        code_report,
        "search_code_migration",
    )
    _require_artifact_type(
        search_report,
        "search_comparison",
    )

    verification_data = _verification_details(
        verification
    )
    summary = _summary(
        project_config=project,
        verification=verification_data,
        filter_report=filter_report,
        code_report=code_report,
        search_report=search_report,
    )
    if not summary.verification_passed:
        poc_result = "FAILED"
    elif summary.recommendation == "READY":
        poc_result = "PASSED"
    else:
        poc_result = "REVIEW_REQUIRED"

    lines = [
        "# Vector DB Migration PoC Report",
        "",
        f"Project: {_markdown_text(summary.project_name)}",
        "",
        "## Executive Summary",
        "",
        f"Source DB: {_markdown_text(summary.source_driver)}",
        f"Target DB: {_markdown_text(summary.target_driver)}",
        (
            "Migration verification: "
            + (
                "PASSED"
                if summary.verification_passed
                else "FAILED"
            )
        ),
        f"Filter migration: {summary.filter_status}",
        f"Search code migration: {summary.code_status}",
        f"Search quality: {summary.search_status}",
        f"PoC Results: {poc_result}",
        "",
        "Production Migration Recommendation:",
        summary.recommendation,
        "",
        "## 1. Migration Assessment",
        "",
        "| Item | Value |",
        "| --- | --- |",
        (
            "| Source collection | "
            f"{_markdown_text(summary.source_collection)} |"
        ),
        (
            "| Target collection | "
            f"{_markdown_text(summary.target_collection)} |"
        ),
        (
            "| Estimated records | "
            f"{summary.estimated_records:,} |"
        ),
        f"| Vector dimension | {summary.dimension:,} |",
        "",
        "## 2. Schema / Metadata Mapping",
        "",
        render_metadata_mapping(
            project.get("metadata_transform")
            if isinstance(
                project.get("metadata_transform"),
                Mapping,
            )
            else None
        ),
        "",
        "## 3. Filter Compatibility",
        "",
        f"Status: {summary.filter_status}",
        "",
    ]

    filter_checks = _sequence(
        filter_report,
        "checks",
    )
    if filter_checks:
        lines.extend(
            [
                "| Operator | Source | Target | Result |",
                "| --- | --- | --- | --- |",
            ]
        )
        for raw_check in filter_checks:
            if not isinstance(raw_check, Mapping):
                raise TypeError(
                    "Filter report checks must be objects."
                )
            operator = raw_check.get("operator", "UNKNOWN")
            lines.append(
                "| "
                f"{_markdown_text(operator)} | "
                f"{_pass_fail(raw_check.get('source_supported'))} | "
                f"{_pass_fail(raw_check.get('target_supported'))} | "
                f"{_pass_fail(raw_check.get('passed'))} |"
            )
    else:
        lines.append("No filter operators were declared.")

    unsupported = _sequence(
        filter_report,
        "unsupported_operators",
    )
    if unsupported:
        lines.extend(["", "Required changes:"])
        lines.extend(
            "- Review or rewrite "
            f"`{_markdown_text(operator)}` usage."
            for operator in unsupported
        )

    lines.extend(
        [
            "",
            "## 4. Application Code Migration",
            "",
            (
                "Framework: "
                f"{_markdown_text(code_report.get('target_framework', 'native'))}"
            ),
            f"Status: {summary.code_status}",
            "",
            "Detected files:",
        ]
    )
    findings = _sequence(code_report, "findings")
    if not findings:
        lines.append("- None")
    for raw_finding in findings:
        if not isinstance(raw_finding, Mapping):
            raise TypeError(
                "Code report findings must be objects."
            )
        lines.append(
            f"- {_safe_file_name(raw_finding.get('file_name', 'unknown.py'))}"
        )

    lines.extend(
        [
            "",
            "Recommended changes:",
            "- Replace the native database client with VecPort.",
            (
                "- Translate application filters with the "
                "VecPort Filter DSL."
            ),
            "- Review and test the patch before production use.",
            "",
            "## 5. Data Verification",
            "",
            "| Check | Result |",
            "| --- | ---: |",
            (
                "| Source records | "
                f"{_integer(verification_data, 'source_count'):,} |"
            ),
            (
                "| Target records | "
                f"{_integer(verification_data, 'target_count'):,} |"
            ),
            (
                "| Matched IDs | "
                f"{_integer(verification_data, 'matched_ids'):,} |"
            ),
            (
                "| Missing IDs | "
                f"{_integer(verification_data, 'missing_ids'):,} |"
            ),
            (
                "| Extra records | "
                f"{_integer(verification_data, 'extra_records'):,} |"
            ),
            (
                "| Dimensions | "
                f"{_pass_fail(verification_data.get('dimensions_ok'))} |"
            ),
            (
                "| Vector values | "
                f"{_pass_fail(verification_data.get('vectors_ok'))} |"
            ),
            (
                "| Metadata | "
                f"{_pass_fail(verification_data.get('metadata_ok'))} |"
            ),
            "",
            "## 6. Search Quality",
            "",
        ]
    )

    top_k = _integer(search_report, "top_k")
    recall = _number(search_report, "recall_at_k")
    top1 = _number(search_report, "top1_match_rate")
    overlap = _number(search_report, "average_overlap")
    lines.extend(
        [
            (
                f"Recall@{top_k} (source-as-reference): "
                f"{recall:.3f}"
            ),
            f"Top-1 Match Rate: {_percent(top1)}",
            f"Average Top-K Overlap: {_percent(overlap)}",
            f"Status: {summary.search_status}",
            "",
            "## 7. Latency Comparison",
            "",
            "| Metric | Source | Target |",
            "| --- | ---: | ---: |",
        ]
    )
    source_latency = _mapping(
        search_report,
        "source_latency",
    )
    target_latency = _mapping(
        search_report,
        "target_latency",
    )
    for display_name, field_name in (
        ("P50", "p50_ms"),
        ("P95", "p95_ms"),
        ("P99", "p99_ms"),
        ("Average", "average_ms"),
    ):
        lines.append(
            "| "
            f"{display_name} | "
            f"{_number(source_latency, field_name):.2f} ms | "
            f"{_number(target_latency, field_name):.2f} ms |"
        )
    lines.extend(
        [
            "",
            (
                "Latency values represent this test environment "
                "and query dataset only."
            ),
            "",
            "## 8. Risks",
            "",
        ]
    )

    risks: list[str] = []
    if not summary.verification_passed:
        risks.append(
            "Migration verification failed and blocks production planning."
        )
    if summary.filter_status != "READY":
        risks.append(
            "Unsupported filter operators require application changes."
        )
    if summary.code_status != "READY_FOR_PATCH":
        risks.append(
            "Application search code requires manual analysis."
        )
    if summary.search_status != "SEARCH_QUALITY_PRESERVED":
        risks.append(
            "Search ranking differences require investigation."
        )
    if not risks:
        risks.append(
            "No blocking migration compatibility issue was detected."
        )
    lines.extend(f"- {risk}" for risk in risks)

    lines.extend(
        [
            "",
            "## 9. Remaining Manual Work",
            "",
            (
                "- Review the application code patch and regression "
                "tests before deployment."
            ),
            (
                "- Define production cutover, rollback, monitoring, "
                "and operational ownership."
            ),
            (
                "- Repeat performance testing with production-like "
                "data and load."
            ),
            "",
            "## 10. Production Migration Recommendation",
            "",
            summary.recommendation,
            "",
            (
                "This recommendation summarizes the tested PoC; "
                "it is not a production-readiness certification."
            ),
            "",
            "## Scope Note",
            "",
            "This report validates the tested migration PoC.",
            "",
            "It does not by itself certify:",
            "- zero-downtime production cutover",
            "- production-scale load capacity",
            "- rollback procedures",
            "- high availability",
            "- disaster recovery",
            "",
        ]
    )

    return "\n".join(lines)
