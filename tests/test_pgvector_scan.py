from tests.test_scan_contract import (
    run_scan_contract,
)

from vecport import connect


def test_pgvector_scan_contract():

    db = connect("pgvector")

    run_scan_contract(db)