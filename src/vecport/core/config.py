import os
import re
from pathlib import Path
from typing import Any

import yaml

_ENV_PATTERN = re.compile(
    r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}"
)

def _expand_env_string(
    value: str,
) -> str:

    def replace(
        match: re.Match[str],
    ) -> str:

        name = match.group(1)

        if name not in os.environ:
            raise ValueError(
                "Environment variable "
                f"'{name}' is not set"
            )

        return os.environ[name]

    return _ENV_PATTERN.sub(
        replace,
        value,
    )

def _expand_env_vars(
    value: Any,
) -> Any:

    if isinstance(
        value,
        str,
    ):
        return _expand_env_string(
            value
        )

    if isinstance(
        value,
        list,
    ):
        return [
            _expand_env_vars(item)
            for item in value
        ]

    if isinstance(
        value,
        dict,
    ):
        return {
            key: _expand_env_vars(item)
            for key, item in value.items()
        }

    return value


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

    return _expand_env_vars(
        data
    )