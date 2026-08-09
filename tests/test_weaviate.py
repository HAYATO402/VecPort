import os

import pytest

from vecport import VectorRecord, connect


@pytest.mark.skipif(
    "WEAVIATE_URL" not in os.environ
    or "WEAVIATE_API_KEY" not in os.environ,
    reason="Weaviate credentials not configured",
)
def test_weaviate_upsert_and_search():

    db = connect(
        "weaviate",
        url=os.environ["WEAVIATE_URL"],
        api_key=os.environ["WEAVIATE_API_KEY"],
    )

    name = "vecport_test"

    try:
        # 前回のCollectionを削除
        db.delete_collection(name)

        # Collectionを作り直す
        db.create_collection(
            name,
            dimension=3,
        )

        test_id = "550e8400-e29b-41d4-a716-446655440000"

        # データ保存
        db.upsert(
            name,
            [
                VectorRecord(
                    id=test_id,
                    vector=[1.0, 0.0, 0.0],
                    metadata={
                        "type": "AI"
                    },
                )
            ],
        )

        # まずgetで保存確認
        records = db.get(
            name,
            [test_id],
        )

        print("GET results:", records)

        assert len(records) == 1
        assert records[0].id == test_id

        # その後search
        results = db.search(
            name,
            [1.0, 0.0, 0.0],
            top_k=1,
        )

        print("SEARCH results:", results)

        assert len(results) >= 1
        assert results[0].id == test_id

    finally:
        try:
            db.delete_collection(name)
        finally:
            db.client.close()