import argparse
import os
import json

from vecport import connect_url

from vecport.core.migration import (
    migrate_collection,
)

from vecport.core.migration import (
    migrate_collection,
    verify_migration,
)

from vecport.core.benchmark import (
    benchmark_search,
    compare_benchmarks,
)

from vecport.core.benchmark_dataset import (
    make_benchmark_query,
)


def _connection_overrides(
    prefix: str,
) -> dict:

    overrides = {}

    api_key = os.environ.get(
        f"VECPORT_{prefix}_API_KEY"
    )

    password = os.environ.get(
        f"VECPORT_{prefix}_PASSWORD"
    )

    token = os.environ.get(
        f"VECPORT_{prefix}_TOKEN"
    )

    if api_key:
        overrides["api_key"] = api_key

    if password:
        overrides["password"] = password

    if token:
        overrides["token"] = token

    return overrides

def _close_driver(
    db,
) -> None:

    close = getattr(
        db,
        "close",
        None,
    )

    if callable(close):
        close()
        return

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


def _parse_vector(
    value: str,
) -> list[float]:

    parts = [
        part.strip()
        for part in value.split(",")
    ]

    if (
        not parts
        or any(
            not part
            for part in parts
        )
    ):
        raise argparse.ArgumentTypeError(
            "Vector must be a comma-separated "
            "list of numbers"
        )

    try:
        return [
            float(part)
            for part in parts
        ]

    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "Vector values must be numbers"
        ) from exc

def _parse_benchmark_target(
    value: str,
) -> tuple[str, str]:

    if "=" not in value:
        raise ValueError(
            "Benchmark target must use LABEL=URL format"
        )

    label, url = value.split(
        "=",
        1,
    )

    label = label.strip()
    url = url.strip()

    if not label or not url:
        raise ValueError(
            "Benchmark target must use LABEL=URL format"
        )

    return label, url


