import pytest

from vecport.core.filters import (
    validate_filter,
)

from vecport.core.errors import InvalidFilterError


def test_valid_eq_filter():

    validate_filter(
        {
            "category": {
                "$eq": "AI"
            }
        }
    )


def test_valid_and_filter():

    validate_filter(
        {
            "$and": [
                {
                    "category": {
                        "$eq": "AI"
                    }
                },
                {
                    "price": {
                        "$lt": 10000
                    }
                },
            ]
        }
    )


def test_invalid_operator():

    with pytest.raises(InvalidFilterError):

        validate_filter(
            {
                "category": {
                    "$unknown": "AI"
                }
            }
        )


def test_invalid_and_type():

    with pytest.raises(InvalidFilterError):

        validate_filter(
            {
                "$and": {
                    "category": {
                        "$eq": "AI"
                    }
                }
            }
        )


def test_invalid_in_value():

    with pytest.raises(InvalidFilterError):

        validate_filter(
            {
                "category": {
                    "$in": "AI"
                }
            }
        )