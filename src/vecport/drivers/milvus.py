from pymilvus import (
    DataType,
    MilvusClient,
)

from vecport.core.filters import validate_filter
from vecport.core.interface import VectorDatabase
from vecport.core.models import (
    Capabilities,
    CollectionInfo,
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
        filters: dict | None = None,
    ) -> list[SearchResult]:

        validate_filter(filters)

        filter_expression = self._build_filter(
            filters
        )

        response = self.client.search(
            collection_name=collection,
            data=[vector],
            limit=top_k,
            filter=filter_expression,
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
                if key not in (
                    "id",
                    "vector",
                )
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

        if not self.client.has_collection(
            collection_name=name
        ):
            return CollectionInfo(
                name=name,
                exists=False,
            )

        description = (
            self.client.describe_collection(
                collection_name=name
            )
        )

        fields = description.get(
            "fields",
            [],
        )

        vector_field = next(
            (
                field
                for field in fields
                if field.get("name")
                == "vector"
            ),
            None,
        )

        dimension = None

        if vector_field is not None:

            params = vector_field.get(
                "params",
                {},
            )

            raw_dimension = params.get(
                "dim"
            )

            if raw_dimension is not None:
                dimension = int(
                    raw_dimension
                )

        index_type = None
        distance_metric = None
        index_params_result = None

        index_names = (
            self.client.list_indexes(
                collection_name=name
            )
        )

        for index_name in index_names:

            index_info = (
                self.client.describe_index(
                    collection_name=name,
                    index_name=index_name,
                )
            )

            if (
                index_info.get(
                    "field_name"
                )
                != "vector"
            ):
                continue

            index_type = (
                index_info.get(
                    "index_type"
                )
            )

            raw_metric = (
                index_info.get(
                    "metric_type"
                )
            )

            if raw_metric is not None:

                normalized = str(
                    raw_metric
                ).lower()

                metric_aliases = {
                    "cosine": "cosine",
                    "ip": "dot",
                    "l2": "l2",
                }

                distance_metric = (
                    metric_aliases.get(
                        normalized,
                        normalized,
                    )
                )

            excluded = {
                "field_name",
                "index_name",
                "index_type",
                "metric_type",
            }

            remaining = {
                key: value
                for key, value
                in index_info.items()
                if key not in excluded
            }

            index_params_result = (
                remaining
                or None
            )

            break

        metadata_schema = {}

        if description.get(
            "enable_dynamic_field",
            False,
        ):
            metadata_schema[
                "__dynamic__"
            ] = "enabled"

        for field in fields:

            field_name = field.get(
                "name"
            )

            if field_name in (
                "id",
                "vector",
            ):
                continue

            metadata_schema[
                field_name
            ] = str(
                field.get(
                    "type"
                )
            )

        return CollectionInfo(
            name=name,
            exists=True,
            dimension=dimension,
            distance_metric=distance_metric,
            index_type=index_type,
            index_params=index_params_result,
            metadata_schema=(
                metadata_schema
                or None
            ),
        )

    def _quote_filter_value(
        self,
        value,
    ):

        if isinstance(value, str):

            value = value.replace(
                '"',
                '\\"',
            )

            return f'"{value}"'

        if isinstance(value, bool):
            return "true" if value else "false"

        return str(value)

    def _build_filter(
        self,
        filters: dict | None,
    ) -> str | None:

        if not filters:
            return None

        expressions = []

        for key, condition in filters.items():

            if key == "$and":

                parts = [
                    self._build_filter(item)
                    for item in condition
                ]

                return (
                    "("
                    + " and ".join(parts)
                    + ")"
                )

            if key == "$or":

                parts = [
                    self._build_filter(item)
                    for item in condition
                ]

                return (
                    "("
                    + " or ".join(parts)
                    + ")"
                )

            for operator, value in condition.items():

                mapping = {
                    "$eq": "==",
                    "$ne": "!=",
                    "$gt": ">",
                    "$gte": ">=",
                    "$lt": "<",
                    "$lte": "<=",
                }

                if operator in mapping:

                    expressions.append(
                        f"{key} "
                        f"{mapping[operator]} "
                        f"{self._quote_filter_value(value)}"
                    )

                elif operator == "$in":

                    values = ", ".join(
                        self._quote_filter_value(item)
                        for item in value
                    )

                    expressions.append(
                        f"{key} in [{values}]"
                    )

                else:

                    raise ValueError(
                        f"Unsupported VecPort filter operator: {operator}"
                    )

        return " and ".join(
            expressions
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

        iterator = self.client.query_iterator(
            collection_name=collection,
            batch_size=batch_size,
            filter="",
            output_fields=["*"],
        )

        try:

            while True:

                rows = iterator.next()

                if not rows:
                    break

                for row in rows:

                    metadata = {
                        key: value
                        for key, value in row.items()
                        if key not in {
                            "id",
                            "vector",
                        }
                    }

                    yield VectorRecord(
                        id=str(row["id"]),
                        vector=list(
                            row["vector"]
                        ),
                        metadata=metadata,
                    )

        finally:
            iterator.close()

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

        if self.client.has_collection(
            collection_name=name
        ):
            return

        metric = (
            info.distance_metric
            or "cosine"
        )

        metrics = {
            "cosine": "COSINE",
            "dot": "IP",
            "l2": "L2",
        }

        if metric not in metrics:
            raise ValueError(
                "Unsupported Milvus "
                f"distance metric: {metric}"
            )

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
            dim=info.dimension,
        )

        index_params = (
            self.client
            .prepare_index_params()
        )

        index_params.add_index(
            field_name="vector",
            index_type="AUTOINDEX",
            metric_type=metrics[
                metric
            ],
        )

        self.client.create_collection(
            collection_name=name,
            schema=schema,
            index_params=index_params,
            consistency_level="Strong",
        )