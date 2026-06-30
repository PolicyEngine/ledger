# PolicyEngine Ledger

PolicyEngine Ledger is the source-backed fact store for PolicyEngine,
Populace, and Thesis. New consumers should use the `policyengine_ledger`
import path and the `ledger` console command.

Ledger is PolicyEngine's source-data foundation for social simulation. It
captures source publications, preserves provenance, and represents published
values as structured, queryable facts.

Ledger may normalize structure: parse files, type values, declare units and
scales, assign geography and period identifiers, preserve lineage back to
source artifacts, and publish target profiles that identify source-backed facts
and measurement contracts. Ledger does not reconcile inconsistent sources,
impute missing data, or execute simulator-specific calibration.

Populace consumes Ledger facts and target profiles, selects the subset its
current support universe can target, applies minimal period alignment when
declared, and runs calibration. Thesis can consume the same facts and
measurement contracts as official observations.

## Purpose

This repository provides:

- **Sources**: Source file references, retrieval metadata, manifests, checksums,
  and provenance.
- **Facts**: Source-backed claims represented with typed values, units,
  geography, period, source table, and lineage.
- **Normalization**: Low-assumption representation changes such as unit/scale
  conversion and source-published total/share arithmetic.
- **Target profiles**: Source-backed target contracts and model-measurement
  bindings that Populace, Thesis, and future rule engines can consume.
- **Microdata**: Survey and administrative microdata ingestion for CPS, PUF,
  FRS, and related datasets.
- **Jurisdiction loaders**: Source-specific ETL that emits the shared Ledger
  schema.

Ledger facts are not PolicyEngine's assertion that a source claim is ultimately true.
They are source-backed claims with provenance.

## Boundary

The load-bearing rule:

> Ledger may re-express a published value and declare target contracts, but may
> not reconcile, impute, or transform published values in ways that change their
> meaning.

| Layer | Owns | Examples |
|-------|------|----------|
| Ledger Sources | Source artifacts and provenance | URLs, checksums, source files, parsed tables/cells |
| Ledger Facts | Structured source claims | SOI cells, ACS estimates, CPI values, CBO-published projections |
| Ledger Normalization | Representation changes | Unit scales, typed values, geography/date identifiers |
| Ledger Target Profiles | Source-backed calibration contracts | SOI EITC totals, CBO baselines, source-published growth factors, measurement bindings |
| Populace Targets | Build-ready active subset | Support-aware activation, solver inputs, diagnostics |

The storage split is documented in
[`docs/storage-architecture.md`](docs/storage-architecture.md): `ledger-raw`
stores immutable source bytes, `ledger-derived` stores reproducible build
artifacts, and Supabase/Postgres hosts the queryable relational Ledger registry
mirrored from accepted builds.

## Repository Model

Ledger is global at the schema, validation, database, and build-harness layer.
Jurisdiction packages are modular source packages that emit the same Ledger
objects.

```text
Planned GitHub repositories after the rename:
  PolicyEngine/ledger # Core schema, validation, harness, DB schema
  PolicyEngine/ledger-us   # US source parsers/specs; emits Ledger records
  PolicyEngine/ledger-uk   # UK source parsers/specs; emits Ledger records

Python distributions:
  policyengine-ledger
  policyengine-ledger-us
  policyengine-ledger-uk

Python imports:
  policyengine_ledger # New public API
  policyengine_ledger_us
  policyengine_ledger_uk
```

The current in-repo US package is a prototype while the core schema is still
moving. Until the GitHub repository rename lands, clone this repository into a
local `ledger` directory. Once the Ledger contract stabilizes, US and UK source
packages should move to `ledger-us` and `ledger-uk`. They must not fork
`AggregateConstraint`, source-row/source-cell lineage, stable keys, validation,
or the relational DB schema.

## Structure

