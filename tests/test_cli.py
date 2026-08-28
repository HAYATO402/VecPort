import json
import sys
from types import SimpleNamespace

import pytest

from vecport.cli import main
from vecport.core.compliance import (
    ComplianceCheck,
    ComplianceReport,
)


class StubComplianceDriver:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


def test_config_check_valid(
    tmp_path,
    monkeypatch,
    capsys,
):

    path = tmp_path / "vecport.yml"

    path.write_text(
        """
benchmark:
  targets:
    - label: qdrant
      url: "vecport://qdrant?url=http://localhost:6333"

    - label: milvus
      url: "vecport://milvus?uri=http://localhost:19530"

  collection: documents
  dimension: 128
  top_k: 10
  iterations: 100
  warmup: 10
  format: json
""",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "vecport",
            "config",
            "check",
            "--config",
            str(path),
        ],
    )

    result = main()

    captured = capsys.readouterr()

    assert result == 0

    assert (
        "Configuration valid"
        in captured.out
    )

    assert (
        "benchmark: OK"
        in captured.out
    )

def test_config_check_migration(
    tmp_path,
    monkeypatch,
    capsys,
):

    path = tmp_path / "vecport.yml"

    path.write_text(
        """
migration:
  from: "vecport://qdrant?url=http://localhost:6333"
  to: "vecport://milvus?uri=http://localhost:19530"
  collection: documents
  target_collection: documents_copy
  batch_size: 500
  verify: true
""",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "vecport",
            "config",
            "check",
            "--config",
            str(path),
        ],
    )

    result = main()

    captured = capsys.readouterr()

    assert result == 0

    assert (
        "migration: OK"
        in captured.out
    )


def test_compliance_command_success(
    tmp_path,
    monkeypatch,
    capsys,
):
    output = tmp_path / "compliance.json"
    db = StubComplianceDriver()
    report = ComplianceReport(
        collection="vecport_compliance_test",
        checks=(
            ComplianceCheck(
                name="create_collection",
                status="pass",
            ),
        ),
    )

    monkeypatch.setattr(
        "vecport.cli.connect_url",
        lambda *args, **kwargs: db,
    )
    monkeypatch.setattr(
        "vecport.cli.run_compliance",
        lambda *args, **kwargs: report,
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "vecport",
            "compliance",
            "--url",
            "vecport://qdrant",
            "--output",
            str(output),
        ],
    )

    result = main()
    payload = json.loads(
        output.read_text(
            encoding="utf-8"
        )
    )
    captured = capsys.readouterr()

    assert result == 0
    assert db.closed
    assert payload["passed"] is True
    assert "url" not in payload
    assert "Compliance: PASSED" in captured.out


def test_compliance_command_failure(
    monkeypatch,
    capsys,
):
    db = StubComplianceDriver()
    report = ComplianceReport(
        collection="vecport_compliance_test",
        checks=(
            ComplianceCheck(
                name="search",
                status="fail",
                detail="search failed",
            ),
        ),
    )

    monkeypatch.setattr(
        "vecport.cli.connect_url",
        lambda *args, **kwargs: db,
    )
    monkeypatch.setattr(
        "vecport.cli.run_compliance",
        lambda *args, **kwargs: report,
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "vecport",
            "compliance",
            "--url",
            "vecport://qdrant",
        ],
    )

    result = main()
    captured = capsys.readouterr()

    assert result == 1
    assert db.closed
    assert "Compliance: FAILED" in captured.out


def test_compliance_command_rejects_small_dimension(
    monkeypatch,
    capsys,
):
    def unexpected_connection(*args, **kwargs):
        raise AssertionError(
            "connect_url() should not be called"
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
            "compliance",
            "--url",
            "vecport://qdrant",
            "--dimension",
            "1",
        ],
    )

    result = main()
    captured = capsys.readouterr()

    assert result == 1
    assert "must be at least 2" in captured.out


def _write_project_run_config(tmp_path):
    path = tmp_path / "migration-intake.yml"
    path.write_text(
        """
project:
  name: customer-demo
source:
  driver: qdrant
  connection: vecport://qdrant
  collection: documents
target:
  driver: milvus
  connection: vecport://milvus
  collection: documents_migrated
data:
  estimated_records: 2
  dimension: 3
""",
        encoding="utf-8",
    )
    return path


def _project_run_result(tmp_path, *, status="COMPLETED"):
    return SimpleNamespace(
        status=status,
        recommendation=(
            "NOT_READY"
            if status == "VERIFICATION_FAILED"
            else "READY"
        ),
        root=tmp_path / "runs" / "customer-demo" / "test",
        stages=(
            SimpleNamespace(
                name="assessment",
                status="READY",
            ),
            SimpleNamespace(
                name="plan",
                status="READY",
            ),
        ),
    )


def test_project_run_help(monkeypatch, capsys):
    monkeypatch.setattr(
        sys,
        "argv",
        ["vecport", "project", "run", "--help"],
    )

    with pytest.raises(SystemExit) as exit_info:
        main()

    output = capsys.readouterr().out
    assert exit_info.value.code == 0
    assert "--source-code" in output
    assert "--queries" in output
    assert "--output-dir" in output
    assert "--execute" in output


def test_project_run_requires_source_code(
    tmp_path,
    monkeypatch,
    capsys,
):
    config = _write_project_run_config(tmp_path)
    monkeypatch.setattr(
        "vecport.cli.run_migration_project",
        lambda *args, **kwargs: pytest.fail(
            "runner must not be called"
        ),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "vecport",
            "project",
            "run",
            "--config",
            str(config),
            "--queries",
            "queries.jsonl",
            "--execute",
        ],
    )

    assert main() == 1
    assert "--source-code is required" in capsys.readouterr().out


def test_project_run_requires_queries(
    tmp_path,
    monkeypatch,
    capsys,
):
    config = _write_project_run_config(tmp_path)
    monkeypatch.setattr(
        "vecport.cli.run_migration_project",
        lambda *args, **kwargs: pytest.fail(
            "runner must not be called"
        ),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "vecport",
            "project",
            "run",
            "--config",
            str(config),
            "--source-code",
            "search.py",
            "--execute",
        ],
    )

    assert main() == 1
    assert "--queries is required" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("status", "expected_exit"),
    [("COMPLETED", 0), ("VERIFICATION_FAILED", 1)],
)
def test_project_run_exit_status(
    tmp_path,
    monkeypatch,
    capsys,
    status,
    expected_exit,
):
    config = _write_project_run_config(tmp_path)
    source_code = tmp_path / "search.py"
    queries = tmp_path / "queries.jsonl"
    source_code.write_text("pass\n", encoding="utf-8")
    queries.write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(
        "vecport.cli.run_migration_project",
        lambda *args, **kwargs: _project_run_result(
            tmp_path,
            status=status,
        ),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "vecport",
            "project",
            "run",
            "--config",
            str(config),
            "--source-code",
            str(source_code),
            "--queries",
            str(queries),
            "--execute",
        ],
    )

    assert main() == expected_exit
    output = capsys.readouterr().out
    assert "VecPort Small Migration PoC" in output
    assert "Recommendation:" in output
