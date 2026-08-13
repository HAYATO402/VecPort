import csv
import json

from vecport.core.reporting import (
    write_csv_report,
    write_json_report,
)


def test_write_json_report(tmp_path):

    output = tmp_path / "report.json"

    payload = {
        "type": "test",
        "value": 123,
    }

    write_json_report(
        str(output),
        payload,
    )

    with output.open(
        encoding="utf-8",
    ) as file:
        result = json.load(file)

    assert result == payload


def test_write_csv_report(tmp_path):

    output = tmp_path / "report.csv"

    rows = [
        {
            "backend": "qdrant",
            "latency_ms": 10.5,
        },
        {
            "backend": "milvus",
            "latency_ms": 5.2,
        },
    ]

    write_csv_report(
        str(output),
        fieldnames=[
            "backend",
            "latency_ms",
        ],
        rows=rows,
    )

    with output.open(
        newline="",
        encoding="utf-8",
    ) as file:
        result = list(
            csv.DictReader(file)
        )

    assert len(result) == 2
    assert result[0]["backend"] == "qdrant"
    assert result[1]["backend"] == "milvus"