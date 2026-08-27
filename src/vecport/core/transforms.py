"""Safe, declarative metadata transformations for migrations."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from vecport.core.errors import MetadataTransformError
from vecport.core.models import VectorRecord

_SUPPORTED_CASTS = {
    "str",
    "int",
    "float",
    "bool",
}

_CONFIG_KEYS = {
    "rename",
    "drop",
    "defaults",
    "cast",
    "strict",
}


@dataclass(frozen=True)
class MetadataTransformSpec:
    """Declarative rules applied to each record's metadata."""

    rename: Mapping[str, str] = field(
        default_factory=dict
    )
    drop: tuple[str, ...] = ()
    defaults: Mapping[str, Any] = field(
        default_factory=dict
    )
    cast: Mapping[str, str] = field(
        default_factory=dict
    )
    strict: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "rename",
            MappingProxyType(dict(self.rename)),
        )
        object.__setattr__(
            self,
            "drop",
            tuple(self.drop),
        )
        object.__setattr__(
            self,
            "defaults",
            MappingProxyType(
                deepcopy(dict(self.defaults))
            ),
        )
        object.__setattr__(
            self,
            "cast",
            MappingProxyType(dict(self.cast)),
        )


@dataclass
class MetadataTransformStats:
    """Cumulative counts for successfully transformed records."""

    records_transformed: int = 0
    fields_renamed: int = 0
    fields_dropped: int = 0
    defaults_applied: int = 0
    casts_applied: int = 0


def _cast_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value

    if isinstance(value, int):
        if value == 1:
            return True
        if value == 0:
            return False

    if isinstance(value, str):
        normalized = value.strip().lower()

        if normalized in {
            "true",
            "1",
            "yes",
            "y",
        }:
            return True

        if normalized in {
            "false",
            "0",
            "no",
            "n",
        }:
            return False

    raise ValueError(
        f"Cannot cast {value!r} to bool."
    )


def _cast_value(
    value: Any,
    cast_type: str,
) -> Any:
    if cast_type == "str":
        return str(value)
    if cast_type == "int":
        return int(value)
    if cast_type == "float":
        return float(value)
    if cast_type == "bool":
        return _cast_bool(value)

    raise MetadataTransformError(
        "Unsupported metadata cast type: "
        f"{cast_type}"
    )


def _validate_field_name(
    value: Any,
    *,
    path: str,
) -> None:
    if not isinstance(value, str) or not value:
        raise MetadataTransformError(
            f"{path} must be a non-empty string."
        )


def validate_transform_spec(
    spec: MetadataTransformSpec,
) -> None:
    """Validate a transform before any records are processed."""

    if not isinstance(spec.strict, bool):
        raise MetadataTransformError(
            "metadata_transform.strict must be true or false."
        )

    targets: dict[str, str] = {}

    for source, target in spec.rename.items():
        _validate_field_name(
            source,
            path="Rename source field",
        )
        _validate_field_name(
            target,
            path="Rename target field",
        )

        previous = targets.get(target)
        if previous is not None and previous != source:
            raise MetadataTransformError(
                "Multiple source fields cannot be renamed to "
                f"'{target}'."
            )

        targets[target] = source

    seen_drop_fields: set[str] = set()
    for field_name in spec.drop:
        _validate_field_name(
            field_name,
            path="Drop field",
        )
        if field_name in seen_drop_fields:
            raise MetadataTransformError(
                "Duplicate metadata drop field: "
                f"{field_name}"
            )
        seen_drop_fields.add(field_name)

    for field_name in spec.defaults:
        _validate_field_name(
            field_name,
            path="Default field",
        )

    unsupported: set[str] = set()
    for field_name, cast_type in spec.cast.items():
        _validate_field_name(
            field_name,
            path="Cast field",
        )
        if (
            not isinstance(cast_type, str)
            or cast_type not in _SUPPORTED_CASTS
        ):
            unsupported.add(str(cast_type))

    if unsupported:
        names = ", ".join(sorted(unsupported))
        raise MetadataTransformError(
            "Unsupported metadata cast type(s): "
            f"{names}"
        )


