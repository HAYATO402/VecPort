import sys

from vecport.cli import main

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