```text
ledger/
├── policyengine_ledger/       # Public Ledger namespace
│   ├── sources/             # Source lineage helpers
│   ├── facts/               # Source-backed facts
│   ├── normalization/       # Low-assumption representation helpers
│   ├── targets/             # Target input schema, client, loaders
│   ├── microdata/           # Microdata registry, ingestion, queries
│   ├── jurisdictions/       # Temporary in-repo jurisdiction source prototypes
├── db/                      # SQLModel persistence and source loaders
│   ├── schema.py            # SQLModel: Target, Stratum, StratumConstraint
│   ├── supabase_client.py   # Supabase client helpers
│   └── etl_*.py             # Source-specific ETL pipelines
├── micro/                   # Legacy simulation consumer prototypes
├── calibration/             # Calibration target adapters and constraints
├── data/                    # Cached data files
└── docs/                    # Architecture and source documentation
```

New code should prefer `policyengine_ledger` for source-backed fact and target
profile consumers. Existing in-repo implementation code may continue using
legacy implementation modules while the namespace migration is completed.
Solver execution and calibrated dataset construction belong in Populace.

## Quick Start

### 1. Install

```bash
pip install policyengine-ledger
# Or for development, clone this repository into a Ledger-named directory:
git clone <current repository URL> ledger
cd ledger
pip install -e ".[dev]"
```

### 2. Initialize and Load Legacy Target Inputs

```bash
ledger init
ledger load soi --years 2021
ledger stats
```

### 3. Validate Fixture Facts

The standalone Ledger fact harness validates JSONL aggregate facts and emits a
JSON report with fact counts, QA counts, warnings, and validation errors:

```bash
uv run ledger validate-facts --fixture
```

To build a tiny source-backed fixture from the packaged IRS SOI Table 1.1
workbook and validate it:

```bash
uv run ledger build-fixture-facts soi-table-1-1 --year 2023 --output /tmp/ledger-soi-facts.jsonl
uv run ledger validate-facts --input /tmp/ledger-soi-facts.jsonl
```

To preserve the whole used range of that workbook as source-cell records before
semantic fact construction:

```bash
uv run ledger build-source-cells soi-table-1-1 --year 2023 --output /tmp/ledger-soi-cells.jsonl
uv run ledger validate-source-cells --input /tmp/ledger-soi-cells.jsonl
```

Delimited source packages should preserve the whole file as row records before
selecting facts. For example, the BEA NIPA flat file pilot parses all source
rows, then emits two selected pension contribution facts:

```bash
uv run ledger build-source-rows bea-nipa-pension-contributions --year 2022 --output /tmp/ledger-bea-rows.jsonl
uv run ledger validate-source-rows --input /tmp/ledger-bea-rows.jsonl
```

ZIP archives with rectangular publisher files use the same row-first contract.
The CMS Marketplace OEP state-level package preserves the raw CMS ZIP, parses
its CSV member into source rows/cells, and emits state-level enrollment and
APTC facts:

```bash
uv run ledger validate-package cms-aca-oep-state-level --year 2024
uv run ledger build-suite cms-aca-oep-state-level --year 2024 --out /tmp/ledger-cms-aca-oep-2024 --replace
```

To build a relational Ledger DB artifact with aggregate facts, first-class
constraints, source-cell lineage, and source-row lineage when available:

```bash
uv run ledger build-db --fixture --db /tmp/ledger-fixture.db --replace
```

This writes queryable Ledger-owned tables such as `source_rows`,
`source_columns`, `source_row_values`, `source_cells`, `aggregate_facts`,
`aggregate_constraints`, `concept_alignments`, `fact_source_cells`, and
`fact_source_rows`. The DB is a deterministic build artifact from source
manifests, parsers, and checked-in specs; hosted Postgres/Supabase should mirror
this schema rather than become the unreproducible origin of source-backed facts.

To run the source-package build suite agents should target, build the source
rows/cells, source-region spec, selector report, aggregate facts, DB artifact,
and JSON reports into one output directory:

```bash
uv run ledger build-suite soi-table-1-1 --year 2023 --out /tmp/ledger-suite --replace
```

The same command accepts a declarative package directory. This is the preferred
agent authoring surface:

```bash
uv run ledger build-suite packages/irs_soi/table_1_1 --year 2023 --out /tmp/ledger-suite --replace
```

The first UK source packages use the OBR March 2026 EFO receipts and
expenditure workbooks and emit 2025-26 fiscal-year aggregate facts:

