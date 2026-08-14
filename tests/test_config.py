import pytest

from vecport.core.config import (
    ConfigError,
    load_config,
)


def test_load_config(tmp_path):

    path = tmp_path / "vecport.yml"

    path.write_text(
        """
benchmark:
  collection: documents
  dimension: 128
""",
        encoding="utf-8",
    )

    config = load_config(
        str(path)
    )

    assert (
        config["benchmark"]["collection"]
        == "documents"
    )

    assert (
        config["benchmark"]["dimension"]
        == 128
    )


def test_load_empty_config(tmp_path):

    path = tmp_path / "vecport.yml"

    path.write_text(
        "",
        encoding="utf-8",
    )

    config = load_config(
        str(path)
    )

    assert config == {}


def test_invalid_config_root(tmp_path):

    path = tmp_path / "vecport.yml"

    path.write_text(
        "- item1\n- item2\n",
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError
    ):
        load_config(
            str(path)
        )


def test_missing_config():

    with pytest.raises(
        FileNotFoundError
    ):
        load_config(
            "does-not-exist.yml"
        )

def test_expand_environment_variable(
    tmp_path,
    monkeypatch,
):

    monkeypatch.setenv(
        "VECPORT_TEST_SECRET",
        "secret-value",
    )

    path = tmp_path / "vecport.yml"

    path.write_text(
        """
service:
  api_key: "${VECPORT_TEST_SECRET}"
""",
        encoding="utf-8",
    )

    config = load_config(
        str(path)
    )

    assert (
        config["service"]["api_key"]
        == "secret-value"
    )

def test_expand_environment_variable_in_string(
    tmp_path,
    monkeypatch,
):

    monkeypatch.setenv(
        "VECPORT_TEST_SECRET",
        "abc123",
    )

    path = tmp_path / "vecport.yml"

    path.write_text(
        """
service:
  url: "https://example.com?key=${VECPORT_TEST_SECRET}"
""",
        encoding="utf-8",
    )

    config = load_config(
        str(path)
    )

    assert (
        config["service"]["url"]
        == "https://example.com?key=abc123"
    )

def test_missing_environment_variable(
    tmp_path,
    monkeypatch,
):

    monkeypatch.delenv(
        "VECPORT_MISSING_SECRET",
        raising=False,
    )

    path = tmp_path / "vecport.yml"

    path.write_text(
        """
service:
  api_key: "${VECPORT_MISSING_SECRET}"
""",
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="VECPORT_MISSING_SECRET",
    ):
        load_config(
            str(path)
        )

def test_invalid_dimension(
    tmp_path,
):

    path = tmp_path / "vecport.yml"

    path.write_text(
        """
benchmark:
  dimension: -1
""",
        encoding="utf-8",
    )

    with pytest.raises(
        ConfigError,
        match="dimension",
    ):
        load_config(
            str(path)
        )

def test_invalid_top_k(
    tmp_path,
):

    path = tmp_path / "vecport.yml"

    path.write_text(
        """
benchmark:
  top_k: 0
""",
        encoding="utf-8",
    )

    with pytest.raises(
        ConfigError,
        match="top_k",
    ):
        load_config(
            str(path)
        )

def test_invalid_format(
    tmp_path,
):

    path = tmp_path / "vecport.yml"

    path.write_text(
        """
benchmark:
  format: xml
""",
        encoding="utf-8",
    )

    with pytest.raises(
        ConfigError,
        match="format",
    ):
        load_config(
            str(path)
        )
        
def test_invalid_target(
    tmp_path,
):

    path = tmp_path / "vecport.yml"

    path.write_text(
        """
benchmark:
  targets:
    - label: qdrant
""",
        encoding="utf-8",
    )

    with pytest.raises(
        ConfigError,
        match="targets",
    ):
        load_config(
            str(path)
        )