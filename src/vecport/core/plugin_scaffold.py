from __future__ import annotations

import keyword
import re
from dataclasses import dataclass
from pathlib import Path

_DRIVER_NAME_PATTERN = re.compile(
    r"^[a-z](?:[a-z0-9]|-(?=[a-z0-9]))*$"
)
_CLASS_NAME_PATTERN = re.compile(
    r"^[A-Z][A-Za-z0-9]*$"
)


@dataclass(frozen=True)
class DriverScaffoldResult:
    root: Path
    files: tuple[Path, ...]


def _validate_driver_name(
    name: str,
) -> None:
    if not _DRIVER_NAME_PATTERN.fullmatch(
        name
    ):
        raise ValueError(
            "Driver name must start with "
            "a lowercase letter and contain "
            "only lowercase letters, digits, "
            "or hyphens."
        )


def _validate_class_name(
    name: str,
) -> None:
    if not _CLASS_NAME_PATTERN.fullmatch(
        name
    ):
        raise ValueError(
            "Driver class name must be a "
            "valid PascalCase Python class name."
        )


def _default_class_name(
    driver_name: str,
) -> str:
    parts = driver_name.split("-")

    return (
        "".join(
            part.capitalize()
            for part in parts
        )
        + "Driver"
    )


def _default_distribution_name(
    driver_name: str,
) -> str:
    return f"vecport-{driver_name}"


def _module_name(
    distribution_name: str,
) -> str:
    module = distribution_name.replace(
        "-",
        "_",
    )

    if (
        not module.isidentifier()
        or keyword.iskeyword(module)
    ):
        raise ValueError(
            "Distribution name cannot be "
            "converted into a valid Python "
            "module name."
        )

    return module


def _render_pyproject(
    *,
    driver_name: str,
    distribution_name: str,
    module_name: str,
    class_name: str,
) -> str:
    return f'''[build-system]
requires = ["setuptools>=77.0.3"]
build-backend = "setuptools.build_meta"

[project]
name = "{distribution_name}"
version = "0.1.0"
description = "Third-party VecPort driver for {driver_name}."
readme = "README.md"
requires-python = ">=3.10"
dependencies = [
    "vecport>=0.7.0,<1.0",
]

[project.entry-points."vecport.drivers"]
{driver_name} = "{module_name}:{class_name}"

[tool.setuptools.packages.find]
where = ["src"]
'''


def _render_driver(
    *,
    class_name: str,
) -> str:
    return f'''from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from vecport.driver_sdk import (
    Capabilities,
    SearchResult,
    VectorDatabase,
    VectorRecord,
)


class {class_name}(VectorDatabase):
    """VecPort third-party driver."""

    def __init__(
        self,
        **kwargs: Any,
    ) -> None:
        self.options = kwargs

    def create_collection(
        self,
        name: str,
        dimension: int,
    ) -> None:
        raise NotImplementedError

    def delete_collection(
        self,
        name: str,
    ) -> None:
        raise NotImplementedError

    def upsert(
        self,
        collection: str,
        records: list[VectorRecord],
    ) -> None:
        raise NotImplementedError

    def get(
        self,
        collection: str,
        ids: list[str],
    ) -> list[VectorRecord]:
        raise NotImplementedError

    def delete(
        self,
        collection: str,
        ids: list[str],
    ) -> None:
        raise NotImplementedError

    def search(
        self,
        collection: str,
        vector: list[float],
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        raise NotImplementedError

    def scan(
        self,
        collection: str,
        *,
        batch_size: int = 100,
    ) -> Iterator[VectorRecord]:
        raise NotImplementedError

    def capabilities(
        self,
    ) -> Capabilities:
        return Capabilities(
            dense_vector=True,
        )
'''


def _render_test(
    *,
    module_name: str,
    class_name: str,
) -> str:
    return f'''from {module_name} import (
    {class_name},
)


def test_driver_can_be_created():
    driver = {class_name}()

    assert driver is not None
'''


def _render_readme(
    *,
    driver_name: str,
    distribution_name: str,
    class_name: str,
) -> str:
    return f'''# {distribution_name}

Third-party `{driver_name}` driver for VecPort.

## Development

Install the package in editable mode:

```bash
pip install -e .
```

Verify that VecPort discovers the driver:

```bash
python -c "from vecport import connect; print(connect('{driver_name}'))"
```

After implementing the VecPort driver contract, run:

```bash
vecport compliance --url "vecport://{driver_name}"
```

The driver entry point is registered under `vecport.drivers` and loads
`{class_name}`.
'''


def _validate_destination(
    *,
    root: Path,
    directories: tuple[Path, ...],
    files: tuple[Path, ...],
    force: bool,
) -> None:
    protected_paths = (
        root,
        *directories,
        *files,
    )

    for path in protected_paths:
        if path.is_symlink():
            raise FileExistsError(
                "Refusing to write through "
                f"a symbolic link: {path}"
            )

    if root.exists() and not root.is_dir():
        raise FileExistsError(
            f"Destination is not a directory: {root}"
        )

    if (
        root.exists()
        and any(root.iterdir())
        and not force
    ):
        raise FileExistsError(
            f"Destination is not empty: {root}"
        )

    for directory in directories:
        if (
            directory.exists()
            and not directory.is_dir()
        ):
            raise FileExistsError(
                "Scaffold directory path is "
                f"not a directory: {directory}"
            )

    for path in files:
        if path.exists() and not path.is_file():
            raise FileExistsError(
                "Scaffold file path is not "
                f"a file: {path}"
            )


def create_driver_project(
    driver_name: str,
    *,
    output_dir: str | Path = ".",
    distribution_name: str | None = None,
    class_name: str | None = None,
    force: bool = False,
) -> DriverScaffoldResult:
    _validate_driver_name(driver_name)
    resolved_distribution = (
        distribution_name
        or _default_distribution_name(
            driver_name
        )
    )
    resolved_class = (
        class_name
        or _default_class_name(
            driver_name
        )
    )
    _validate_class_name(resolved_class)
    module_name = _module_name(
        resolved_distribution
    )
    root = (
        Path(output_dir)
        / resolved_distribution
    )
    source_dir = root / "src"
    package_dir = source_dir / module_name
    tests_dir = root / "tests"
    files = {
        root / "pyproject.toml": (
            _render_pyproject(
                driver_name=driver_name,
                distribution_name=(
                    resolved_distribution
                ),
                module_name=module_name,
                class_name=resolved_class,
            )
        ),
        package_dir / "__init__.py": (
            _render_driver(
                class_name=resolved_class,
            )
        ),
        tests_dir / "test_driver.py": (
            _render_test(
                module_name=module_name,
                class_name=resolved_class,
            )
        ),
        root / "README.md": (
            _render_readme(
                driver_name=driver_name,
                distribution_name=(
                    resolved_distribution
                ),
                class_name=resolved_class,
            )
        ),
    }

    _validate_destination(
        root=root,
        directories=(
            source_dir,
            package_dir,
            tests_dir,
        ),
        files=tuple(files),
        force=force,
    )
    package_dir.mkdir(
        parents=True,
        exist_ok=True,
    )
    tests_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    for path, content in files.items():
        path.write_text(
            content,
            encoding="utf-8",
        )

    return DriverScaffoldResult(
        root=root,
        files=tuple(files),
    )
