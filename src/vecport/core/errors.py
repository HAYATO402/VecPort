class VecPortError(Exception):
    """Base exception for VecPort."""


class InvalidFilterError(VecPortError):
    """Raised when a VecPort filter is invalid."""


class UnsupportedFeatureError(VecPortError):
    """Raised when a driver does not support a feature."""


class DriverNotFoundError(VecPortError):
    """Raised when an unknown driver is requested."""

class InvalidConnectionURLError(VecPortError):
    """Raised when a VecPort connection URL is invalid."""

class MigrationError(VecPortError):
    """Raised when a VecPort migration fails."""


class DriverPluginError(VecPortError):
    """Base exception for driver plugin failures."""


class DriverPluginLoadError(DriverPluginError):
    """Raised when a driver plugin cannot be loaded."""


class DriverPluginConflictError(
    DriverPluginError
):
    """Raised when plugins use the same driver name."""
