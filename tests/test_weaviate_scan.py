import os

import pytest

from tests.test_scan_contract import (
    run_scan_contract,
)
from vecport import connect


@pytest.mark.skipif(
    not os.environ.get("WEAVIATE_URL")
    or not os.environ.get("WEAVIATE_API_KEY"),
    reason="Weaviate credentials not configured",
)
def test_weaviate_scan_contract():

    db = connect(
        "weaviate",
        url=os.environ[
            "WEAVIATE_URL"
        ],
        api_key=os.environ[
            "WEAVIATE_API_KEY"
        ],
    )

    try:
        run_scan_contract(db)

    finally:
        db.client.close()