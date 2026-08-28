from __future__ import annotations

import ast
import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from vecport.core.errors import (
    SearchCodeMigrationError,
)


@dataclass(frozen=True)
class SearchCodeFinding:
    """Search-related API usage detected in one Python file."""

    file_name: str
    framework: str
    detected_driver: str | None
    imports: tuple[str, ...]
    operations: tuple[str, ...]
    filter_keywords: tuple[str, ...]

    @property
    def recognized(self) -> bool:
        return (
            self.detected_driver is not None
            and "search" in self.operations
        )


@dataclass(frozen=True)
class SearchCodeMigrationReport:
    """Read-only migration guidance for customer search code."""

    source_driver: str
    target_driver: str
    findings: tuple[SearchCodeFinding, ...]
    target_framework: str
    target_example: str
    notes: tuple[str, ...]

    @property
    def requires_manual_review(self) -> bool:
        if not self.findings:
            return True

        return any(
            (
                not finding.recognized
                or (
                    finding.detected_driver
                    is not None
                    and finding.detected_driver
                    != self.source_driver
                )
            )
            for finding in self.findings
        )

    @property
    def status(self) -> str:
        if self.requires_manual_review:
            return "MANUAL_REVIEW"

        return "READY_FOR_PATCH"


def code_migration_report_to_dict(
    report: SearchCodeMigrationReport,
) -> dict[str, Any]:
    """Return an artifact without source code, paths, or target code."""

    return {
        "type": "search_code_migration",
        "source_driver": report.source_driver,
        "target_driver": report.target_driver,
        "target_framework": report.target_framework,
        "status": report.status,
        "requires_manual_review": (
            report.requires_manual_review
        ),
        "findings": [
            {
                "file_name": finding.file_name,
                "framework": finding.framework,
                "detected_driver": (
                    finding.detected_driver
                ),
                "operations": list(
                    finding.operations
                ),
                "filter_keywords": list(
                    finding.filter_keywords
                ),
            }
            for finding in report.findings
        ],
        "notes": list(report.notes),
    }


_DRIVER_IMPORT_MARKERS = {
    "qdrant": (
        "qdrant_client",
        "langchain_qdrant",
        "llama_index.vector_stores.qdrant",
    ),
    "pinecone": (
        "pinecone",
        "langchain_pinecone",
        "llama_index.vector_stores.pinecone",
    ),
    "weaviate": (
        "weaviate",
        "langchain_weaviate",
        "llama_index.vector_stores.weaviate",
    ),
    "milvus": (
        "pymilvus",
        "langchain_milvus",
        "llama_index.vector_stores.milvus",
    ),
    "pgvector": (
        "pgvector",
        "langchain_postgres",
        "llama_index.vector_stores.postgres",
    ),
}

_SEARCH_CALL_NAMES = {
    "search",
    "query",
    "query_points",
    "near_vector",
    "similarity_search",
    "similarity_search_with_score",
    "retrieve",
    "l2_distance",
    "cosine_distance",
    "max_inner_product",
    "l1_distance",
    "hamming_distance",
    "jaccard_distance",
}

_FILTER_KEYWORDS = {
    "filter",
    "filters",
    "query_filter",
    "where",
    "expr",
}

_SUPPORTED_FRAMEWORKS = {
    "native",
    "langchain",
    "llamaindex",
}

_MAX_SOURCE_FILES = 3


def _dotted_name(
    node: ast.AST,
) -> str | None:
    if isinstance(node, ast.Name):
        return node.id

    if isinstance(node, ast.Attribute):
        parent = _dotted_name(node.value)

        if parent:
            return f"{parent}.{node.attr}"

        return node.attr

    return None


def _collect_imports(
    tree: ast.AST,
) -> tuple[str, ...]:
    imports: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)

        elif (
            isinstance(node, ast.ImportFrom)
            and node.module
        ):
            imports.add(node.module)

    return tuple(sorted(imports))


