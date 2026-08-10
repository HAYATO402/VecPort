from vecport import connect
from tests.test_contract import run_vector_database_contract


def test_pgvector_contract():

    db = connect("pgvector")

    run_vector_database_contract(db)