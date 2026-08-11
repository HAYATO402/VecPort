from abc import ABC, abstractmethod

from vecport.core.models import (
    Capabilities,
    SearchResult,
    VectorRecord,
)


class VectorDatabase(ABC):

    @abstractmethod
    def create_collection(
        self,
        name: str,
        dimension: int,
    ) -> None:
        pass

    @abstractmethod
    def delete_collection(
        self,
        name: str,
    ) -> None:
        pass

    @abstractmethod
    def upsert(
        self,
        collection: str,
        records: list[VectorRecord],
    ) -> None:
        pass

    @abstractmethod
    def get(
        self,
        collection: str,
        ids: list[str],
    ) -> list[VectorRecord]:
        pass

    @abstractmethod
    def delete(
        self,
        collection: str,
        ids: list[str],
    ) -> None:
        pass

    @abstractmethod
    def search(
        self,
        collection: str,
        vector: list[float],
        top_k: int = 10,
        filters: dict | None = None,
    ) -> list[SearchResult]:
        pass

    @abstractmethod
    def capabilities(
        self,
    ) -> Capabilities:
        pass