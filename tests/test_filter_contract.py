from vecport import VectorRecord

from tests.helpers import wait_for_search


FILTER_ID_1 = "550e8400-e29b-41d4-a716-446655440100"
FILTER_ID_2 = "550e8400-e29b-41d4-a716-446655440101"


def run_filter_contract(db):

    collection = "vecport_test"

    db.delete_collection(collection)

    try:

        db.create_collection(
            collection,
            dimension=3,
        )

        db.upsert(
            collection,
            [
                VectorRecord(
                    id=FILTER_ID_1,
                    vector=[1.0, 0.0, 0.0],
                    metadata={
                        "category": "AI",
                        "price": 5000,
                    },
                ),
                VectorRecord(
                    id=FILTER_ID_2,
                    vector=[0.99, 0.01, 0.0],
                    metadata={
                        "category": "Sports",
                        "price": 15000,
                    },
                ),
            ],
        )

        results = wait_for_search(
            db,
            collection,
            [1.0, 0.0, 0.0],
            top_k=10,
            filters={
                "$and": [
                    {
                        "category": {
                            "$eq": "AI"
                        }
                    },
                    {
                        "price": {
                            "$lt": 10000
                        }
                    },
                ]
            },
            expected_count=1,
        )

        assert len(results) == 1
        assert results[0].metadata["category"] == "AI"
        assert results[0].metadata["price"] == 5000

    finally:

        db.delete_collection(collection)