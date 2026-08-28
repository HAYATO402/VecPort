from vecport.core.models import CollectionInfo
from vecport.drivers.milvus import (
    MilvusDriver,
    _migration_index_type,
)


def _qdrant_hnsw_info(
    *,
    record_count: int | None,
    dimension: int | None = 128,
) -> CollectionInfo:
    return CollectionInfo(
        name="documents",
        exists=True,
        record_count=record_count,
        dimension=dimension,
        distance_metric="cosine",
        index_type="HNSW",
        index_params={
            "full_scan_threshold": 10_000,
        },
    )


def test_small_qdrant_collection_uses_exact_milvus_index():
    info = _qdrant_hnsw_info(
        record_count=10_000,
    )

    assert _migration_index_type(info) == "FLAT"


def test_large_qdrant_collection_keeps_milvus_autoindex():
    info = _qdrant_hnsw_info(
        record_count=100_000,
    )

    assert _migration_index_type(info) == "AUTOINDEX"


def test_unknown_source_size_keeps_milvus_autoindex():
    info = _qdrant_hnsw_info(
        record_count=None,
    )

    assert _migration_index_type(info) == "AUTOINDEX"


def test_flat_source_keeps_exact_milvus_index():
    info = CollectionInfo(
        name="documents",
        record_count=100_000,
        dimension=128,
        index_type="FLAT",
    )

    assert _migration_index_type(info) == "FLAT"


def test_milvus_prepares_recent_writes_for_search():
    calls = []

    class FakeClient:
        def flush(self, *, collection_name):
            calls.append(("flush", collection_name))

        def refresh_load(self, *, collection_name):
            calls.append(("refresh_load", collection_name))

    driver = object.__new__(MilvusDriver)
    driver.client = FakeClient()

    driver.prepare_for_search("documents")

    assert calls == [
        ("flush", "documents"),
        ("refresh_load", "documents"),
    ]


def test_milvus_readiness_supports_older_clients():
    calls = []

    class FakeClient:
        def flush(self, *, collection_name):
            calls.append(("flush", collection_name))

        def load_collection(self, *, collection_name):
            calls.append(("load", collection_name))

    driver = object.__new__(MilvusDriver)
    driver.client = FakeClient()

    driver.prepare_for_search("documents")

    assert calls == [
        ("flush", "documents"),
        ("load", "documents"),
    ]
