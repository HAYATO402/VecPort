from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchAny,
    MatchValue,
    PointIdsList,
    PointStruct,
    Range,
    VectorParams,
)

from vecport.core.errors import (
    UnsupportedFeatureError,
)
from vecport.core.filters import validate_filter
from vecport.core.interface import VectorDatabase
from vecport.core.models import (
    Capabilities,
    CollectionInfo,
    SearchResult,
    VectorRecord,
)


class QdrantDriver(VectorDatabase):

    def __init__(
        self,
        url: str | None = None,
        path: str | None = None,
        **kwargs,
    ):

        if url is not None:

            self.client = QdrantClient(
                url=url,
                **kwargs,
            )

        elif path is not None:

            self.client = QdrantClient(
                path=path,
                **kwargs,
            )

        else:

            self.client = QdrantClient(
                ":memory:"
            )

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

    def create_collection_from_info(
        self,
        name: str,
        info: CollectionInfo,
    ) -> None:

        if info.dimension is None:
            raise ValueError(
                "Collection dimension "
                "is required."
            )

        metric = (
            info.distance_metric
            or "cosine"
        )

        distances = {
            "cosine": Distance.COSINE,
            "dot": Distance.DOT,
            "l2": Distance.EUCLID,
        }

        if metric not in distances:
            raise ValueError(
                "Unsupported Qdrant "
                f"distance metric: {metric}"
            )

        self.client.create_collection(
            collection_name=name,
            vectors_config=VectorParams(
                size=info.dimension,
                distance=distances[
                    metric
                ],
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
    
    def _build_filter(
        self,
        filters: dict | None,
    ):

        if not filters:
            return None

        must = []
        must_not = []

        for key, condition in filters.items():

            if key == "$and":

                nested_filters = [
                    self._build_filter(item)
                    for item in condition
                ]

                return Filter(
                    must=nested_filters
                )

            if key == "$or":

                nested_filters = [
                    self._build_filter(item)
                    for item in condition
                ]

                return Filter(
                    should=nested_filters
                )

            for operator, value in condition.items():

                if operator == "$eq":

                    must.append(
                        FieldCondition(
                            key=key,
                            match=MatchValue(
                                value=value
                            ),
                        )
                    )

                elif operator == "$ne":

                    must_not.append(
                        FieldCondition(
                            key=key,
                            match=MatchValue(
                                value=value
                            ),
                        )
                    )

                elif operator == "$gt":

                    must.append(
                        FieldCondition(
                            key=key,
                            range=Range(
                                gt=value
                            ),
                        )
                    )

                elif operator == "$gte":

                    must.append(
                        FieldCondition(
                            key=key,
                            range=Range(
                                gte=value
                            ),
                        )
                    )

                elif operator == "$lt":

                    must.append(
                        FieldCondition(
                            key=key,
                            range=Range(
                                lt=value
                            ),
                        )
                    )

                elif operator == "$lte":

                    must.append(
                        FieldCondition(
                            key=key,
                            range=Range(
                                lte=value
                            ),
                        )
                    )

                elif operator == "$in":

                    must.append(
                        FieldCondition(
                            key=key,
                            match=MatchAny(
                                any=value
                            ),
                        )
                    )

                else:

                    raise ValueError(
                        f"Unsupported VecPort filter operator: {operator}"
                    )

        return Filter(
        must=must or None,
        must_not=must_not or None,
        )

    def search(
        self,
        collection: str,
        vector: list[float],
        top_k: int = 10,
        filters: dict | None = None,
    ) -> list[SearchResult]:

        validate_filter(filters)

        query_filter = self._build_filter(
            filters
        )

        response = self.client.query_points(
            collection_name=collection,
            query=vector,
            query_filter=query_filter,
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

    def collection_info(
        self,
        name: str,
    ) -> CollectionInfo:

        collections = (
            self.client
            .get_collections()
            .collections
        )

        exists = any(
            collection.name == name
            for collection in collections
        )

        if not exists:
            return CollectionInfo(
                name=name,
                exists=False,
            )

        info = self.client.get_collection(
            collection_name=name
        )

        vectors = (
            info.config
            .params
            .vectors
        )

        # 現在のVecPort Qdrant Driverは
        # unnamed single dense vectorを前提としている
        if isinstance(vectors, dict):
            return CollectionInfo(
                name=name,
                exists=True,
            )

        dimension = getattr(
            vectors,
            "size",
            None,
        )

        raw_distance = getattr(
            vectors,
            "distance",
            None,
        )

        distance_metric = None

        if raw_distance is not None:

            raw_value = getattr(
                raw_distance,
                "value",
                raw_distance,
            )

            normalized = str(
                raw_value
            ).lower()

            distance_aliases = {
                "cosine": "cosine",
                "dot": "dot",
                "euclid": "l2",
                "euclidean": "l2",
                "manhattan": "manhattan",
            }

            distance_metric = (
                distance_aliases.get(
                    normalized,
                    normalized,
                )
            )

        hnsw = getattr(
            info.config,
            "hnsw_config",
            None,
        )

        index_params = {}

        if hnsw is not None:

            for field in (
                "m",
                "ef_construct",
                "full_scan_threshold",
                "max_indexing_threads",
                "on_disk",
            ):

                value = getattr(
                    hnsw,
                    field,
                    None,
                )

                if value is not None:
                    index_params[field] = value

        return CollectionInfo(
            name=name,
            exists=True,
            dimension=dimension,
            distance_metric=distance_metric,
            index_type=(
                "HNSW"
                if hnsw is not None
                else None
            ),
            index_params=(
                index_params
                or None
            ),
            metadata_schema=None,
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

        offset = None

        while True:

            points, offset = self.client.scroll(
                collection_name=collection,
                limit=batch_size,
                offset=offset,
                with_payload=True,
                with_vectors=True,
            )

            for point in points:

                vector = point.vector

                if not isinstance(vector, list):
                    raise UnsupportedFeatureError(
                        "VecPort migration currently supports "
                        "single dense vectors only"
                    )

                yield VectorRecord(
                    id=str(point.id),
                    vector=list(vector),
                    metadata=point.payload or {},
                )

            if offset is None:
                break

    def close(
        self,
    ) -> None:

        self.client.close()