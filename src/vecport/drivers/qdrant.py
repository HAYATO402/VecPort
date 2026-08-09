from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    PointIdsList,
    PointStruct,
    VectorParams,
)

from vecport.core.interface import VectorDatabase
from vecport.core.models import (
    Capabilities,
    SearchResult,
    VectorRecord,
)


class QdrantDriver(VectorDatabase):

    def __init__(
        self,
        url: str | None = None,
        api_key: str | None = None,
    ):
        if url:
            self.client = QdrantClient(
                url=url,
                api_key=api_key,
            )
        else:
            self.client = QdrantClient(":memory:")

    def create_collection(
        self,
        name: str,
        dimension: int,
    ) -> None:

        self.client.create_collection(
            collection_name=name,
            vectors_config=VectorParams(
                size=dimension,
                distance=Distance.COSINE,
            ),
        )

    def delete_collection(
        self,
        name: str,
    ) -> None:

        self.client.delete_collection(
            collection_name=name
        )

    def upsert(
        self,
        collection: str,
        records: list[VectorRecord],
    ) -> None:

        points = [
            PointStruct(
                id=record.id,
                vector=record.vector,
                payload=record.metadata,
            )
            for record in records
        ]

        self.client.upsert(
            collection_name=collection,
            points=points,
        )

    def get(
        self,
        collection: str,
        ids: list[str],
    ) -> list[VectorRecord]:

        records = self.client.retrieve(
            collection_name=collection,
            ids=ids,
            with_vectors=True,
            with_payload=True,
        )

        return [
            VectorRecord(
                id=str(record.id),
                vector=list(record.vector),
                metadata=record.payload or {},
            )
            for record in records
        ]

    def delete(
        self,
        collection: str,
        ids: list[str],
    ) -> None:

        self.client.delete(
            collection_name=collection,
            points_selector=PointIdsList(
                points=ids,
            ),
        )

    def search(
        self,
        collection: str,
        vector: list[float],
        top_k: int = 10,
    ) -> list[SearchResult]:

        response = self.client.query_points(
            collection_name=collection,
            query=vector,
            limit=top_k,
            with_payload=True,
        )

        return [
            SearchResult(
                id=str(point.id),
                score=float(point.score),
                metadata=point.payload or {},
            )
            for point in response.points
        ]

    def capabilities(
        self,
    ) -> Capabilities:

        return Capabilities(
            dense_vector=True,
            metadata_filter=True,
            sparse_vector=True,
            hybrid_search=True,
            namespaces=False,
            named_vectors=True,
        )