import time

from pinecone import Pinecone, ServerlessSpec

from vecport.core.interface import VectorDatabase
from vecport.core.models import (
    Capabilities,
    SearchResult,
    VectorRecord,
)


class PineconeDriver(VectorDatabase):

    def __init__(
        self,
        api_key: str,
        cloud: str = "aws",
        region: str = "us-east-1",
    ):
        self.client = Pinecone(
            api_key=api_key
        )

        self.cloud = cloud
        self.region = region

    def create_collection(
        self,
        name: str,
        dimension: int,
    ) -> None:

        if not self.client.has_index(name):

            self.client.create_index(
                name=name,
                dimension=dimension,
                metric="cosine",
                spec=ServerlessSpec(
                    cloud=self.cloud,
                    region=self.region,
                ),
            )

            while not self.client.describe_index(
                name
            ).status["ready"]:
                time.sleep(1)

    def delete_collection(
        self,
        name: str,
    ) -> None:

        if self.client.has_index(name):
            self.client.delete_index(name)

    def upsert(
        self,
        collection: str,
        records: list[VectorRecord],
    ) -> None:

        index = self.client.Index(collection)

        vectors = [
            {
                "id": record.id,
                "values": record.vector,
                "metadata": record.metadata,
            }
            for record in records
        ]

        index.upsert(
            vectors=vectors
        )

    def get(
        self,
        collection: str,
        ids: list[str],
    ) -> list[VectorRecord]:

        index = self.client.Index(collection)

        response = index.fetch(
            ids=ids
        )

        return [
            VectorRecord(
                id=str(record_id),
                vector=list(record.values),
                metadata=record.metadata or {},
            )
            for record_id, record
            in response.vectors.items()
        ]

    def delete(
        self,
        collection: str,
        ids: list[str],
    ) -> None:

        index = self.client.Index(collection)

        index.delete(
            ids=ids
        )

    def search(
        self,
        collection: str,
        vector: list[float],
        top_k: int = 10,
    ) -> list[SearchResult]:

        index = self.client.Index(collection)

        response = index.query(
            vector=vector,
            top_k=top_k,
            include_metadata=True,
        )

        return [
            SearchResult(
                id=str(match.id),
                score=float(match.score),
                metadata=match.metadata or {},
            )
            for match in response.matches
        ]

    def capabilities(
        self,
    ) -> Capabilities:

        return Capabilities(
            dense_vector=True,
            metadata_filter=True,
            sparse_vector=True,
            hybrid_search=True,
            namespaces=True,
            named_vectors=False,
        )