from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from vecport.core.config import ConfigError, load_config
from vecport.core.connection import parse_connection_url
from vecport.core.errors import (
    InvalidConnectionURLError,
    MetadataTransformError,
)
from vecport.core.filter_compatibility import (
    FilterCompatibilityReport,
    FilterRequirements,
    assess_filter_compatibility,
    filter_requirements_from_config,
)
from vecport.core.migration import (
    MigrationPlan,
    plan_migration,
)
from vecport.core.search_comparison import (
    SearchComparisonConfig,
)
from vecport.core.transforms import (
    MetadataTransformSpec,
    transform_spec_from_config,
)

SUPPORTED_PROJECT_DRIVERS = (
    "qdrant",
    "pinecone",
    "weaviate",
    "milvus",
    "pgvector",
)

BASIC_FILTER_OPERATORS = (
    "$eq",
    "$ne",
    "$gt",
    "$gte",
    "$lt",
    "$lte",
    "$in",
    "$and",
    "$or",
)

_RISK_PRIORITY = {
    "LOW": 0,
    "MEDIUM": 1,
    "HIGH": 2,
}

_PROJECT_NAME_PATTERN = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._-]*$"
)


@dataclass(frozen=True)
class ProjectDetails:
    name: str


@dataclass(frozen=True)
class ProjectEndpoint:
    driver: str
    connection: str = field(repr=False)
    collection: str


@dataclass(frozen=True)
class ProjectData:
    estimated_records: int
    dimension: int
    collection_count: int = 1
    vector_mode: str = "dense"
    metadata_mapping: bool = False
    filter_operators: tuple[str, ...] = (
        BASIC_FILTER_OPERATORS
    )


@dataclass(frozen=True)
class ProjectMigration:
    batch_size: int = 500
    verify: bool = True
    resume: bool = True
    existing_policy: str = "repair"


@dataclass(frozen=True)
class ProjectBenchmark:
    enabled: bool = True
    top_k: int = 10
    queries: int = 50


@dataclass(frozen=True)
class ProjectApplication:
    language: str = "python"
    framework: str = "native"


@dataclass(frozen=True)
class ProjectDeliverables:
    migration_plan: bool = True
    verification: bool = True
    benchmark: bool = True
    code_patch: bool = True


@dataclass(frozen=True)
class MigrationProject:
    project: ProjectDetails
    source: ProjectEndpoint
    target: ProjectEndpoint
    data: ProjectData
    filter_requirements: FilterRequirements
    metadata_transform: MetadataTransformSpec | None
    migration: ProjectMigration
    benchmark: ProjectBenchmark
    search_comparison: SearchComparisonConfig | None
    application: ProjectApplication
    deliverables: ProjectDeliverables


@dataclass(frozen=True)
class AssessmentCheck:
    name: str
    status: str
    detail: str | None = None


@dataclass(frozen=True)
class AssessmentRisk:
    level: str
    detail: str


@dataclass(frozen=True)
class MigrationAssessment:
    project_name: str
    source_driver: str
    target_driver: str
    source_collection: str
    target_collection: str
    estimated_records: int
    actual_records: int
    dimension: int | None
    estimated_batches: int
    checks: tuple[AssessmentCheck, ...]
    risks: tuple[AssessmentRisk, ...]
    risk_level: str
    recommendation: str
    filter_report: FilterCompatibilityReport = field(
        repr=False
    )
    metadata_transform: MetadataTransformSpec | None = field(
        repr=False
    )
    plan: MigrationPlan = field(repr=False)

    @property
    def ready(self) -> bool:
        return self.recommendation != "NOT READY"


def _mapping(
    config: dict[str, Any],
    key: str,
    *,
    required: bool = False,
) -> dict[str, Any]:
    value = config.get(key)

    if value is None and not required:
        return {}

    if not isinstance(value, dict):
        requirement = "required and " if required else ""
        raise ConfigError(
            f"'{key}' is {requirement}must be a mapping"
        )

    return value


def _non_empty_string(
    config: dict[str, Any],
    key: str,
    *,
    path: str,
    default: str | None = None,
) -> str:
    value = config.get(key, default)

    if not isinstance(value, str) or not value.strip():
        raise ConfigError(
            f"'{path}.{key}' must be a non-empty string"
        )

    return value.strip()


def _positive_integer(
    config: dict[str, Any],
    key: str,
    *,
    path: str,
    default: int | None = None,
) -> int:
    value = config.get(key, default)

    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or value <= 0
    ):
        raise ConfigError(
            f"'{path}.{key}' must be a positive integer"
        )

    return value


def _non_negative_integer(
    config: dict[str, Any],
    key: str,
    *,
    path: str,
    default: int,
) -> int:
    value = config.get(key, default)

    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or value < 0
    ):
        raise ConfigError(
            f"'{path}.{key}' must be a "
            "non-negative integer"
        )

    return value


