import weaviate
from weaviate.classes.init import Auth
from weaviate.classes.config import Configure

from vecport.core.interface import VectorDatabase
from vecport.core.models import (
    Capabilities,
    SearchResult,
    VectorRecord,
)


class WeaviateDriver(VectorDatabase):

    def __init__(
        self,
        url: str,
        api_key: str,
    ):
        self.client = weaviate.connect_to_weaviate_cloud(
            cluster_url=url,
            auth_credentials=Auth.api_key(api_key),
        )

    def create_collection(
        self,
        name: str,
        dimension: int,
    ) -> None:

        if  self.client.collections.exists(name):
                return

        self.client.collections.create(
            name=name,
            vector_config=Configure.Vectors.self_provided(),
        )

    def delete_collection(
        self,
        name: str,
    ) -> None:

        if self.client.collections.exists(name):
            self.client.collections.delete(name)

    def upsert(
        self,
        collection: str,
        records: list[VectorRecord],
    ) -> None:

        col = self.client.collections.get(collection)

        for record in records:
            col.data.insert(
                uuid=record.id,
                properties=record.metadata,
                vector=record.vector,
            )

    def get(
        self,
        collection: str,
        ids: list[str],
    ) -> list[VectorRecord]:

        col = self.client.collections.get(collection)

        output = []

        for record_id in ids:
            obj = col.query.fetch_object_by_id(
                record_id,
                include_vector=True,
            )

            if obj is None:
                continue

            vector = obj.vector

            if isinstance(vector, dict):
                vector = vector.get("default", [])

            output.append(
                VectorRecord(
                    id=str(obj.uuid),
                    vector=list(vector),
                    metadata=obj.properties or {},
                )
            )

        return output

    def delete(
        self,
        collection: str,
        ids: list[str],
    ) -> None:

        col = self.client.collections.get(collection)

        for record_id in ids:
            col.data.delete_by_id(record_id)

    def search(
        self,
        collection: str,
        vector: list[float],
        top_k: int = 10,
    ) -> list[SearchResult]:

        col = self.client.collections.get(collection)

        response = col.query.near_vector(
            near_vector=vector,
            limit=top_k,
        )

        return [
            SearchResult(
                id=str(obj.uuid),
                score=0.0,
                metadata=obj.properties or {},
            )
            for obj in response.objects
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