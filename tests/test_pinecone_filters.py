import os

import pytest

from tests.test_filter_contract import (
    run_filter_contract,
)

from vecport import connect


@pytest.mark.skipif(
    not os.environ.get("PINECONE_API_KEY"),
    reason="PINECONE_API_KEY is not configured",
)
def test_pinecone_filter_contract():

    db = connect(
        "pinecone",
        api_key=os.environ["PINECONE_API_KEY"],
    )

    run_filter_contract(db)