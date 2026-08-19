from tests.test_filter_contract import (
    run_filter_contract,
)
from vecport import connect


def test_pgvector_filter_contract():

    db = connect("pgvector")

    run_filter_contract(db)