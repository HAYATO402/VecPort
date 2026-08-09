from vecport.core.models import (
    Capabilities,
    SearchResult,
    VectorRecord,
)
from vecport.drivers.qdrant import QdrantDriver


def connect(
    driver: str,
    **kwargs,
):
    if driver == "qdrant":
        return QdrantDriver(**kwargs)

    raise ValueError(
        f"Unsupported VecPort driver: {driver}"
    )


__all__ = [
    "connect",
    "VectorRecord",
    "SearchResult",
    "Capabilities",
]