from tests.test_scan_contract import (
    run_scan_contract,
)
from vecport import connect


def test_milvus_scan_contract():

    db = connect("milvus")

    run_scan_contract(db)