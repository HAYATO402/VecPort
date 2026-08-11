from vecport import connect_url

from vecport.core.benchmark_dataset import (
    load_benchmark_dataset,
)


COLLECTION = "vecport_benchmark_50k_128"
COUNT = 50_000
DIMENSION = 128
BATCH_SIZE = 500
SEED = 42


targets = [
    (
        "qdrant",
        "vecport://qdrant?url=http://localhost:6333",
    ),
    (
        "milvus",
        "vecport://milvus?uri=http://localhost:19530",
    ),
]


for label, url in targets:

    print()
    print(
        f"Loading benchmark dataset into {label}..."
    )

    db = connect_url(
        url
    )

    try:

        report = load_benchmark_dataset(
            db,
            collection=COLLECTION,
            count=COUNT,
            dimension=DIMENSION,
            batch_size=BATCH_SIZE,
            seed=SEED,
            recreate=True,
        )

        print(
            f"{label}: complete"
        )

        print(
            f"Records: "
            f"{report.count}"
        )

        print(
            f"Dimension: "
            f"{report.dimension}"
        )

        print(
            f"Elapsed: "
            f"{report.elapsed_seconds:.2f}s"
        )

        print(
            f"Throughput: "
            f"{report.records_per_second:.2f} records/s"
        )

    finally:

        close = getattr(
            db,
            "close",
            None,
        )

        if callable(close):
            close()

        else:

            client = getattr(
                db,
                "client",
                None,
            )

            close = getattr(
                client,
                "close",
                None,
            )

            if callable(close):
                close()