class MetadataTransformer:
    """Apply a validated metadata transform to vector records."""

    def __init__(
        self,
        spec: MetadataTransformSpec,
    ) -> None:
        validate_transform_spec(spec)
        self.spec = spec
        self.stats = MetadataTransformStats()

    def transform_metadata(
        self,
        metadata: Mapping[str, Any],
    ) -> dict[str, Any]:
        result = dict(metadata)

        fields_renamed = self._apply_rename(result)
        fields_dropped = self._apply_drop(result)
        defaults_applied = self._apply_defaults(result)
        casts_applied = self._apply_cast(result)

        # Commit statistics only after the whole record succeeds.
        self.stats.records_transformed += 1
        self.stats.fields_renamed += fields_renamed
        self.stats.fields_dropped += fields_dropped
        self.stats.defaults_applied += defaults_applied
        self.stats.casts_applied += casts_applied

        return result

    def _apply_rename(
        self,
        metadata: dict[str, Any],
    ) -> int:
        original = dict(metadata)
        present: list[tuple[str, str]] = []

        for source, target in self.spec.rename.items():
            if source not in original:
                if self.spec.strict:
                    raise MetadataTransformError(
                        "Required rename source field is missing: "
                        f"{source}"
                    )
                continue

            present.append((source, target))

        renamed_sources = {
            source
            for source, target in present
            if source != target
        }

        for source, target in present:
            if (
                target != source
                and target in original
                and target not in renamed_sources
            ):
                raise MetadataTransformError(
                    "Metadata rename would overwrite an existing "
                    f"field: {target}"
                )

        for source in renamed_sources:
            metadata.pop(source)

        renamed = 0
        for source, target in present:
            metadata[target] = original[source]
            if source != target:
                renamed += 1

        return renamed

    def _apply_drop(
        self,
        metadata: dict[str, Any],
    ) -> int:
        dropped = 0
        for field_name in self.spec.drop:
            if field_name in metadata:
                metadata.pop(field_name)
                dropped += 1
        return dropped

    def _apply_defaults(
        self,
        metadata: dict[str, Any],
    ) -> int:
        applied = 0
        for field_name, value in self.spec.defaults.items():
            if field_name not in metadata:
                metadata[field_name] = deepcopy(value)
                applied += 1
        return applied

    def _apply_cast(
        self,
        metadata: dict[str, Any],
    ) -> int:
        applied = 0
        for field_name, cast_type in self.spec.cast.items():
            if field_name not in metadata:
                if self.spec.strict:
                    raise MetadataTransformError(
                        "Required cast field is missing: "
                        f"{field_name}"
                    )
                continue

            original = metadata[field_name]
            try:
                converted = _cast_value(
                    original,
                    cast_type,
                )
            except (ValueError, TypeError, OverflowError) as error:
                raise MetadataTransformError(
                    "Failed to cast metadata field "
                    f"'{field_name}' to {cast_type}: "
                    f"{original!r}"
                ) from error

            metadata[field_name] = converted
            applied += 1

        return applied

    def transform(
        self,
        record: VectorRecord,
    ) -> VectorRecord:
        return VectorRecord(
            id=record.id,
            vector=list(record.vector),
            metadata=self.transform_metadata(
                record.metadata or {}
            ),
        )

    def __call__(
        self,
        record: VectorRecord,
    ) -> VectorRecord:
        return self.transform(record)


def transform_spec_from_config(
    config: Mapping[str, Any] | None,
) -> MetadataTransformSpec | None:
    """Parse and validate a metadata_transform configuration section."""

    if config is None:
        return None
    if not isinstance(config, Mapping):
        raise MetadataTransformError(
            "metadata_transform must be a mapping."
        )

    unknown = set(config) - _CONFIG_KEYS
    if unknown:
        names = ", ".join(sorted(str(key) for key in unknown))
        raise MetadataTransformError(
            "Unsupported metadata_transform option(s): "
            f"{names}"
        )

    rename = config.get("rename", {})
    drop = config.get("drop", [])
    defaults = config.get("defaults", {})
    cast = config.get("cast", {})
    strict = config.get("strict", False)

    if not isinstance(rename, Mapping):
        raise MetadataTransformError(
            "metadata_transform.rename must be a mapping."
        )
    if not isinstance(drop, (list, tuple)):
        raise MetadataTransformError(
            "metadata_transform.drop must be a list."
        )
    if not isinstance(defaults, Mapping):
        raise MetadataTransformError(
            "metadata_transform.defaults must be a mapping."
        )
    if not isinstance(cast, Mapping):
        raise MetadataTransformError(
            "metadata_transform.cast must be a mapping."
        )
    if not isinstance(strict, bool):
        raise MetadataTransformError(
            "metadata_transform.strict must be true or false."
        )

    normalized_cast: dict[str, str] = {}
    for key, value in cast.items():
        normalized_cast[key] = (
            value.strip().lower()
            if isinstance(value, str)
            else value
        )

    spec = MetadataTransformSpec(
        rename=dict(rename),
        drop=tuple(drop),
        defaults=dict(defaults),
        cast=normalized_cast,
        strict=strict,
    )
    validate_transform_spec(spec)
    return spec
