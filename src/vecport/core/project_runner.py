"""One-command orchestration for Small Migration PoC projects."""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from vecport import connect_url
from vecport.core.code_migration import (
    SearchCodeMigrationReport,
    build_search_code_migration_report,
    code_migration_report_to_dict,
    render_search_code_report,
)
from vecport.core.customer_report import (
    determine_production_recommendation,
    render_customer_migration_report,
)
from vecport.core.errors import ProjectRunError
from vecport.core.filter_compatibility import (
    FilterCompatibilityReport,
    filter_report_to_dict,
    render_filter_report,
)
from vecport.core.migration import (
    MigrationPlan,
    MigrationReport,
    VerificationReport,
    migrate_collection,
    verify_migration,
)
from vecport.core.project import (
    MigrationAssessment,
    MigrationProject,
    assess_migration_project,
    parse_migration_project,
)
from vecport.core.search_comparison import (
    SearchComparisonReport,
    compare_search_results,
    load_search_queries,
    render_search_comparison_report,
    search_comparison_report_to_dict,
    validate_query_dimensions,
)
from vecport.core.transforms import MetadataTransformer

_RUN_ID_PATTERN = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$"
)


@dataclass(frozen=True)
class ProjectRunPaths:
    root: Path
    manifest: Path
    assessment: Path
    migration_plan: Path
    migration: Path
    verification: Path
    filter_json: Path
    filter_markdown: Path
    code_json: Path
    code_markdown: Path
    search_json: Path
    search_markdown: Path
    customer_report: Path


@dataclass(frozen=True)
class ProjectRunStage:
    name: str
    status: str
    detail: str = ""


@dataclass(frozen=True)
class ProjectRunResult:
    run_id: str
    root: Path
    executed: bool
    verification_passed: bool | None
    recommendation: str | None
    status: str
    paths: ProjectRunPaths
    stages: tuple[ProjectRunStage, ...]


def _safe_slug(value: str) -> str:
    normalized = value.strip().lower()
    normalized = re.sub(
        r"[^a-z0-9_-]+",
        "-",
        normalized,
    )
    normalized = normalized.strip("-_")

    if not normalized:
        return "migration-project"

    return normalized[:80]


def _default_run_id() -> str:
    now = datetime.now(timezone.utc)
    return now.strftime("%Y%m%dT%H%M%SZ")


def _validate_run_id(run_id: str) -> None:
    if (
        not _RUN_ID_PATTERN.fullmatch(run_id)
        or run_id in {".", ".."}
    ):
        raise ProjectRunError(
            "Run ID must contain only letters, digits, dots, "
            "underscores, or hyphens."
        )


def create_project_run_paths(
    *,
    output_dir: str | Path,
    project_name: str,
    run_id: str | None = None,
) -> ProjectRunPaths:
    resolved_run_id = run_id or _default_run_id()
    _validate_run_id(resolved_run_id)
    root = (
        Path(output_dir)
        / _safe_slug(project_name)
        / resolved_run_id
    )

    if root.exists():
        raise ProjectRunError(
            "Project run directory already exists."
        )

    root.mkdir(parents=True, exist_ok=False)

    return ProjectRunPaths(
        root=root,
        manifest=root / "00_run_manifest.json",
        assessment=root / "01_assessment.json",
        migration_plan=root / "02_migration_plan.json",
        migration=root / "03_migration.json",
        verification=root / "04_verification.json",
        filter_json=root / "05_filter_mapping.json",
        filter_markdown=root / "05_filter_mapping.md",
        code_json=root / "06_search_code_migration.json",
        code_markdown=root / "06_search_code_migration.md",
        search_json=root / "07_search_comparison.json",
        search_markdown=root / "07_search_comparison.md",
        customer_report=root / "08_migration_report.md",
    )


def build_safe_run_manifest(
    *,
    project_name: str,
    source_driver: str,
    target_driver: str,
    run_id: str,
    status: str,
    executed: bool,
    recommendation: str | None,
    stages: Sequence[ProjectRunStage] = (),
) -> dict[str, Any]:
    """Build a manifest without connection data or customer inputs."""

    return {
        "type": "vecport_project_run",
        "project": project_name,
        "source_driver": source_driver,
        "target_driver": target_driver,
        "run_id": run_id,
        "status": status,
        "executed": executed,
        "recommendation": recommendation,
        "stages": [
            {
                "name": stage.name,
                "status": stage.status,
                "detail": stage.detail,
            }
            for stage in stages
        ],
    }


