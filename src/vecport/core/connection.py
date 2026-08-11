from dataclasses import dataclass
from urllib.parse import parse_qsl, urlparse

from vecport.core.errors import InvalidConnectionURLError


@dataclass(frozen=True)
class ConnectionConfig:
    driver: str
    options: dict[str, str]


SENSITIVE_OPTIONS = {
    "api_key",
    "password",
    "token",
    "secret",
}


def parse_connection_url(
    url: str,
) -> ConnectionConfig:

    if not isinstance(url, str) or not url.strip():
        raise InvalidConnectionURLError(
            "Connection URL must be a non-empty string"
        )

    parsed = urlparse(url)

    if parsed.scheme != "vecport":
        raise InvalidConnectionURLError(
            "Connection URL must use the vecport:// scheme"
        )

    driver = parsed.netloc.strip().lower()

    if not driver:
        raise InvalidConnectionURLError(
            "Connection URL must include a driver"
        )

    options: dict[str, str] = {}

    for key, value in parse_qsl(
        parsed.query,
        keep_blank_values=True,
    ):

        if key in SENSITIVE_OPTIONS:
            raise InvalidConnectionURLError(
                f"Sensitive option '{key}' must not be placed "
                "inside a connection URL"
            )

        if key in options:
            raise InvalidConnectionURLError(
                f"Duplicate connection option: {key}"
            )

        options[key] = value

    return ConnectionConfig(
        driver=driver,
        options=options,
    )