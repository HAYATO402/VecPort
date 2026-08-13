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

> Build against one interface while keeping the freedom to choose your vector database.

## Use Cases

VecPort is designed for teams that want to:

- Build applications without tightly coupling them to one vector database
- Evaluate multiple vector databases using a common application interface
- Reduce the cost of switching vector database providers
- Standardize vector database access across multiple projects
- Build reusable AI and retrieval infrastructure
- Prepare applications for future database migration and routing

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

## Unified Connection URLs

VecPort supports a unified connection URL format for selecting and configuring vector database drivers.

```python
from vecport import connect_url

db = connect_url(
    "vecport://qdrant"
)
```

Connection options can be provided through query parameters.

### Milvus

```python
db = connect_url(
    "vecport://milvus?uri=http://localhost:19530"
)
```

### pgvector

```python
db = connect_url(
    "vecport://pgvector?host=localhost&port=5432&dbname=vecport"
)
```

Sensitive credentials should not be stored inside connection URLs.

Pass credentials separately, preferably through environment variables.

```python
import os

from vecport import connect_url

db = connect_url(
    "vecport://pinecone",
    api_key=os.environ["PINECONE_API_KEY"],
)
```

Unified connection URLs provide a foundation for future connection profiles, managed infrastructure, migration tooling, and routing.

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

## Benchmarking

VecPort provides a common benchmarking interface for measuring and comparing vector search performance across supported databases.

### Single-Backend Benchmark

```bash
vecport benchmark \
  --url "vecport://qdrant?url=http://localhost:6333" \
  --collection vecport_benchmark_10k_128 \
  --dimension 128 \
  --top-k 10 \
  --iterations 100 \
  --warmup 10
```

VecPort reports:

- average latency
- p50 latency
- p95 latency
- p99 latency
- successful requests
- failed requests
- success rate

### Cross-Database Benchmark Comparison

The same workload can be executed against multiple vector databases.

```bash
vecport benchmark compare \
  --target "qdrant=vecport://qdrant?url=http://localhost:6333" \
  --target "milvus=vecport://milvus?uri=http://localhost:19530" \
  --collection vecport_benchmark_100k_128 \
  --dimension 128 \
  --top-k 10 \
  --iterations 100 \
  --warmup 10
```

VecPort uses the same query vector and benchmark parameters for every target.

### Example Local Benchmark Results

The following results were measured in a local development environment using VecPort's reproducible benchmark dataset generator.

Common settings:

- `top_k = 10`
- `iterations = 100`
- `warmup = 10`
- dataset seed = `42`
- identical generated records across backends
- Qdrant and Milvus running locally

| Records | Dimension | Backend | Avg | p50 | p95 | p99 | Success |
|---:|---:|---|---:|---:|---:|---:|---:|
| 10,000 | 128 | Qdrant | 16.091 ms | 15.577 ms | 25.408 ms | 30.395 ms | 100% |
| 10,000 | 128 | Milvus | 6.874 ms | 6.764 ms | 7.660 ms | 8.746 ms | 100% |
| 10,000 | 384 | Qdrant | 22.846 ms | 24.377 ms | 31.547 ms | 31.974 ms | 100% |
| 10,000 | 384 | Milvus | 10.669 ms | 10.298 ms | 12.355 ms | 13.015 ms | 100% |
| 30,000 | 128 | Qdrant | 17.998 ms | 15.557 ms | 30.561 ms | 31.080 ms | 100% |
| 30,000 | 128 | Milvus | 7.402 ms | 7.311 ms | 8.017 ms | 8.545 ms | 100% |
| 50,000 | 128 | Qdrant | 23.843 ms | 29.954 ms | 31.385 ms | 31.509 ms | 100% |
| 50,000 | 128 | Milvus | 9.793 ms | 9.685 ms | 10.575 ms | 10.986 ms | 100% |
| 100,000 | 128 | Qdrant | 23.921 ms | 30.077 ms | 31.537 ms | 31.904 ms | 100% |
| 100,000 | 128 | Milvus | 14.622 ms | 14.368 ms | 16.163 ms | 16.485 ms | 100% |

These numbers are example measurements from one local development environment and should not be interpreted as universal performance rankings between database products.

Performance depends on hardware, deployment topology, index configuration, database configuration, dataset characteristics, network conditions, and workload.

### Reproducible Benchmark Datasets

VecPort can generate deterministic benchmark datasets using a fixed random seed.

Using the same:

- record count
- vector dimension
- dataset seed
- query seed
- `top_k`
- iteration count
- warmup count

allows the same workload to be reproduced across multiple backends.

### Benchmark Reports

Benchmark comparison results can be exported as JSON or CSV.

#### JSON

```bash
vecport benchmark compare \
  --target "qdrant=vecport://qdrant?url=http://localhost:6333" \
  --target "milvus=vecport://milvus?uri=http://localhost:19530" \
  --collection vecport_benchmark_100k_128 \
  --dimension 128 \
  --top-k 10 \
  --iterations 100 \
  --warmup 10 \
  --format json \
  --output benchmarks/100k-128.json

## Extensible Driver Registry

VecPort uses a driver registry that allows additional vector database drivers to be registered without modifying the core connection API.

```python
from vecport import connect, register_driver


class MyVectorDriver:

    def __init__(self, **kwargs):
        self.options = kwargs


register_driver(
    "my-vector-db",
    MyVectorDriver,
)

db = connect(
    "my-vector-db",
)
```

Built-in drivers and third-party drivers can use the same VecPort connection interface.

```python
db = connect("qdrant")
db = connect("milvus")
db = connect("my-vector-db")
```

The driver registry provides a foundation for a future VecPort driver ecosystem and third-party driver compliance tooling.

## Cross-Database Migration

VecPort can migrate vector records between supported vector databases using the same common interface.

```bash
vecport migrate \
  --from "vecport://qdrant?path=.vecport-qdrant" \
  --to "vecport://milvus?uri=http://localhost:19530" \
  --collection documents \
  --recreate-target \
  --verify
```

VecPort migrates records in batches using the common `scan()` and `upsert()` APIs.

### Migration Verification

Use `--verify` to automatically validate the migrated collection after the migration completes.

VecPort verifies:

- record counts
- record IDs
- vector dimensions
- vector values
- metadata

Example output:

```text
Migration complete
Scanned: 10000
Migrated: 10000

Verification report
Source count: 10000
Target count: 10000
Matched IDs: 10000
Missing IDs: 0
Dimensions: OK
Vectors: OK
Metadata: OK

Migration verification: PASSED
```

### Dry Run

Inspect a migration without writing to the destination:

```bash
vecport migrate \
  --from "vecport://qdrant?path=.vecport-qdrant" \
  --to "vecport://milvus?uri=http://localhost:19530" \
  --collection documents \
  --dry-run
```

The initial migration implementation focuses on single dense vectors, IDs, metadata, batch migration, and one collection at a time.

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
              ┌───────────────┼───────────────┐
              │               │               │
              ▼               ▼               ▼
      Filter Validation   Capabilities   Common Errors
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