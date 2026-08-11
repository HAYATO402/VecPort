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


def _close_driver(db):

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


if __name__ == "__main__":
    main()