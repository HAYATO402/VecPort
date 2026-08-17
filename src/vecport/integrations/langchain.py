from __future__ import annotations

from collections.abc import Iterable
from typing import Any
from uuid import uuid4

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.vectorstores import VectorStore

from vecport.core.interface import VectorDatabase
from vecport.core.models import SearchResult, VectorRecord

_DEFAULT_CONTENT_KEY = "_vecport_page_content"


class VecPortVectorStore(VectorStore):
    """LangChain VectorStore adapter for VecPort."""

    def __init__(
        self,
        db: VectorDatabase,
        collection: str,
        embedding: Embeddings,
        *,
        content_key: str = _DEFAULT_CONTENT_KEY,
    ) -> None:
        self._db = db
        self._collection = collection
        self._embedding = embedding
        self._content_key = content_key

    @property
    def embeddings(self) -> Embeddings:
        return self._embedding

    def add_texts(
        self,
        texts: Iterable[str],
        metadatas: list[dict[str, Any]] | None = None,
        *,
        ids: list[str] | None = None,
        **kwargs: Any,
    ) -> list[str]:
        if kwargs:
            unexpected = ", ".join(sorted(kwargs))
            raise TypeError(f"Unsupported arguments: {unexpected}")

        texts_list = list(texts)
        if not texts_list:
            return []

        if metadatas is not None and len(metadatas) != len(texts_list):
            raise ValueError(
                "The number of metadatas must match the number of texts."
            )

        if ids is not None and len(ids) != len(texts_list):
            raise ValueError("The number of IDs must match the number of texts.")

        resolved_ids = (
            list(ids)
            if ids is not None
            else [str(uuid4()) for _ in texts_list]
        )
        resolved_metadatas = (
            metadatas if metadatas is not None else [{} for _ in texts_list]
        )

        vectors = self._embedding.embed_documents(texts_list)
        if len(vectors) != len(texts_list):
            raise ValueError(
                "Embedding provider returned an unexpected number of vectors."
            )

        records: list[VectorRecord] = []
        for record_id, text, metadata, vector in zip(
            resolved_ids,
            texts_list,
            resolved_metadatas,
            vectors,
            strict=True,
        ):
            stored_metadata = dict(metadata)
            if self._content_key in stored_metadata:
                raise ValueError(
                    f"Metadata key '{self._content_key}' is reserved by VecPort."
                )

            stored_metadata[self._content_key] = text
            records.append(
                VectorRecord(
                    id=record_id,
                    vector=list(vector),
                    metadata=stored_metadata,
                )
            )

        self._db.upsert(
            collection=self._collection,
            records=records,
        )
        return resolved_ids

    def delete(
        self,
        ids: list[str] | None = None,
        **kwargs: Any,
    ) -> bool | None:
        if kwargs:
            unexpected = ", ".join(sorted(kwargs))
            raise TypeError(f"Unsupported arguments: {unexpected}")

        if ids is None:
            raise ValueError("VecPortVectorStore requires explicit IDs for deletion.")

        self._db.delete(
            collection=self._collection,
            ids=ids,
        )
        return True

    def similarity_search(
        self,
        query: str,
        k: int = 4,
        **kwargs: Any,
    ) -> list[Document]:
        return [
            document
            for document, _score in self.similarity_search_with_score(
                query,
                k=k,
                **kwargs,
            )
        ]

    def similarity_search_with_score(
        self,
        query: str,
        k: int = 4,
        **kwargs: Any,
    ) -> list[tuple[Document, float]]:
        filters = kwargs.pop("filter", None)
        vecport_filters = kwargs.pop("filters", None)

        if filters is not None and vecport_filters is not None:
            raise ValueError("Use either 'filter' or 'filters', not both.")

        filters = filters if filters is not None else vecport_filters
        if kwargs:
            unexpected = ", ".join(sorted(kwargs))
            raise TypeError(f"Unsupported arguments: {unexpected}")

        query_vector = self._embedding.embed_query(query)
        results = self._db.search(
            collection=self._collection,
            vector=list(query_vector),
            top_k=k,
            filters=filters,
        )

        return [
            (self._to_document(result), float(result.score)) for result in results
        ]

    @classmethod
    def from_texts(
        cls,
        texts: list[str],
        embedding: Embeddings,
        metadatas: list[dict[str, Any]] | None = None,
        *,
        ids: list[str] | None = None,
        **kwargs: Any,
    ) -> VecPortVectorStore:
        db = kwargs.pop("db", None)
        collection = kwargs.pop("collection", None)
        content_key = kwargs.pop("content_key", _DEFAULT_CONTENT_KEY)

        if db is None:
            raise ValueError("'db' is required.")
        if not collection:
            raise ValueError("'collection' is required.")

        store = cls(
            db=db,
            collection=collection,
            embedding=embedding,
            content_key=content_key,
        )
        store.add_texts(
            texts,
            metadatas=metadatas,
            ids=ids,
            **kwargs,
        )
        return store

    def _to_document(self, result: SearchResult) -> Document:
        metadata = dict(result.metadata or {})
        if self._content_key not in metadata:
            raise ValueError(
                "Search result does not contain "
                f"'{self._content_key}'. Records must contain page content "
                "to be used as LangChain Documents."
            )

        page_content = metadata.pop(self._content_key)
        return Document(
            id=str(result.id),
            page_content=str(page_content),
            metadata=metadata,
        )
