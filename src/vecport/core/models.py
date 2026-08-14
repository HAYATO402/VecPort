from dataclasses import dataclass, field
from typing import Any


@dataclass
class VectorRecord:
    id: str
    vector: list[float]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SearchResult:
    id: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass
class Capabilities:
    dense_vector: bool = True
    metadata_filter: bool = False

    filter_operators: tuple[str, ...] = ()

    sparse_vector: bool = False
    hybrid_search: bool = False
    namespaces: bool = False
    named_vectors: bool = False

FilterValue = dict[str, Any]

@dataclass(frozen=True)
class CollectionInfo:
    name: str

    exists: bool | None = None

    dimension: int | None = None
    distance_metric: str | None = None

    index_type: str | None = None
    index_params: dict[str, object] | None = None

    metadata_schema: dict[str, str] | None = None
    