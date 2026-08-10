import time

from vecport import VectorRecord, connect


print("1. Milvusに接続します")

db = connect("pgvector")


print("2. Collectionを作成します")

db.create_collection(
    name="documents",
    dimension=3,
)


print("3. データを保存します")

db.upsert(
    collection="documents",
    records=[
        VectorRecord(
            id="1",
            vector=[1.0, 0.0, 0.0],
            metadata={
                "text": "AI"
            },
        )
    ],
)

time.sleep(2)


print("4. 検索します")

results = db.search(
    collection="documents",
    vector=[1.0, 0.0, 0.0],
    top_k=5,
)


print("5. 検索結果件数:", len(results))

for result in results:
    print(result)


if results:
    print("VecPort -> Milvus 接続成功")
else:
    print("検索結果が0件です")