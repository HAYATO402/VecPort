import pytest

from vecport import connect
from vecport.core.errors import (
    DriverNotFoundError,
    InvalidFilterError,
)
from vecport.core.filters import (
    validate_filter,
)


def test_unknown_driver():

    with pytest.raises(
        DriverNotFoundError
    ):
        connect("unknown-database")


def test_invalid_filter():

    with pytest.raises(
        InvalidFilterError
    ):
        validate_filter(
            {
                "category": {
                    "$wrong": "AI"
                }
            }
        )