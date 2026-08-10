class VecPortError(Exception):
    """Base exception for VecPort."""


class InvalidFilterError(VecPortError):
    """Raised when a VecPort filter is invalid."""


class UnsupportedFeatureError(VecPortError):
    """Raised when a driver does not support a feature."""


class DriverNotFoundError(VecPortError):
    """Raised when an unknown driver is requested."""