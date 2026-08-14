import os
import re
from pathlib import Path
from typing import Any

import yaml


_ENV_PATTERN = re.compile(
    r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}"
)


class ConfigError(ValueError):
    """Raised when a VecPort configuration is invalid."""


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


def _validate_benchmark_config(
    benchmark: Any,
) -> None:

    if not isinstance(
        benchmark,
        dict,
    ):
        raise ConfigError(
            "'benchmark' must be a mapping"
        )

    targets = benchmark.get(
        "targets"
    )

    if targets is not None:

        if not isinstance(
            targets,
            list,
        ):
            raise ConfigError(
                "'benchmark.targets' must be a list"
            )

        if len(targets) < 2:
            raise ConfigError(
                "'benchmark.targets' must contain "
                "at least two targets"
            )

        for index, target in enumerate(
            targets
        ):

            if not isinstance(
                target,
                dict,
            ):
                raise ConfigError(
                    "Each benchmark target "
                    "must be a mapping"
                )

            label = target.get(
                "label"
            )

            url = target.get(
                "url"
            )

            if (
                not isinstance(
                    label,
                    str,
                )
                or not label
            ):
                raise ConfigError(
                    "benchmark.targets"
                    f"[{index}].label "
                    "must be a non-empty string"
                )

            if (
                not isinstance(
                    url,
                    str,
                )
                or not url
            ):
                raise ConfigError(
                    "benchmark.targets"
                    f"[{index}].url "
                    "must be a non-empty string"
                )

    collection = benchmark.get(
        "collection"
    )

    if collection is not None:

        if (
            not isinstance(
                collection,
                str,
            )
            or not collection
        ):
            raise ConfigError(
                "'benchmark.collection' "
                "must be a non-empty string"
            )

    dimension = benchmark.get(
        "dimension"
    )

    if dimension is not None:

        if (
            not isinstance(
                dimension,
                int,
            )
            or isinstance(
                dimension,
                bool,
            )
            or dimension <= 0
        ):
            raise ConfigError(
                "'benchmark.dimension' "
                "must be a positive integer"
            )

    top_k = benchmark.get(
        "top_k"
    )

    if top_k is not None:

        if (
            not isinstance(
                top_k,
                int,
            )
            or isinstance(
                top_k,
                bool,
            )
            or top_k <= 0
        ):
            raise ConfigError(
                "'benchmark.top_k' "
                "must be a positive integer"
            )

    iterations = benchmark.get(
        "iterations"
    )

    if iterations is not None:

        if (
            not isinstance(
                iterations,
                int,
            )
            or isinstance(
                iterations,
                bool,
            )
            or iterations <= 0
        ):
            raise ConfigError(
                "'benchmark.iterations' "
                "must be a positive integer"
            )

    warmup = benchmark.get(
        "warmup"
    )

    if warmup is not None:

        if (
            not isinstance(
                warmup,
                int,
            )
            or isinstance(
                warmup,
                bool,
            )
            or warmup < 0
        ):
            raise ConfigError(
                "'benchmark.warmup' "
                "must be a non-negative integer"
            )

    output_format = benchmark.get(
        "format"
    )

    if (
        output_format is not None
        and output_format not in {
            "json",
            "csv",
        }
    ):
        raise ConfigError(
            "'benchmark.format' "
            "must be 'json' or 'csv'"
        )

    output = benchmark.get(
        "output"
    )

    if output is not None:

        if (
            not isinstance(
                output,
                str,
            )
            or not output
        ):
            raise ConfigError(
                "'benchmark.output' "
                "must be a non-empty string"
            )


def validate_config(
    config: dict[str, Any],
) -> None:

    benchmark = config.get(
        "benchmark"
    )

    if benchmark is not None:
        _validate_benchmark_config(
            benchmark
        )


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

    if not isinstance(
        data,
        dict,
    ):
        raise ValueError(
            "Config root must be a YAML mapping"
        )

    expanded = _expand_env_vars(
        data
    )

    validate_config(
        expanded
    )

    return expanded