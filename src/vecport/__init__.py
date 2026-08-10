from vecport.core.models import (
    Capabilities,
    SearchResult,
    VectorRecord,
)
from vecport.drivers.pinecone import PineconeDriver
from vecport.drivers.qdrant import QdrantDriver

from vecport.drivers.weaviate import WeaviateDriver

from vecport.drivers.milvus import MilvusDriver

from vecport.drivers.pgvector import PgVectorDriver

from vecport.core.errors import DriverNotFoundError


def connect(
    driver: str,
    **kwargs,
):
    if driver == "qdrant":
        return QdrantDriver(**kwargs)

    if driver == "pinecone":
        return PineconeDriver(**kwargs)

    if driver == "weaviate":
        return WeaviateDriver(**kwargs)

    if driver == "milvus":
        return MilvusDriver(**kwargs)

    if driver == "pgvector":
        return PgVectorDriver(**kwargs)

    
    from vecport.core.errors import (
        DriverNotFoundError,
    )

    raise DriverNotFoundError(
        f"Unsupported VecPort driver: {driver}"
    )

__all__ = [
    "connect",
    "VectorRecord",
    "SearchResult",
    "Capabilities",
]