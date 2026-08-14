import pytest

from vecport.core.config import (
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