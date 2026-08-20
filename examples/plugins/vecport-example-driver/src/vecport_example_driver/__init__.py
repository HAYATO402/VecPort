from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

from vecport.core.interface import VectorDatabase
from vecport.core.models import (
    Capabilities,
    SearchResult,
    VectorRecord,
)


@dataclass
class _Collection:
    dimension: int
    records: dict[str, VectorRecord] = field(
        default_factory=dict
    )


class ExampleDriver(VectorDatabase):
    """Minimal in-memory VecPort plugin driver."""

    def __init__(
        self,
        **kwargs: Any,
    ) -> None:
        self.options = kwargs
        self._collections: dict[
            str,
            _Collection,
        ] = {}

    def create_collection(
        self,
        name: str,
        dimension: int,
    ) -> None:
        self._collections[name] = _Collection(
            dimension=dimension
        )

    def delete_collection(
        self,
        name: str,
    ) -> None:
        self._collections.pop(name, None)

    def upsert(
        self,
        collection: str,
        records: list[VectorRecord],
    ) -> None:
        stored = self._collections[collection]

        for record in records:
            if len(record.vector) != stored.dimension:
                raise ValueError(
                    "Vector dimension does not match."
                )
            stored.records[record.id] = record

    def get(
        self,
        collection: str,
        ids: list[str],
    ) -> list[VectorRecord]:
        stored = self._collections[
            collection
        ].records

        return [
            stored[record_id]
            for record_id in ids
            if record_id in stored
        ]

    def delete(
        self,
        collection: str,
        ids: list[str],
    ) -> None:
        stored = self._collections[
            collection
        ].records

        for record_id in ids:
            stored.pop(record_id, None)

    def scan(
        self,
        collection: str,
        *,
        batch_size: int = 100,
    ) -> Iterator[VectorRecord]:
        del batch_size
        yield from self._collections[
            collection
        ].records.values()

    def search(
        self,
        collection: str,
        vector: list[float],
        top_k: int = 10,
        filters: dict | None = None,
    ) -> list[SearchResult]:
        records = list(
            self._collections[
                collection
            ].records.values()
        )

        if filters:
            records = [
                record
                for record in records
                if self._matches(
                    record.metadata,
                    filters,
                )
            ]

        scored = sorted(
            (
                (
                    sum(
                        left * right
                        for left, right in zip(
                            record.vector,
                            vector,
                        )
                    ),
                    record,
                )
                for record in records
            ),
            key=lambda item: item[0],
            reverse=True,
        )

        return [
            SearchResult(
                id=record.id,
                score=float(score),
                metadata=dict(
                    record.metadata
                ),
            )
            for score, record in scored[:top_k]
        ]

    def capabilities(self) -> Capabilities:
        return Capabilities(
            dense_vector=True,
            metadata_filter=True,
            filter_operators=("$eq",),
        )

    @staticmethod
    def _matches(
        metadata: dict[str, Any],
        filters: dict[str, Any],
    ) -> bool:
        if "$and" in filters:
            return all(
                ExampleDriver._matches(
                    metadata,
                    child,
                )
                for child in filters["$and"]
            )

        for metadata_field, condition in (
            filters.items()
        ):
            if (
                "$eq" in condition
                and metadata.get(
                    metadata_field
                )
                != condition["$eq"]
            ):
                return False

        return True
