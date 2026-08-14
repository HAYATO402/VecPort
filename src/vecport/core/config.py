from pathlib import Path
from typing import Any

import yaml


def load_config(
    path: str,
) -> dict[str, Any]:

    config_path = Path(path)

    if not config_path.exists():
        raise FileNotFoundError(
            f"Config file not found: {path}"
        )

    with config_path.open(
        "r",
        encoding="utf-8",
    ) as file:
        data = yaml.safe_load(file)

    if data is None:
        return {}

    if not isinstance(data, dict):
        raise ValueError(
            "Config root must be a YAML mapping"
        )

    return data