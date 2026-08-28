"""Filter compatibility assessment for migration projects."""

from __future__ import annotations

import re
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from vecport.core.filters import (
    SUPPORTED_FILTER_OPERATORS,
    SUPPORTED_LOGICAL_OPERATORS,
)
from vecport.core.models import Capabilities

VEC_PORT_FILTER_OPERATORS = frozenset(
    SUPPORTED_FILTER_OPERATORS
    | SUPPORTED_LOGICAL_OPERATORS
)

_OPERATOR_DESCRIPTIONS = {
    "$eq": "equals",
    "$ne": "not equals",
    "$gt": "greater than",
    "$gte": "greater than or equal",
    "$lt": "less than",
    "$lte": "less than or equal",
    "$in": "value is in list",
    "$and": "logical AND",
    "$or": "logical OR",
}

_CONFIG_KEYS = {
    "required_operators",
    "examples",
}

_OPERATOR_PATTERN = re.compile(
    r"^\$[A-Za-z0-9_-]+$"
)


@dataclass(frozen=True)
class FilterExample:
    """A named customer filter used to discover operators."""

    name: str
    expression: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "expression",
            MappingProxyType(
                deepcopy(dict(self.expression))
            ),
        )


@dataclass(frozen=True)
class FilterRequirements:
    """Filter operators and examples required by an application."""

    required_operators: tuple[str, ...] = ()
    examples: tuple[FilterExample, ...] = ()


@dataclass(frozen=True)
class FilterCompatibilityCheck:
    """Compatibility result for one filter operator."""

    operator: str
    description: str
    source_supported: bool
    target_supported: bool
    in_vecport_dsl: bool

    @property
    def passed(self) -> bool:
        return (
            self.in_vecport_dsl
            and self.target_supported
        )


@dataclass(frozen=True)
class FilterCompatibilityReport:
    """Filter compatibility results for a source/target pair."""

    source_driver: str
    target_driver: str
    checks: tuple[FilterCompatibilityCheck, ...]

    @property
    def passed(self) -> bool:
        return all(
            check.passed
            for check in self.checks
        )

    @property
    def unsupported_operators(
        self,
    ) -> tuple[str, ...]:
        return tuple(
            check.operator
            for check in self.checks
            if not check.passed
        )

    @property
    def recommendation(self) -> str:
        return (
            "READY"
            if self.passed
            else "CONDITIONAL"
        )


def filter_report_to_dict(
    report: FilterCompatibilityReport,
) -> dict[str, Any]:
    """Return a credential-free artifact for report consolidation."""

    return {
        "type": "filter_compatibility",
        "source_driver": report.source_driver,
        "target_driver": report.target_driver,
        "passed": report.passed,
        "recommendation": report.recommendation,
        "unsupported_operators": list(
            report.unsupported_operators
        ),
        "checks": [
            {
                "operator": check.operator,
                "description": check.description,
                "source_supported": (
                    check.source_supported
                ),
                "target_supported": (
                    check.target_supported
                ),
                "in_vecport_dsl": (
                    check.in_vecport_dsl
                ),
                "passed": check.passed,
            }
            for check in report.checks
        ],
    }


def collect_filter_operators(
    value: Any,
) -> tuple[str, ...]:
    """Recursively collect operator keys without validating the DSL."""

    operators: set[str] = set()

    def visit(current: Any) -> None:
        if isinstance(current, Mapping):
            for key, child in current.items():
                if (
                    isinstance(key, str)
                    and key.startswith("$")
                ):
                    operators.add(key)
                visit(child)
        elif isinstance(current, (list, tuple)):
            for child in current:
                visit(child)

    visit(value)
    return tuple(sorted(operators))


def required_filter_operators(
    requirements: FilterRequirements,
) -> tuple[str, ...]:
    """Combine declared and example-discovered operators."""

    operators = set(
        requirements.required_operators
    )
    for example in requirements.examples:
        operators.update(
            collect_filter_operators(
                example.expression
            )
        )
    return tuple(sorted(operators))


def assess_filter_compatibility(
    *,
    source_driver: str,
    target_driver: str,
    requirements: FilterRequirements,
    source_capabilities: Capabilities,
    target_capabilities: Capabilities,
) -> FilterCompatibilityReport:
    """Compare required operators with declared driver capabilities."""

    source_supported = set(
        source_capabilities.filter_operators
    )
    target_supported = set(
        target_capabilities.filter_operators
    )
    checks = []

    for operator in required_filter_operators(
        requirements
    ):
        checks.append(
            FilterCompatibilityCheck(
                operator=operator,
                description=(
                    _OPERATOR_DESCRIPTIONS.get(
                        operator,
                        "unknown / driver-specific",
                    )
                ),
                source_supported=(
                    source_capabilities.metadata_filter
                    and operator in source_supported
                ),
                target_supported=(
                    target_capabilities.metadata_filter
                    and operator in target_supported
                ),
                in_vecport_dsl=(
                    operator
                    in VEC_PORT_FILTER_OPERATORS
                ),
            )
        )

    return FilterCompatibilityReport(
        source_driver=source_driver,
        target_driver=target_driver,
        checks=tuple(checks),
    )


