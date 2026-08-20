import argparse
import os

from vecport import connect_url
from vecport.core.benchmark import (
    benchmark_search,
    compare_benchmarks,
)
from vecport.core.benchmark_dataset import (
    make_benchmark_query,
)
from vecport.core.compliance import (
    ComplianceReport,
    run_compliance,
)
from vecport.core.config import load_config
from vecport.core.migration import (
    migrate_collection,
    plan_migration,
    verify_migration,
)
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

    connection = getattr(
        db,
        "conn",
        None,
    )

    close = getattr(
        connection,
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


def _print_compliance_report(
    report: ComplianceReport,
) -> None:
    print()
    print("VecPort Driver Compliance")
    print(
        "Temporary collection: "
        f"{report.collection}"
    )
    print()

    for check in report.checks:
        line = (
            f"{check.name:<20} "
            f"{check.status.upper()}"
        )

        if check.detail:
            line += f" - {check.detail}"

        print(line)

    print()
    print(
        "Summary: "
        f"{report.passed_count} passed, "
        f"{report.failed_count} failed, "
        f"{report.skipped_count} skipped"
    )
    print(
        "Compliance: "
        + (
            "PASSED"
            if report.passed
            else "FAILED"
        )
    )


def _compliance_payload(
    report: ComplianceReport,
) -> dict[str, object]:
    return {
        "type": "driver_compliance",
        "collection": report.collection,
        "passed": report.passed,
        "summary": {
            "passed": report.passed_count,
            "failed": report.failed_count,
            "skipped": report.skipped_count,
        },
        "checks": [
            {
                "name": check.name,
                "status": check.status,
                "detail": check.detail,
            }
            for check in report.checks
        ],
    }


def _run_compliance_command(
    args: argparse.Namespace,
) -> int:
    if args.dimension < 2:
        print(
            "Compliance dimension must "
            "be at least 2."
        )
        return 1

    db = connect_url(
        args.url,
        **_connection_overrides(
            "COMPLIANCE"
        ),
    )

    try:
        report = run_compliance(
            db,
            collection_prefix=(
                args.collection_prefix
            ),
            dimension=args.dimension,
            cleanup=not args.no_cleanup,
        )

        _print_compliance_report(report)

        if args.output:
            write_json_report(
                args.output,
                _compliance_payload(report),
            )
            print()
            print(
                "Report written to: "
                f"{args.output}"
            )

        return 0 if report.passed else 1

    finally:
        _close_driver(db)


def main():

    parser = argparse.ArgumentParser(
        prog="vecport"
    )

    commands = parser.add_subparsers(
        dest="command",
        required=True,
    )

    config_command = commands.add_parser(
        "config",
        help="Validate and inspect VecPort configuration.",
    )

    config_command.add_argument(
        "config_action",
        choices=[
            "check",
        ],
    )

    config_command.add_argument(
        "--config",
        required=True,
        help="Path to a VecPort YAML configuration file.",
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
        "--plan",
        action="store_true",
        help=(
            "Analyze migration compatibility "
            "without writing data."
        ),
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

    migrate.add_argument(
        "--resume",
        action="store_true",
        default=None,
        help=(
            "Resume a migration by skipping "
            "records already present in the "
            "target collection."
        ),
    )

    migrate.add_argument(
        "--existing-policy",
        choices=[
            "skip",
            "repair",
            "error",
        ],
        default=None,
        help=(
            "How resume handles IDs already "
            "present in the target: "
            "skip, repair, or error."
        ),
    )

    migrate.add_argument(
        "--progress",
        action="store_true",
        default=None,
        help=(
            "Show migration progress, "
            "processing speed, and ETA."
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

    compliance = commands.add_parser(
        "compliance",
        help=(
            "Validate a vector database driver "
            "against the VecPort contract."
        ),
    )

    compliance.add_argument(
        "--url",
        required=True,
        help=(
            "VecPort connection URL for the "
            "driver to validate."
        ),
    )

    compliance.add_argument(
        "--dimension",
        type=int,
        default=3,
        help=(
            "Vector dimension used by the "
            "compliance test. Default: 3."
        ),
    )

    compliance.add_argument(
        "--collection-prefix",
        default="vecport_compliance",
        help=(
            "Prefix for temporary compliance "
            "collections."
        ),
    )

    compliance.add_argument(
        "--no-cleanup",
        action="store_true",
        help=(
            "Keep the temporary compliance "
            "collection after the test."
        ),
    )

    compliance.add_argument(
        "--output",
        help=(
            "Optional path for a JSON "
            "compliance report."
        ),
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

    if (
        args.command == "config"
        and args.config_action == "check"
    ):
        print("Configuration valid")

        if config:
            print()
            print("Sections:")

            for section in config:
                print(
                    f"- {section}: OK"
                )

        return 0

    if args.command == "compliance":
        return _run_compliance_command(args)

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

        resume = (
            args.resume
            if args.resume is not None
            else migration_config.get(
                "resume",
                False,
            )
        )

        existing_policy = (
            args.existing_policy
            if args.existing_policy is not None
            else migration_config.get(
                "existing_policy",
                "skip",
            )
        )

        show_progress = (
            args.progress
            if args.progress is not None
            else migration_config.get(
                "progress",
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

        if (
            resume
            and recreate_target
        ):
            parser.error(
                "--resume cannot be used "
                "with --recreate-target"
            )

        if (
            resume
            and dry_run
        ):
            parser.error(
                "--resume cannot be used "
                "with --dry-run"
            )

        if (
            args.existing_policy is not None
            and not resume
        ):
            parser.error(
                "--existing-policy requires --resume"
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

            if args.plan:

                plan = plan_migration(
                    source,
                    target,
                    source_collection=collection,
                    target_collection=target_collection,
                    batch_size=batch_size,
                )

                print()
                print("Migration plan")
                print()

                print(
                    "Source collection: "
                    f"{plan.source_collection}"
                )

                print(
                    "Target collection: "
                    f"{plan.target_collection}"
                )

                print()

                print(
                    f"Records: "
                    f"{plan.source_count}"
                )

                print(
                    f"Dimension: "
                    f"{plan.dimension}"
                )

                print(
                    f"Batch size: "
                    f"{plan.batch_size}"
                )

                print(
                    "Estimated batches: "
                    f"{plan.estimated_batches}"
                )

                print()

                print(
                    "Dimensions: "
                    + (
                        "OK"
                        if plan.dimensions_ok
                        else "FAILED"
                    )
                )

                print(
                    "Dense vector support: "
                    + (
                        "OK"
                        if plan.dense_vector_ok
                        else "FAILED"
                    )
                )

                print()

                print("Collection information")
                print()

                print(
                    "Source dimension: "
                    f"{plan.source_info.dimension}"
                )

                print(
                    "Source distance metric: "
                    f"{plan.source_info.distance_metric or 'UNKNOWN'}"
                )

                print(
                    "Source index type: "
                    f"{plan.source_info.index_type or 'UNKNOWN'}"
                )

                print()

                print(
                    "Target exists: "
                    + (
                        "YES"
                        if plan.target_info.exists is True
                        else (
                            "NO"
                            if plan.target_info.exists is False
                            else "UNKNOWN"
                        )
                    )
                )

                print(
                    "Target dimension: "
                    + (
                        str(
                            plan.target_info.dimension
                        )
                        if plan.target_info.dimension
                        is not None
                        else "N/A"
                    )
                )

                print(
                    "Target distance metric: "
                    f"{plan.target_info.distance_metric or 'N/A'}"
                )

                print(
                    "Target index type: "
                    f"{plan.target_info.index_type or 'N/A'}"
                )

                print()

                if (
                    plan.target_dimension_ok
                    is True
                ):
                    dimension_status = "OK"

                elif (
                    plan.target_dimension_ok
                    is False
                ):
                    dimension_status = "WARN"

                else:
                    dimension_status = "N/A"

                print(
                    "Target dimension compatibility: "
                    f"{dimension_status}"
                )

                if (
                    plan.distance_metric_ok
                    is True
                ):
                    metric_status = "OK"

                elif (
                    plan.distance_metric_ok
                    is False
                ):
                    metric_status = "WARN"

                else:
                    metric_status = "N/A"

                print(
                    "Distance metric compatibility: "
                    f"{metric_status}"
                )

                print()

                print("Compatibility")
                print()

                for check in plan.compatibility:

                    source_value = (
                        "YES"
                        if check.source_supported
                        else "NO"
                    )

                    target_value = (
                        "YES"
                        if check.target_supported
                        else "NO"
                    )

                    print(
                        f"{check.name}: "
                        f"{check.status} "
                        f"(source={source_value}, "
                        f"target={target_value})"
                    )

                    if check.detail:
                        print(
                            f"  {check.detail}"
                        )

                print()

                print(
                    "Driver capability gaps:"
                )

                if plan.capability_gaps:

                    for gap in plan.capability_gaps:
                        print(
                            f"- {gap}"
                        )

                else:
                    print(
                        "- None"
                    )

                print()
                print(
                    "No data will be written."
                )
                print()

                print(
                    "Migration plan: "
                    + (
                        "READY"
                        if plan.ready
                        else "NOT READY"
                    )
                )

                return 0

            def print_migration_progress(
                progress,
            ):

                total_text = (
                    str(progress.total_records)
                    if progress.total_records
                    is not None
                    else "?"
                )

                percent_text = (
                    f"{progress.percent:.1f}%"
                    if progress.percent
                    is not None
                    else "N/A"
                )

                eta_text = (
                    f"{progress.eta_seconds:.1f}s"
                    if progress.eta_seconds
                    is not None
                    else "N/A"
                )

                print(
                    "Progress: "
                    f"{progress.scanned}/"
                    f"{total_text} "
                    f"({percent_text}) "
                    "| "
                    f"{progress.records_per_second:.1f} records/s "
                    "| "
                    f"ETA {eta_text} "
                    "| "
                    f"Batch {progress.batches_completed}"
                )

            total_records = None
            progress_callback = None

            if show_progress:

                progress_plan = plan_migration(
                    source,
                    target,
                    source_collection=collection,
                    target_collection=target_collection,
                    batch_size=batch_size,
                )

                total_records = (
                    progress_plan.source_count
                )

                progress_callback = (
                    print_migration_progress
                )

            report = migrate_collection(
                source,
                target,
                collection=collection,
                target_collection=target_collection,
                batch_size=batch_size,
                recreate_target=recreate_target,
                dry_run=dry_run,
                resume=resume,
                existing_policy=existing_policy,
                total_records=total_records,
                progress_callback=progress_callback,
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

            if report.resumed:

                print(
                    "Existing policy: "
                    f"{report.existing_policy}"
                )

                print(
                    "Skipped existing: "
                    f"{report.skipped_existing}"
                )

                print(
                    "Repaired existing: "
                    f"{report.repaired_existing}"
                )

            print(
                f"Resume: {report.resumed}"
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
