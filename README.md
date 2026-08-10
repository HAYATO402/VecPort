# VecPort

**One interface for vector databases.**

VecPort is an open-source Python interface for building applications that can work across multiple vector database backends.

Write your vector database logic once and connect to:

- Qdrant
- Pinecone
- Weaviate
- Milvus
- pgvector

without rewriting your application-level database logic.

## Why VecPort?

Vector databases expose different SDKs, connection methods, query APIs, filtering syntax, and capabilities.

This creates vendor-specific application code and makes switching databases expensive.

VecPort introduces a common abstraction layer between your application and the vector database.

```text
Application
    │
    ▼
  VecPort
    │
    ├── Qdrant
    ├── Pinecone
    ├── Weaviate
    ├── Milvus
    └── pgvector
```

The goal of VecPort is simple:

>## Use Cases

VecPort is designed for teams that want to:

- Build applications without tightly coupling them to one vector database
- Evaluate multiple vector databases using a common application interface
- Reduce the cost of switching vector database providers
- Standardize vector database access across multiple projects
- Build reusable AI and retrieval infrastructure
- Prepare applications for future database migration and routing Build against one interface while keeping the freedom to choose your vector database.

## Supported Drivers

| Driver | Basic Operations | Metadata Filters | Common Filter DSL |
|---|---:|---:|---:|
| Qdrant | ✅ | ✅ | ✅ |
| Pinecone | ✅ | ✅ | ✅ |
| Weaviate | ✅ | ✅ | ✅ |
| Milvus | ✅ | ✅ | ✅ |
| pgvector | ✅ | ✅ | ✅ |

## Installation

VecPort is currently under active development.

Clone the repository:

```bash
git clone <YOUR_REPOSITORY_URL>
cd vecport
pip install -e .
```

PyPI distribution is planned for a future release.

## Quick Start

```python
from vecport import VectorRecord, connect

db = connect("qdrant")

db.create_collection(
    "documents",
    dimension=3,
)

db.upsert(
    "documents",
    [
        VectorRecord(
            id="550e8400-e29b-41d4-a716-446655440000",
            vector=[1.0, 0.0, 0.0],
            metadata={
                "category": "AI",
                "price": 5000,
            },
        )
    ],
)

results = db.search(
    "documents",
    vector=[1.0, 0.0, 0.0],
    top_k=5,
)

for result in results:
    print(result)
```

## Switch Databases Without Rewriting Your Application Logic

Use Qdrant:

```python
db = connect("qdrant")
```

Switch to Milvus:

```python
db = connect("milvus")
```

Or use pgvector:

```python
db = connect("pgvector")
```

The rest of your VecPort application can continue using the same common interface.

```python
results = db.search(
    "documents",
    vector=[1.0, 0.0, 0.0],
    top_k=10,
)
```

## Common Filter DSL

Vector databases use different filtering systems.

VecPort provides a common filter DSL that drivers translate into their native database syntax.

```python
results = db.search(
    collection="documents",
    vector=[1.0, 0.0, 0.0],
    top_k=10,
    filters={
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
    },
)
```

The application writes one VecPort filter while each driver handles the database-specific translation.

### Supported Filter Operators

| Operator | Meaning |
|---|---|
| `$eq` | Equal |
| `$ne` | Not equal |
| `$gt` | Greater than |
| `$gte` | Greater than or equal |
| `$lt` | Less than |
| `$lte` | Less than or equal |
| `$in` | Match any value in a list |
| `$and` | All conditions must match |
| `$or` | At least one condition must match |

## Filter Validation

VecPort validates filters before sending them to database drivers.

Valid filter:

```python
filters={
    "category": {
        "$eq": "AI"
    }
}
```

Invalid or unsupported filters raise a VecPort `InvalidFilterError`.

```python
filters={
    "category": {
        "$unknown": "AI"
    }
}
```

This provides consistent validation behavior across supported drivers.

## Driver Capabilities

Different vector databases support different features.

VecPort allows applications to inspect driver capabilities programmatically.

```python
db = connect("qdrant")

capabilities = db.capabilities()

print(capabilities.metadata_filter)
print(capabilities.filter_operators)
```

This makes it possible to build applications that adapt to the capabilities of the selected backend.

## Error Handling

VecPort provides a common exception hierarchy.

```text
VecPortError
├── InvalidFilterError
├── UnsupportedFeatureError
└── DriverNotFoundError
```

Example:

```python
from vecport import connect
from vecport.core.errors import DriverNotFoundError

try:
    db = connect("unknown-driver")

except DriverNotFoundError as error:
    print(error)
```

Applications can handle VecPort-level errors without depending directly on database-specific exceptions.

## Cross-Database Contract Testing

VecPort uses shared contract tests to verify consistent behavior across supported drivers.

The test suite covers:

- Collection operations
- Vector upsert and retrieval
- Vector similarity search
- Cross-database filter behavior
- Filter validation
- Driver capabilities
- VecPort error handling

Run the complete test suite:

```bash
pytest -v
```

The goal is not only to provide multiple drivers, but to verify that they follow the same VecPort contract.

## Architecture

```text
                        Application
                            │
                            ▼
                     VecPort Interface
                            │
             ┌──────────────┼──────────────┐
             │              │              │
             ▼              ▼              ▼
      Filter Validation  Capabilities   Common Errors
             │
             ▼
                       Driver Layer
             │
     ┌───────┼────────┬────────┬─────────┐
     ▼       ▼        ▼        ▼         ▼
  Qdrant  Pinecone  Weaviate  Milvus  pgvector
```

VecPort separates application-level vector database logic from backend-specific implementations.

## Roadmap

VecPort is evolving from a common database interface toward a broader interoperability layer for vector infrastructure.

Planned areas include:

- Unified connection URLs
- Driver registry and third-party drivers
- Async API
- Cross-database migration tools
- Vector database benchmarking
- Routing across multiple vector database backends
- Failover support
- Observability
- Managed connection profiles
- Team and enterprise configuration
- Compliance tooling for third-party drivers
- PyPI distribution
- LangChain integration
- LlamaIndex integration

## Open Source and Future Managed Services

VecPort Core is focused on providing an open interface, shared driver behavior, and a common developer experience across vector databases.

Future managed and enterprise offerings may build on top of the open-source core with features such as:

- Managed connections and credentials
- Migration automation
- Benchmarking and cost analysis
- Observability
- Multi-database routing
- Failover
- Team management
- SSO and RBAC
- Audit logging
- Private and self-hosted deployment options

The open-source core will remain the foundation of the VecPort ecosystem.

## Who Is VecPort For?

VecPort may be useful for:

- AI application developers
- RAG infrastructure teams
- Platform engineering teams
- Companies evaluating multiple vector databases
- Teams planning a vector database migration
- Libraries and frameworks that want database-independent vector storage
- Organizations that want to reduce vector database vendor lock-in