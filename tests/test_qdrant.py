from tests.test_contract import run_vector_database_contract
from vecport import VectorRecord, connect


def test_qdrant_contract():

    db = connect("qdrant")

    run_vector_database_contract(db)


def test_qdrant_collection_info_reports_record_count():
    db = connect("qdrant")
    db.create_collection(
        "record-count",
        dimension=3,
    )
    db.upsert(
        "record-count",
        [
            VectorRecord(
                id="00000000-0000-0000-0000-000000000001",
                vector=[1.0, 0.0, 0.0],
            ),
            VectorRecord(
                id="00000000-0000-0000-0000-000000000002",
                vector=[0.0, 1.0, 0.0],
            ),
        ],
    )

    info = db.collection_info("record-count")

    assert info.record_count == 2