def _unit_interval(
    config: dict[str, Any],
    key: str,
    *,
    path: str,
    default: float,
) -> float:
    value = config.get(key, default)

    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not 0.0 <= float(value) <= 1.0
    ):
        raise ConfigError(
            f"'{path}.{key}' must be between "
            "0.0 and 1.0"
        )

    return float(value)


def _boolean(
    config: dict[str, Any],
    key: str,
    *,
    path: str,
    default: bool,
) -> bool:
    value = config.get(key, default)

    if not isinstance(value, bool):
        raise ConfigError(
            f"'{path}.{key}' must be a boolean"
        )

    return value


def _string_tuple(
    config: dict[str, Any],
    key: str,
    *,
    path: str,
    default: tuple[str, ...],
) -> tuple[str, ...]:
    value = config.get(key)

    if value is None:
        return default

    if (
        not isinstance(value, list)
        or any(
            not isinstance(item, str)
            or not item.strip()
            for item in value
        )
    ):
        raise ConfigError(
            f"'{path}.{key}' must be a list "
            "of non-empty strings"
        )

    return tuple(
        item.strip()
        for item in value
    )


def _parse_endpoint(
    config: dict[str, Any],
    section: str,
) -> ProjectEndpoint:
    driver = _non_empty_string(
        config,
        "driver",
        path=section,
    ).lower()
    connection = _non_empty_string(
        config,
        "connection",
        path=section,
    )
    collection = _non_empty_string(
        config,
        "collection",
        path=section,
    )

    if driver not in SUPPORTED_PROJECT_DRIVERS:
        supported = ", ".join(
            SUPPORTED_PROJECT_DRIVERS
        )
        raise ConfigError(
            f"'{section}.driver' must be one of: "
            f"{supported}"
        )

    try:
        parsed = parse_connection_url(
            connection
        )

    except InvalidConnectionURLError as error:
        raise ConfigError(
            f"Invalid '{section}.connection': {error}"
        ) from error

    if parsed.driver != driver:
        raise ConfigError(
            f"'{section}.driver' is '{driver}' but "
            "the connection URL uses "
            f"'{parsed.driver}'"
        )

    return ProjectEndpoint(
        driver=driver,
        connection=connection,
        collection=collection,
    )


