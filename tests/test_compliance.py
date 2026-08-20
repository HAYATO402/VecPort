from __future__ import annotations

from collections.abc import Iterator

import pytest

from vecport.core.compliance import run_compliance
from vecport.core.interface import VectorDatabase
from vecport.core.models import (
    Capabilities,
    SearchResult,
    VectorRecord,
)


class FakeComplianceDriver(VectorDatabase):
    def __init__(
        self,
        *,
        metadata_filter: bool = True,
    ) -> None:
        self._metadata_filter = metadata_filter
        self.collections: dict[
            str,
            dict[str, VectorRecord],
        ] = {}
        self.dimensions: dict[str, int] = {}

    def create_collection(
        self,
        name: str,
        dimension: int,
    ) -> None:
        if name in self.collections:
            raise ValueError(
                "Collection already exists."
            )
        self.collections[name] = {}
        self.dimensions[name] = dimension

    def delete_collection(
        self,
        name: str,
    ) -> None:
        self.collections.pop(name, None)
        self.dimensions.pop(name, None)

    def upsert(
        self,
        collection: str,
        records: list[VectorRecord],
    ) -> None:
        stored = self.collections[collection]
        dimension = self.dimensions[collection]

        for record in records:
            if len(record.vector) != dimension:
                raise ValueError(
                    "Vector dimension does not match."
                )
            stored[record.id] = VectorRecord(
                id=record.id,
                vector=list(record.vector),
                metadata=dict(record.metadata),
            )

    def get(
        self,
        collection: str,
        ids: list[str],
    ) -> list[VectorRecord]:
        stored = self.collections[collection]

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
        stored = self.collections[collection]

        for record_id in ids:
            stored.pop(record_id, None)

    def search(
        self,
        collection: str,
        vector: list[float],
        top_k: int = 10,
        filters: dict | None = None,
    ) -> list[SearchResult]:
        records = list(
            self.collections[collection].values()
        )

        if filters is not None:
            category = filters.get(
                "category",
                {},
            ).get("$eq")
            records = [
                record
                for record in records
                if record.metadata.get("category")
                == category
            ]

        scored = sorted(
            records,
            key=lambda record: sum(
                left * right
                for left, right in zip(
                    record.vector,
                    vector,
                )
            ),
            reverse=True,
        )

        return [
            SearchResult(
                id=record.id,
                score=sum(
                    left * right
                    for left, right in zip(
                        record.vector,
                        vector,
                    )
                ),
                metadata=dict(record.metadata),
            )
            for record in scored[:top_k]
        ]

    def capabilities(self) -> Capabilities:
        return Capabilities(
            metadata_filter=(
                self._metadata_filter
            ),
            filter_operators=(
                ("$eq",)
                if self._metadata_filter
                else ()
            ),
        )

    def scan(
        self,
        collection: str,
        *,
        batch_size: int = 100,
    ) -> Iterator[VectorRecord]:
        del batch_size
        yield from self.collections[
            collection
        ].values()


class BrokenSearchDriver(FakeComplianceDriver):
    def search(
        self,
        collection: str,
        vector: list[float],
        top_k: int = 10,
        filters: dict | None = None,
    ) -> list[SearchResult]:
        del collection, vector, top_k, filters
        return []


def test_compliance_passes_and_cleans_up() -> None:
    db = FakeComplianceDriver()

    report = run_compliance(db)

    assert report.passed
    assert report.passed_count == 7
    assert report.failed_count == 0
    assert report.skipped_count == 0
    assert report.collection not in db.collections


def test_compliance_reports_expected_checks() -> None:
    report = run_compliance(
        FakeComplianceDriver()
    )

    assert [
        check.name
        for check in report.checks
    ] == [
        "create_collection",
        "upsert_get",
        "search",
        "filter_eq",
        "scan",
        "delete",
        "cleanup",
    ]


def test_compliance_reports_broken_search() -> None:
    db = BrokenSearchDriver()

    report = run_compliance(db)

    failed_names = {
        check.name
        for check in report.checks
        if check.failed
    }
    assert not report.passed
    assert "search" in failed_names
    assert report.collection not in db.collections


def test_compliance_skips_unsupported_filter() -> None:
    report = run_compliance(
        FakeComplianceDriver(
            metadata_filter=False
        )
    )

    filter_check = next(
        check
        for check in report.checks
        if check.name == "filter_eq"
    )
    assert report.passed
    assert report.skipped_count == 1
    assert filter_check.skipped


def test_compliance_can_keep_collection() -> None:
    db = FakeComplianceDriver()

    report = run_compliance(
        db,
        cleanup=False,
    )

    assert report.passed
    assert "cleanup" not in {
        check.name
        for check in report.checks
    }
    assert report.collection in db.collections


def test_compliance_rejects_small_dimension() -> None:
    with pytest.raises(
        ValueError,
        match="at least 2",
    ):
        run_compliance(
            FakeComplianceDriver(),
            dimension=1,
        )