def main():

    parser = argparse.ArgumentParser(
        prog="vecport"
    )

    commands = parser.add_subparsers(
        dest="command",
        required=True,
    )

    migrate = commands.add_parser(
        "migrate"
    )

    migrate.add_argument(
        "--from",
        dest="source_url",
        required=True,
    )

    migrate.add_argument(
        "--to",
        dest="target_url",
        required=True,
    )

    migrate.add_argument(
        "--collection",
        required=True,
    )

    migrate.add_argument(
        "--target-collection",
    )

    migrate.add_argument(
        "--batch-size",
        type=int,
        default=100,
    )

    migrate.add_argument(
        "--recreate-target",
        action="store_true",
    )

    migrate.add_argument(
        "--dry-run",
        action="store_true",
    )

    migrate.add_argument(
        "--verify",
        action="store_true",
        help=(
            "Verify IDs, vectors, and metadata "
            "after migration"
        ),
    )

    benchmark = commands.add_parser(
        "benchmark",
        help="Benchmark vector search performance",
    )

    benchmark.add_argument(
        "--url",
        help="VecPort connection URL",
    )

    benchmark.add_argument(
        "--collection",
        required=True,
        help="Collection to benchmark",
    )

    benchmark.add_argument(
        "--vector",
        type=_parse_vector,
        help=(
            "Query vector as comma-separated "
            "numbers, e.g. 1,0,0"
        ),
    )

    benchmark.add_argument(
        "--top-k",
        type=int,
        default=10,
    )

    benchmark.add_argument(
        "--iterations",
        type=int,
        default=20,
    )

    benchmark.add_argument(
        "--warmup",
        type=int,
        default=3,
    )

    benchmark.add_argument(
        "--label",
    )

    benchmark.add_argument(
        "benchmark_action",
        nargs="?",
        choices=[
            "compare",
        ],
    )

    benchmark.add_argument(
        "--target",
        action="append",
        default=[],
        help=(
            "Benchmark target in LABEL=URL format. "
            "Repeat for multiple databases."
        ),
    )

    benchmark.add_argument(
        "--dimension",
        type=int,
        )

    benchmark.add_argument(
        "--query-seed",
        type=int,
        default=999,
    )

    benchmark.add_argument(
        "--output",
    )

    args = parser.parse_args()

    if (
        args.command == "migrate"
        and args.dry_run
        and args.verify
    ):
        parser.error(
            "--verify cannot be used with --dry-run"
        )

    if args.command == "migrate":

        source = connect_url(
            args.source_url,
            **_connection_overrides(
                "SOURCE"
            ),
        )

        target = connect_url(
            args.target_url,
            **_connection_overrides(
                "TARGET"
            ),
        )

        try:

            report = migrate_collection(
                source,
                target,
                collection=args.collection,
                target_collection=(
                    args.target_collection
                ),
                batch_size=args.batch_size,
                recreate_target=(
                    args.recreate_target
                ),
                dry_run=args.dry_run,
            )

            print(
                "Migration complete"
            )

            print(
                f"Source: "
                f"{report.source_collection}"
            )

            print(
                f"Target: "
                f"{report.target_collection}"
            )

            print(
                f"Scanned: "
                f"{report.scanned}"
            )

            print(
                f"Migrated: "
                f"{report.migrated}"
            )

            print(
                f"Dimension: "
                f"{report.dimension}"
            )

            print(
                f"Dry run: "
                f"{report.dry_run}"
            )

            if args.verify:

                verification = verify_migration(
                    source,
                    target,
                    source_collection=args.collection,
                    target_collection=(
                        args.target_collection
                    ),
                    batch_size=args.batch_size,
                )

                print()
                print(
                    "Verification report"
                )

                print(
                    f"Source count: "
                    f"{verification.source_count}"
                )

                print(
                    f"Target count: "
                    f"{verification.target_count}"
                )

                print(
                    f"Matched IDs: "
                    f"{verification.matched_ids}"
                )

                print(
                    f"Missing IDs: "
                    f"{verification.missing_ids}"
                )

                print(
                    f"Extra records: "
                    f"{verification.extra_records}"
                )

                print(
                    f"Dimensions: "
                    f"{'OK' if verification.dimensions_ok else 'FAILED'}"
                )

                print(
                    f"Vectors: "
                    f"{'OK' if verification.vectors_ok else 'FAILED'}"
                )

                print(
                    f"Metadata: "
                    f"{'OK' if verification.metadata_ok else 'FAILED'}"
                )

                print()

                if verification.passed:
                    print(
                        "Migration verification: PASSED"
                    )

                else:
                    raise MigrationError(
                        "Migration verification failed"
                    )

        finally:

            _close_driver(source)
            _close_driver(target)

    elif args.command == "benchmark":

        if args.top_k <= 0:
            parser.error(
                "--top-k must be greater than 0"
            )

        if args.iterations <= 0:
            parser.error(
                "--iterations must be greater than 0"
            )

        if args.warmup < 0:
            parser.error(
                "--warmup cannot be negative"
            )

        if args.vector:

            query_vector = args.vector

        elif args.dimension:

            if args.dimension <= 0:
                parser.error(
                    "--dimension must be greater than 0"
                )

            query_vector = make_benchmark_query(
                dimension=args.dimension,
                seed=args.query_seed,
            )

        else:

            parser.error(
                "Provide either --vector or --dimension"
            )

        # -------------------------
        # Compare mode
        # -------------------------

        if args.benchmark_action == "compare":

            if len(args.target) < 2:
                parser.error(
                    "benchmark compare requires "
                    "at least two --target values"
                )

            connections = []

            try:

                for raw_target in args.target:

                    try:

                        label, url = (
                            _parse_benchmark_target(
                                raw_target
                            )
                        )

                    except ValueError as exc:

                        parser.error(
                            str(exc)
                        )

                    db = connect_url(
                        url
                    )

                    connections.append(
                        (
                            label,
                            db,
                        )
                    )


                comparison = compare_benchmarks(
                    connections,
                    collection=args.collection,
                    vector=query_vector,
                    top_k=args.top_k,
                    iterations=args.iterations,
                    warmup=args.warmup,
                )


                print()

                print(
                    f"{'Backend':<18}"
                    f"{'Avg':>12}"
                    f"{'p50':>12}"
                    f"{'p95':>12}"
                    f"{'p99':>12}"
                    f"{'Success':>12}"
                )

                print(
                    "-" * 78
                )


                for report in comparison.reports:

                    print(
                        f"{report.label:<18}"
                        f"{report.average_ms:>10.3f}ms"
                        f"{report.p50_ms:>10.3f}ms"
                        f"{report.p95_ms:>10.3f}ms"
                        f"{report.p99_ms:>10.3f}ms"
                        f"{report.success_rate:>11.2f}%"
                    )

                if args.output:

                    payload = {
                        "collection": args.collection,
                        "top_k": args.top_k,
                        "iterations": args.iterations,
                        "warmup": args.warmup,
                        "results": [
                            {
                                "label": report.label,
                                "requests": report.requests,
                                "successes": report.successes,
                                "failures": report.failures,
                                "success_rate": report.success_rate,
                                "average_ms": report.average_ms,
                                "p50_ms": report.p50_ms,
                                "p95_ms": report.p95_ms,
                                "p99_ms": report.p99_ms,
                            }
                            for report in comparison.reports
                        ],
                    }

                    with open(
                        args.output,
                        "w",
                        encoding="utf-8",
                    ) as file:

                        json.dump(
                            payload,
                            file,
                            indent=2,
                        )

                    print()
                    print(
                        f"Report written to: {args.output}"
                    )


            finally:

                for _, db in connections:

                    _close_driver(
                        db
                    )


        # -------------------------
        # Single benchmark mode
        # -------------------------

        else:

            if not args.url:
                parser.error(
                    "--url is required unless "
                    "using benchmark compare"
                )

            db = connect_url(
                args.url,
                **_connection_overrides(
                    "BENCHMARK"
                ),
            )

            try:

                label = args.label

                if not label:
                    label = (
                        args.url
                        .split(
                            "://",
                            1,
                        )[-1]
                        .split(
                            "?",
                            1,
                        )[0]
                    )


                report = benchmark_search(
                    db,
                    label=label,
                    collection=args.collection,
                    vector=query_vector,
                    top_k=args.top_k,
                    iterations=args.iterations,
                    warmup=args.warmup,
                )


                print()
                print(
                    "Benchmark complete"
                )

                print(
                    f"Database: "
                    f"{report.label}"
                )

                print(
                    f"Requests: "
                    f"{report.requests}"
                )

                print(
                    f"Successes: "
                    f"{report.successes}"
                )

                print(
                    f"Failures: "
                    f"{report.failures}"
                )

                print(
                    f"Success rate: "
                    f"{report.success_rate:.2f}%"
                )

                print()

                print(
                    f"Average: "
                    f"{report.average_ms:.3f} ms"
                )

                print(
                    f"p50: "
                    f"{report.p50_ms:.3f} ms"
                )

                print(
                    f"p95: "
                    f"{report.p95_ms:.3f} ms"
                )

                print(
                    f"p99: "
                    f"{report.p99_ms:.3f} ms"
                )


            finally:

                _close_driver(
                    db
                )

if __name__ == "__main__":
    main()