import json
import sys

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