def _write_json(
    path: Path,
    payload: Mapping[str, Any],
) -> None:
    path.write_text(
        json.dumps(
            dict(payload),
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )


def _write_manifest(
    *,
    paths: ProjectRunPaths,
    project: MigrationProject,
    run_id: str,
    status: str,
    executed: bool,
    recommendation: str | None,
    stages: Sequence[ProjectRunStage],
) -> None:
    _write_json(
        paths.manifest,
        build_safe_run_manifest(
            project_name=project.project.name,
            source_driver=project.source.driver,
            target_driver=project.target.driver,
            run_id=run_id,
            status=status,
            executed=executed,
            recommendation=recommendation,
            stages=stages,
        ),
    )


def _assessment_to_dict(
    assessment: MigrationAssessment,
) -> dict[str, Any]:
    return {
        "type": "migration_assessment",
        "project": assessment.project_name,
        "source_driver": assessment.source_driver,
        "target_driver": assessment.target_driver,
        "source_collection": assessment.source_collection,
        "target_collection": assessment.target_collection,
        "estimated_records": assessment.estimated_records,
        "actual_records": assessment.actual_records,
        "dimension": assessment.dimension,
        "estimated_batches": assessment.estimated_batches,
        "risk_level": assessment.risk_level,
        "recommendation": assessment.recommendation,
        "checks": [
            {
                "name": check.name,
                "status": check.status,
                "detail": check.detail,
            }
            for check in assessment.checks
        ],
        "risks": [
            {
                "level": risk.level,
                "detail": risk.detail,
            }
            for risk in assessment.risks
        ],
    }


def _plan_to_dict(plan: MigrationPlan) -> dict[str, Any]:
    return {
        "type": "migration_plan",
        "source_collection": plan.source_collection,
        "target_collection": plan.target_collection,
        "source_count": plan.source_count,
        "dimension": plan.dimension,
        "batch_size": plan.batch_size,
        "estimated_batches": plan.estimated_batches,
        "dimensions_ok": plan.dimensions_ok,
        "dense_vector_ok": plan.dense_vector_ok,
        "target_dimension_ok": plan.target_dimension_ok,
        "distance_metric_ok": plan.distance_metric_ok,
        "capability_gaps": list(plan.capability_gaps),
        "compatibility": [
            {
                "name": check.name,
                "source_supported": check.source_supported,
                "target_supported": check.target_supported,
                "status": check.status,
                "detail": check.detail,
            }
            for check in plan.compatibility
        ],
        "ready": plan.ready,
    }


def _migration_to_dict(
    report: MigrationReport,
    transformer: MetadataTransformer | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "type": "migration",
        "migration": {
            "source_collection": report.source_collection,
            "target_collection": report.target_collection,
            "scanned": report.scanned,
            "migrated": report.migrated,
            "dimension": report.dimension,
            "resumed": report.resumed,
            "skipped_existing": report.skipped_existing,
            "repaired_existing": report.repaired_existing,
            "existing_policy": report.existing_policy,
        },
    }

    if transformer is not None:
        payload["metadata_transform"] = {
            "records_transformed": (
                transformer.stats.records_transformed
            ),
            "fields_renamed": transformer.stats.fields_renamed,
            "fields_dropped": transformer.stats.fields_dropped,
            "defaults_applied": transformer.stats.defaults_applied,
            "casts_applied": transformer.stats.casts_applied,
        }

    return payload


def _verification_to_dict(
    report: VerificationReport,
) -> dict[str, Any]:
    return {
        "type": "migration",
        "verification": {
            "source_count": report.source_count,
            "target_count": report.target_count,
            "matched_ids": report.matched_ids,
            "missing_ids": report.missing_ids,
            "extra_records": report.extra_records,
            "dimensions_ok": report.dimensions_ok,
            "vectors_ok": report.vectors_ok,
            "metadata_ok": report.metadata_ok,
            "passed": report.passed,
        },
    }


def _close_driver(db: Any) -> None:
    close = getattr(db, "close", None)
    if callable(close):
        close()
        return

    for attribute in ("conn", "client"):
        connection = getattr(db, attribute, None)
        close = getattr(connection, "close", None)
        if callable(close):
            close()
            return


def _project_config_for_report(
    project: MigrationProject,
) -> dict[str, Any]:
    config: dict[str, Any] = {
        "project": {"name": project.project.name},
        "source": {
            "driver": project.source.driver,
            "connection": f"vecport://{project.source.driver}",
            "collection": project.source.collection,
        },
        "target": {
            "driver": project.target.driver,
            "connection": f"vecport://{project.target.driver}",
            "collection": project.target.collection,
        },
        "data": {
            "estimated_records": project.data.estimated_records,
            "dimension": project.data.dimension,
            "collection_count": project.data.collection_count,
            "vector_mode": project.data.vector_mode,
            "metadata_mapping": project.data.metadata_mapping,
        },
        "application": {
            "language": project.application.language,
            "framework": project.application.framework,
        },
    }

    spec = project.metadata_transform
    if spec is not None:
        config["metadata_transform"] = {
            "rename": dict(spec.rename),
            "drop": list(spec.drop),
            "defaults": dict(spec.defaults),
            "cast": dict(spec.cast),
            "strict": spec.strict,
        }

    return config


def _normalize_project(
    value: Mapping[str, Any] | MigrationProject,
) -> tuple[MigrationProject, Mapping[str, Any]]:
    if isinstance(value, MigrationProject):
        return value, _project_config_for_report(value)

    config = dict(value)
    return parse_migration_project(config), config


def _result(
    *,
    run_id: str,
    paths: ProjectRunPaths,
    executed: bool,
    verification_passed: bool | None,
    recommendation: str | None,
    status: str,
    stages: Sequence[ProjectRunStage],
) -> ProjectRunResult:
    return ProjectRunResult(
        run_id=run_id,
        root=paths.root,
        executed=executed,
        verification_passed=verification_passed,
        recommendation=recommendation,
        status=status,
        paths=paths,
        stages=tuple(stages),
    )


def _run_assessment_stage(
    *,
    project: MigrationProject,
    source: Any,
    target: Any,
    paths: ProjectRunPaths,
) -> MigrationAssessment:
    assessment = assess_migration_project(
        project,
        source,
        target,
    )
    _write_json(
        paths.assessment,
        _assessment_to_dict(assessment),
    )
    return assessment


def _run_plan_stage(
    *,
    assessment: MigrationAssessment,
    paths: ProjectRunPaths,
) -> MigrationPlan:
    plan = assessment.plan
    _write_json(paths.migration_plan, _plan_to_dict(plan))
    return plan


def _run_migration_stage(
    *,
    project: MigrationProject,
    plan: MigrationPlan,
    source: Any,
    target: Any,
    paths: ProjectRunPaths,
) -> MigrationReport:
    transformer = (
        MetadataTransformer(project.metadata_transform)
        if project.metadata_transform is not None
        else None
    )
    report = migrate_collection(
        source,
        target,
        collection=project.source.collection,
        target_collection=project.target.collection,
        batch_size=project.migration.batch_size,
        resume=project.migration.resume,
        existing_policy=project.migration.existing_policy,
        total_records=plan.source_count,
        record_transform=transformer,
    )
    _write_json(
        paths.migration,
        _migration_to_dict(report, transformer),
    )
    return report


def _run_verification_stage(
    *,
    project: MigrationProject,
    source: Any,
    target: Any,
    paths: ProjectRunPaths,
) -> tuple[VerificationReport, dict[str, Any]]:
    transformer = (
        MetadataTransformer(project.metadata_transform)
        if project.metadata_transform is not None
        else None
    )
    report = verify_migration(
        source,
        target,
        source_collection=project.source.collection,
        target_collection=project.target.collection,
        batch_size=project.migration.batch_size,
        record_transform=transformer,
    )
    payload = _verification_to_dict(report)
    _write_json(paths.verification, payload)
    return report, payload


def _run_filter_stage(
    *,
    assessment: MigrationAssessment,
    paths: ProjectRunPaths,
) -> tuple[FilterCompatibilityReport, dict[str, Any]]:
    report = assessment.filter_report
    payload = filter_report_to_dict(report)
    _write_json(paths.filter_json, payload)
    paths.filter_markdown.write_text(
        render_filter_report(report),
        encoding="utf-8",
    )
    return report, payload


def _run_code_stage(
    *,
    project: MigrationProject,
    source_code_files: Sequence[str | Path],
    paths: ProjectRunPaths,
) -> tuple[SearchCodeMigrationReport, dict[str, Any]]:
    report = build_search_code_migration_report(
        source_driver=project.source.driver,
        target_driver=project.target.driver,
        collection=project.target.collection,
        source_files=source_code_files,
        preferred_framework=project.application.framework,
    )
    payload = code_migration_report_to_dict(report)
    _write_json(paths.code_json, payload)
    paths.code_markdown.write_text(
        render_search_code_report(report),
        encoding="utf-8",
    )
    return report, payload


def _run_search_stage(
    *,
    project: MigrationProject,
    source: Any,
    target: Any,
    queries_path: str | Path,
    paths: ProjectRunPaths,
) -> tuple[SearchComparisonReport, dict[str, Any]]:
    comparison_config = project.search_comparison
    if comparison_config is None:
        raise ProjectRunError(
            "Search comparison inputs are incomplete."
        )

    queries = load_search_queries(queries_path)
    validate_query_dimensions(
        queries,
        expected_dimension=project.data.dimension,
    )
    report = compare_search_results(
        source_db=source,
        target_db=target,
        source_driver=project.source.driver,
        target_driver=project.target.driver,
        source_collection=project.source.collection,
        target_collection=project.target.collection,
        queries=queries,
        config=comparison_config,
    )
    payload = search_comparison_report_to_dict(report)
    _write_json(paths.search_json, payload)
    paths.search_markdown.write_text(
        render_search_comparison_report(report),
        encoding="utf-8",
    )
    return report, payload


def _run_customer_report_stage(
    *,
    report_config: Mapping[str, Any],
    verification: VerificationReport,
    verification_payload: Mapping[str, Any],
    filter_report: FilterCompatibilityReport,
    filter_payload: Mapping[str, Any],
    code_report: SearchCodeMigrationReport,
    code_payload: Mapping[str, Any],
    search_report: SearchComparisonReport,
    search_payload: Mapping[str, Any],
    paths: ProjectRunPaths,
) -> str:
    recommendation = determine_production_recommendation(
        verification_passed=verification.passed,
        filter_status=filter_report.recommendation,
        code_status=code_report.status,
        search_status=search_report.recommendation,
    )
    paths.customer_report.write_text(
        render_customer_migration_report(
            project=report_config,
            verification=verification_payload,
            filter_report=filter_payload,
            code_report=code_payload,
            search_report=search_payload,
        ),
        encoding="utf-8",
    )
    return recommendation


def run_migration_project(
    project: Mapping[str, Any] | MigrationProject,
    *,
    source_code_files: Sequence[str | Path] = (),
    queries_path: str | Path | None = None,
    output_dir: str | Path = "runs",
    execute: bool = False,
    run_id: str | None = None,
    source_options: Mapping[str, Any] | None = None,
    target_options: Mapping[str, Any] | None = None,
    connector: Callable[..., Any] = connect_url,
) -> ProjectRunResult:
    """Run the complete PoC workflow without copying customer inputs."""

    parsed, report_config = _normalize_project(project)

    if execute and not source_code_files:
        raise ProjectRunError(
            "Source code is required for a full project run."
        )
    if execute and queries_path is None:
        raise ProjectRunError(
            "Search queries are required for a full project run."
        )
    if execute and not parsed.migration.verify:
        raise ProjectRunError(
            "Full project runs require migration verification."
        )
    if execute and parsed.search_comparison is None:
        raise ProjectRunError(
            "Search comparison must be enabled for a full project run."
        )

    paths = create_project_run_paths(
        output_dir=output_dir,
        project_name=parsed.project.name,
        run_id=run_id,
    )
    resolved_run_id = paths.root.name
    stages: list[ProjectRunStage] = []
    source = None
    target = None
    current_stage = "connection"

    try:
        source = connector(
            parsed.source.connection,
            **dict(source_options or {}),
        )
        target = connector(
            parsed.target.connection,
            **dict(target_options or {}),
        )

        current_stage = "assessment"
        assessment = _run_assessment_stage(
            project=parsed,
            source=source,
            target=target,
            paths=paths,
        )
        stages.append(
            ProjectRunStage(
                "assessment",
                assessment.recommendation,
            )
        )

        current_stage = "plan"
        plan = _run_plan_stage(
            assessment=assessment,
            paths=paths,
        )
        stages.append(
            ProjectRunStage(
                "plan",
                "READY" if plan.ready else "NOT_READY",
            )
        )

        if not assessment.ready or not plan.ready:
            _write_manifest(
                paths=paths,
                project=parsed,
                run_id=resolved_run_id,
                status="NOT_READY",
                executed=False,
                recommendation="NOT_READY",
                stages=stages,
            )
            raise ProjectRunError(
                "Migration project assessment is NOT_READY."
            )

        if not execute:
            _write_manifest(
                paths=paths,
                project=parsed,
                run_id=resolved_run_id,
                status="PLAN_ONLY",
                executed=False,
                recommendation=assessment.recommendation,
                stages=stages,
            )
            return _result(
                run_id=resolved_run_id,
                paths=paths,
                executed=False,
                verification_passed=None,
                recommendation=assessment.recommendation,
                status="PLAN_ONLY",
                stages=stages,
            )

        current_stage = "migration"
        _run_migration_stage(
            project=parsed,
            plan=plan,
            source=source,
            target=target,
            paths=paths,
        )
        stages.append(ProjectRunStage("migration", "PASSED"))

        current_stage = "verification"
        (
            verification,
            verification_payload,
        ) = _run_verification_stage(
            project=parsed,
            source=source,
            target=target,
            paths=paths,
        )
        stages.append(
            ProjectRunStage(
                "verification",
                "PASSED" if verification.passed else "FAILED",
            )
        )

        current_stage = "filter"
        filter_report, filter_payload = _run_filter_stage(
            assessment=assessment,
            paths=paths,
        )
        stages.append(
            ProjectRunStage(
                "filter",
                filter_report.recommendation,
            )
        )

        current_stage = "code"
        code_report, code_payload = _run_code_stage(
            project=parsed,
            source_code_files=source_code_files,
            paths=paths,
        )
        stages.append(ProjectRunStage("code", code_report.status))

        current_stage = "search"
        if queries_path is None:
            raise ProjectRunError(
                "Search comparison inputs are incomplete."
            )
        search_report, search_payload = _run_search_stage(
            project=parsed,
            source=source,
            target=target,
            queries_path=queries_path,
            paths=paths,
        )
        stages.append(
            ProjectRunStage(
                "search",
                search_report.recommendation,
            )
        )

        current_stage = "customer_report"
        recommendation = _run_customer_report_stage(
            report_config=report_config,
            verification=verification,
            verification_payload=verification_payload,
            filter_report=filter_report,
            filter_payload=filter_payload,
            code_report=code_report,
            code_payload=code_payload,
            search_report=search_report,
            search_payload=search_payload,
            paths=paths,
        )
        stages.append(
            ProjectRunStage("customer_report", "GENERATED")
        )

        status = (
            "COMPLETED"
            if verification.passed
            else "VERIFICATION_FAILED"
        )
        _write_manifest(
            paths=paths,
            project=parsed,
            run_id=resolved_run_id,
            status=status,
            executed=True,
            recommendation=recommendation,
            stages=stages,
        )
        return _result(
            run_id=resolved_run_id,
            paths=paths,
            executed=True,
            verification_passed=verification.passed,
            recommendation=recommendation,
            status=status,
            stages=stages,
        )

    except ProjectRunError:
        if not paths.manifest.exists():
            _write_manifest(
                paths=paths,
                project=parsed,
                run_id=resolved_run_id,
                status="FAILED",
                executed=execute,
                recommendation=None,
                stages=stages,
            )
        raise
    except Exception as error:
        _write_manifest(
            paths=paths,
            project=parsed,
            run_id=resolved_run_id,
            status="FAILED",
            executed=execute,
            recommendation=None,
            stages=[
                *stages,
                ProjectRunStage(current_stage, "FAILED"),
            ],
        )
        raise ProjectRunError(
            "Migration project run failed during "
            f"the {current_stage} stage."
        ) from error
    finally:
        if target is not None:
            _close_driver(target)
        if source is not None and source is not target:
            _close_driver(source)
