import json

import pytest

from vecport.core.errors import ProjectRunError
from vecport.core.migration import VerificationReport
from vecport.core.models import (
    Capabilities,
    CollectionInfo,
    SearchResult,
    VectorRecord,
)
from vecport.core.project_runner import (
    build_safe_run_manifest,
    create_project_run_paths,
    run_migration_project,
)

_OPERATORS = (
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


class FakeProjectDriver:
    def __init__(self):
        self.collections = {}
        self.dimensions = {}
        self.write_calls = 0
        self.closed = False

    def capabilities(self):
        return Capabilities(
            dense_vector=True,
            metadata_filter=True,
            filter_operators=_OPERATORS,
        )

    def collection_info(self, name):
        if name not in self.collections:
            return CollectionInfo(
                name=name,
                exists=False,
            )

        return CollectionInfo(
            name=name,
            exists=True,
            dimension=self.dimensions[name],
            distance_metric="cosine",
        )

    def create_collection_from_info(self, name, info):
        self.write_calls += 1
        self.collections[name] = []
        self.dimensions[name] = info.dimension

    def upsert(self, collection, records):
        self.write_calls += 1
        existing = {
            record.id: record
            for record in self.collections.setdefault(
                collection,
                [],
            )
        }
        for record in records:
            existing[record.id] = record
        self.collections[collection] = list(existing.values())

    def get(self, collection, ids):
        wanted = set(ids)
        return [
            record
            for record in self.collections.get(collection, [])
            if record.id in wanted
        ]

    def scan(self, collection, *, batch_size=100):
        del batch_size
        yield from self.collections.get(collection, [])

    def search(
        self,
        collection,
        vector,
        top_k=10,
        filters=None,
    ):
        del vector, filters
        return [
            SearchResult(
                id=record.id,
                score=1.0,
                metadata=dict(record.metadata),
            )
            for record in self.collections.get(
                collection,
                [],
            )[:top_k]
        ]

    def close(self):
        self.closed = True


def _records():
    return [
        VectorRecord(
            id="private-doc-1",
            vector=[1.0, 0.0, 0.0],
            metadata={"old_category": "AI"},
        ),
        VectorRecord(
            id="private-doc-2",
            vector=[0.0, 1.0, 0.0],
            metadata={"old_category": "database"},
        ),
    ]


def _drivers():
    source = FakeProjectDriver()
    source.collections["documents"] = _records()
    source.dimensions["documents"] = 3
    return source, FakeProjectDriver()


def _config(*, transform=False, secret=None):
    config = {
        "project": {"name": "customer-demo"},
        "source": {
            "driver": "qdrant",
            "connection": "vecport://qdrant",
            "collection": "documents",
        },
        "target": {
            "driver": "milvus",
            "connection": "vecport://milvus",
            "collection": "documents_migrated",
        },
        "data": {
            "estimated_records": 2,
            "dimension": 3,
        },
        "filters": {
            "required_operators": ["$eq", "$and"],
        },
        "migration": {
            "batch_size": 2,
            "verify": True,
            "resume": True,
            "existing_policy": "repair",
        },
        "search_comparison": {
            "enabled": True,
            "top_k": 2,
            "warmup": 0,
            "minimum_recall_at_k": 0.9,
            "minimum_top1_match_rate": 0.8,
        },
        "application": {
            "language": "python",
            "framework": "native",
        },
    }
    if transform:
        config["metadata_transform"] = {
            "rename": {"old_category": "category"},
        }
    if secret is not None:
        config["metadata_transform"] = {
            "defaults": {"private_default": secret},
        }
    return config


def _write_inputs(tmp_path, *, secret=""):
    source_code = tmp_path / "search.py"
    source_code.write_text(
        "from qdrant_client import QdrantClient\n"
        f"PRIVATE_VALUE = {secret!r}\n"
        "client = QdrantClient()\n"
        "client.search(collection_name='documents')\n",
        encoding="utf-8",
    )
    queries = tmp_path / "search-queries.jsonl"
    queries.write_text(
        json.dumps(
            {
                "id": "private-query-1",
                "vector": [1.0, 0.0, 0.0],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return source_code, queries


def _connector(source, target):
    def connect(url, **options):
        assert options == {}
        return source if "qdrant" in url else target

    return connect


def test_project_run_paths(tmp_path):
    paths = create_project_run_paths(
        output_dir=tmp_path,
        project_name="Customer Demo",
        run_id="test-run",
    )

    assert (
        paths.root
        == tmp_path / "customer-demo" / "test-run"
    )
    assert paths.customer_report.name == "08_migration_report.md"


def test_existing_run_directory_fails(tmp_path):
    root = tmp_path / "customer-demo" / "test-run"
    root.mkdir(parents=True)

    with pytest.raises(ProjectRunError):
        create_project_run_paths(
            output_dir=tmp_path,
            project_name="Customer Demo",
            run_id="test-run",
        )


@pytest.mark.parametrize("run_id", ["../bad", "..", "bad/path"])
def test_unsafe_run_id_fails(tmp_path, run_id):
    with pytest.raises(ProjectRunError):
        create_project_run_paths(
            output_dir=tmp_path,
            project_name="demo",
            run_id=run_id,
        )


def test_manifest_contains_no_connections():
    manifest = build_safe_run_manifest(
        project_name="demo",
        source_driver="qdrant",
        target_driver="milvus",
        run_id="test",
        status="COMPLETED",
        executed=True,
        recommendation="READY",
    )
    serialized = str(manifest).lower()

    assert "connection" not in serialized
    assert "password" not in serialized
    assert "api_key" not in serialized


def test_plan_only_does_not_write_target(tmp_path):
    source, target = _drivers()
    result = run_migration_project(
        _config(),
        output_dir=tmp_path,
        run_id="plan-only",
        connector=_connector(source, target),
    )

    assert result.status == "PLAN_ONLY"
    assert not result.executed
    assert target.write_calls == 0
    assert result.paths.manifest.exists()
    assert result.paths.assessment.exists()
    assert result.paths.migration_plan.exists()
    assert not result.paths.migration.exists()
    assert source.closed
    assert target.closed


def test_full_run_generates_every_artifact(tmp_path):
    source, target = _drivers()
    source_code, queries = _write_inputs(tmp_path)
    result = run_migration_project(
        _config(transform=True),
        source_code_files=[source_code],
        queries_path=queries,
        output_dir=tmp_path / "runs",
        execute=True,
        run_id="full-run",
        connector=_connector(source, target),
    )

    assert result.status == "COMPLETED"
    assert result.verification_passed is True
    assert result.recommendation == "READY"
    expected = [
        result.paths.manifest,
        result.paths.assessment,
        result.paths.migration_plan,
        result.paths.migration,
        result.paths.verification,
        result.paths.filter_json,
        result.paths.filter_markdown,
        result.paths.code_json,
        result.paths.code_markdown,
        result.paths.search_json,
        result.paths.search_markdown,
        result.paths.customer_report,
    ]
    assert all(artifact.exists() for artifact in expected)
    assert {
        path.name
        for path in result.root.rglob("*")
        if path.is_file()
    }.isdisjoint({"search.py", "search-queries.jsonl"})
    target_records = target.collections["documents_migrated"]
    assert target_records[0].metadata == {"category": "AI"}


def test_customer_inputs_and_secrets_are_not_copied(tmp_path):
    secret = "super-secret-password"
    source, target = _drivers()
    source_code, queries = _write_inputs(
        tmp_path,
        secret=secret,
    )
    result = run_migration_project(
        _config(secret=secret),
        source_code_files=[source_code],
        queries_path=queries,
        output_dir=tmp_path / "runs",
        execute=True,
        run_id="safe-run",
        connector=_connector(source, target),
    )

    combined = "\n".join(
        path.read_text(encoding="utf-8")
        for path in result.root.rglob("*")
        if path.is_file()
    )
    assert secret not in combined
    assert "private-query-1" not in combined
    assert "private-doc-1" not in combined
    assert "vecport://" not in combined


def test_verification_failure_is_not_success(
    tmp_path,
    monkeypatch,
):
    source, target = _drivers()
    source_code, queries = _write_inputs(tmp_path)
    monkeypatch.setattr(
        "vecport.core.project_runner.verify_migration",
        lambda *args, **kwargs: VerificationReport(
            source_count=2,
            target_count=1,
            matched_ids=1,
            missing_ids=1,
            extra_records=0,
            dimensions_ok=True,
            vectors_ok=True,
            metadata_ok=True,
            passed=False,
        ),
    )

    result = run_migration_project(
        _config(),
        source_code_files=[source_code],
        queries_path=queries,
        output_dir=tmp_path / "runs",
        execute=True,
        run_id="failed-verification",
        connector=_connector(source, target),
    )

    assert result.status == "VERIFICATION_FAILED"
    assert result.verification_passed is False
    assert result.recommendation == "NOT_READY"
    customer_report = result.paths.customer_report.read_text(
        encoding="utf-8"
    )
    assert "Production Migration Recommendation:\nNOT_READY" in (
        customer_report
    )


def test_full_run_requires_all_inputs(tmp_path):
    source, target = _drivers()

    with pytest.raises(ProjectRunError):
        run_migration_project(
            _config(),
            output_dir=tmp_path,
            execute=True,
            connector=_connector(source, target),
        )

    assert not list(tmp_path.iterdir())
