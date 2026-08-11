import pytest

from vecport.core.errors import (
    DriverNotFoundError,
)
from vecport.core.registry import (
    create_driver,
    get_driver_factory,
    list_drivers,
    register_driver,
)
from vecport import connect


class DummyDriver:

    def __init__(
        self,
        value=None,
    ):
        self.value = value


def test_register_driver():

    register_driver(
        "test-driver",
        DummyDriver,
        replace=True,
    )

    factory = get_driver_factory(
        "test-driver"
    )

    assert factory is DummyDriver


def test_create_registered_driver():

    register_driver(
        "test-create-driver",
        DummyDriver,
        replace=True,
    )

    driver = create_driver(
        "test-create-driver",
        value="hello",
    )

    assert isinstance(
        driver,
        DummyDriver,
    )

    assert driver.value == "hello"


def test_unknown_driver():

    with pytest.raises(
        DriverNotFoundError
    ):

        create_driver(
            "driver-that-does-not-exist"
        )


def test_list_drivers():

    drivers = list_drivers()

    assert "qdrant" in drivers
    assert "pinecone" in drivers
    assert "weaviate" in drivers
    assert "milvus" in drivers
    assert "pgvector" in drivers

def test_connect_uses_registry():

    db = connect("qdrant")

    assert db is not None