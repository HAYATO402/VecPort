import pytest

from vecport.core.errors import MetadataTransformError
from vecport.core.models import VectorRecord
from vecport.core.transforms import (
    MetadataTransformer,
    MetadataTransformSpec,
    transform_spec_from_config,
)


def test_metadata_transform():
    transformer = MetadataTransformer(
        MetadataTransformSpec(
            rename={
                "old_category": "category",
                "createdAt": "created_at",
            },
            drop=("debug",),
            defaults={
                "source": "legacy",
            },
            cast={
                "price": "int",
            },
        )
    )
    record = VectorRecord(
        id="1",
        vector=[1.0, 0.0, 0.0],
        metadata={
            "old_category": "AI",
            "price": "5000",
            "createdAt": "2026-08-01",
            "debug": "temporary",
        },
    )

    transformed = transformer(record)

    assert transformed.metadata == {
        "category": "AI",
        "price": 5000,
        "created_at": "2026-08-01",
        "source": "legacy",
    }


def test_transform_does_not_mutate_original():
    transformer = MetadataTransformer(
        MetadataTransformSpec(
            rename={"old": "new"}
        )
    )
    record = VectorRecord(
        id="1",
        vector=[1.0, 0.0],
        metadata={"old": "value"},
    )

    transformed = transformer(record)

    assert record.metadata == {"old": "value"}
    assert transformed.metadata == {"new": "value"}
    assert transformed.vector is not record.vector


def test_rename_conflict_fails():
    transformer = MetadataTransformer(
        MetadataTransformSpec(
            rename={"old_category": "category"}
        )
    )
    record = VectorRecord(
        id="1",
        vector=[1.0, 0.0],
        metadata={
            "old_category": "AI",
            "category": "Finance",
        },
    )

    with pytest.raises(MetadataTransformError):
        transformer(record)


def test_invalid_cast_fails_without_updating_stats():
    transformer = MetadataTransformer(
        MetadataTransformSpec(
            rename={"old": "new"},
            cast={"price": "int"},
        )
    )
    record = VectorRecord(
        id="1",
        vector=[1.0, 0.0],
        metadata={
            "old": "value",
            "price": "not-a-number",
        },
    )

    with pytest.raises(MetadataTransformError):
        transformer(record)

    assert transformer.stats.records_transformed == 0
    assert transformer.stats.fields_renamed == 0


def test_strict_mode_requires_field():
    transformer = MetadataTransformer(
        MetadataTransformSpec(
            cast={"price": "int"},
            strict=True,
        )
    )

    with pytest.raises(MetadataTransformError):
        transformer(
            VectorRecord(
                id="1",
                vector=[1.0, 0.0],
                metadata={},
            )
        )


def test_bool_casts_supported_values():
    transformer = MetadataTransformer(
        MetadataTransformSpec(
            cast={"enabled": "bool"}
        )
    )

    assert transformer.transform_metadata(
        {"enabled": "yes"}
    )["enabled"] is True
    assert transformer.transform_metadata(
        {"enabled": "0"}
    )["enabled"] is False


def test_transform_stats():
    transformer = MetadataTransformer(
        MetadataTransformSpec(
            rename={"old": "new"},
            drop=("debug",),
            defaults={"source": "legacy"},
            cast={"price": "int"},
        )
    )

    transformer(
        VectorRecord(
            id="1",
            vector=[1.0, 0.0],
            metadata={
                "old": "value",
                "debug": True,
                "price": "10",
            },
        )
    )

    stats = transformer.stats
    assert stats.records_transformed == 1
    assert stats.fields_renamed == 1
    assert stats.fields_dropped == 1
    assert stats.defaults_applied == 1
    assert stats.casts_applied == 1


def test_transform_spec_from_config():
    spec = transform_spec_from_config(
        {
            "rename": {"old": "new"},
            "drop": ["debug"],
            "defaults": {"source": "legacy"},
            "cast": {"price": "INT"},
            "strict": False,
        }
    )

    assert spec is not None
    assert spec.rename == {"old": "new"}
    assert spec.drop == ("debug",)
    assert spec.cast == {"price": "int"}


def test_duplicate_rename_target_is_rejected():
    with pytest.raises(
        MetadataTransformError,
        match="Multiple source fields",
    ):
        MetadataTransformer(
            MetadataTransformSpec(
                rename={
                    "old_a": "category",
                    "old_b": "category",
                }
            )
        )


def test_unknown_config_option_is_rejected():
    with pytest.raises(
        MetadataTransformError,
        match="Unsupported metadata_transform option",
    ):
        transform_spec_from_config(
            {"renmae": {"old": "new"}}
        )
