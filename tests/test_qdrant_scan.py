from tests.test_scan_contract import (
    run_scan_contract,
)
from vecport import connect


def test_qdrant_scan_contract():

    db = connect("qdrant")

    run_scan_contract(db)