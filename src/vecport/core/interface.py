from abc import ABC, abstractmethod

from vecport.core.models import (
    Capabilities,
    CollectionInfo,
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

        self.create_collection(
            name,
            info.dimension,
        )

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

    def prepare_for_search(
        self,
        collection: str,
    ) -> None:
        """Make recently written records searchable when required."""

    @abstractmethod
    def capabilities(
        self,
    ) -> Capabilities:
        pass

    def collection_info(
        self,
        name: str,
    ) -> CollectionInfo:

        return CollectionInfo(
            name=name
        )
