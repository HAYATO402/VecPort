"""Public SDK for third-party VecPort driver authors."""

from vecport.core.compliance import (
    ComplianceCheck,
    ComplianceReport,
    run_compliance,
)
from vecport.core.interface import VectorDatabase
from vecport.core.models import (
    Capabilities,
    SearchResult,
    VectorRecord,
)
from vecport.core.plugins import (
    DRIVER_ENTRY_POINT_GROUP,
    DriverPluginInfo,
    discover_driver_plugins,
)

__all__ = [
    "DRIVER_ENTRY_POINT_GROUP",
    "Capabilities",
    "ComplianceCheck",
    "ComplianceReport",
    "DriverPluginInfo",
    "SearchResult",
    "VectorDatabase",
    "VectorRecord",
    "discover_driver_plugins",
    "run_compliance",
]
