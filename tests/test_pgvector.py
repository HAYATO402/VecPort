from tests.test_contract import run_vector_database_contract
from vecport import connect


def test_pgvector_contract():

    db = connect("pgvector")

    run_vector_database_contract(db)