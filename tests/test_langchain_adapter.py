from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from vecport.core.models import SearchResult
from vecport.integrations.langchain import VecPortVectorStore


class FakeEmbeddings(Embeddings):
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0, 0.0] for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        return [1.0, 0.0, 0.0]


class FakeDriver:
    def __init__(self) -> None:
        self.upserted = []
        self.deleted_ids = []
        self.search_results = []
        self.last_filters = None

    def upsert(self, collection, records) -> None:
        self.upserted.extend(records)

    def delete(self, collection, ids) -> None:
        self.deleted_ids.extend(ids)

    def search(
        self,
        collection,
        vector,
        top_k=10,
        filters=None,
    ):
        self.last_filters = filters
        return self.search_results


def make_store(db: FakeDriver) -> VecPortVectorStore:
    return VecPortVectorStore(
        db=db,
        collection="documents",
        embedding=FakeEmbeddings(),
    )


def test_add_documents() -> None:
    db = FakeDriver()
    store = make_store(db)

    ids = store.add_documents(
        [
            Document(
                id="doc-1",
                page_content="VecPort supports vector databases.",
                metadata={"category": "AI"},
            )
        ]
    )

    assert ids == ["doc-1"]
    assert len(db.upserted) == 1

    record = db.upserted[0]
    assert record.id == "doc-1"
    assert record.vector == [1.0, 0.0, 0.0]
    assert record.metadata["category"] == "AI"
    assert (
        record.metadata["_vecport_page_content"]
        == "VecPort supports vector databases."
    )


def test_add_documents_generates_ids() -> None:
    db = FakeDriver()
    store = make_store(db)

    ids = store.add_documents([Document(page_content="Hello")])

    assert len(ids) == 1
    assert ids[0]
    assert db.upserted[0].id == ids[0]


def test_similarity_search() -> None:
    db = FakeDriver()
    db.search_results = [
        SearchResult(
            id="doc-1",
            score=0.95,
            metadata={
                "category": "AI",
                "_vecport_page_content": "VecPort supports vector databases.",
            },
        )
    ]
    store = make_store(db)

    documents = store.similarity_search("vector databases", k=1)

    assert len(documents) == 1
    assert documents[0].page_content == "VecPort supports vector databases."
    assert documents[0].metadata == {"category": "AI"}
    assert documents[0].id == "doc-1"


def test_langchain_filter_maps_to_vecport() -> None:
    db = FakeDriver()
    store = make_store(db)

    store.similarity_search(
        "AI",
        filter={"category": {"$eq": "AI"}},
    )

    assert db.last_filters == {"category": {"$eq": "AI"}}


def test_delete() -> None:
    db = FakeDriver()
    store = make_store(db)

    result = store.delete(ids=["doc-1"])

    assert result is True
    assert db.deleted_ids == ["doc-1"]


def test_similarity_search_with_score_preserves_vecport_score() -> None:
    db = FakeDriver()
    db.search_results = [
        SearchResult(
            id="doc-1",
            score=0.95,
            metadata={"_vecport_page_content": "Hello"},
        )
    ]
    store = make_store(db)

    document, score = store.similarity_search_with_score("Hello", k=1)[0]

    assert document.page_content == "Hello"
    assert score == 0.95


def test_as_retriever() -> None:
    db = FakeDriver()
    db.search_results = [
        SearchResult(
            id="doc-1",
            score=0.95,
            metadata={"_vecport_page_content": "VecPort document"},
        )
    ]
    store = make_store(db)
    retriever = store.as_retriever(search_kwargs={"k": 1})

    documents = retriever.invoke("VecPort")

    assert len(documents) == 1
    assert documents[0].page_content == "VecPort document"


def test_from_texts() -> None:
    db = FakeDriver()

    store = VecPortVectorStore.from_texts(
        texts=["Hello VecPort"],
        embedding=FakeEmbeddings(),
        metadatas=[{"category": "AI"}],
        ids=["doc-1"],
        db=db,
        collection="documents",
    )

    assert isinstance(store, VecPortVectorStore)
    assert len(db.upserted) == 1
    assert db.upserted[0].id == "doc-1"
