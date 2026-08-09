from vecport import VectorRecord, connect


def test_qdrant_upsert_and_search():

    db = connect("qdrant")

    db.create_collection(
        name="test",
        dimension=3,
    )

    db.upsert(
        collection="test",
        records=[
            VectorRecord(
                id="550e8400-e29b-41d4-a716-446655440000",
                vector=[1.0, 0.0, 0.0],
                metadata={
                    "type": "AI"
                },
            )
        ],
    )

    results = db.search(
        collection="test",
        vector=[1.0, 0.0, 0.0],
        top_k=1,
    )

    assert len(results) == 1
    assert results[0].id == "550e8400-e29b-41d4-a716-446655440000"