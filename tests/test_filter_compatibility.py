import pytest

from vecport.core.filter_compatibility import (
    FilterExample,
    FilterRequirements,
    assess_filter_compatibility,
    collect_filter_operators,
    filter_requirements_from_config,
    render_filter_report,
)
from vecport.core.models import Capabilities


def _capabilities(*operators):
    return Capabilities(
        metadata_filter=True,
        filter_operators=operators,
    )


def test_collect_filter_operators():
    operators = collect_filter_operators(
        {
            "$and": [
                {
                    "category": {
                        "$eq": "AI",
                    }
                },
                {
                    "price": {
                        "$lt": 10000,
                    }
                },
            ]
        }
    )

    assert set(operators) == {
        "$and",
        "$eq",
        "$lt",
    }


def test_filter_compatibility_ready():
    capabilities = _capabilities(
        "$eq",
        "$lt",
        "$and",
    )
    report = assess_filter_compatibility(
        source_driver="qdrant",
        target_driver="milvus",
        requirements=FilterRequirements(
            required_operators=(
                "$eq",
                "$lt",
                "$and",
            )
        ),
        source_capabilities=capabilities,
        target_capabilities=capabilities,
    )

    assert report.passed
    assert report.recommendation == "READY"
    assert report.unsupported_operators == ()


def test_filter_compatibility_conditional():
    report = assess_filter_compatibility(
        source_driver="qdrant",
        target_driver="milvus",
        requirements=FilterRequirements(
            required_operators=(
                "$eq",
                "$text",
            )
        ),
        source_capabilities=_capabilities(
            "$eq",
            "$text",
        ),
        target_capabilities=_capabilities(
            "$eq"
        ),
    )

    assert not report.passed
    assert "$text" in report.unsupported_operators
    assert report.recommendation == "CONDITIONAL"
    text_check = next(
        check
        for check in report.checks
        if check.operator == "$text"
    )
    assert not text_check.in_vecport_dsl


def test_examples_add_required_operators():
    requirements = FilterRequirements(
        examples=(
            FilterExample(
                name="price",
                expression={
                    "price": {
                        "$gte": 1000,
                    }
                },
            ),
        )
    )
    report = assess_filter_compatibility(
        source_driver="qdrant",
        target_driver="milvus",
        requirements=requirements,
        source_capabilities=_capabilities(
            "$gte"
        ),
        target_capabilities=_capabilities(
            "$gte"
        ),
    )

    assert report.passed
    assert report.checks[0].operator == "$gte"


def test_filter_requirements_from_config():
    requirements = filter_requirements_from_config(
        {
            "required_operators": ["$in"],
            "examples": [
                {
                    "name": "category",
                    "expression": {
                        "category": {
                            "$eq": "AI",
                        }
                    },
                }
            ],
        }
    )

    assert "$in" in requirements.required_operators
    assert requirements.examples[0].name == "category"
    assert {
        "$in",
        *collect_filter_operators(
            requirements.examples[0].expression
        ),
    } == {"$eq", "$in"}


def test_invalid_filter_config_is_rejected():
    with pytest.raises(
        ValueError,
        match="must start with",
    ):
        filter_requirements_from_config(
            {
                "required_operators": [
                    "eq",
                ]
            }
        )


def test_render_filter_report():
    report = assess_filter_compatibility(
        source_driver="qdrant",
        target_driver="milvus",
        requirements=FilterRequirements(
            required_operators=("$eq",)
        ),
        source_capabilities=_capabilities("$eq"),
        target_capabilities=_capabilities("$eq"),
    )

    markdown = render_filter_report(report)

    assert "# Filter Compatibility Report" in markdown
    assert "| $eq | equals | YES | YES | SUPPORTED |" in markdown
    assert "Filter migration: READY" in markdown


def test_render_conditional_report_lists_changes():
    report = assess_filter_compatibility(
        source_driver="qdrant",
        target_driver="milvus",
        requirements=FilterRequirements(
            required_operators=("$text",)
        ),
        source_capabilities=_capabilities("$text"),
        target_capabilities=_capabilities(),
    )

    markdown = render_filter_report(report)

    assert "Filter migration: CONDITIONAL" in markdown
    assert "Review or rewrite `$text` usage." in markdown