```bash
uv run ledger validate-package obr-efo-receipts --year 2025
uv run ledger build-suite obr-efo-receipts --year 2025 --out /tmp/ledger-obr-efo-receipts-2025 --replace
uv run ledger validate-package obr-efo-expenditure --year 2025
uv run ledger build-suite obr-efo-expenditure --year 2025 --out /tmp/ledger-obr-efo-expenditure-2025 --replace
uv run ledger validate-package slc-student-support-england-2025 --year 2025
uv run ledger build-suite slc-student-support-england-2025 --year 2025 --out /tmp/ledger-slc-student-support-england-2025 --replace
```

The first ZIP-backed PE migration package is CMS Marketplace OEP state-level
PUF:

```bash
uv run ledger validate-package cms-aca-oep-state-level --year 2024
uv run ledger build-suite cms-aca-oep-state-level --year 2024 --out /tmp/ledger-cms-aca-oep-2024 --replace
```

This writes:

```text
<output-dir>/
  datapackage.json
  ro-crate-metadata.json
  source_rows.jsonl
  source_cells.jsonl
  source_regions.jsonl
  facts.jsonl
  consumer_facts.jsonl
  ledger.db
  reports/
    source_rows.json
    source_cells.json
    source_regions.json
    selectors.json
    source_records.json
    facts.json
    consumer_facts.json
    concept_alignments.json
    database.json
    agent_acceptance.json
    build_summary.json
```

Agent-authored source packages should be judged by these reports. They should
add or update source manifests, parsers, selector specs, and source-record
specs; they should not hand-edit DB artifacts or core schemas.
The quick gate is `reports/agent_acceptance.json`, which checks raw R2 links,
full-document parsing, fact provenance, source-cell/source-row lineage,
expected first-class constraints, row-backed filter/constraint evidence,
concept alignment evidence, Axiom concept validation status, and stage-report
validity.

To build the downstream integration artifact Populace can inspect, merge
available source-package suites for a year into one bundle:

```bash
uv run ledger build-bundle --year 2023 --out /tmp/ledger-us-2023 --replace
```

This writes a root `consumer_facts.jsonl`, `source_packages.json`,
`coverage.json`, and `reports/build_bundle.json`. Source-specific suite outputs
remain nested under `sources/<source-package>/`. The bundle coverage report
includes counts by source, geography, entity, period, observed measure, and
concept plus duplicate `aggregate_fact_key` and `semantic_fact_key` diagnostics.
The row-level downstream contract is `consumer_facts.jsonl`; the other bundle
files are diagnostic reports for gating and review. Consumer-contract rows must
carry canonical constraints explicitly in `universe_constraints`; source-layout
`dimensions` are metadata and are not target constraints.

Builds without an Axiom CLI still pass when the source package is otherwise
valid, but `agent_acceptance.json` warns with
`concept_alignment_validation_skipped`. For strict agent review, require every
canonical concept to resolve through Axiom:

```bash
uv run ledger build-suite packages/irs_soi/table_1_1 \
  --year 2023 \
  --out /tmp/ledger-suite \
  --replace \
  --axiom-cli axiom \
  --axiom-root ../rules-us \
  --require-axiom-validation
```

For the faster authoring loop before running the full build suite, validate a
package directory directly:

```bash
uv run ledger validate-package packages/irs_soi/table_1_1 --year 2023
```

To start a new package from the constrained YAML template:

```bash
uv run ledger scaffold-package --source-id irs_soi --package-id soi-table-1-2 \
  --out packages/irs_soi/table_1_2 \
  --source-table "Publication 1304 Table 1.2" \
  --resource-directory data/irs_soi/table_1_2
```

Raw source artifacts should be content-addressed and checksum-locked before a
package spec depends on them. Tiny fixtures can stay in Git, but production raw
files should live in private Cloudflare R2 buckets, with `manifest.yaml` and the
hosted database carrying the queryable provenance:

