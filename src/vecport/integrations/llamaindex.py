from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from llama_index.core.bridge.pydantic import PrivateAttr
from llama_index.core.schema import (
    BaseNode,
    MetadataMode,
    NodeRelationship,
    RelatedNodeInfo,
    TextNode,
)
from llama_index.core.vector_stores.types import (
    BasePydanticVectorStore,
    FilterCondition,
    FilterOperator,
    MetadataFilters,
    VectorStoreQuery,
    VectorStoreQueryMode,
    VectorStoreQueryResult,
)

from vecport.core.errors import UnsupportedFeatureError
from vecport.core.interface import VectorDatabase
from vecport.core.models import SearchResult, VectorRecord

_DEFAULT_TEXT_KEY = "_vecport_llama_text"
_DEFAULT_REF_DOC_ID_KEY = "_vecport_llama_ref_doc_id"
_DEFAULT_NODE_ID_KEY = "_vecport_llama_node_id"

_FILTER_OPERATOR_MAP: dict[FilterOperator, str] = {
    FilterOperator.EQ: "$eq",
    FilterOperator.NE: "$ne",
    FilterOperator.GT: "$gt",
    FilterOperator.GTE: "$gte",
    FilterOperator.LT: "$lt",
    FilterOperator.LTE: "$lte",
    FilterOperator.IN: "$in",
}


def _metadata_filters_to_vecport(
    filters: MetadataFilters | None,
) -> dict[str, Any] | None:
    """Translate supported LlamaIndex metadata filters to VecPort filters."""
    if filters is None:
        return None

    parts: list[dict[str, Any]] = []
    for item in filters.filters:
        if isinstance(item, MetadataFilters):
            nested = _metadata_filters_to_vecport(item)
            if nested is not None:
                parts.append(nested)
            continue

        operator = _FILTER_OPERATOR_MAP.get(item.operator)
        if operator is None:
            raise UnsupportedFeatureError(
                "Unsupported LlamaIndex filter operator: "
                f"{item.operator.value}"
            )
        parts.append({item.key: {operator: item.value}})

    if not parts:
        return None

    condition = filters.condition or FilterCondition.AND
    if condition == FilterCondition.NOT:
        raise UnsupportedFeatureError(
            "LlamaIndex NOT filters are not supported by VecPort."
        )
    if len(parts) == 1:
        return parts[0]

    if condition == FilterCondition.AND:
        return {"$and": parts}
    if condition == FilterCondition.OR:
        return {"$or": parts}
    raise UnsupportedFeatureError(f"Unsupported filter condition: {condition.value}")


def _reject_unexpected_kwargs(
    operation: str,
    kwargs: dict[str, Any],
) -> None:
    if not kwargs:
        return
    unexpected = ", ".join(sorted(kwargs))
    raise TypeError(f"Unsupported {operation} arguments: {unexpected}")


