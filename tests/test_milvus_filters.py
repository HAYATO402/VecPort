from tests.test_filter_contract import (
    run_filter_contract,
)

from vecport import connect


def test_milvus_filter_contract():

    db = connect("milvus")

    run_filter_contract(db)