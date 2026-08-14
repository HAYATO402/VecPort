import argparse
import os

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

from vecport.core.config import load_config

from vecport.core.reporting import (
    write_csv_report,
    write_json_report,
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
    )

    migrate.add_argument(
        "--to",
        dest="target_url",
    )

    migrate.add_argument(
        "--collection",
    )

    migrate.add_argument(
        "--target-collection",
    )

    migrate.add_argument(
        "--batch-size",
        type=int,
        default=None,
    )

    migrate.add_argument(
        "--recreate-target",
        action="store_true",
        default=None,
    )

    migrate.add_argument(
        "--dry-run",
        action="store_true",
        default=None,
    )

    migrate.add_argument(
        "--verify",
        action="store_true",
        default=None,
        help=(
            "Verify IDs, vectors, and metadata "
            "after migration"
        ),
    )

    migrate.add_argument(
        "--output",
        help="Write the migration report to a file.",
    )

    migrate.add_argument(
        "--format",
        choices=[
            "json",
            "csv",
        ],
        default=None,
        help="Migration report format.",
    )

    migrate.add_argument(
        "--config",
        help="Load migration settings from a YAML file.",
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
        default=None,
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
        default=None,
    )

    benchmark.add_argument(
        "--iterations",
        type=int,
        default=None,
    )

    benchmark.add_argument(
        "--warmup",
        type=int,
        default=None,
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
        default=None,
        help=(
            "Benchmark target in LABEL=URL format. "
            "Repeat for multiple databases."
        ),
    )

    benchmark.add_argument(
        "--dimension",
        type=int,
        default=None,
        )

    benchmark.add_argument(
        "--query-seed",
        type=int,
        default=999,
    )

    benchmark.add_argument(
        "--output",
    )

    benchmark.add_argument(
        "--format",
        choices=[
            "json",
            "csv",
        ],
        default=None,
        help="Output report format.",
    )

    benchmark.add_argument(
        "--config",
        help="Load benchmark settings from a YAML file.",
    )

    args = parser.parse_args()

    config = {}

    if getattr(
        args,
        "config",
        None,
    ):
        config = load_config(
            args.config
        )

    if args.command == "migrate":

        migration_config = config.get(
            "migration",
            {},
        )

        source_url = (
            args.source_url
            or migration_config.get(
                "from"
            )
        )

        target_url = (
            args.target_url
            or migration_config.get(
                "to"
            )
        )

        collection = (
            args.collection
            or migration_config.get(
                "collection"
            )
        )

        target_collection = (
            args.target_collection
            or migration_config.get(
                "target_collection"
            )
            or collection
        )

        batch_size = (
            args.batch_size
            if args.batch_size is not None
            else migration_config.get(
                "batch_size",
                500,
            )
        )

        recreate_target = (
            args.recreate_target
            if args.recreate_target is not None
            else migration_config.get(
                "recreate_target",
                False,
            )
        )

        dry_run = (
            args.dry_run
            if args.dry_run is not None
            else migration_config.get(
                "dry_run",
                False,
            )
        )

        verify = (
            args.verify
            if args.verify is not None
            else migration_config.get(
                "verify",
                False,
            )
        )

        output_format = (
            args.format
            if args.format is not None
            else migration_config.get(
                "format",
                "json",
            )
        )

        output = (
            args.output
            or migration_config.get(
                "output"
            )
        )

        if not source_url:
            parser.error(
                "Migration source is required. "
                "Use --from or --config."
            )

        if not target_url:
            parser.error(
                "Migration target is required. "
                "Use --to or --config."
            )

        if not collection:
            parser.error(
                "Migration collection is required. "
                "Use --collection or --config."
            )

        if batch_size <= 0:
            parser.error(
                "--batch-size must be greater than 0"
            )

        if dry_run and verify:
            parser.error(
                "--verify cannot be used with --dry-run"
            )

        source = connect_url(
            source_url
        )

        target = connect_url(
            target_url
        )

        try:

            report = migrate_collection(
                source,
                target,
                collection=collection,
                target_collection=target_collection,
                batch_size=batch_size,
                recreate_target=recreate_target,
                dry_run=dry_run,
            )

            verification = None


            print("Migration complete")
            print(
                f"Source: {report.source_collection}"
            )
            print(
                f"Target: {report.target_collection}"
            )
            print(
                f"Scanned: {report.scanned}"
            )
            print(
                f"Migrated: {report.migrated}"
            )


            if verify:

                verification = verify_migration(
                    source,
                    target,
                    source_collection=collection,
                    target_collection=target_collection,
                    batch_size=batch_size,
                )

                print()
                print("Verification report")
                print(
                    f"Source count: {verification.source_count}"
                )
                print(
                    f"Target count: {verification.target_count}"
                )
                print(
                    f"Matched IDs: {verification.matched_ids}"
                )
                print(
                    f"Missing IDs: {verification.missing_ids}"
                )
                print(
                    f"Extra records: {verification.extra_records}"
                )
                print(
                    "Dimensions: "
                    f"{'OK' if verification.dimensions_ok else 'FAILED'}"
                )
                print(
                    "Vectors: "
                    f"{'OK' if verification.vectors_ok else 'FAILED'}"
                )
                print(
                    "Metadata: "
                    f"{'OK' if verification.metadata_ok else 'FAILED'}"
                )

                print()

                if verification.passed:
                    print(
                        "Migration verification: PASSED"
                    )
                else:
                    print(
                        "Migration verification: FAILED"
                    )


            if output:

                payload = {
                    "type": "migration",
                    "migration": {
                        "source_collection": (
                            report.source_collection
                        ),
                        "target_collection": (
                            report.target_collection
                        ),
                        "scanned": report.scanned,
                        "migrated": report.migrated,
                    },
                }

                if verification is not None:

                    payload["verification"] = {
                        "source_count": (
                            verification.source_count
                        ),
                        "target_count": (
                            verification.target_count
                        ),
                        "matched_ids": (
                            verification.matched_ids
                        ),
                        "missing_ids": (
                            verification.missing_ids
                        ),
                        "extra_records": (
                            verification.extra_records
                        ),
                        "dimensions_ok": (
                            verification.dimensions_ok
                        ),
                        "vectors_ok": (
                            verification.vectors_ok
                        ),
                        "metadata_ok": (
                            verification.metadata_ok
                        ),
                        "passed": (
                            verification.passed
                        ),
                    }

                if output_format == "json":

                    write_json_report(
                        output,
                        payload,
                    )

                elif output_format == "csv":

                    row = {
                        "source_collection": (
                            report.source_collection
                        ),
                        "target_collection": (
                            report.target_collection
                        ),
                        "scanned": report.scanned,
                        "migrated": report.migrated,
                        "source_count": "",
                        "target_count": "",
                        "matched_ids": "",
                        "missing_ids": "",
                        "extra_records": "",
                        "dimensions_ok": "",
                        "vectors_ok": "",
                        "metadata_ok": "",
                        "passed": "",
                    }

                    if verification is not None:

                        row.update(
                            {
                                "source_count": (
                                    verification.source_count
                                ),
                                "target_count": (
                                    verification.target_count
                                ),
                                "matched_ids": (
                                    verification.matched_ids
                                ),
                                "missing_ids": (
                                    verification.missing_ids
                                ),
                                "extra_records": (
                                    verification.extra_records
                                ),
                                "dimensions_ok": (
                                    verification.dimensions_ok
                                ),
                                "vectors_ok": (
                                    verification.vectors_ok
                                ),
                                "metadata_ok": (
                                    verification.metadata_ok
                                ),
                                "passed": (
                                    verification.passed
                                ),
                            }
                        )

                    write_csv_report(
                        output,
                        fieldnames=[
                            "source_collection",
                            "target_collection",
                            "scanned",
                            "migrated",
                            "source_count",
                            "target_count",
                            "matched_ids",
                            "missing_ids",
                            "extra_records",
                            "dimensions_ok",
                            "vectors_ok",
                            "metadata_ok",
                            "passed",
                        ],
                        rows=[row],
                    )

                print()
                print(
                    f"Report written to: {output}"
                )

        finally:

            _close_driver(source)
            _close_driver(target)

    elif args.command == "benchmark":


        # -------------------------
        # Compare mode
        # -------------------------

        if args.benchmark_action == "compare":

            benchmark_config = config.get(
                "benchmark",
                {},
            )

            config_targets = []

            for item in benchmark_config.get(
                "targets",
                [],
            ):
                label = item["label"]
                url = item["url"]

                config_targets.append(
                    f"{label}={url}"
                )

            targets = (
                args.target
                or config_targets
            )

            collection = (
                args.collection
                or benchmark_config.get(
                    "collection"
                )
            )

            dimension = (
                args.dimension
                if args.dimension is not None
                else benchmark_config.get(
                    "dimension"
                )
            )

            top_k = (
                args.top_k
                if args.top_k is not None
                else benchmark_config.get(
                    "top_k",
                    10,
                )
            )

            iterations = (
                args.iterations
                if args.iterations is not None
                else benchmark_config.get(
                    "iterations",
                    100,
                )
            )

            warmup = (
                args.warmup
                if args.warmup is not None
                else benchmark_config.get(
                    "warmup",
                    10,
                )
            )

            output_format = (
                args.format
                if args.format is not None
                else benchmark_config.get(
                    "format",
                    "json",
                )
            )

            output = (
                args.output
                or benchmark_config.get(
                    "output"
                )
            )

            if not targets:
                parser.error(
                    "Benchmark targets are required. "
                    "Use --target or --config."
                )

            if len(targets) < 2:
                parser.error(
                    "benchmark compare requires "
                    "at least two --target values"
                )

            if not collection:
                parser.error(
                    "Benchmark collection is required. "
                    "Use --collection or --config."
                )

            if dimension is None:
                parser.error(
                    "Benchmark dimension is required. "
                    "Use --dimension or --config."
                )

            if dimension <= 0:
                parser.error(
                    "--dimension must be greater than 0"
                )

            if top_k <= 0:
                parser.error(
                    "--top-k must be greater than 0"
                )

            if iterations <= 0:
                parser.error(
                    "--iterations must be greater than 0"
                )

            if warmup < 0:
                parser.error(
                    "--warmup cannot be negative"
                )

            # 6. Queryを作る
            if args.vector:
                query_vector = args.vector
            else:
                query_vector = make_benchmark_query(
                    dimension=dimension,
                    seed=args.query_seed,
                )

            connections = []

            try:

                for raw_target in targets:

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
                    collection=collection,
                    vector=query_vector,
                    top_k=top_k,
                    iterations=iterations,
                    warmup=warmup,
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

                if output:

                    payload = {
                        "collection": collection,
                        "dimension": dimension,
                        "top_k": top_k,
                        "iterations": iterations,
                        "warmup": warmup,
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

                    if output_format == "json":

                        write_json_report(
                            output,
                            payload,
                        )

                    elif output_format == "csv":

                        rows = []

                        for report in comparison.reports:

                            rows.append(
                                {
                                    "collection": args.collection,
                                    "dimension": args.dimension,
                                    "top_k": args.top_k,
                                    "iterations": args.iterations,
                                    "warmup": args.warmup,
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
                            )

                        write_csv_report(
                            output,
                            fieldnames=[
                                "collection",
                                "dimension",
                                "top_k",
                                "iterations",
                                "warmup",
                                "label",
                                "requests",
                                "successes",
                                "failures",
                                "success_rate",
                                "average_ms",
                                "p50_ms",
                                "p95_ms",
                                "p99_ms",
                            ],
                            rows=rows,
                        )
                

                    print()
                    print(
                        f"Report written to: {output}"
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