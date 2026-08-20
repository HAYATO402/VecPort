from __future__ import annotations

from dataclasses import dataclass
from importlib.metadata import (
    EntryPoint,
    entry_points,
)

from vecport.core.errors import (
    DriverPluginConflictError,
    DriverPluginLoadError,
)

DRIVER_ENTRY_POINT_GROUP = "vecport.drivers"


@dataclass(frozen=True)
class DriverPluginInfo:
    name: str
    value: str


def discover_driver_plugins(
) -> tuple[DriverPluginInfo, ...]:
    discovered = entry_points(
        group=DRIVER_ENTRY_POINT_GROUP
    )
    plugins = [
        DriverPluginInfo(
            name=entry_point.name,
            value=entry_point.value,
        )
        for entry_point in discovered
    ]

    return tuple(
        sorted(
            plugins,
            key=lambda plugin: (
                plugin.name,
                plugin.value,
            ),
        )
    )


def _find_driver_entry_points(
    name: str,
) -> tuple[EntryPoint, ...]:
    discovered = entry_points(
        group=DRIVER_ENTRY_POINT_GROUP,
        name=name,
    )

    return tuple(discovered)


def load_driver_plugin(
    name: str,
) -> bool:
    matches = _find_driver_entry_points(
        name
    )

    if not matches:
        return False

    if len(matches) > 1:
        values = ", ".join(
            sorted(
                entry_point.value
                for entry_point in matches
            )
        )
        raise DriverPluginConflictError(
            "Multiple VecPort driver "
            "plugins are registered as "
            f"'{name}': {values}"
        )

    entry_point = matches[0]

    try:
        driver_factory = entry_point.load()

    except Exception as error:
        raise DriverPluginLoadError(
            "Failed to load VecPort "
            f"driver plugin '{name}' "
            f"from '{entry_point.value}'."
        ) from error

    if not callable(driver_factory):
        raise DriverPluginLoadError(
            "VecPort driver plugin "
            f"'{name}' loaded "
            f"'{entry_point.value}', "
            "but the object is not callable."
        )

    # Import lazily to avoid a plugins/registry
    # initialization cycle.
    from vecport.core.registry import (
        register_driver,
    )

    register_driver(
        name,
        driver_factory,
    )

    return True
