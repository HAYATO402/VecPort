from vecport import connect
from tests.test_contract import run_vector_database_contract


def test_qdrant_contract():

    db = connect("qdrant")

    run_vector_database_contract(db)