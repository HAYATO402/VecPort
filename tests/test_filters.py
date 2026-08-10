from vecport import VectorRecord, connect


def test_qdrant_eq_filter():

    db = connect("qdrant")

    collection = "vecport_filter_eq_test"

    db.delete_collection(collection)

    db.create_collection(
        collection,
        dimension=3,
    )

    db.upsert(
        collection,
        [
            VectorRecord(
                id="550e8400-e29b-41d4-a716-446655440000",
                vector=[1.0, 0.0, 0.0],
                metadata={
                    "category": "AI",
                    "price": 5000,
                },
            ),
            VectorRecord(
                id="550e8400-e29b-41d4-a716-446655440001",
                vector=[0.99, 0.01, 0.0],
                metadata={
                    "category": "Sports",
                    "price": 3000,
                },
            ),
        ],
    )

    results = db.search(
        collection,
        [1.0, 0.0, 0.0],
        top_k=10,
        filters={
            "category": {
                "$eq": "AI"
            }
        },
    )

    assert len(results) == 1
    assert results[0].metadata["category"] == "AI"

    db.delete_collection(collection)


def test_qdrant_lt_filter():

    db = connect("qdrant")

    collection = "vecport_filter_lt_test"

    db.delete_collection(collection)

    db.create_collection(
        collection,
        dimension=3,
    )

    db.upsert(
        collection,
        [
            VectorRecord(
                id="550e8400-e29b-41d4-a716-446655440010",
                vector=[1.0, 0.0, 0.0],
                metadata={
                    "category": "AI",
                    "price": 5000,
                },
            ),
            VectorRecord(
                id="550e8400-e29b-41d4-a716-446655440011",
                vector=[0.99, 0.01, 0.0],
                metadata={
                    "category": "Sports",
                    "price": 15000,
                },
            ),
        ],
    )

    results = db.search(
        collection,
        [1.0, 0.0, 0.0],
        top_k=10,
        filters={
            "price": {
                "$lt": 10000
            }
        },
    )

    assert len(results) == 1
    assert results[0].metadata["price"] == 5000

    db.delete_collection(collection)

def test_qdrant_and_filter():

    db = connect("qdrant")

    collection = "vecport_filter_and_test"

    db.delete_collection(
        collection
    )

    db.create_collection(
        collection,
        dimension=3,
    )

    db.upsert(
        collection,
        [
            VectorRecord(
                id="550e8400-e29b-41d4-a716-446655440020",
                vector=[1.0, 0.0, 0.0],
                metadata={
                    "category": "AI",
                    "price": 5000,
                },
            ),
            VectorRecord(
                id="550e8400-e29b-41d4-a716-446655440021",
                vector=[0.99, 0.01, 0.0],
                metadata={
                    "category": "AI",
                    "price": 15000,
                },
            ),
            VectorRecord(
                id="550e8400-e29b-41d4-a716-446655440022",
                vector=[0.98, 0.02, 0.0],
                metadata={
                    "category": "Sports",
                    "price": 3000,
                },
            ),
        ],
    )

    results = db.search(
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
                }
            ]
        },
    )

    assert len(results) == 1

    assert (
        results[0].metadata["category"]
        == "AI"
    )

    assert (
        results[0].metadata["price"]
        == 5000
    )

    db.delete_collection(
        collection
    )

def test_qdrant_or_filter():

    db = connect("qdrant")

    collection = "vecport_filter_or_test"

    db.delete_collection(
        collection
    )

    db.create_collection(
        collection,
        dimension=3,
    )

    db.upsert(
        collection,
        [
            VectorRecord(
                id="550e8400-e29b-41d4-a716-446655440030",
                vector=[1.0, 0.0, 0.0],
                metadata={
                    "category": "AI",
                    "price": 15000,
                },
            ),
            VectorRecord(
                id="550e8400-e29b-41d4-a716-446655440031",
                vector=[0.99, 0.01, 0.0],
                metadata={
                    "category": "Sports",
                    "price": 5000,
                },
            ),
            VectorRecord(
                id="550e8400-e29b-41d4-a716-446655440032",
                vector=[0.98, 0.02, 0.0],
                metadata={
                    "category": "Sports",
                    "price": 15000,
                },
            ),
        ],
    )

    results = db.search(
        collection,
        [1.0, 0.0, 0.0],
        top_k=10,
        filters={
            "$or": [
                {
                    "category": {
                        "$eq": "AI"
                    }
                },
                {
                    "price": {
                        "$lt": 10000
                    }
                }
            ]
        },
    )

    assert len(results) == 2

    categories = [
        result.metadata["category"]
        for result in results
    ]

    prices = [
        result.metadata["price"]
        for result in results
    ]

    assert "AI" in categories
    assert 5000 in prices

    db.delete_collection(
        collection
    )

def test_qdrant_in_filter():

    db = connect("qdrant")

    collection = "vecport_filter_in_test"

    db.delete_collection(collection)

    db.create_collection(
        collection,
        dimension=3,
    )

    db.upsert(
        collection,
        [
            VectorRecord(
                id="550e8400-e29b-41d4-a716-446655440040",
                vector=[1.0, 0.0, 0.0],
                metadata={
                    "category": "AI",
                },
            ),
            VectorRecord(
                id="550e8400-e29b-41d4-a716-446655440041",
                vector=[0.99, 0.01, 0.0],
                metadata={
                    "category": "Finance",
                },
            ),
            VectorRecord(
                id="550e8400-e29b-41d4-a716-446655440042",
                vector=[0.98, 0.02, 0.0],
                metadata={
                    "category": "Sports",
                },
            ),
        ],
    )

    results = db.search(
        collection,
        [1.0, 0.0, 0.0],
        top_k=10,
        filters={
            "category": {
                "$in": [
                    "AI",
                    "Finance",
                ]
            }
        },
    )

    assert len(results) == 2

    categories = {
        result.metadata["category"]
        for result in results
    }

    assert categories == {
        "AI",
        "Finance",
    }

    db.delete_collection(collection)