def parse_migration_project(
    config: dict[str, Any],
) -> MigrationProject:
    project_config = _mapping(
        config,
        "project",
        required=True,
    )
    source_config = _mapping(
        config,
        "source",
        required=True,
    )
    target_config = _mapping(
        config,
        "target",
        required=True,
    )
    data_config = _mapping(
        config,
        "data",
        required=True,
    )
    migration_config = _mapping(
        config,
        "migration",
    )
    benchmark_config = _mapping(
        config,
        "benchmark",
    )
    search_comparison_config = _mapping(
        config,
        "search_comparison",
    )
    application_config = _mapping(
        config,
        "application",
    )
    deliverables_config = _mapping(
        config,
        "deliverables",
    )

    project_name = _non_empty_string(
        project_config,
        "name",
        path="project",
    )

    if not _PROJECT_NAME_PATTERN.fullmatch(
        project_name
    ):
        raise ConfigError(
            "'project.name' must start with a letter "
            "or digit and contain only letters, digits, "
            "dots, underscores, or hyphens"
        )

    existing_policy = _non_empty_string(
        migration_config,
        "existing_policy",
        path="migration",
        default="repair",
    ).lower()

    if existing_policy not in {
        "skip",
        "repair",
        "error",
    }:
        raise ConfigError(
            "'migration.existing_policy' must be "
            "'skip', 'repair', or 'error'"
        )

    try:
        metadata_transform = (
            transform_spec_from_config(
                config.get("metadata_transform")
            )
        )
    except MetadataTransformError as error:
        raise ConfigError(
            f"Invalid metadata_transform: {error}"
        ) from error

    data_filter_operators = _string_tuple(
        data_config,
        "filter_operators",
        path="data",
        default=BASIC_FILTER_OPERATORS,
    )

    try:
        if config.get("filters") is None:
            filter_requirements = (
                FilterRequirements(
                    required_operators=(
                        data_filter_operators
                    )
                )
            )
        else:
            filter_requirements = (
                filter_requirements_from_config(
                    config.get("filters")
                )
            )
    except (TypeError, ValueError) as error:
        raise ConfigError(
            f"Invalid filters configuration: {error}"
        ) from error

    parsed_search_comparison = None

    if config.get("search_comparison") is not None:
        search_comparison_enabled = _boolean(
            search_comparison_config,
            "enabled",
            path="search_comparison",
            default=True,
        )
        configured_search_comparison = (
            SearchComparisonConfig(
                top_k=_positive_integer(
                    search_comparison_config,
                    "top_k",
                    path="search_comparison",
                    default=10,
                ),
                warmup=_non_negative_integer(
                    search_comparison_config,
                    "warmup",
                    path="search_comparison",
                    default=3,
                ),
                minimum_recall_at_k=(
                    _unit_interval(
                        search_comparison_config,
                        "minimum_recall_at_k",
                        path="search_comparison",
                        default=0.90,
                    )
                ),
                minimum_top1_match_rate=(
                    _unit_interval(
                        search_comparison_config,
                        "minimum_top1_match_rate",
                        path="search_comparison",
                        default=0.80,
                    )
                ),
            )
        )

        if search_comparison_enabled:
            parsed_search_comparison = (
                configured_search_comparison
            )

    return MigrationProject(
        project=ProjectDetails(
            name=project_name,
        ),
        source=_parse_endpoint(
            source_config,
            "source",
        ),
        target=_parse_endpoint(
            target_config,
            "target",
        ),
        data=ProjectData(
            estimated_records=_positive_integer(
                data_config,
                "estimated_records",
                path="data",
            ),
            dimension=_positive_integer(
                data_config,
                "dimension",
                path="data",
            ),
            collection_count=_positive_integer(
                data_config,
                "collection_count",
                path="data",
                default=1,
            ),
            vector_mode=_non_empty_string(
                data_config,
                "vector_mode",
                path="data",
                default="dense",
            ).lower(),
            metadata_mapping=_boolean(
                data_config,
                "metadata_mapping",
                path="data",
                default=False,
            ),
            filter_operators=data_filter_operators,
        ),
        filter_requirements=filter_requirements,
        metadata_transform=metadata_transform,
        migration=ProjectMigration(
            batch_size=_positive_integer(
                migration_config,
                "batch_size",
                path="migration",
                default=500,
            ),
            verify=_boolean(
                migration_config,
                "verify",
                path="migration",
                default=True,
            ),
            resume=_boolean(
                migration_config,
                "resume",
                path="migration",
                default=True,
            ),
            existing_policy=existing_policy,
        ),
        benchmark=ProjectBenchmark(
            enabled=_boolean(
                benchmark_config,
                "enabled",
                path="benchmark",
                default=True,
            ),
            top_k=_positive_integer(
                benchmark_config,
                "top_k",
                path="benchmark",
                default=10,
            ),
            queries=_positive_integer(
                benchmark_config,
                "queries",
                path="benchmark",
                default=50,
            ),
        ),
        search_comparison=(
            parsed_search_comparison
        ),
        application=ProjectApplication(
            language=_non_empty_string(
                application_config,
                "language",
                path="application",
                default="python",
            ).lower(),
            framework=_non_empty_string(
                application_config,
                "framework",
                path="application",
                default="native",
            ).lower(),
        ),
        deliverables=ProjectDeliverables(
            migration_plan=_boolean(
                deliverables_config,
                "migration_plan",
                path="deliverables",
                default=True,
            ),
            verification=_boolean(
                deliverables_config,
                "verification",
                path="deliverables",
                default=True,
            ),
            benchmark=_boolean(
                deliverables_config,
                "benchmark",
                path="deliverables",
                default=True,
            ),
            code_patch=_boolean(
                deliverables_config,
                "code_patch",
                path="deliverables",
                default=True,
            ),
        ),
    )


def load_migration_project(
    path: str,
) -> MigrationProject:
    return parse_migration_project(
        load_config(path)
    )


def _check_status(
    value: bool | None,
    *,
    success: str = "SUPPORTED",
    failure: str = "UNSUPPORTED",
) -> str:
    if value is True:
        return success
    if value is False:
        return failure
    return "N/A"


