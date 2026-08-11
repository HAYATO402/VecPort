import pytest

from vecport.core.connection import (
    parse_connection_url,
)
from vecport.core.errors import (
    InvalidConnectionURLError,
)

from vecport import connect_url


def test_parse_qdrant_connection_url():

    config = parse_connection_url(
        "vecport://qdrant"
    )

    assert config.driver == "qdrant"
    assert config.options == {}


def test_parse_milvus_connection_url():

    config = parse_connection_url(
        "vecport://milvus?uri=http://localhost:19530"
    )

    assert config.driver == "milvus"
    assert config.options == {
        "uri": "http://localhost:19530"
    }


def test_parse_pgvector_connection_url():

    config = parse_connection_url(
        "vecport://pgvector"
        "?host=localhost"
        "&port=5432"
        "&dbname=vecport"
    )

    assert config.driver == "pgvector"

    assert config.options == {
        "host": "localhost",
        "port": "5432",
        "dbname": "vecport",
    }


def test_invalid_connection_scheme():

    with pytest.raises(
        InvalidConnectionURLError
    ):

        parse_connection_url(
            "http://qdrant"
        )


def test_missing_driver():

    with pytest.raises(
        InvalidConnectionURLError
    ):

        parse_connection_url(
            "vecport://"
        )


def test_secret_in_connection_url():

    with pytest.raises(
        InvalidConnectionURLError
    ):

        parse_connection_url(
            "vecport://pinecone"
            "?api_key=secret"
        )

def test_connect_url_qdrant():

    db = connect_url(
        "vecport://qdrant"
    )

    assert db is not None

