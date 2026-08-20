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

VecPort requires Python 3.10 or newer.

After the package is published to PyPI, install the release with:

```bash
pip install vecport
```

For local development, clone the repository and install it in editable mode:

```bash
git clone https://github.com/HAYATO402/vecport.git
cd vecport
pip install -e .
```

### LangChain integration

Install VecPort with LangChain support:

```bash
pip install "vecport[langchain]"
```

VecPort can be used as a LangChain vector store while keeping the underlying
vector database behind the VecPort interface.

```python
from langchain_core.documents import Document

from vecport import connect
from vecport.integrations.langchain import VecPortVectorStore

db = connect("qdrant")

vector_store = VecPortVectorStore(
    db=db,
    collection="documents",
    embedding=embeddings,
)

vector_store.add_documents(
    [
        Document(
            page_content="VecPort provides one interface for vector databases.",
            metadata={"category": "AI"},
        )
    ]
)

documents = vector_store.similarity_search(
    "vector databases",
    k=5,
)
```

The adapter supports:

- document insertion
- deletion by ID
- similarity search
- metadata filters using the VecPort filter DSL
- `as_retriever()` for LangChain retrieval workflows

The target VecPort collection must use a vector dimension compatible with the
configured LangChain embedding model. The application supplies its preferred
LangChain `Embeddings` implementation.

### LlamaIndex integration

Install VecPort with LlamaIndex support:

```bash
pip install "vecport[llamaindex]"
```

Use VecPort as the vector-store layer behind LlamaIndex:

```python
from llama_index.core import StorageContext, VectorStoreIndex

from vecport import connect
from vecport.integrations.llamaindex import VecPortLlamaIndexVectorStore

db = connect("qdrant")

vector_store = VecPortLlamaIndexVectorStore(
    db=db,
    collection="documents",
)
storage_context = StorageContext.from_defaults(
    vector_store=vector_store,
)
index = VectorStoreIndex.from_documents(
    documents,
    storage_context=storage_context,
    embed_model=embed_model,
)

retriever = index.as_retriever(similarity_top_k=5)
results = retriever.retrieve("vector databases")
```

The adapter supports:

- inserting embedded LlamaIndex nodes
- dense `VectorStoreQuery` search
- metadata filters supported by the VecPort filter DSL
- deletion by reference document ID
- direct node deletion and retrieval
- `StorageContext` integration
- `VectorStoreIndex` retrieval

The target collection must already exist with a dimension compatible with the
configured LlamaIndex embedding model. Sparse, hybrid, MMR, NOT filters, and
filter-based node deletion are not currently supported. Reference-document
deletion uses the common VecPort `scan()` API and can be expensive for large
collections.

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

### YAML Configuration

Benchmark settings can be stored in a YAML configuration file.

Example `vecport.yml`:

```yaml
benchmark:
  targets:
    - label: qdrant
      url: "vecport://qdrant?url=http://localhost:6333"

    - label: milvus
      url: "vecport://milvus?uri=http://localhost:19530"

  collection: vecport_benchmark_100k_128
  dimension: 128
  top_k: 10
  iterations: 100
  warmup: 10
  format: json
  output: benchmarks/100k-128.json
```

Run the benchmark with:

```bash
vecport benchmark compare --config vecport.yml
```

Command-line options override values from the YAML configuration.

#### Validate a configuration file

VecPort can validate a YAML configuration without running a benchmark or migration.

```bash
vecport config check --config vecport.yml
```

Example output:

```text
Configuration valid

Sections:
- benchmark: OK
- migration: OK
```

The command validates:

- YAML syntax
- environment-variable references
- benchmark configuration
- migration configuration

Sensitive environment-variable values are not printed.

#### Migration configuration

Migration settings can also be stored in `vecport.yml`.

```yaml
migration:
  from: "vecport://qdrant?url=http://localhost:6333"
  to: "vecport://milvus?uri=http://localhost:19530"
  collection: documents
  target_collection: documents_migrated
  batch_size: 500
  recreate_target: true
  dry_run: false
  verify: true
  format: json
  output: reports/migration.json
```

Run the migration with:

```bash
vecport migrate --config vecport.yml
```

Command-line options override values defined in the YAML configuration.

### Plan a migration

VecPort can inspect a migration before writing any data.

```bash
vecport migrate \
  --plan \
  --from "vecport://qdrant?url=http://localhost:6333" \
  --to "vecport://milvus?uri=http://localhost:19530" \
  --collection documents
```

The migration plan reports information such as:

- source record count
- vector dimension
- batch size
- estimated number of batches
- migration readiness

Plan mode does not write data to the target database.

Migration plan mode also compares driver capabilities before migration.

Compatibility checks currently include:

- dense vector support
- metadata filtering
- sparse vector support
- hybrid search
- namespaces
- named vectors
- filter operators

A `WARN` indicates that the source driver supports a feature that the target driver does not support. Capability warnings do not necessarily block migration because the source collection may not use that feature.

### Resume an interrupted migration

VecPort can resume a migration by skipping records that already exist in the target collection.

```bash
vecport migrate \
  --from "vecport://qdrant?url=http://localhost:6333" \
  --to "vecport://milvus?uri=http://localhost:19530" \
  --collection documents \
  --target-collection documents_copy \
  --resume
```

Resume mode:

- checks whether the target collection already exists
- verifies known dimension and distance-metric compatibility
- checks record IDs in each batch
- skips records already present in the target
- writes only missing records

