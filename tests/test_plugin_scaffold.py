import sys

import pytest

from vecport.cli import main
from vecport.core.plugin_scaffold import (
    create_driver_project,
)


def test_create_driver_project(
    tmp_path,
):
    result = create_driver_project(
        "example-cloud",
        output_dir=tmp_path,
    )
    root = (
        tmp_path
        / "vecport-example-cloud"
    )

    assert result.root == root
    assert len(result.files) == 4
    assert (
        root / "pyproject.toml"
    ).exists()
    assert (
        root
        / "src"
        / "vecport_example_cloud"
        / "__init__.py"
    ).exists()
    assert (
        root
        / "tests"
        / "test_driver.py"
    ).exists()
    pyproject = (
        root / "pyproject.toml"
    ).read_text(
        encoding="utf-8"
    )

    assert (
        '[project.entry-points."vecport.drivers"]'
        in pyproject
    )
    assert (
        'example-cloud = '
        '"vecport_example_cloud:'
        'ExampleCloudDriver"'
        in pyproject
    )
    assert (
        '"vecport>=0.7.0,<1.0"'
        in pyproject
    )


def test_generated_driver_uses_public_sdk(
    tmp_path,
):
    result = create_driver_project(
        "example",
        output_dir=tmp_path,
    )
    driver = (
        result.root
        / "src"
        / "vecport_example"
        / "__init__.py"
    ).read_text(
        encoding="utf-8"
    )

    assert (
        "from vecport.driver_sdk import ("
        in driver
    )
    assert (
        "class ExampleDriver(VectorDatabase):"
        in driver
    )


@pytest.mark.parametrize(
    "driver_name",
    [
        "../bad-driver",
        "BadDriver",
        "bad_driver",
        "-bad-driver",
        "bad-driver-",
        "bad--driver",
    ],
)
def test_invalid_driver_name(
    tmp_path,
    driver_name,
):
    with pytest.raises(ValueError):
        create_driver_project(
            driver_name,
            output_dir=tmp_path,
        )


def test_invalid_class_name(
    tmp_path,
):
    with pytest.raises(ValueError):
        create_driver_project(
            "example",
            output_dir=tmp_path,
            class_name="not-valid",
        )


def test_invalid_distribution_name(
    tmp_path,
):
    with pytest.raises(ValueError):
        create_driver_project(
            "example",
            output_dir=tmp_path,
            distribution_name="../outside",
        )

    with pytest.raises(ValueError):
        create_driver_project(
            "example",
            output_dir=tmp_path,
            distribution_name="class",
        )


def test_existing_directory_is_protected(
    tmp_path,
):
    root = (
        tmp_path
        / "vecport-example"
    )
    root.mkdir()
    existing = root / "existing.txt"
    existing.write_text(
        "do not overwrite",
        encoding="utf-8",
    )

    with pytest.raises(FileExistsError):
        create_driver_project(
            "example",
            output_dir=tmp_path,
        )

    assert existing.read_text(
        encoding="utf-8"
    ) == "do not overwrite"


def test_force_replaces_generated_files_only(
    tmp_path,
):
    first = create_driver_project(
        "example",
        output_dir=tmp_path,
    )
    custom = first.root / "custom.txt"
    custom.write_text(
        "keep me",
        encoding="utf-8",
    )
    pyproject = (
        first.root / "pyproject.toml"
    )
    pyproject.write_text(
        "replace me",
        encoding="utf-8",
    )

    create_driver_project(
        "example",
        output_dir=tmp_path,
        force=True,
    )

    assert "[project]" in pyproject.read_text(
        encoding="utf-8"
    )
    assert custom.read_text(
        encoding="utf-8"
    ) == "keep me"


def test_plugin_init_command(
    tmp_path,
    monkeypatch,
    capsys,
):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "vecport",
            "plugin",
            "init",
            "example",
            "--output",
            str(tmp_path),
        ],
    )

    result = main()
    captured = capsys.readouterr()

    assert result == 0
    assert "project created" in captured.out
    assert (
        tmp_path
        / "vecport-example"
        / "pyproject.toml"
    ).exists()


def test_plugin_init_command_reports_error(
    tmp_path,
    monkeypatch,
    capsys,
):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "vecport",
            "plugin",
            "init",
            "../bad",
            "--output",
            str(tmp_path),
        ],
    )

    result = main()
    captured = capsys.readouterr()

    assert result == 1
    assert (
        "Plugin scaffold error"
        in captured.out
    )


def test_plugin_list_command(
    monkeypatch,
    capsys,
):
    class Plugin:
        name = "example"
        value = "example_driver:Driver"

    monkeypatch.setattr(
        "vecport.cli.discover_driver_plugins",
        lambda: (Plugin(),),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "vecport",
            "plugin",
            "list",
        ],
    )

    result = main()
    captured = capsys.readouterr()

    assert result == 0
    assert "VecPort driver plugins" in captured.out
    assert "example_driver:Driver" in captured.out


def test_plugin_list_command_without_plugins(
    monkeypatch,
    capsys,
):
    monkeypatch.setattr(
        "vecport.cli.discover_driver_plugins",
        lambda: (),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "vecport",
            "plugin",
            "list",
        ],
    )

    result = main()
    captured = capsys.readouterr()

    assert result == 0
    assert (
        "No third-party VecPort driver plugins"
        in captured.out
    )
