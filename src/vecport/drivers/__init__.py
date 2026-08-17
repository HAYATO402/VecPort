from vecport.core.models import (
    Capabilities,
    SearchResult,
    VectorRecord,
)
from vecport.drivers.pinecone import PineconeDriver
from vecport.drivers.qdrant import QdrantDriver


def connect(
    driver: str,
    **kwargs,
):
    if driver == "qdrant":
        return QdrantDriver(**kwargs)

    if driver == "pinecone":
        return PineconeDriver(**kwargs)

    raise ValueError(
        f"Unsupported VecPort driver: {driver}"
    )


__all__ = [
    "Capabilities",
    "SearchResult",
    "VectorRecord",
    "connect",
]