def _collect_call_information(
    tree: ast.AST,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    operations: set[str] = set()
    filter_keywords: set[str] = set()

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        dotted = _dotted_name(node.func)

        if dotted:
            final_name = dotted.rsplit(".", 1)[-1]

            if final_name in _SEARCH_CALL_NAMES:
                operations.add("search")

        for keyword in node.keywords:
            if keyword.arg in _FILTER_KEYWORDS:
                filter_keywords.add(keyword.arg)

    return (
        tuple(sorted(operations)),
        tuple(sorted(filter_keywords)),
    )


def _detect_framework(
    imports: Iterable[str],
) -> str:
    imports_tuple = tuple(imports)

    if any(
        item.startswith("llama_index")
        for item in imports_tuple
    ):
        return "llamaindex"

    if any(
        item.startswith("langchain")
        for item in imports_tuple
    ):
        return "langchain"

    return "native"


def _detect_driver(
    imports: Iterable[str],
) -> str | None:
    imports_tuple = tuple(imports)
    matches: list[str] = []

    for driver, markers in _DRIVER_IMPORT_MARKERS.items():
        if any(
            any(
                imported.startswith(marker)
                for marker in markers
            )
            for imported in imports_tuple
        ):
            matches.append(driver)

    if len(matches) == 1:
        return matches[0]

    return None


def analyze_python_search_code(
    source: str,
    *,
    file_name: str = "<memory>",
) -> SearchCodeFinding:
    """Analyze Python source without executing or retaining it."""

    safe_file_name = (
        str(file_name)
        .replace("\\", "/")
        .rsplit("/", 1)[-1]
        or "<unknown>"
    )

    try:
        tree = ast.parse(
            source,
            filename=safe_file_name,
        )

    except SyntaxError as error:
        raise SearchCodeMigrationError(
            "Failed to parse Python source file: "
            f"{safe_file_name}"
        ) from error

    imports = _collect_imports(tree)
    operations, filter_keywords = (
        _collect_call_information(tree)
    )

    return SearchCodeFinding(
        file_name=safe_file_name,
        framework=_detect_framework(imports),
        detected_driver=_detect_driver(imports),
        imports=imports,
        operations=operations,
        filter_keywords=filter_keywords,
    )


def analyze_python_search_file(
    path: str | Path,
) -> SearchCodeFinding:
    """Read and analyze one local Python source file."""

    file_path = Path(path)

    if file_path.suffix.lower() != ".py":
        raise SearchCodeMigrationError(
            "Search code migration currently supports "
            "only Python files."
        )

    try:
        source = file_path.read_text(
            encoding="utf-8"
        )

    except (OSError, UnicodeError) as error:
        raise SearchCodeMigrationError(
            "Failed to read source file: "
            f"{file_path.name}"
        ) from error

    return analyze_python_search_code(
        source,
        file_name=file_path.name,
    )


def _collection_literal(
    collection: str,
) -> str:
    return json.dumps(collection)


def _render_native_target(
    *,
    collection: str,
) -> str:
    return f'''import os

from vecport import connect_url


db = connect_url(
    os.environ["VECPORT_TARGET_URL"]
)

results = db.search(
    collection={_collection_literal(collection)},
    vector=query_vector,
    top_k=10,
    filters=vecport_filters,
)
'''


def _render_langchain_target(
    *,
    collection: str,
) -> str:
    return f'''import os

from vecport import connect_url
from vecport.integrations.langchain import (
    VecPortVectorStore,
)


db = connect_url(
    os.environ["VECPORT_TARGET_URL"]
)

vector_store = VecPortVectorStore(
    db=db,
    collection={_collection_literal(collection)},
    embedding=embeddings,
)

documents = vector_store.similarity_search(
    query,
    k=10,
    filter=vecport_filter,
)
'''


def _render_llamaindex_target(
    *,
    collection: str,
) -> str:
    return f'''import os

from llama_index.core import (
    StorageContext,
    VectorStoreIndex,
)

from vecport import connect_url
from vecport.integrations.llamaindex import (
    VecPortLlamaIndexVectorStore,
)


db = connect_url(
    os.environ["VECPORT_TARGET_URL"]
)

vector_store = VecPortLlamaIndexVectorStore(
    db=db,
    collection={_collection_literal(collection)},
)

storage_context = StorageContext.from_defaults(
    vector_store=vector_store,
)
'''


def render_target_search_code(
    *,
    framework: str,
    collection: str,
) -> str:
    """Render a credential-free VecPort replacement example."""

    if framework == "native":
        return _render_native_target(
            collection=collection
        )

    if framework == "langchain":
        return _render_langchain_target(
            collection=collection
        )

    if framework == "llamaindex":
        return _render_llamaindex_target(
            collection=collection
        )

    raise SearchCodeMigrationError(
        "Unsupported application framework: "
        f"{framework}"
    )


def build_search_code_migration_report(
    *,
    source_driver: str,
    target_driver: str,
    collection: str,
    source_files: Iterable[str | Path],
    preferred_framework: str | None = None,
) -> SearchCodeMigrationReport:
    """Build migration guidance for one to three Python files."""

    source_paths = tuple(source_files)

    if not source_paths:
        raise SearchCodeMigrationError(
            "At least one Python source file is required."
        )

    if len(source_paths) > _MAX_SOURCE_FILES:
        raise SearchCodeMigrationError(
            "Search code migration supports at most "
            f"{_MAX_SOURCE_FILES} Python source files."
        )

    findings = tuple(
        analyze_python_search_file(path)
        for path in source_paths
    )
    detected_frameworks = {
        finding.framework
        for finding in findings
    }

    if preferred_framework is not None:
        framework = preferred_framework.lower()

    elif len(detected_frameworks) == 1:
        framework = next(iter(detected_frameworks))

    else:
        framework = "native"

    if framework not in _SUPPORTED_FRAMEWORKS:
        raise SearchCodeMigrationError(
            "Unsupported application framework: "
            f"{framework}"
        )

    notes: list[str] = []

    for finding in findings:
        if not finding.recognized:
            notes.append(
                f"{finding.file_name}: search usage could "
                "not be identified reliably."
            )

        elif finding.detected_driver != source_driver:
            notes.append(
                f"{finding.file_name}: detected driver "
                f"'{finding.detected_driver}' does not match "
                f"configured source '{source_driver}'."
            )

        if finding.filter_keywords:
            notes.append(
                f"{finding.file_name}: filter arguments "
                "detected; apply the STEP59 VecPort "
                "filter mapping."
            )

    target_example = render_target_search_code(
        framework=framework,
        collection=collection,
    )

    return SearchCodeMigrationReport(
        source_driver=source_driver,
        target_driver=target_driver,
        findings=findings,
        target_framework=framework,
        target_example=target_example,
        notes=tuple(notes),
    )


def _markdown_text(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("`", "\\`")
        .replace("\r", " ")
        .replace("\n", " ")
    )


def render_search_code_report(
    report: SearchCodeMigrationReport,
) -> str:
    """Render a report without copying customer source code."""

    lines = [
        "# Search Code Migration Report",
        "",
        f"Source DB: {_markdown_text(report.source_driver)}",
        f"Target DB: {_markdown_text(report.target_driver)}",
        (
            "Target framework: "
            f"{_markdown_text(report.target_framework)}"
        ),
        f"Status: {report.status}",
        "",
        "## Detected usage",
        "",
    ]

    for finding in report.findings:
        filter_arguments = (
            ", ".join(finding.filter_keywords)
            or "None"
        )
        lines.extend(
            [
                f"### {_markdown_text(finding.file_name)}",
                "",
                (
                    "Detected driver: "
                    f"{finding.detected_driver or 'UNKNOWN'}"
                ),
                f"Framework: {finding.framework}",
                (
                    "Search operation: "
                    + (
                        "YES"
                        if "search" in finding.operations
                        else "NO"
                    )
                ),
                (
                    "Filter arguments: "
                    f"{filter_arguments}"
                ),
                "",
            ]
        )

    lines.extend(
        [
            "## Recommended VecPort code",
            "",
            "```python",
            report.target_example.rstrip(),
            "```",
            "",
            "## Migration notes",
            "",
        ]
    )

    if report.notes:
        lines.extend(
            f"- {_markdown_text(note)}"
            for note in report.notes
        )

    else:
        lines.append(
            "- No blocking search-code issues detected."
        )

    lines.extend(
        [
            "",
            "## Manual review",
            "",
            (
                "This report is a migration plan. Review "
                "application behavior and tests before "
                "replacing production code."
            ),
            "",
        ]
    )

    return "\n".join(lines)
