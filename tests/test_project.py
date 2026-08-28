import json
import sys

import pytest

from vecport.cli import main
from vecport.core.config import ConfigError
from vecport.core.filter_compatibility import (
    required_filter_operators,
)
from vecport.core.models import (
    Capabilities,
    CollectionInfo,
    VectorRecord,
)
from vecport.core.project import (
    BASIC_FILTER_OPERATORS,
    assess_migration_project,
    load_migration_project,
    parse_migration_project,
)


class FakeAssessmentDriver:
    def __init__(
        self,
        *,
        records=None,
        info=None,
        operators=BASIC_FILTER_OPERATORS,
        metadata_filter=True,
    ):
        self.records = list(
            records or []
        )
        self.info = info
        self.operators = operators
        self.metadata_filter = (
            metadata_filter
        )
        self.closed = False

    def capabilities(self):
        return Capabilities(
            dense_vector=True,
            metadata_filter=(
                self.metadata_filter
            ),
            filter_operators=(
                self.operators
            ),
        )

    def collection_info(self, name):
        if self.info is not None:
            return self.info

        return CollectionInfo(
            name=name,
            exists=False,
        )

    def scan(
        self,
        collection,
        *,
        batch_size=100,
    ):
        del collection, batch_size
        yield from self.records

    def close(self):
        self.closed = True


def _project_config(**data_overrides):
    data = {
        "estimated_records": 2,
        "dimension": 3,
        "filter_operators": [
            "$eq",
            "$lt",
        ],
    }
    data.update(
        data_overrides
    )

    return {
        "project": {
            "name": "customer-demo",
        },
        "source": {
            "driver": "qdrant",
            "connection": (
                "vecport://qdrant"
                "?url=http://localhost:6333"
            ),
            "collection": "documents",
        },
        "target": {
            "driver": "milvus",
            "connection": (
                "vecport://milvus"
                "?uri=http://localhost:19530"
            ),
            "collection": "documents_migrated",
        },
        "data": data,
        "migration": {
            "batch_size": 2,
            "verify": True,
            "resume": True,
            "existing_policy": "repair",
        },
        "benchmark": {
            "enabled": True,
            "top_k": 10,
            "queries": 50,
        },
        "application": {
            "language": "python",
            "framework": "langchain",
        },
        "deliverables": {
            "migration_plan": True,
            "verification": True,
            "benchmark": True,
            "code_patch": True,
        },
    }


def _records():
    return [
        VectorRecord(
            id="1",
            vector=[
                1.0,
                0.0,
                0.0,
            ],
            metadata={
                "category": "AI",
            },
        ),
        VectorRecord(
            id="2",
            vector=[
                0.0,
                1.0,
                0.0,
            ],
            metadata={
                "category": "database",
            },
        ),
    ]


def _drivers(
    *,
    target_operators=BASIC_FILTER_OPERATORS,
):
    source = FakeAssessmentDriver(
        records=_records(),
        info=CollectionInfo(
            name="documents",
            exists=True,
            dimension=3,
            distance_metric="cosine",
        ),
    )
    target = FakeAssessmentDriver(
        operators=target_operators,
        info=CollectionInfo(
            name="documents_migrated",
            exists=False,
        ),
    )
    return source, target


def test_parse_migration_project():
    project = parse_migration_project(
        _project_config()
    )

    assert project.project.name == "customer-demo"
    assert project.source.driver == "qdrant"
    assert project.target.driver == "milvus"
    assert project.data.dimension == 3
    assert project.migration.batch_size == 2
    assert project.benchmark.queries == 50
    assert (
        project.filter_requirements.required_operators
        == ("$eq", "$lt")
    )
    assert project.metadata_transform is None
    assert project.search_comparison is None
    assert "localhost" not in repr(
        project.source
    )


def test_project_parses_search_comparison():
    config = _project_config()
    config["search_comparison"] = {
        "enabled": True,
        "top_k": 5,
        "warmup": 2,
        "minimum_recall_at_k": 0.95,
        "minimum_top1_match_rate": 0.85,
    }

    project = parse_migration_project(config)
    comparison = project.search_comparison

    assert comparison is not None
    assert comparison.top_k == 5
    assert comparison.warmup == 2
    assert comparison.minimum_recall_at_k == 0.95
    assert comparison.minimum_top1_match_rate == 0.85