class VecPortLlamaIndexVectorStore(BasePydanticVectorStore):
    """LlamaIndex VectorStore adapter for VecPort."""

    stores_text: bool = True
    is_embedding_query: bool = True
    collection: str
    content_key: str = _DEFAULT_TEXT_KEY
    ref_doc_id_key: str = _DEFAULT_REF_DOC_ID_KEY
    node_id_key: str = _DEFAULT_NODE_ID_KEY

    _db: VectorDatabase = PrivateAttr()

    def __init__(
        self,
        *,
        db: VectorDatabase,
        collection: str,
        content_key: str = _DEFAULT_TEXT_KEY,
        ref_doc_id_key: str = _DEFAULT_REF_DOC_ID_KEY,
        node_id_key: str = _DEFAULT_NODE_ID_KEY,
    ) -> None:
        if not collection:
            raise ValueError("'collection' must be a non-empty string.")

        reserved_keys = (content_key, ref_doc_id_key, node_id_key)
        if any(not key for key in reserved_keys):
            raise ValueError("Reserved metadata keys must be non-empty strings.")
        if len(set(reserved_keys)) != len(reserved_keys):
            raise ValueError("Reserved metadata keys must be unique.")

        model_values: dict[str, Any] = {
            "collection": collection,
            "content_key": content_key,
            "ref_doc_id_key": ref_doc_id_key,
            "node_id_key": node_id_key,
        }
        super().__init__(**model_values)
        self._db = db

    @property
    def client(self) -> Any:
        return self._db

    def add(
        self,
        nodes: Sequence[BaseNode],
        **kwargs: Any,
    ) -> list[str]:
        _reject_unexpected_kwargs("add", kwargs)

        records: list[VectorRecord] = []
        ids: list[str] = []
        reserved_keys = {
            self.content_key,
            self.ref_doc_id_key,
            self.node_id_key,
        }

        for node in nodes:
            if node.embedding is None:
                raise ValueError(
                    "LlamaIndex nodes must contain an embedding before "
                    "they are added to VecPort."
                )

            metadata = dict(node.metadata or {})
            conflicts = reserved_keys & metadata.keys()
            if conflicts:
                raise ValueError(
                    "Reserved VecPort LlamaIndex metadata key already exists: "
                    f"{sorted(conflicts)}"
                )

            metadata[self.content_key] = node.get_content(
                metadata_mode=MetadataMode.NONE
            )
            metadata[self.node_id_key] = node.node_id
            if node.ref_doc_id is not None:
                metadata[self.ref_doc_id_key] = node.ref_doc_id

            records.append(
                VectorRecord(
                    id=node.node_id,
                    vector=list(node.get_embedding()),
                    metadata=metadata,
                )
            )
            ids.append(node.node_id)

        if records:
            self._db.upsert(
                collection=self.collection,
                records=records,
            )
        return ids

    def _metadata_to_node(
        self,
        *,
        record_id: str,
        metadata: dict[str, Any],
        embedding: list[float] | None = None,
    ) -> TextNode:
        stored_metadata = dict(metadata)
        if self.content_key not in stored_metadata:
            raise ValueError(
                "VecPort record does not contain LlamaIndex text metadata."
            )

        text = stored_metadata.pop(self.content_key)
        node_id = str(stored_metadata.pop(self.node_id_key, record_id))
        ref_doc_id = stored_metadata.pop(self.ref_doc_id_key, None)
        relationships = (
            {
                NodeRelationship.SOURCE: RelatedNodeInfo(
                    node_id=str(ref_doc_id)
                )
            }
            if ref_doc_id is not None
            else {}
        )
        return TextNode(
            id_=node_id,
            text=str(text),
            metadata=stored_metadata,
            relationships=relationships,
            embedding=embedding,
        )

    def _search_result_to_node(
        self,
        result: SearchResult,
    ) -> TextNode:
        return self._metadata_to_node(
            record_id=str(result.id),
            metadata=result.metadata or {},
        )

    def query(
        self,
        query: VectorStoreQuery,
        **kwargs: Any,
    ) -> VectorStoreQueryResult:
        _reject_unexpected_kwargs("query", kwargs)

        if query.mode != VectorStoreQueryMode.DEFAULT:
            raise UnsupportedFeatureError(
                "VecPort LlamaIndex adapter currently supports only "
                "DEFAULT dense vector search."
            )
        if query.query_embedding is None:
            raise ValueError("VectorStoreQuery.query_embedding is required.")

        filter_parts: list[dict[str, Any]] = []
        metadata_filter = _metadata_filters_to_vecport(query.filters)
        if metadata_filter is not None:
            filter_parts.append(metadata_filter)
        if query.node_ids:
            filter_parts.append(
                {self.node_id_key: {"$in": list(query.node_ids)}}
            )
        if query.doc_ids:
            filter_parts.append(
                {self.ref_doc_id_key: {"$in": list(query.doc_ids)}}
            )

        filters: dict[str, Any] | None
        if not filter_parts:
            filters = None
        elif len(filter_parts) == 1:
            filters = filter_parts[0]
        else:
            filters = {"$and": filter_parts}

        results = self._db.search(
            collection=self.collection,
            vector=list(query.query_embedding),
            top_k=query.similarity_top_k,
            filters=filters,
        )
        return VectorStoreQueryResult(
            nodes=[self._search_result_to_node(result) for result in results],
            similarities=[float(result.score) for result in results],
            ids=[str(result.id) for result in results],
        )

    def _scan_records(self) -> list[VectorRecord]:
        scan = getattr(self._db, "scan", None)
        if scan is None:
            raise UnsupportedFeatureError(
                "This VecPort driver does not support scanning records."
            )
        return list(scan(self.collection))

    def delete(
        self,
        ref_doc_id: str,
        **delete_kwargs: Any,
    ) -> None:
        _reject_unexpected_kwargs("delete", delete_kwargs)

        ids = [
            str(record.id)
            for record in self._scan_records()
            if (record.metadata or {}).get(self.ref_doc_id_key) == ref_doc_id
        ]
        if ids:
            self._db.delete(
                collection=self.collection,
                ids=ids,
            )

    def delete_nodes(
        self,
        node_ids: list[str] | None = None,
        filters: MetadataFilters | None = None,
        **delete_kwargs: Any,
    ) -> None:
        _reject_unexpected_kwargs("delete_nodes", delete_kwargs)
        if filters is not None:
            raise UnsupportedFeatureError(
                "Deleting by LlamaIndex metadata filter is not supported yet."
            )
        if not node_ids:
            return
        self._db.delete(
            collection=self.collection,
            ids=list(node_ids),
        )

    def get_nodes(
        self,
        node_ids: list[str] | None = None,
        filters: MetadataFilters | None = None,
    ) -> list[BaseNode]:
        if filters is not None:
            raise UnsupportedFeatureError(
                "get_nodes with metadata filters is not supported yet."
            )

        records = (
            self._scan_records()
            if node_ids is None
            else self._db.get(
                collection=self.collection,
                ids=node_ids,
            )
        )
        return [
            self._metadata_to_node(
                record_id=str(record.id),
                metadata=record.metadata or {},
                embedding=list(record.vector),
            )
            for record in records
            if self.content_key in (record.metadata or {})
        ]
