from vecport.core.errors import InvalidFilterError

SUPPORTED_FILTER_OPERATORS = {
    "$eq",
    "$ne",
    "$gt",
    "$gte",
    "$lt",
    "$lte",
    "$in",
}

SUPPORTED_LOGICAL_OPERATORS = {
    "$and",
    "$or",
}


def validate_filter(
    filters: dict | None,
) -> None:

    if filters is None:
        return

    if not isinstance(filters, dict):
        raise InvalidFilterError(
            "VecPort filters must be a dictionary"
        )

    for key, value in filters.items():

        if key in SUPPORTED_LOGICAL_OPERATORS:

            if not isinstance(value, list):
                raise InvalidFilterError(
                    f"{key} must contain a list"
                )

            if not value:
                raise InvalidFilterError(
                    f"{key} cannot be empty"
                )

            for item in value:
                validate_filter(item)

            continue

        if key.startswith("$"):
            raise InvalidFilterError(
                f"Unsupported VecPort logical operator: {key}"
            )

        if not isinstance(value, dict):
            raise InvalidFilterError(
                f"Filter for '{key}' must be a dictionary"
            )

        if not value:
            raise InvalidFilterError(
                f"Filter for '{key}' cannot be empty"
            )

        for operator, operand in value.items():

            if operator not in SUPPORTED_FILTER_OPERATORS:
                raise InvalidFilterError(
                    f"Unsupported VecPort filter operator: "
                    f"{operator}"
                )

            if operator == "$in":

                if not isinstance(
                    operand,
                    (list, tuple),
                ):
                    raise InvalidFilterError(
                        "$in requires a list or tuple"
                    )

                if not operand:
                    raise InvalidFilterError(
                        "$in cannot be empty"
                    )