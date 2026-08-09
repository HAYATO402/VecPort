from vecport import VectorRecord, connect


db = connect("qdrant")


db.create_collection(
    name="documents",
    dimension=3,
)


db.upsert(
    collection="documents",
    records=[
        VectorRecord(
            id="550e8400-e29b-41d4-a716-446655440000",
            vector=[1.0, 0.0, 0.0],
            metadata={
                "text": "AIについての文章"
            },
        ),
        VectorRecord(
            id="550e8400-e29b-41d4-a716-446655440001",
            vector=[0.0, 1.0, 0.0],
            metadata={
                "text": "サッカーについての文章"
            },
        ),
    ],
)


results = db.search(
    collection="documents",
    vector=[1.0, 0.0, 0.0],
    top_k=2,
)


for result in results:
    print(
        result.id,
        result.score,
        result.metadata,
    )