```bash
# One-time after creating the PolicyEngine Cloudflare account and running
# `npx wrangler login`:
uv run ledger bootstrap-r2 --raw-bucket ledger-raw --derived-bucket ledger-derived

# Fetch/register a source artifact, write db/data/.../manifest.yaml, and upload
# the exact bytes to R2 when Wrangler is authenticated:
uv run ledger fetch-artifact \
  --url https://www.irs.gov/pub/irs-soi/23in12ms.xls \
  --source-id irs_soi \
  --package-id soi-table-1-2 \
  --year 2023 \
  --out-dir db/data/irs_soi/table_1_2 \
  --source-page https://www.irs.gov/statistics/soi-tax-stats-individual-income-tax-returns-complete-report-publication-1304-basic-tables-part-1 \
  --table "Publication 1304 Table 1.2" \
  --upload-r2

# Audit local manifests and checksums:
uv run ledger inventory-artifacts --root db/data

# Upload all existing manifest-declared local artifacts to ledger-raw and write
# storage.r2 metadata back into the manifests:
uv run ledger publish-raw --root db/data
```

To coordinate broad PE source migration without jumping straight to semantic
target construction, generate an agent batch plan from the PE manifest:

```bash
uv run ledger plan-pe-sources \
  --manifest docs/pe-us-source-manifest.csv \
  --out docs/pe-us-source-agent-plan.json \
  --markdown docs/pe-us-source-agent-plan.md
```

The plan marks existing source packages, primary-source lookup work,
fetch/register work, source-cell scaffolds, and repair items. Fetch hints
include `--upload-r2`; semantic target work still requires a package to pass
`build-suite`. Aggregators such as FRED stay in the migration plan only as
publisher-source lookup clues; they should not become canonical Ledger source
artifacts or target provenance.

R2 owns the immutable bytes. Ledger manifests and Supabase/Postgres mirrors own
metadata such as source URL, checksum, size, vintage, extraction date, and R2
key. Source-package parsers still read deterministic local/package resources,
so builds remain reproducible without making hosted storage the source of
schema truth.

The same build-suite path also supports the SOI Table 1.4 wage pilot:

```bash
uv run ledger build-suite soi-table-1-4 --year 2023 --out /tmp/ledger-suite-1-4 --replace
uv run ledger build-suite packages/irs_soi/table_1_4 --year 2023 --out /tmp/ledger-suite-1-4 --replace
```

To prepare the deterministic SQLite artifact for a hosted Supabase/Postgres
mirror, export each relational table to JSONL plus a manifest:

```bash
uv run ledger export-db-tables --db /tmp/ledger-suite/ledger.db --out /tmp/ledger-mirror --replace
```

To publish the deterministic build outputs to the `ledger-derived` R2 bucket:

```bash
uv run ledger publish-derived \
  --dir /tmp/ledger-suite \
  --source-id irs_soi \
  --package-id soi-table-1-1 \
  --year 2023 \
  --build-artifacts-out /tmp/ledger-build-artifacts.jsonl
```

The Supabase schema for this mirror lives at
`supabase/migrations/20260504_ledger_bronze.sql`. Raw government spreadsheets are
mirrored as artifact metadata plus one row per parsed cell, not one tidy table
per sheet. Typed rectangular microdata can still use separate raw microdata
tables.

After the migration is applied and the `ledger` schema is exposed through the
Supabase Data API, accepted mirror exports can be upserted with:

```bash
uv run ledger load-supabase-mirror \
  --dir /tmp/ledger-mirror \
  --build-artifacts /tmp/ledger-build-artifacts.jsonl
```

Use `--dry-run` first to validate JSONL row counts and file coverage without
writing to Supabase.

Ledger facts keep source concepts and canonical concepts separately. For example,
the SOI Table 1.1 adjusted gross income column is preserved as
`irs_soi.adjusted_gross_income`, while the canonical concept is
`us:statutes/26/62#adjusted_gross_income` with an `exact` alignment assertion.
The SOI Table 1.4 wage amount column is preserved as `irs_soi.total_wages`,
while the canonical concept is `us:statutes/26/62#input.wages` with a
`broad_match` assertion because Axiom currently treats wages as an inferred
input under IRC section 62 rather than an exact statutory term.
This lets Ledger share vocabulary with Axiom legal terms without importing Axiom
runtime code.

To validate source-to-canonical concept alignments against an installed Axiom
concept CLI outside the full suite:

```bash
uv run ledger validate-concept-alignments --input /tmp/ledger-soi-facts.jsonl \
  --axiom-cli axiom \
  --axiom-root ../rules-us
```

