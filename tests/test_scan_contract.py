from vecport import VectorRecord

SCAN_ID_1 = (
    "550e8400-e29b-41d4-a716-446655440201"
)

SCAN_ID_2 = (
    "550e8400-e29b-41d4-a716-446655440202"
)

SCAN_ID_3 = (
    "550e8400-e29b-41d4-a716-446655440203"
)


def run_scan_contract(db):

    collection = "vecport_scan_contract"

    db.delete_collection(
        collection
    )

    try:

        db.create_collection(
            collection,
            dimension=3,
        )

        db.upsert(
            collection,
            [
                VectorRecord(
                    id=SCAN_ID_1,
                    vector=[
                        1.0,
                        0.0,
                        0.0,
                    ],
                    metadata={
                        "category": "AI",
                    },
                ),
                VectorRecord(
                    id=SCAN_ID_2,
                    vector=[
                        0.9,
                        0.1,
                        0.0,
                    ],
                    metadata={
                        "category": "Finance",
                    },
                ),
                VectorRecord(
                    id=SCAN_ID_3,
                    vector=[
                        0.8,
                        0.2,
                        0.0,
                    ],
                    metadata={
                        "category": "Sports",
                    },
                ),
            ],
        )

        records = list(
            db.scan(
                collection,
                batch_size=2,
            )
        )

        assert len(records) == 3

        ids = {
            record.id
            for record in records
        }

        assert ids == {
            SCAN_ID_1,
            SCAN_ID_2,
            SCAN_ID_3,
        }

        for record in records:

            assert len(
                record.vector
            ) == 3

            assert isinstance(
                record.metadata,
                dict,
            )

    finally:

        db.delete_collection(
            collection
        )