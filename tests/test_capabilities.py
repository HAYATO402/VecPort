from vecport import connect


def test_qdrant_filter_capabilities():

    db = connect("qdrant")

    capabilities = db.capabilities()

    assert capabilities.metadata_filter is True
    assert "$eq" in capabilities.filter_operators
    assert "$and" in capabilities.filter_operators
    assert "$or" in capabilities.filter_operators