from collections.abc import Callable
from typing import Any

from vecport.core.errors import DriverNotFoundError

DriverFactory = Callable[..., Any]


_DRIVERS: dict[str, DriverFactory] = {}


def _normalize_driver_name(
    driver_name: str,
) -> str:

    if (
        not isinstance(driver_name, str)
        or not driver_name.strip()
    ):
        raise DriverNotFoundError(
            "Driver name must be a non-empty string"
        )

    return driver_name.strip().lower()


def register_driver(
    driver_name: str,
    factory: DriverFactory,
    *,
    replace: bool = False,
) -> None:

    normalized = _normalize_driver_name(
        driver_name
    )

    if (
        normalized in _DRIVERS
        and not replace
    ):
        raise ValueError(
            f"Driver '{normalized}' is already registered"
        )

    _DRIVERS[normalized] = factory


def get_driver_factory(
    driver_name: str,
) -> DriverFactory:

    normalized = _normalize_driver_name(
        driver_name
    )

    try:
        return _DRIVERS[normalized]

    except KeyError as exc:
        raise DriverNotFoundError(
            f"Unsupported VecPort driver: {normalized}"
        ) from exc


def create_driver(
    driver_name: str,
    **kwargs,
):

    factory = get_driver_factory(
        driver_name
    )

    return factory(**kwargs)

def list_drivers() -> tuple[str, ...]:

    return tuple(
        sorted(_DRIVERS.keys())
    )
