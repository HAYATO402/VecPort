import pytest
from llama_index.core import (
    Document,
    MockEmbedding,
    StorageContext,
    VectorStoreIndex,
)
from llama_index.core.schema import (
    NodeRelationship,
    RelatedNodeInfo,
    TextNode,
)
from llama_index.core.vector_stores.types import (
    FilterCondition,
    FilterOperator,
    MetadataFilter,
    MetadataFilters,
    VectorStoreQuery,
    VectorStoreQueryMode,
)

from vecport.core.errors import UnsupportedFeatureError
from vecport.core.models import SearchResult, VectorRecord
from vecport.integrations.llamaindex import VecPortLlamaIndexVectorStore


class FakeDriver:
    def __init__(self) -> None:
        self.records: dict[str, VectorRecord] = {}
        self.deleted_ids: list[str] = []
        self.last_filters = None
        self.last_vector = None
        self.last_top_k = None

    def upsert(self, collection, records) -> None:
        for record in records:
            self.records[record.id] = record

    def get(self, collection, ids):
        return [
            self.records[record_id]
            for record_id in ids
            if record_id in self.records
        ]

    def delete(self, collection, ids) -> None:
        self.deleted_ids.extend(ids)
        for record_id in ids:
            self.records.pop(record_id, None)

    def scan(self, collection, *, batch_size=100):
        yield from self.records.values()

    def search(
        self,
        collection,
        vector,
        top_k=10,
        filters=None,
    ):
        self.last_filters = filters
        self.last_vector = vector
        self.last_top_k = top_k
        records = list(self.records.values())[:top_k]
        return [
            SearchResult(
                id=record.id,
                score=1.0,
                metadata=dict(record.metadata),
            )
            for record in records
        ]


def make_store(db: FakeDriver) -> VecPortLlamaIndexVectorStore:
    return VecPortLlamaIndexVectorStore(
        db=db,
        collection="documents",
    )


def embedded_node(
    *,
    node_id: str = "node-1",
    text: str = "VecPort supports vector databases.",
) -> TextNode:
    return TextNode(
        id_=node_id,
        text=text,
        metadata={"category": "AI"},
        embedding=[1.0, 0.0, 0.0],
    )


def test_add_node() -> None:
    db = FakeDriver()
    store = make_store(db)

    ids = store.add([embedded_node()])

    assert ids == ["node-1"]
    record = db.records["node-1"]
    assert record.vector == [1.0, 0.0, 0.0]
    assert record.metadata["category"] == "AI"
    assert (
        record.metadata["_vecport_llama_text"]
        == "VecPort supports vector databases."
    )
    assert record.metadata["_vecport_llama_node_id"] == "node-1"


def test_add_node_preserves_reference_document_id() -> None:
    db = FakeDriver()
    store = make_store(db)
    node = TextNode(
        id_="node-1",
        text="Hello",
        embedding=[1.0, 0.0, 0.0],
        relationships={
            NodeRelationship.SOURCE: RelatedNodeInfo(node_id="document-1")
        },
    )

    store.add([node])

    assert (
        db.records["node-1"].metadata["_vecport_llama_ref_doc_id"]
        == "document-1"
    )


def test_add_rejects_missing_embedding() -> None:
    store = make_store(FakeDriver())

    with pytest.raises(ValueError, match="must contain an embedding"):
        store.add([TextNode(id_="node-1", text="Hello")])


def test_add_rejects_reserved_metadata() -> None:
    store = make_store(FakeDriver())
    node = TextNode(
        id_="node-1",
        text="Hello",
        embedding=[1.0, 0.0, 0.0],
        metadata={"_vecport_llama_text": "conflict"},
    )

    with pytest.raises(ValueError, match="metadata key already exists"):
        store.add([node])


def test_query() -> None:
    db = FakeDriver()
    store = make_store(db)
    store.add([embedded_node(text="VecPort document")])

    result = store.query(
        VectorStoreQuery(
            query_embedding=[1.0, 0.0, 0.0],
            similarity_top_k=1,
        )
    )

    assert result.ids == ["node-1"]
    assert result.nodes is not None
    assert result.nodes[0].get_content() == "VecPort document"
    assert result.nodes[0].metadata == {"category": "AI"}
    assert result.similarities == [1.0]
    assert db.last_vector == [1.0, 0.0, 0.0]
    assert db.last_top_k == 1


def test_metadata_filters() -> None:
    db = FakeDriver()
    store = make_store(db)

    store.query(
        VectorStoreQuery(
            query_embedding=[1.0, 0.0, 0.0],
            similarity_top_k=5,
            filters=MetadataFilters(
                filters=[
                    MetadataFilter(
                        key="category",
                        value="AI",
                        operator=FilterOperator.EQ,
                    ),
                    MetadataFilter(
                        key="price",
                        value=10000,
                        operator=FilterOperator.LT,
                    ),
                ],
                condition=FilterCondition.AND,
            ),
        )
    )

    assert db.last_filters == {
        "$and": [
            {"category": {"$eq": "AI"}},
            {"price": {"$lt": 10000}},
        ]
    }


def test_query_combines_metadata_node_and_document_filters() -> None:
    db = FakeDriver()
    store = make_store(db)

    store.query(
        VectorStoreQuery(
            query_embedding=[1.0, 0.0, 0.0],
            filters=MetadataFilters(
                filters=[MetadataFilter(key="category", value="AI")]
            ),
            node_ids=["node-1"],
            doc_ids=["document-1"],
        )
    )

    assert db.last_filters == {
        "$and": [
            {"category": {"$eq": "AI"}},
            {"_vecport_llama_node_id": {"$in": ["node-1"]}},
            {"_vecport_llama_ref_doc_id": {"$in": ["document-1"]}},
        ]
    }


