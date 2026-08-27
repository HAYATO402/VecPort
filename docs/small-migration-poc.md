# VecPort Small Migration PoC

VecPort Small Migration PoC is a fixed-scope service for assessing and
demonstrating a small vector database migration in a test environment.

## Outcome

The service covers one supported source database, one supported target
database, and one collection. It produces a repeatable assessment, migration,
verification, benchmark, and customer-facing report workflow.

Supported databases:

- Qdrant
- Pinecone
- Weaviate
- Milvus
- pgvector

## Deliverables

Every completed PoC provides:

1. Migration Plan
2. Migrated vector data
3. Schema and metadata mapping
4. Filter mapping
5. Python search-code change proposal
6. Before-and-after validation and benchmark results
7. Migration Report

Customer deliverables use the following structure:

```text
customer-migration/
├── 01_migration_plan.md
├── 02_schema_mapping.yml
├── 03_filter_mapping.md
├── 04_code_changes/
│   ├── before.py
│   └── after.py
├── 05_verification.json
├── 06_benchmark.json
├── 07_migration_report.md
└── README.md
```

Customer intake files, generated runs, and deliverables are local artifacts.
They must not be committed to the VecPort repository.

## Scope

Included:

- one source database to one target database
- one collection
- dense vectors
- IDs and basic schema information
- metadata
- `$eq`, `$ne`, `$gt`, `$gte`, `$lt`, `$lte`, `$in`, `$and`, and `$or`
- migration planning and execution
- data verification
- benchmark comparison
- Python code-change proposal for native SDK, LangChain, or LlamaIndex usage

Not included:

- sparse, hybrid, multi-vector, or named-vector migrations
- production zero-downtime cutovers
- multi-region migration
- large or complex ACL migrations
- production SLA or 24/7 support
- performance guarantees outside the supplied test environment and dataset

## Size and pricing boundaries

Initial service tiers:

| Tier | Boundary | Indicative price |
|---|---|---:|
| Small PoC | Up to 10,000 vectors, one collection | JPY 50,000 |
| Small Plus | Up to 100,000 vectors, up to three collections after review | JPY 100,000 |
| Standard Migration | Production and broader requirements | From JPY 250,000 |

The automated Small PoC workflow remains limited to exactly one collection.
Projects above 50,000 vectors require review, and projects above 100,000
vectors are outside the PoC scope.

## Risk levels

- `LOW`: dense vector, one collection, supported filters, and compatible
  dimensions and distance metric.
- `MEDIUM`: metadata transformation or Small Plus volume requires manual
  review.
- `HIGH`: unsupported vector mode or filter, multiple collections, dimension
  mismatch, distance mismatch, unsupported application stack, or more than
  100,000 vectors.

Assessment recommendations are:

- `READY` for low-risk projects
- `CONDITIONAL` for medium-risk projects
- `NOT READY` for high-risk projects

## Completion criteria

The product is ready when an operator can:

1. capture the customer requirements in one intake YAML file;
2. assess migration feasibility within 30 minutes;
3. execute Assessment, Plan, Migration, Verification, Benchmark, and Report
   using a repeatable procedure; and
4. deliver the seven fixed outputs without placing customer data or secrets in
   GitHub.

Assessment is read-only. Its output describes compatibility in the supplied
environment and is not a production performance guarantee.
