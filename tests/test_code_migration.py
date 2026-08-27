import sys

import pytest

from vecport.cli import main
from vecport.core.code_migration import (
    analyze_python_search_code,
    build_search_code_migration_report,
    render_search_code_report,
    render_target_search_code,
)
from vecport.core.errors import (
    SearchCodeMigrationError,
)


def _write_qdrant_search(
    path,
    *,
    extra: str = "",
):
    path.write_text(
        f'''from qdrant_client import QdrantClient

{extra}

results = client.query_points(
    collection_name="documents",
    query=query_vector,
    query_filter=my_filter,
    limit=10,
)
''',
        encoding="utf-8",
    )


def _write_project_config(
    path,
    *,
    framework: str = "native",
):
    path.write_text(
        f'''
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
  estimated_records: 10
  dimension: 3
application:
  language: python
  framework: {framework}
''',
        encoding="utf-8",
    )


def test_detects_qdrant_search():
    finding = analyze_python_search_code(
        """
from qdrant_client import QdrantClient

client = QdrantClient(":memory:")

results = client.query_points(
    collection_name="documents",
    query=query_vector,
    query_filter=my_filter,
    limit=10,
)
""",
        file_name="search.py",
    )

    assert finding.detected_driver == "qdrant"
    assert finding.framework == "native"
    assert "search" in finding.operations
    assert "query_filter" in finding.filter_keywords


def test_detects_langchain():
    finding = analyze_python_search_code(
        """
from langchain_core.vectorstores import VectorStore
from qdrant_client import QdrantClient

documents = vector_store.similarity_search(
    query,
    k=5,
    filter=my_filter,
)
""",
        file_name="retriever.py",
    )

    assert finding.framework == "langchain"
    assert finding.detected_driver == "qdrant"
    assert "search" in finding.operations


def test_detects_langchain_driver_integration():
    finding = analyze_python_search_code(
        """
from langchain_qdrant import QdrantVectorStore

documents = vector_store.similarity_search(query)
""",
        file_name="retriever.py",
    )

    assert finding.framework == "langchain"
    assert finding.detected_driver == "qdrant"
    assert finding.recognized


def test_detects_llamaindex_driver_integration():
    finding = analyze_python_search_code(
        """
from llama_index.vector_stores.milvus import MilvusVectorStore

nodes = retriever.retrieve(query)
""",
        file_name="retriever.py",
    )

    assert finding.framework == "llamaindex"
    assert finding.detected_driver == "milvus"
    assert finding.recognized


@pytest.mark.parametrize(
    ("module", "driver"),
    [
        ("qdrant_client", "qdrant"),
        ("pinecone", "pinecone"),
        ("weaviate", "weaviate"),
        ("pymilvus", "milvus"),
        ("pgvector", "pgvector"),
    ],
)
def test_detects_supported_driver_imports(
    module,
    driver,
):
    finding = analyze_python_search_code(
        f"import {module}\nclient.search(vector=query_vector)",
        file_name="search.py",
    )

    assert finding.detected_driver == driver
    assert finding.recognized


def test_multiple_driver_imports_require_review(
    tmp_path,
):
    source_file = tmp_path / "search.py"
    source_file.write_text(
        """
import pinecone
import qdrant_client

client.search(vector=query_vector)
""",
        encoding="utf-8",
    )

    report = build_search_code_migration_report(
        source_driver="qdrant",
        target_driver="milvus",
        collection="documents",
        source_files=[source_file],
    )

    assert report.status == "MANUAL_REVIEW"
    assert report.findings[0].detected_driver is None


def test_driver_mismatch_requires_review(
    tmp_path,
):
    source_file = tmp_path / "search.py"
    _write_qdrant_search(source_file)

    report = build_search_code_migration_report(
        source_driver="pinecone",
        target_driver="milvus",
        collection="documents",
        source_files=[source_file],
    )

    assert report.status == "MANUAL_REVIEW"
    assert "does not match configured source" in report.notes[0]


def test_generates_vecport_target_code(
    tmp_path,
):
    source_file = tmp_path / "search.py"
    _write_qdrant_search(source_file)

    report = build_search_code_migration_report(
        source_driver="qdrant",
        target_driver="milvus",
        collection="documents",
        source_files=[source_file],
    )

    assert "connect_url(" in report.target_example
    assert "db.search(" in report.target_example
    assert "VECPORT_TARGET_URL" in report.target_example
    assert report.status == "READY_FOR_PATCH"


@pytest.mark.parametrize(
    "framework",
    ["native", "langchain", "llamaindex"],
)
def test_generates_supported_framework_targets(
    framework,
):
    target = render_target_search_code(
        framework=framework,
        collection='documents"unsafe',
    )

    assert "VECPORT_TARGET_URL" in target
    compile(target, "<target-example>", "exec")