`--resume` cannot be combined with `--recreate-target` or `--dry-run`.

#### Existing record policies

Resume mode can control how records that already exist in the target are handled.

```bash
vecport migrate \
  --from "vecport://qdrant?url=http://localhost:6333" \
  --to "vecport://milvus?uri=http://localhost:19530" \
  --collection documents \
  --target-collection documents_copy \
  --resume \
  --existing-policy repair
```

Available policies:

- `skip` — skip any ID already present in the target
- `repair` — skip matching records and overwrite records whose vectors or metadata differ
- `error` — stop the migration when an existing record differs from the source

The default policy is `skip` for backward compatibility.

#### Collection compatibility

Migration plans also inspect collection-level configuration.

VecPort currently checks:

- vector dimension
- distance metric
- target collection existence
- source and target index type

Example:

```text
Collection information

Source dimension: 128
Source distance metric: cosine
Source index type: HNSW

Target exists: YES
Target dimension: 128
Target distance metric: cosine
Target index type: AUTOINDEX

Target dimension compatibility: OK
Distance metric compatibility: OK
```

A known dimension or distance-metric mismatch causes the migration plan to report `NOT READY`.

Index types are reported for visibility but do not currently block migration because index implementations differ between vector databases.

#### Configuration validation

VecPort validates YAML configuration before executing a command.

Invalid values such as negative dimensions, unsupported report formats, or malformed benchmark targets produce a configuration error before connecting to a database.

For example:

```yaml
benchmark:
  dimension: 128
  top_k: 10
  iterations: 100
  warmup: 10
  format: json

### Migration progress

Use `--progress` to display migration progress, throughput, and estimated remaining time.

```bash
vecport migrate \
  --from "vecport://qdrant?url=http://localhost:6333" \
  --to "vecport://milvus?uri=http://localhost:19530" \
  --collection documents \
  --target-collection documents_copy \
  --progress
```

Example output:

```text
Progress: 2500/10000 (25.0%) | 1450.2 records/s | ETA 5.2s | Batch 5
```

Progress reporting includes:

- scanned records
- completion percentage
- completed batches
- records per second
- estimated remaining time

Progress reporting can also be combined with resumable migrations.

### Environment Variables and Secrets

Sensitive values such as API keys should not be stored directly in `vecport.yml`.

VecPort supports environment-variable references using `${VARIABLE_NAME}` syntax.

```yaml
service:
  api_key: "${PINECONE_API_KEY}"
```

Set the environment variable before running VecPort.

PowerShell:

```powershell
$env:PINECONE_API_KEY="your-api-key"
```

VecPort resolves environment-variable references when loading the YAML configuration.

If a referenced environment variable is not defined, VecPort stops with an error instead of using an empty secret.

Do not commit API keys, tokens, passwords, or other credentials to Git.

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
```

## Driver Compliance

VecPort includes a driver compliance suite for validating whether a
vector database driver follows the VecPort contract.

```bash
vecport compliance \
  --url "vecport://qdrant"
```

The compliance suite validates:

- collection creation
- vector upsert and retrieval
- similarity search
- declared metadata filter behavior
- record scanning
- record deletion
- temporary collection cleanup

Example:

```text
VecPort Driver Compliance

create_collection    PASS
upsert_get           PASS
search               PASS
filter_eq            PASS
scan                 PASS
delete               PASS
cleanup              PASS

Compliance: PASSED
```

A JSON report can also be generated:

```bash
vecport compliance \
  --url "vecport://qdrant" \
  --output reports/compliance.json
```

The JSON report intentionally excludes the connection URL so credentials
and connection details are not persisted. Compliance checks use a temporary
collection and remove it automatically after the test unless `--no-cleanup`
is specified.

A successful compliance run exits with code `0`. A failed compliance run
exits with code `1`.

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

### Migration Reports

Migration results can be exported as JSON or CSV.

```bash
vecport migrate \
  --from "vecport://qdrant?url=http://localhost:6333" \
  --to "vecport://milvus?uri=http://localhost:19530" \
  --collection documents \
  --target-collection documents_migrated \
  --recreate-target \
  --verify \
  --format json \
  --output reports/migration.json
```

Migration reports can include:

- source collection
- target collection
- scanned records
- migrated records
- source record count
- target record count
- matched IDs
- missing IDs
- extra records
- vector dimension validation
- vector value validation
- metadata validation
- final verification status

Example JSON structure:

```json
{
  "type": "migration",
  "migration": {
    "source_collection": "documents",
    "target_collection": "documents_migrated",
    "scanned": 10000,
    "migrated": 10000
  },
  "verification": {
    "source_count": 10000,
    "target_count": 10000,
    "matched_ids": 10000,
    "missing_ids": 0,
    "extra_records": 0,
    "dimensions_ok": true,
    "vectors_ok": true,
    "metadata_ok": true,
    "passed": true
  }
}
```

CSV output is also supported:

```bash
vecport migrate \
  --from "vecport://qdrant?url=http://localhost:6333" \
  --to "vecport://milvus?uri=http://localhost:19530" \
  --collection documents \
  --target-collection documents_migrated \
  --recreate-target \
  --verify \
  --format csv \
  --output reports/migration.csv
```

JSON is useful for CI pipelines, APIs, and automated tooling, while CSV is convenient for spreadsheets and data analysis.

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
