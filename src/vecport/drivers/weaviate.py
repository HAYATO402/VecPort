import weaviate
from weaviate.classes.init import Auth
from weaviate.classes.config import Configure

from vecport.core.interface import VectorDatabase
from vecport.core.models import (
    Capabilities,
    SearchResult,
    VectorRecord,
)

from weaviate.classes.query import Filter

from vecport.core.filters import validate_filter

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

        col = self.client.collections.get(
            collection
        )

        with col.batch.fixed_size(
            batch_size=50
        ) as batch:

            for record in records:

                batch.add_object(
                    uuid=record.id,
                    properties=record.metadata,
                    vector=record.vector,
                )

            if batch.number_errors > 0:
                raise RuntimeError(
                    f"Weaviate batch failed: "
                    f"{batch.failed_objects}"
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
        filters: dict | None = None,
    ) -> list[SearchResult]:

        validate_filter(filters)

        col = self.client.collections.get(
            collection
        )

        weaviate_filter = (
            self._build_filter(filters)
        )

        response = col.query.near_vector(
            near_vector=vector,
            limit=top_k,
            filters=weaviate_filter,
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
    
    def _build_filter(
        self,
        filters: dict | None,
    ):

        if not filters:
            return None

        # AND
        if "$and" in filters:

            items = [
                self._build_filter(item)
                for item in filters["$and"]
            ]

            return Filter.all_of(items)

        # OR
        if "$or" in filters:

            items = [
                self._build_filter(item)
                for item in filters["$or"]
            ]

            return Filter.any_of(items)

        # 通常のフィールド条件
        expressions = []

        for key, condition in filters.items():

            prop = Filter.by_property(key)

            for operator, value in condition.items():

                if operator == "$eq":

                    expressions.append(
                        prop.equal(value)
                    )

                elif operator == "$ne":

                    expressions.append(
                        Filter.not_(
                            prop.equal(value)
                        )
                    )

                elif operator == "$gt":

                    expressions.append(
                        prop.greater_than(value)
                    )

                elif operator == "$gte":

                    expressions.append(
                        prop.greater_or_equal(value)
                    )

                elif operator == "$lt":

                    expressions.append(
                        prop.less_than(value)
                    )

                elif operator == "$lte":

                    expressions.append(
                        prop.less_or_equal(value)
                    )

                elif operator == "$in":

                    expressions.append(
                        prop.contains_any(value)
                    )

                else:

                    raise ValueError(
                        f"Unsupported VecPort filter operator: {operator}"
                    )

        if len(expressions) == 1:
            return expressions[0]

        return Filter.all_of(expressions)

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

        col = self.client.collections.use(
            collection
        )

        for item in col.iterator(
            include_vector=True
        ):

            raw_vector = item.vector

            if isinstance(
                raw_vector,
                dict,
            ):

                if "default" in raw_vector:
                    vector = raw_vector[
                        "default"
                    ]

                elif len(raw_vector) == 1:
                    vector = next(
                        iter(
                            raw_vector.values()
                        )
                    )

                else:
                    raise UnsupportedFeatureError(
                        "VecPort migration currently supports "
                        "single dense vectors only"
                    )

            else:
                vector = raw_vector

            yield VectorRecord(
                id=str(item.uuid),
                vector=list(vector),
                metadata=dict(
                    item.properties or {}
                ),
            )