def test_report_does_not_copy_source_code_or_path(
    tmp_path,
):
    private_value = "customer-private-value-not-for-output"
    source_file = tmp_path / "private-project" / "search.py"
    source_file.parent.mkdir()
    _write_qdrant_search(
        source_file,
        extra=f'api_key = "{private_value}"',
    )
    report = build_search_code_migration_report(
        source_driver="qdrant",
        target_driver="milvus",
        collection="documents",
        source_files=[source_file],
    )

    markdown = render_search_code_report(report)

    assert private_value not in markdown
    assert str(source_file.parent) not in markdown
    assert "### search.py" in markdown
    assert "filter arguments detected" in markdown


@pytest.mark.parametrize(
    "file_name",
    [
        "/home/customer/private/search.py",
        r"C:\customer\private\search.py",
    ],
)
def test_in_memory_analysis_keeps_only_file_name(
    file_name,
):
    finding = analyze_python_search_code(
        "import qdrant_client\nclient.search(query)",
        file_name=file_name,
    )

    assert finding.file_name == "search.py"


def test_invalid_python_fails():
    with pytest.raises(
        SearchCodeMigrationError,
        match="broken.py",
    ):
        analyze_python_search_code(
            "def broken(:",
            file_name="broken.py",
        )


def test_non_python_file_fails(
    tmp_path,
):
    source_file = tmp_path / "search.js"
    source_file.write_text(
        "client.search(queryVector)",
        encoding="utf-8",
    )

    with pytest.raises(
        SearchCodeMigrationError,
        match="only Python files",
    ):
        build_search_code_migration_report(
            source_driver="qdrant",
            target_driver="milvus",
            collection="documents",
            source_files=[source_file],
        )


def test_more_than_three_source_files_fails(
    tmp_path,
):
    source_files = []

    for index in range(4):
        source_file = tmp_path / f"search_{index}.py"
        _write_qdrant_search(source_file)
        source_files.append(source_file)

    with pytest.raises(
        SearchCodeMigrationError,
        match="at most 3",
    ):
        build_search_code_migration_report(
            source_driver="qdrant",
            target_driver="milvus",
            collection="documents",
            source_files=source_files,
        )


def test_code_report_cli_writes_secure_markdown(
    tmp_path,
    monkeypatch,
    capsys,
):
    config_path = tmp_path / "migration-intake.yml"
    source_file = tmp_path / "customer-code" / "search.py"
    output_path = tmp_path / "reports" / "code-report.md"
    source_file.parent.mkdir()
    _write_project_config(config_path)
    _write_qdrant_search(
        source_file,
        extra='api_key = "local-only-value"',
    )
    source_before = source_file.read_text(
        encoding="utf-8"
    )

    def unexpected_connection(*args, **kwargs):
        raise AssertionError(
            "code-report must not connect to a database"
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
            "code-report",
            "--config",
            str(config_path),
            "--source-code",
            str(source_file),
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
    assert "Status: READY_FOR_PATCH" in captured.out
    assert "Status: READY_FOR_PATCH" in markdown
    assert "local-only-value" not in markdown
    assert "localhost" not in markdown
    assert "documents_migrated" in markdown
    assert source_file.read_text(
        encoding="utf-8"
    ) == source_before


def test_code_report_cli_manual_review_is_success(
    tmp_path,
    monkeypatch,
    capsys,
):
    config_path = tmp_path / "migration-intake.yml"
    source_file = tmp_path / "unknown.py"
    output_path = tmp_path / "report.md"
    _write_project_config(config_path)
    source_file.write_text(
        "result = custom_client.fetch(query)",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "vecport",
            "project",
            "code-report",
            "--config",
            str(config_path),
            "--source-code",
            str(source_file),
            "--output",
            str(output_path),
        ],
    )

    result = main()
    captured = capsys.readouterr()

    assert result == 0
    assert "Status: MANUAL_REVIEW" in captured.out
    assert output_path.exists()


def test_code_report_cli_parse_error_returns_failure(
    tmp_path,
    monkeypatch,
    capsys,
):
    config_path = tmp_path / "migration-intake.yml"
    source_file = tmp_path / "broken.py"
    output_path = tmp_path / "report.md"
    _write_project_config(config_path)
    source_file.write_text(
        "def broken(:",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "vecport",
            "project",
            "code-report",
            "--config",
            str(config_path),
            "--source-code",
            str(source_file),
            "--output",
            str(output_path),
        ],
    )

    result = main()
    captured = capsys.readouterr()

    assert result == 1
    assert "Failed to parse Python source file: broken.py" in (
        captured.out
    )
    assert not output_path.exists()
