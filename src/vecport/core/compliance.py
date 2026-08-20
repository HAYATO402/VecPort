from __future__ import annotations

from dataclasses import dataclass
from math import isclose
from typing import Literal
from uuid import uuid4

from vecport.core.interface import VectorDatabase
from vecport.core.models import VectorRecord

ComplianceStatus = Literal[
    "pass",
    "fail",
    "skip",
]


@dataclass(frozen=True)
class ComplianceCheck:
    name: str
    status: ComplianceStatus
    detail: str = ""

    @property
    def passed(self) -> bool:
        return self.status == "pass"

    @property
    def failed(self) -> bool:
        return self.status == "fail"

    @property
    def skipped(self) -> bool:
        return self.status == "skip"


@dataclass(frozen=True)
class ComplianceReport:
    collection: str
    checks: tuple[ComplianceCheck, ...]

    @property
    def passed(self) -> bool:
        return not any(
            check.failed
            for check in self.checks
        )

    @property
    def passed_count(self) -> int:
        return sum(
            check.passed
            for check in self.checks
        )

    @property
    def failed_count(self) -> int:
        return sum(
            check.failed
            for check in self.checks
        )

    @property
    def skipped_count(self) -> int:
        return sum(
            check.skipped
            for check in self.checks
        )


def _passed(
    name: str,
    detail: str = "",
) -> ComplianceCheck:
    return ComplianceCheck(
        name=name,
        status="pass",
        detail=detail,
    )


def _failed(
    name: str,
    error: Exception,
) -> ComplianceCheck:
    return ComplianceCheck(
        name=name,
        status="fail",
        detail=(
            f"{type(error).__name__}: "
            f"{error}"
        ),
    )


def _skipped(
    name: str,
    detail: str,
) -> ComplianceCheck:
    return ComplianceCheck(
        name=name,
        status="skip",
        detail=detail,
    )


def _temporary_collection_name(
    prefix: str,
) -> str:
    suffix = uuid4().hex[:8]

    return f"{prefix}_{suffix}"


def _sample_records(
    dimension: int,
) -> list[VectorRecord]:
    if dimension < 2:
        raise ValueError(
            "Compliance test dimension "
            "must be at least 2."
        )

    first_vector = [
        0.0
        for _ in range(dimension)
    ]
    first_vector[0] = 1.0

    second_vector = [
        0.0
        for _ in range(dimension)
    ]
    second_vector[1] = 1.0

    return [
        VectorRecord(
            id=str(uuid4()),
            vector=first_vector,
            metadata={
                "category": "AI",
                "price": 5000,
            },
        ),
        VectorRecord(
            id=str(uuid4()),
            vector=second_vector,
            metadata={
                "category": "Sports",
                "price": 15000,
            },
        ),
    ]


def _vectors_match(
    actual: list[float],
    expected: list[float],
) -> bool:
    if len(actual) != len(expected):
        return False

    return all(
        isclose(
            actual_value,
            expected_value,
            rel_tol=1e-5,
            abs_tol=1e-6,
        )
        for actual_value, expected_value
        in zip(actual, expected)
    )


def _check_upsert_get(
    db: VectorDatabase,
    collection: str,
    records: list[VectorRecord],
    checks: list[ComplianceCheck],
) -> None:
    try:
        db.upsert(
            collection=collection,
            records=records,
        )

        fetched = db.get(
            collection=collection,
            ids=[
                record.id
                for record in records
            ],
        )

        fetched_by_id = {
            record.id: record
            for record in fetched
        }
        expected_ids = {
            record.id
            for record in records
        }

        if set(fetched_by_id) != expected_ids:
            raise AssertionError(
                "get() did not return exactly "
                "the inserted record IDs."
            )

        for expected in records:
            actual = fetched_by_id[expected.id]

            if not _vectors_match(
                actual.vector,
                expected.vector,
            ):
                raise AssertionError(
                    "Vector changed after "
                    "upsert/get."
                )

            if actual.metadata != expected.metadata:
                raise AssertionError(
                    "Metadata changed after "
                    "upsert/get."
                )

        checks.append(
            _passed(
                "upsert_get",
                f"{len(records)} records",
            )
        )

    except Exception as error:  # noqa: BLE001
        checks.append(
            _failed(
                "upsert_get",
                error,
            )
        )


def _check_search(
    db: VectorDatabase,
    collection: str,
    records: list[VectorRecord],
    checks: list[ComplianceCheck],
) -> None:
    try:
        results = db.search(
            collection=collection,
            vector=records[0].vector,
            top_k=2,
        )

        if not results:
            raise AssertionError(
                "search() returned no results."
            )

        if results[0].id != records[0].id:
            raise AssertionError(
                "search() did not rank the "
                "nearest record first."
            )

        checks.append(
            _passed(
                "search",
                f"{len(results)} results",
            )
        )

    except Exception as error:  # noqa: BLE001
        checks.append(
            _failed(
                "search",
                error,
            )
        )


