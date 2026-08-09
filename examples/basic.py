import os

from vecport import VectorRecord, connect


# =========================
# ここだけでDBを選択
# =========================

db = connect(
    "pinecone",
    api_key=os.environ["PINECONE_API_KEY"],
)


# =========================
# ここから下は共通コード
# =========================

db.create_collection(
    name="documents",
    dimension=3,
)


db.upsert(
    collection="documents",
    records=[
        VectorRecord(
            id="550e8400-e29b-41d4-a716-446655440000",
            vector=[
                1.0,
                0.0,
                0.0,
            ],
            metadata={
                "text": "AI"
            },
        )
    ],
)


results = db.search(
    collection="documents",
    vector=[
        1.0,
        0.0,
        0.0,
    ],
    top_k=5,
)


print("Search results:")

for result in results:
    print(
        result.id,
        result.score,
        result.metadata,
    )