def _validate_operator(operator: Any) -> str:
    if (
        not isinstance(operator, str)
        or not _OPERATOR_PATTERN.fullmatch(operator)
    ):
        raise ValueError(
            "Filter operators must start with '$' and contain "
            "only letters, digits, underscores, or hyphens."
        )
    return operator


def filter_requirements_from_config(
    config: Mapping[str, Any] | None,
) -> FilterRequirements:
    """Parse the filters section of a migration intake file."""

    if config is None:
        return FilterRequirements()
    if not isinstance(config, Mapping):
        raise TypeError(
            "filters must be a mapping."
        )

    unknown = set(config) - _CONFIG_KEYS
    if unknown:
        unknown_names = ", ".join(
            sorted(str(key) for key in unknown)
        )
        raise ValueError(
            "Unsupported filters option(s): "
            f"{unknown_names}"
        )

    required = config.get(
        "required_operators",
        [],
    )
    examples_config = config.get(
        "examples",
        [],
    )

    if not isinstance(required, (list, tuple)):
        raise TypeError(
            "filters.required_operators must be a list."
        )
    if not isinstance(examples_config, (list, tuple)):
        raise TypeError(
            "filters.examples must be a list."
        )

    required_operators = tuple(
        _validate_operator(operator)
        for operator in required
    )
    examples: list[FilterExample] = []
    example_names: set[str] = set()

    for item in examples_config:
        if not isinstance(item, Mapping):
            raise TypeError(
                "Each filter example must be a mapping."
            )

        unknown_item = set(item) - {
            "name",
            "expression",
        }
        if unknown_item:
            options = ", ".join(
                sorted(
                    str(key)
                    for key in unknown_item
                )
            )
            raise ValueError(
                "Unsupported filter example option(s): "
                f"{options}"
            )

        name = item.get("name")
        expression = item.get("expression")

        if not isinstance(name, str) or not name.strip():
            raise ValueError(
                "Filter example name must be a non-empty string."
            )
        name = name.strip()
        if name in example_names:
            raise ValueError(
                "Filter example names must be unique: "
                f"{name}"
            )
        if (
            not isinstance(expression, Mapping)
            or not expression
        ):
            raise ValueError(
                "Filter example expression must be a non-empty mapping."
            )

        for operator in collect_filter_operators(
            expression
        ):
            _validate_operator(operator)

        example_names.add(name)
        examples.append(
            FilterExample(
                name=name,
                expression=expression,
            )
        )

    return FilterRequirements(
        required_operators=(
            required_operators
        ),
        examples=tuple(examples),
    )


def _markdown_cell(value: str) -> str:
    return (
        value.replace("|", "\\|")
        .replace("\r", " ")
        .replace("\n", " ")
    )


def _markdown_code(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("`", "\\`")
        .replace("\r", " ")
        .replace("\n", " ")
    )


def render_filter_report(
    report: FilterCompatibilityReport,
) -> str:
    """Render a customer-facing Markdown compatibility report."""

    lines = [
        "# Filter Compatibility Report",
        "",
        f"Source: {_markdown_cell(report.source_driver)}",
        f"Target: {_markdown_cell(report.target_driver)}",
        "",
        "| Operator | Meaning | Source | Target | Result |",
        "| --- | --- | --- | --- | --- |",
    ]

    for check in report.checks:
        source = (
            "YES"
            if check.source_supported
            else "NO"
        )
        target = (
            "YES"
            if check.target_supported
            else "NO"
        )
        result = (
            "SUPPORTED"
            if check.passed
            else "UNSUPPORTED"
        )
        lines.append(
            "| "
            f"{_markdown_cell(check.operator)} | "
            f"{_markdown_cell(check.description)} | "
            f"{source} | "
            f"{target} | "
            f"{result} |"
        )

    lines.extend(
        [
            "",
            "## Recommendation",
            "",
            (
                "Filter migration: "
                f"{report.recommendation}"
            ),
        ]
    )

    if report.unsupported_operators:
        lines.extend(
            [
                "",
                "## Required changes",
                "",
            ]
        )
        for operator in report.unsupported_operators:
            lines.append(
                "- Review or rewrite "
                f"`{_markdown_code(operator)}` usage."
            )

    return "\n".join(lines) + "\n"