def test_nested_or_metadata_filters() -> None:
    db = FakeDriver()
    store = make_store(db)

    store.query(
        VectorStoreQuery(
            query_embedding=[1.0, 0.0, 0.0],
            filters=MetadataFilters(
                filters=[
                    MetadataFilters(
                        filters=[
                            MetadataFilter(key="category", value="AI"),
                            MetadataFilter(key="category", value="ML"),
                        ],
                        condition=FilterCondition.OR,
                    ),
                    MetadataFilter(
                        key="price",
                        value=100,
                        operator=FilterOperator.GTE,
                    ),
                ],
                condition=FilterCondition.AND,
            ),
        )
    )

    assert db.last_filters == {
        "$and": [
            {
                "$or": [
                    {"category": {"$eq": "AI"}},
                    {"category": {"$eq": "ML"}},
                ]
            },
            {"price": {"$gte": 100}},
        ]
    }


@pytest.mark.parametrize(
    "operator",
    [
        FilterOperator.NIN,
        FilterOperator.TEXT_MATCH,
        FilterOperator.IS_EMPTY,
    ],
)
def test_query_rejects_unsupported_filter_operators(operator) -> None:
    store = make_store(FakeDriver())

    with pytest.raises(UnsupportedFeatureError, match="filter operator"):
        store.query(
            VectorStoreQuery(
                query_embedding=[1.0, 0.0, 0.0],
                filters=MetadataFilters(
                    filters=[
                        MetadataFilter(
                            key="category",
                            value="AI",
                            operator=operator,
                        )
                    ]
                ),
            )
        )


def test_query_rejects_not_filter_condition() -> None:
    store = make_store(FakeDriver())

    with pytest.raises(UnsupportedFeatureError, match="NOT filters"):
        store.query(
            VectorStoreQuery(
                query_embedding=[1.0, 0.0, 0.0],
                filters=MetadataFilters(
                    filters=[MetadataFilter(key="category", value="AI")],
                    condition=FilterCondition.NOT,
                ),
            )
        )


def test_query_requires_embedding_and_default_mode() -> None:
    store = make_store(FakeDriver())

    with pytest.raises(ValueError, match="query_embedding"):
        store.query(VectorStoreQuery())
    with pytest.raises(UnsupportedFeatureError, match="DEFAULT"):
        store.query(
            VectorStoreQuery(
                query_embedding=[1.0, 0.0, 0.0],
                mode=VectorStoreQueryMode.HYBRID,
            )
        )


def test_delete_by_ref_doc_id() -> None:
    db = FakeDriver()
    store = make_store(db)
    db.upsert(
        "documents",
        [
            VectorRecord(
                id="node-1",
                vector=[1.0, 0.0, 0.0],
                metadata={
                    "_vecport_llama_text": "Hello",
                    "_vecport_llama_ref_doc_id": "document-1",
                },
            )
        ],
    )

    store.delete("document-1")

    assert "node-1" not in db.records
    assert db.deleted_ids == ["node-1"]


def test_delete_nodes() -> None:
    db = FakeDriver()
    store = make_store(db)
    store.add([embedded_node()])

    store.delete_nodes(["node-1"])

    assert db.records == {}
    assert db.deleted_ids == ["node-1"]


def test_get_nodes_restores_embedding_and_reference_document() -> None:
    db = FakeDriver()
    store = make_store(db)
    node = TextNode(
        id_="node-1",
        text="Hello",
        embedding=[1.0, 0.0, 0.0],
        relationships={
            NodeRelationship.SOURCE: RelatedNodeInfo(node_id="document-1")
        },
    )
    store.add([node])

    result = store.get_nodes(["node-1"])

    assert len(result) == 1
    assert result[0].node_id == "node-1"
    assert result[0].get_embedding() == [1.0, 0.0, 0.0]
    assert result[0].ref_doc_id == "document-1"


def test_node_filter_operations_are_explicitly_unsupported() -> None:
    store = make_store(FakeDriver())
    filters = MetadataFilters(
        filters=[MetadataFilter(key="category", value="AI")]
    )

    with pytest.raises(UnsupportedFeatureError, match="Deleting by"):
        store.delete_nodes(filters=filters)
    with pytest.raises(UnsupportedFeatureError, match="get_nodes"):
        store.get_nodes(filters=filters)


def test_vector_store_index_integration() -> None:
    db = FakeDriver()
    store = make_store(db)
    storage_context = StorageContext.from_defaults(vector_store=store)

    index = VectorStoreIndex.from_documents(
        [
            Document(
                text="VecPort provides one interface for vector databases.",
                id_="document-1",
            )
        ],
        storage_context=storage_context,
        embed_model=MockEmbedding(embed_dim=3),
    )

    assert index.vector_store is store
    assert db.records
    assert all(
        record.metadata.get("_vecport_llama_ref_doc_id") == "document-1"
        for record in db.records.values()
    )


def test_vector_store_index_retrieval() -> None:
    db = FakeDriver()
    store = make_store(db)
    storage_context = StorageContext.from_defaults(vector_store=store)
    index = VectorStoreIndex.from_documents(
        [
            Document(
                text="VecPort vector database adapter.",
                id_="document-1",
            )
        ],
        storage_context=storage_context,
        embed_model=MockEmbedding(embed_dim=3),
    )

    results = index.as_retriever(similarity_top_k=1).retrieve(
        "vector database"
    )

    assert len(results) == 1
    assert results[0].node.get_content() == "VecPort vector database adapter."
