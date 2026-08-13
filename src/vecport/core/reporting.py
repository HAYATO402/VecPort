import csv
import json
from pathlib import Path
from typing import Any


def write_json_report(
    path: str,
    payload: dict[str, Any],
) -> None:

    output = Path(path)

    output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with output.open(
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            payload,
            file,
            indent=2,
        )


def write_csv_report(
    path: str,
    *,
    fieldnames: list[str],
    rows: list[dict[str, Any]],
) -> None:

    output = Path(path)

    output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with output.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
        )

        writer.writeheader()

        writer.writerows(
            rows
        )