from vecport import VectorRecord

TEST_ID = "550e8400-e29b-41d4-a716-446655440000"


def run_vector_database_contract(db):

    collection = "vecport_contract_test"

    db.delete_collection(collection)

    db.create_collection(
        collection,
        dimension=3,
    )

    db.upsert(
        collection,
        [
            VectorRecord(
                id=TEST_ID,
                vector=[1.0, 0.0, 0.0],
                metadata={
                    "category": "AI"
                },
            )
        ],
    )

    records = db.get(
        collection,
        [TEST_ID],
    )

    assert len(records) == 1
    assert records[0].id == TEST_ID

    results = db.search(
        collection,
        [1.0, 0.0, 0.0],
        top_k=1,
    )

    assert len(results) == 1
    assert results[0].id == TEST_ID

    db.delete(
        collection,
        [TEST_ID],
    )

    records = db.get(
        collection,
        [TEST_ID],
    )

    assert len(records) == 0

    db.delete_collection(collection)