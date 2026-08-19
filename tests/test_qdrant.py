from tests.test_contract import run_vector_database_contract
from vecport import connect


def test_qdrant_contract():

    db = connect("qdrant")

    run_vector_database_contract(db)