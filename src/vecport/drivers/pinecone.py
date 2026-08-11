import time

from pinecone import Pinecone, ServerlessSpec

from vecport.core.interface import VectorDatabase
from vecport.core.models import (
    Capabilities,
    SearchResult,
    VectorRecord,
)

from vecport.core.filters import validate_filter


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

    def _normalize_index_name(
        self,
        name: str,
    ) -> str:

        return (
            name
            .lower()
            .replace("_", "-")
        )

    def create_collection(
        self,
        name: str,
        dimension: int,
    ) -> None:

        index_name = self._normalize_index_name(
            name
        )

        if not self.client.has_index(
            index_name
        ):

            self.client.create_index(
                name=index_name,
                dimension=dimension,
                metric="cosine",
                spec=ServerlessSpec(
                    cloud=self.cloud,
                    region=self.region,
                ),
            )

            while not self.client.describe_index(
                index_name
            ).status["ready"]:
                time.sleep(1)

    def delete_collection(
        self,
        name: str,
    ) -> None:

        index_name = self._normalize_index_name(
            name
        )

        if self.client.has_index(
            index_name
        ):
            self.client.delete_index(
                index_name
            )

    def upsert(
        self,
        collection: str,
        records: list[VectorRecord],
    ) -> None:

        index_name = self._normalize_index_name(
            collection
        )

        index = self.client.Index(
            index_name
        )

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

        index_name = self._normalize_index_name(
            collection
        )

        index = self.client.Index(
            index_name
        )

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

        index_name = self._normalize_index_name(
            collection
        )

        index = self.client.Index(
            index_name
        )

        index.delete(
            ids=ids
        )

    def search(
        self,
        collection: str,
        vector: list[float],
        top_k: int = 10,
        filters: dict | None = None,
    ) -> list[SearchResult]:

        validate_filter(filters)

        index_name = self._normalize_index_name(
            collection
        )

        index = self.client.Index(
            index_name
        )

        query_args = {
            "vector": vector,
            "top_k": top_k,
            "include_metadata": True,
        }

        if filters:
            query_args["filter"] = filters

        response = index.query(
            **query_args
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
            filter_operators=(
                "$eq",
                "$ne",
                "$gt",
                "$gte",
                "$lt",
                "$lte",
                "$in",
                "$and",
                "$or",
            ),
            sparse_vector=True,
            hybrid_search=True,
            namespaces=False,
            named_vectors=False,
        )

    def scan(
        self,
        collection: str,
        *,
        batch_size: int = 100,
    ):
        if batch_size <= 0:
            raise ValueError(
                "batch_size must be greater than 0"
            )

        fetch_size = min(
            batch_size,
            1000,
        )

        index_name = (
            self._normalize_index_name(
                collection
            )
        )

        index = self.client.Index(
            index_name
        )

        for items in index.list(
            limit=fetch_size
        ):

            record_ids = []

            for item in items:

                if isinstance(item, str):
                    record_ids.append(item)

                else:
                    record_ids.append(
                        item.id
                    )

            if not record_ids:
                continue

            response = index.fetch(
                ids=record_ids
            )

            vectors = response.vectors

            for record_id in record_ids:

                record = vectors.get(
                    record_id
                )

                if record is None:
                    continue

                yield VectorRecord(
                    id=str(record.id),
                    vector=list(
                        record.values
                    ),
                    metadata=dict(
                        record.metadata
                        or {}
                    ),
                )