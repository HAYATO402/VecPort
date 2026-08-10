from tests.test_filter_contract import (
    run_filter_contract,
)

from vecport import connect


def test_qdrant_filter_contract():

    db = connect("qdrant")

    run_filter_contract(db)