def _check_filter(
    db: VectorDatabase,
    collection: str,
    records: list[VectorRecord],
    checks: list[ComplianceCheck],
) -> None:
    name = "filter_eq"

    try:
        capabilities = db.capabilities()

        if not capabilities.metadata_filter:
            checks.append(
                _skipped(
                    name,
                    "Driver does not declare "
                    "metadata filter support.",
                )
            )
            return

        if "$eq" not in capabilities.filter_operators:
            checks.append(
                _skipped(
                    name,
                    "Driver does not declare "
                    "$eq support.",
                )
            )
            return

        results = db.search(
            collection=collection,
            vector=records[0].vector,
            top_k=10,
            filters={
                "category": {
                    "$eq": "AI",
                }
            },
        )

        result_ids = {
            result.id
            for result in results
        }

        if records[0].id not in result_ids:
            raise AssertionError(
                "$eq filter did not return "
                "the matching record."
            )

        if records[1].id in result_ids:
            raise AssertionError(
                "$eq filter returned a "
                "non-matching record."
            )

        checks.append(
            _passed(name)
        )

    except Exception as error:  # noqa: BLE001
        checks.append(
            _failed(
                name,
                error,
            )
        )


def _check_scan(
    db: VectorDatabase,
    collection: str,
    records: list[VectorRecord],
    checks: list[ComplianceCheck],
) -> None:
    try:
        scan = getattr(
            db,
            "scan",
            None,
        )

        if not callable(scan):
            raise TypeError(
                "Driver does not implement "
                "scan()."
            )

        scanned = list(
            scan(
                collection,
                batch_size=1,
            )
        )

        scanned_ids = [
            record.id
            for record in scanned
        ]
        expected_ids = {
            record.id
            for record in records
        }

        if (
            set(scanned_ids) != expected_ids
            or len(scanned_ids) != len(expected_ids)
        ):
            raise AssertionError(
                "scan() did not return exactly "
                "the inserted records."
            )

        checks.append(
            _passed(
                "scan",
                f"{len(scanned)} records",
            )
        )

    except Exception as error:  # noqa: BLE001
        checks.append(
            _failed(
                "scan",
                error,
            )
        )


def _check_delete(
    db: VectorDatabase,
    collection: str,
    records: list[VectorRecord],
    checks: list[ComplianceCheck],
) -> None:
    try:
        deleted_id = records[1].id

        db.delete(
            collection=collection,
            ids=[deleted_id],
        )

        remaining = db.get(
            collection=collection,
            ids=[deleted_id],
        )

        if remaining:
            raise AssertionError(
                "Deleted record is still "
                "returned by get()."
            )

        checks.append(
            _passed("delete")
        )

    except Exception as error:  # noqa: BLE001
        checks.append(
            _failed(
                "delete",
                error,
            )
        )


def run_compliance(
    db: VectorDatabase,
    *,
    collection_prefix: str = (
        "vecport_compliance"
    ),
    dimension: int = 3,
    cleanup: bool = True,
) -> ComplianceReport:
    if dimension < 2:
        raise ValueError(
            "Compliance dimension "
            "must be at least 2."
        )

    collection = _temporary_collection_name(
        collection_prefix
    )
    checks: list[ComplianceCheck] = []
    records = _sample_records(dimension)
    created = False

    try:
        try:
            db.create_collection(
                name=collection,
                dimension=dimension,
            )
            created = True
            checks.append(
                _passed("create_collection")
            )

        except Exception as error:  # noqa: BLE001
            checks.append(
                _failed(
                    "create_collection",
                    error,
                )
            )

            return ComplianceReport(
                collection=collection,
                checks=tuple(checks),
            )

        _check_upsert_get(
            db,
            collection,
            records,
            checks,
        )
        _check_search(
            db,
            collection,
            records,
            checks,
        )
        _check_filter(
            db,
            collection,
            records,
            checks,
        )
        _check_scan(
            db,
            collection,
            records,
            checks,
        )
        _check_delete(
            db,
            collection,
            records,
            checks,
        )

    finally:
        if created and cleanup:
            try:
                db.delete_collection(
                    collection
                )
                checks.append(
                    _passed("cleanup")
                )

            except Exception as error:  # noqa: BLE001
                checks.append(
                    _failed(
                        "cleanup",
                        error,
                    )
                )

    return ComplianceReport(
        collection=collection,
        checks=tuple(checks),
    )