def test_project_can_disable_search_comparison():
    config = _project_config()
    config["search_comparison"] = {
        "enabled": False,
    }

    project = parse_migration_project(config)

    assert project.search_comparison is None


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("enabled", "yes"),
        ("top_k", 0),
        ("top_k", True),
        ("warmup", -1),
        ("warmup", False),
        ("minimum_recall_at_k", 90),
        ("minimum_recall_at_k", True),
        ("minimum_top1_match_rate", -0.1),
        ("minimum_top1_match_rate", 1.1),
    ],
)
def test_project_rejects_invalid_search_comparison(
    key,
    value,
):
    config = _project_config()
    config["search_comparison"] = {
        key: value,
    }

    with pytest.raises(
        ConfigError,
        match="search_comparison",
    ):
        parse_migration_project(config)


def test_load_project_expands_environment_variables(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv(
        "SOURCE_URL",
        "vecport://qdrant?url=http://localhost:6333",
    )
    monkeypatch.setenv(
        "TARGET_URL",
        "vecport://milvus?uri=http://localhost:19530",
    )
    path = tmp_path / "migration-intake.yml"
    path.write_text(
        """
project:
  name: customer-demo
source:
  driver: qdrant
  connection: "${SOURCE_URL}"
  collection: documents
target:
  driver: milvus
  connection: "${TARGET_URL}"
  collection: documents_migrated
data:
  estimated_records: 2
  dimension: 3
""",
        encoding="utf-8",
    )

    project = load_migration_project(
        str(path)
    )

    assert (
        project.source.connection
        == "vecport://qdrant?url=http://localhost:6333"
    )


def test_project_rejects_driver_url_mismatch():
    config = _project_config()
    config["source"][
        "driver"
    ] = "pinecone"

    with pytest.raises(
        ConfigError,
        match="connection URL uses 'qdrant'",
    ):
        parse_migration_project(
            config
        )


def test_project_rejects_secret_in_connection_url():
    config = _project_config()
    config["source"][
        "connection"
    ] = "vecport://qdrant?api_key=secret"

    with pytest.raises(
        ConfigError,
        match="must not be placed",
    ):
        parse_migration_project(
            config
        )


@pytest.mark.parametrize(
    "project_name",
    [
        "../customer",
        "..",
        ".",
        "-customer",
    ],
)
def test_project_rejects_unsafe_project_name(
    project_name,
):
    config = _project_config()
    config["project"][
        "name"
    ] = project_name

    with pytest.raises(
        ConfigError,
        match="must start with",
    ):
        parse_migration_project(
            config
        )


def test_assessment_reports_low_risk():
    project = parse_migration_project(
        _project_config()
    )
    source, target = _drivers()

    assessment = assess_migration_project(
        project,
        source,
        target,
    )

    assert assessment.actual_records == 2
    assert assessment.estimated_batches == 1
    assert assessment.risk_level == "LOW"
    assert assessment.recommendation == "READY"
    assert assessment.ready
    assert assessment.risks == ()


def test_assessment_reports_medium_mapping_risk():
    project = parse_migration_project(
        _project_config(
            metadata_mapping=True,
        )
    )
    source, target = _drivers()

    assessment = assess_migration_project(
        project,
        source,
        target,
    )

    assert assessment.risk_level == "MEDIUM"
    assert (
        assessment.recommendation
        == "CONDITIONAL"
    )
    assert assessment.ready


def test_project_parses_and_reports_metadata_transform():
    config = _project_config()
    config["metadata_transform"] = {
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
        "strict": False,
    }
    project = parse_migration_project(config)
    source, target = _drivers()

    assessment = assess_migration_project(
        project,
        source,
        target,
    )

    assert project.metadata_transform is not None
    assert project.metadata_transform.rename == {
        "old_category": "category",
    }
    assert assessment.metadata_transform is (
        project.metadata_transform
    )
    assert assessment.risk_level == "MEDIUM"
    assert assessment.recommendation == "CONDITIONAL"


def test_project_rejects_invalid_metadata_transform():
    config = _project_config()
    config["metadata_transform"] = {
        "cast": {
            "price": "decimal",
        }
    }

    with pytest.raises(
        ConfigError,
        match="Invalid metadata_transform",
    ):
        parse_migration_project(config)


def test_assessment_reports_high_dimension_risk():
    project = parse_migration_project(
        _project_config(
            dimension=4,
        )
    )
    source, target = _drivers()

    assessment = assess_migration_project(
        project,
        source,
        target,
    )

    assert assessment.risk_level == "HIGH"
    assert assessment.recommendation == "NOT READY"
    assert not assessment.ready
    dimension = next(
        check
        for check in assessment.checks
        if check.name == "Dimension"
    )
    assert dimension.status == "INCOMPATIBLE"


def test_assessment_reports_missing_filter_operator():
    project = parse_migration_project(
        _project_config()
    )
    source, target = _drivers(
        target_operators=(
            "$eq",
        )
    )

    assessment = assess_migration_project(
        project,
        source,
        target,
    )

    assert assessment.risk_level == "MEDIUM"
    assert assessment.recommendation == "CONDITIONAL"
    assert assessment.ready
    filters = next(
        check
        for check in assessment.checks
        if check.name == "Filters"
    )
    assert filters.status == "UNSUPPORTED"
    assert "$lt" in filters.detail


def test_project_filter_examples_add_requirements():
    config = _project_config()
    config["data"]["filter_operators"] = [
        "$ne",
    ]
    config["filters"] = {
        "required_operators": ["$in"],
        "examples": [
            {
                "name": "ai_under_10000",
                "expression": {
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
                },
            }
        ],
    }

    project = parse_migration_project(config)

    assert set(
        required_filter_operators(
            project.filter_requirements
        )
    ) == {
        "$and",
        "$eq",
        "$in",
        "$lt",
    }


def test_project_rejects_invalid_filters():
    config = _project_config()
    config["filters"] = {
        "required_operators": ["eq"]
    }

    with pytest.raises(
        ConfigError,
        match="Invalid filters configuration",
    ):
        parse_migration_project(config)


def test_project_check_cli_is_read_only_and_hides_urls(
    tmp_path,
    monkeypatch,
    capsys,
):
    path = tmp_path / "migration-intake.yml"
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
  estimated_records: 2
  dimension: 3
  filter_operators: ["$eq", "$lt"]
migration:
  batch_size: 2
metadata_transform:
  rename:
    old_category: category
  strict: false
""",
        encoding="utf-8",
    )
    source, target = _drivers()

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
            "check",
            "--config",
            str(path),
        ],
    )

    result = main()
    captured = capsys.readouterr()

    assert result == 0
    assert source.closed
    assert target.closed
    assert "VecPort Migration Assessment" in captured.out
    assert "Enabled:                  YES" in captured.out
    assert "Rename fields:            1" in captured.out
    assert "Strict:                   NO" in captured.out
    assert "Filter compatibility" in captured.out
    assert any(
        line.startswith("$eq")
        and line.endswith("SUPPORTED")
        for line in captured.out.splitlines()
    )
    assert "Unsupported operators      None" in captured.out
    assert "Filter migration           READY" in captured.out
    assert "Risk level: MEDIUM" in captured.out
    assert "Migration PoC: CONDITIONAL" in captured.out
    assert "No data will be written." in captured.out
    assert "localhost" not in captured.out


def test_project_filter_report_cli_writes_markdown(
    tmp_path,
    monkeypatch,
    capsys,
):
    config_path = tmp_path / "migration-intake.yml"
    output_path = tmp_path / "reports" / "filter-mapping.md"
    json_path = tmp_path / "reports" / "filter-mapping.json"
    config_path.write_text(
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
  estimated_records: 2
  dimension: 3
filters:
  required_operators: ["$eq", "$text"]
""",
        encoding="utf-8",
    )
    source, target = _drivers(
        target_operators=("$eq",)
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
            "filter-report",
            "--config",
            str(config_path),
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
    assert "Filter migration: CONDITIONAL" in markdown
    assert "| $text |" in markdown
    assert "Review or rewrite `$text` usage." in markdown
    assert str(output_path) in captured.out
    assert "localhost" not in captured.out
    assert payload["type"] == "filter_compatibility"
    assert payload["recommendation"] == "CONDITIONAL"
    assert "connection" not in payload


def test_project_check_cli_reports_conditional_filters(
    tmp_path,
    monkeypatch,
    capsys,
):
    path = tmp_path / "migration-intake.yml"
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
  estimated_records: 2
  dimension: 3
filters:
  required_operators: ["$eq", "$text"]
""",
        encoding="utf-8",
    )
    source, target = _drivers(
        target_operators=("$eq",)
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
            "check",
            "--config",
            str(path),
        ],
    )

    result = main()
    captured = capsys.readouterr()

    assert result == 0
    assert any(
        line.startswith("$text")
        and line.endswith("UNSUPPORTED")
        for line in captured.out.splitlines()
    )
    assert "Unsupported operators      $text" in captured.out
    assert "Filter migration           CONDITIONAL" in captured.out
    assert "Risk level: MEDIUM" in captured.out
    assert "Migration PoC: CONDITIONAL" in captured.out