def assess_migration_project(
    project: MigrationProject,
    source,
    target,
) -> MigrationAssessment:
    plan = plan_migration(
        source,
        target,
        source_collection=(
            project.source.collection
        ),
        target_collection=(
            project.target.collection
        ),
        batch_size=(
            project.migration.batch_size
        ),
    )
    source_capabilities = (
        source.capabilities()
    )
    target_capabilities = (
        target.capabilities()
    )
    filter_report = assess_filter_compatibility(
        source_driver=project.source.driver,
        target_driver=project.target.driver,
        requirements=project.filter_requirements,
        source_capabilities=source_capabilities,
        target_capabilities=target_capabilities,
    )
    missing_operators = (
        filter_report.unsupported_operators
    )
    configured_dimension_ok = (
        plan.dimension
        == project.data.dimension
    )
    dimension_ok = (
        plan.dimensions_ok
        and configured_dimension_ok
        and plan.target_dimension_ok
        is not False
    )
    filters_ok = filter_report.passed
    checks = (
        AssessmentCheck(
            name="Dense vectors",
            status=_check_status(
                plan.dense_vector_ok
            ),
        ),
        AssessmentCheck(
            name="Metadata",
            status=_check_status(
                target_capabilities.metadata_filter
            ),
        ),
        AssessmentCheck(
            name="Filters",
            status=_check_status(
                filters_ok
            ),
            detail=(
                "Missing on target: "
                + ", ".join(
                    missing_operators
                )
                if missing_operators
                else None
            ),
        ),
        AssessmentCheck(
            name="Dimension",
            status=_check_status(
                dimension_ok,
                success="COMPATIBLE",
                failure="INCOMPATIBLE",
            ),
            detail=(
                "Configured dimension "
                f"{project.data.dimension}, "
                "source dimension "
                f"{plan.dimension}"
                if not configured_dimension_ok
                else None
            ),
        ),
        AssessmentCheck(
            name="Distance metric",
            status=_check_status(
                plan.distance_metric_ok,
                success="COMPATIBLE",
                failure="INCOMPATIBLE",
            ),
        ),
    )
    risks: list[AssessmentRisk] = []

    def add_risk(
        level: str,
        detail: str,
    ) -> None:
        if not any(
            risk.detail == detail
            for risk in risks
        ):
            risks.append(
                AssessmentRisk(
                    level=level,
                    detail=detail,
                )
            )

    if project.data.vector_mode != "dense":
        add_risk(
            "HIGH",
            "Only dense vectors are in the Small PoC scope.",
        )

    if project.data.collection_count != 1:
        add_risk(
            "HIGH",
            "Small PoC supports exactly one collection.",
        )

    if project.application.language != "python":
        add_risk(
            "HIGH",
            "Small PoC code migration supports Python only.",
        )

    if project.application.framework not in {
        "native",
        "langchain",
        "llamaindex",
    }:
        add_risk(
            "HIGH",
            "Application framework is outside the supported scope.",
        )

    if not plan.dense_vector_ok:
        add_risk(
            "HIGH",
            "Dense vector migration is not supported by both drivers.",
        )

    if plan.source_count == 0:
        add_risk(
            "HIGH",
            "Source collection contains no records.",
        )

    if not dimension_ok:
        add_risk(
            "HIGH",
            "Vector dimensions are not compatible.",
        )

    if plan.distance_metric_ok is False:
        add_risk(
            "HIGH",
            "Source and target distance metrics differ.",
        )

    if not filters_ok:
        add_risk(
            "MEDIUM",
            "Filter operators require application code review: "
            + ", ".join(missing_operators),
        )

    record_scope = max(
        project.data.estimated_records,
        plan.source_count,
    )

    if record_scope > 100_000:
        add_risk(
            "HIGH",
            "Record count exceeds the 100,000-record PoC limit.",
        )
    elif record_scope > 50_000:
        add_risk(
            "MEDIUM",
            "Record count requires Small Plus pricing and review.",
        )

    count_difference = abs(
        plan.source_count
        - project.data.estimated_records
    )
    count_tolerance = max(
        100,
        int(
            project.data.estimated_records
            * 0.2
        ),
    )

    if count_difference > count_tolerance:
        add_risk(
            "MEDIUM",
            "Actual record count differs materially from the estimate.",
        )

    if (
        project.data.metadata_mapping
        or project.metadata_transform is not None
    ):
        add_risk(
            "MEDIUM",
            "Metadata transformation requires mapping review.",
        )

    if not plan.ready and not any(
        risk.level == "HIGH"
        for risk in risks
    ):
        add_risk(
            "HIGH",
            "Migration Plan is not ready.",
        )

    risk_level = max(
        (risk.level for risk in risks),
        key=lambda level: _RISK_PRIORITY[level],
        default="LOW",
    )
    recommendation = {
        "LOW": "READY",
        "MEDIUM": "CONDITIONAL",
        "HIGH": "NOT READY",
    }[risk_level]

    return MigrationAssessment(
        project_name=project.project.name,
        source_driver=project.source.driver,
        target_driver=project.target.driver,
        source_collection=(
            project.source.collection
        ),
        target_collection=(
            project.target.collection
        ),
        estimated_records=(
            project.data.estimated_records
        ),
        actual_records=plan.source_count,
        dimension=plan.dimension,
        estimated_batches=(
            plan.estimated_batches
        ),
        checks=checks,
        risks=tuple(risks),
        risk_level=risk_level,
        recommendation=recommendation,
        filter_report=filter_report,
        metadata_transform=(
            project.metadata_transform
        ),
        plan=plan,
    )
