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
    