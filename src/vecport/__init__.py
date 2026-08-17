from vecport.core.connection import parse_connection_url
from vecport.core.errors import DriverNotFoundError
from vecport.core.models import (
    Capabilities,
    SearchResult,
    VectorRecord,
)
from vecport.core.registry import (
    create_driver,
    list_drivers,
    register_driver,
)
from vecport.drivers.milvus import MilvusDriver
from vecport.drivers.pgvector import PgVectorDriver
from vecport.drivers.pinecone import PineconeDriver
from vecport.drivers.qdrant import QdrantDriver
from vecport.drivers.weaviate import WeaviateDriver

register_driver(
    "qdrant",
    QdrantDriver,
    replace=True,
)

register_driver(
    "pinecone",
    PineconeDriver,
    replace=True,
)

register_driver(
    "weaviate",
    WeaviateDriver,
    replace=True,
)

register_driver(
    "milvus",
    MilvusDriver,
    replace=True,
)

register_driver(
    "pgvector",
    PgVectorDriver,
    replace=True,
)


def connect(
    driver: str,
    **kwargs,
):

    return create_driver(
        driver,
        **kwargs,
    )

__all__ = [
    "Capabilities",
    "DriverNotFoundError",
    "SearchResult",
    "VectorRecord",
    "connect",
    "connect_url",
    "list_drivers",
]

def connect_url(
    url: str,
    **overrides,
):

    config = parse_connection_url(url)

    options = {
        **config.options,
        **overrides,
    }

    return connect(
        config.driver,
        **options,
    )
