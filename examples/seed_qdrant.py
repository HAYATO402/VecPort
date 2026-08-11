from vecport import (
    VectorRecord,
    connect_url,
)


db = connect_url(
    "vecport://qdrant?path=.vecport-qdrant"
)

collection = "documents"


try:
    db.delete_collection(
        collection
    )

except Exception:
    pass


db.create_collection(
    collection,
    dimension=3,
)


db.upsert(
    collection,
    [
        VectorRecord(
            id="550e8400-e29b-41d4-a716-446655440301",
            vector=[
                1.0,
                0.0,
                0.0,
            ],
            metadata={
                "category": "AI",
                "title": "Document 1",
            },
        ),

        VectorRecord(
            id="550e8400-e29b-41d4-a716-446655440302",
            vector=[
                0.9,
                0.1,
                0.0,
            ],
            metadata={
                "category": "Finance",
                "title": "Document 2",
            },
        ),

        VectorRecord(
            id="550e8400-e29b-41d4-a716-446655440303",
            vector=[
                0.8,
                0.2,
                0.0,
            ],
            metadata={
                "category": "Sports",
                "title": "Document 3",
            },
        ),
    ],
)


print(
    "Qdrant seed complete."
)