The command emits JSON with the alignments checked, validation errors, and
warnings. If the Axiom CLI is omitted, Ledger still reports alignment metadata and
warns that external concept validation was skipped. `build-suite` accepts the
same `--axiom-cli` and `--axiom-root` flags, plus
`--require-axiom-validation` when skipped concept checks should fail agent
acceptance.

### 4. Run Ledger Explorer

Ledger Explorer is a Next/Tailwind app that reads the fixture fact JSONL and
source-cell JSONL, then shows aggregate facts, source-cell lineage, and
consumer-contract fields:

```bash
cd explorer
npm install
npm run dev -- --port 3090
```

Then open `http://localhost:3090`.

By default, the workbench reads the current local suite outputs at
`/tmp/ledger-us-2023-parity/sources/*` and
`/tmp/ledger-soi-historic-table-2-2022`. To point it at another build, set:

```bash
LEDGER_EXPLORER_DATA_DIRS=/tmp/ledger-build-a,/tmp/ledger-build-b npm run dev -- --port 3090
```

### 5. Query Target Inputs in Python

```python
from policyengine_ledger.targets import DataSource, Target, TargetType
from calibration.targets import get_targets

target_inputs = get_targets(
    jurisdiction="us",
    year=2021,
    sources=["irs-soi"],
)
```

### 6. Query Microdata

```python
from policyengine_ledger.microdata import query_cps_asec

persons = query_cps_asec(year=2024, table_type="person", limit=10_000)
```

## Target Input Schema

Target inputs use a three-table schema:

- **strata**: Population subgroups, such as California filers with AGI between
  $50k and $75k.
- **stratum_constraints**: Rules defining each stratum.
- **targets**: Source-published aggregate values linked to strata.

These are inputs to Ledger target profiles. Populace owns the active
support-aware subset and calibrated solver execution.

## Ledger Facts And Populace Targets

Source facts should be structurally normalized before Populace considers them
as calibration target candidates.
Normalization is about representation, not modeling: units, scales, typed
values, geography IDs, period IDs, and same-source arithmetic where the source
publishes the total/share relationship.

Inflation, cross-source reconciliation, and support-aware activation belong in
Populace unless the source itself publishes the adjusted or projected series.
Target profiles in Ledger may declare the source-backed rows and measurement
bindings Populace is allowed to activate.

```python
from policyengine_ledger.facts import SourceFact
from policyengine_ledger.normalization import convert_units

fact = SourceFact(
    name="snap_households",
    value=22_323,
    period=2023,
    unit="thousands",
    source="usda_snap",
    jurisdiction="us",
)

normalized_fact = convert_units(fact, 1000, "count")
```

## Current Coverage

### Microdata

| Source | Variables | Description |
|--------|-----------|-------------|
| US CPS ASEC | 78 | Census household survey |
| US IRS PUF | 33 | Tax return sample |
| UK FRS | 29 | DWP household survey |

### Aggregate Facts And Target Inputs

| Source | Coverage | Description |
|--------|----------|-------------|
| IRS SOI | National, state, AGI brackets | Tax return aggregates |
| Census | Demographics, poverty, districts | Population statistics |
| BLS | Labor market and price data | Employment and index series |
| CBO | Federal projections | Budget and economic projections |
| SSA/SSI | National and state programs | Social Security data |
| SNAP | State-level | Food assistance |
| CMS | Medicaid and ACA enrollment | Health coverage |
| HMRC/ONS/OBR | UK tax, population, projections | UK official statistics |

## Boundaries

- **Ledger** owns source data, provenance, source facts, aggregate facts,
  microdata ingestion, target profiles, and measurement contracts.
- **Populace** owns support-aware target activation, minimal period alignment,
  simulation interfaces, entity modeling, weights, diagnostics, and calibration
  execution.
- **Jurisdiction source packages** such as `ledger-us` and `ledger-uk` own
  source-specific parsers and specs that emit shared Ledger records.
- **Jurisdiction simulation packages** own simulation-specific variable
  mappings and target recipes.
- **PolicyEngine** owns policy-facing tools and analysis workflows.

## Related Repositories

- [populace](https://github.com/PolicyEngine/populace) - Simulation data builds,
  target selection, and calibration execution.
- [thesis](https://github.com/PolicyEngine/thesis) - Public-facing official
  observations and analysis surfaces backed by Ledger facts.
