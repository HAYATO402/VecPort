from pymilvus import (
    DataType,
    MilvusClient,
)

from vecport.core.interface import VectorDatabase
from vecport.core.models import (
    Capabilities,
    SearchResult,
    VectorRecord,
)


class MilvusDriver(VectorDatabase):

    def __init__(
        self,
        uri: str = "http://localhost:19530",
):
        self.client = MilvusClient(
            uri=uri
    )

    def create_collection(
        self,
        name: str,
        dimension: int,
) -> None:

        if self.client.has_collection(name):
            return

        schema = MilvusClient.create_schema(
            auto_id=False,
            enable_dynamic_field=True,
        )

        schema.add_field(
            field_name="id",
            datatype=DataType.VARCHAR,
            is_primary=True,
            max_length=512,
        )

        schema.add_field(
            field_name="vector",
            datatype=DataType.FLOAT_VECTOR,
            dim=dimension,
        )

        index_params = self.client.prepare_index_params()

        index_params.add_index(
            field_name="vector",
            index_type="AUTOINDEX",
            metric_type="COSINE",
        )

        self.client.create_collection(
            collection_name=name,
            schema=schema,
            index_params=index_params,
            consistency_level="Strong",
        )


    def delete_collection(
        self,
        name: str,
    ) -> None:

        if self.client.has_collection(name):
            self.client.drop_collection(name)

    def upsert(
        self,
        collection: str,
        records: list[VectorRecord],
    ) -> None:

        data = []

        for record in records:
            data.append(
                {
                    "id": record.id,
                    "vector": record.vector,
                    **record.metadata,
                }
            )

        self.client.upsert(
            collection_name=collection,
            data=data,
        )

    def get(
        self,
        collection: str,
        ids: list[str],
    ) -> list[VectorRecord]:

        results = self.client.get(
            collection_name=collection,
            ids=ids,
            output_fields=["*"],
        )

        records = []

        for item in results:

            metadata = {
                key: value
                for key, value in item.items()
                if key not in ("id", "vector")
            }

            records.append(
                VectorRecord(
                    id=str(item["id"]),
                    vector=list(
                        item.get("vector", [])
                    ),
                    metadata=metadata,
                )
            )

        return records

    def delete(
        self,
        collection: str,
        ids: list[str],
    ) -> None:

        self.client.delete(
            collection_name=collection,
            ids=ids,
        )

    def search(
        self,
        collection: str,
        vector: list[float],
        top_k: int = 10,
    ) -> list[SearchResult]:

        response = self.client.search(
            collection_name=collection,
            data=[vector],
            limit=top_k,
            output_fields=["*"],
        )

        results = []

        for item in response[0]:

            entity = item.get(
                "entity",
                {},
            )

            metadata = {
                key: value
                for key, value in entity.items()
                if key not in ("id", "vector")
            }

            results.append(
                SearchResult(
                    id=str(item["id"]),
                    score=float(
                        item["distance"]
                    ),
                    metadata=metadata,
                )
            )

        return results

    def capabilities(
        self,
    ) -> Capabilities:

        return Capabilities(
            dense_vector=True,
            metadata_filter=True,
            sparse_vector=True,
            hybrid_search=True,
            namespaces=False,
            named_vectors=False,
        )