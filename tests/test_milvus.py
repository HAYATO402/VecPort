from tests.test_contract import run_vector_database_contract
from vecport import connect


def test_milvus_contract():

    db = connect("milvus")

    run_vector_database_contract(db)