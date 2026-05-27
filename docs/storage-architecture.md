# Arch Storage Architecture

This note is the canonical storage plan for Arch while the source-package
harness stabilizes. The detailed agent workflow remains in
`docs/agent-source-package-harness.md`; this document only defines where each
class of Arch data belongs.

## Decision Summary

Arch uses three storage layers with different jobs.

`arch-raw` is the immutable source-byte archive. It stores exact publisher
artifacts as fetched: workbooks, CSVs, PDFs, ZIPs, HTML snapshots, public raw
microdata files when allowed, and similar source files. Raw objects are
content-addressed by checksum and should never be overwritten in place.

`arch-derived` is the reproducible artifact archive. It stores build outputs
that Arch can regenerate from raw bytes, package specs, parser code, and build
configuration. Examples include parsed-cell or parsed-row Parquet/JSONL files,
source record outputs, `arch.db`, mirror JSONL exports, QA reports, Data
Package metadata, and RO-Crate metadata.

Supabase/Postgres is the queryable relational registry for accepted Arch
builds. It stores rows that applications, agents, and downstream systems need
to search and join: source artifacts, source rows/cells, source records,
aggregate facts, aggregate constraints, concept alignments, lineage edges, build
metadata, validation status, and object-location pointers. Supabase is not the
source of raw bytes and should not be hand-edited as the ingestion authority.

The deterministic local build remains the authority for source-backed facts.
Hosted tables mirror accepted build outputs and provide a shared query surface.

## Ownership Matrix

| Data class | Git/local package | `arch-raw` R2 | `arch-derived` R2 | SQLite `arch.db` | Supabase/Postgres |
|------------|-------------------|---------------|-------------------|------------------|-------------------|
| Source package specs | Authoritative YAML and parser code | No | Optional packaged snapshot | No | Metadata only |
| Raw publisher files | Tiny fixtures only | Authoritative bytes | No | Metadata only | Metadata plus R2 pointer |
| Source manifests | Authoritative checked metadata | No | Optional snapshot | Metadata loaded into tables | Queryable artifact registry |
| Parsed source rows/cells | Generated local output | No | Snapshot artifact | Queryable table | Queryable mirror |
| Source records/facts | Generated local output | No | Snapshot artifact | Queryable table | Queryable mirror |
| Aggregate constraints | Generated local output | No | Snapshot artifact | Queryable table | Queryable mirror |
| Build reports and QA | Generated local output | No | Snapshot artifact | Build summary rows | Queryable validation status |
| Mirror JSONL exports | Generated local output | No | Snapshot artifact | Export source | Bulk-load input |
| Microplex active targets | No | No | No | No | Future adapter output outside Arch core |

## Object Key Conventions

Raw source artifacts use the implemented content-addressed key shape:

```text
raw/{source_id}/{package_id}/{year}/{sha256}/{filename}
```

For example:

```text
raw/irs_soi/soi-table-1-1/2023/842da11...aca17/23in11si.xls
```

Derived build artifacts should use build-scoped keys so different builds can
coexist and be audited:

```text
derived/{source_id}/{package_id}/{year}/{build_id}/{artifact_name}
```

Examples:

```text
derived/irs_soi/soi-table-1-1/2023/{build_id}/source_cells.jsonl
derived/bea/bea-nipa-pension-contributions/2022/{build_id}/source_rows.jsonl
derived/irs_soi/soi-table-1-1/2023/{build_id}/arch.db
derived/irs_soi/soi-table-1-1/2023/{build_id}/reports/build_summary.json
derived/irs_soi/soi-table-1-1/2023/{build_id}/mirror/aggregate_facts.jsonl
```

Derived artifacts are reproducible and may be replaced by a new build, but a
specific `{build_id}` path should be immutable once published.

## Relational Registry Contract

The hosted `arch` schema should be the lookup surface for Arch, not the place
where agents invent source facts. Rows should be bulk-loaded from deterministic
build outputs.

The registry should expose:

- source artifact identity: source name, table/file, URL, vintage, extraction
  date, extraction method, checksum, size, and raw R2 bucket/key/URI;
- source rows/cells and source records, including exact source-row and
  source-cell lineage;
- source columns and source-row values, so row-oriented artifacts are queryable
  by raw or normalized column names without JSON scans;
- aggregate facts and aggregate constraints with stable keys, dimensions,
  filters, units, aggregation semantics, labels, and source provenance;
- concept alignments, including source concept, canonical concept, relation,
  authority, legal vintage, and evidence;
- build metadata, validation status, and derived artifact R2 bucket/key/URI.

The current Supabase migration mirrors the core relational tables and includes
R2 location fields for raw source artifacts and derived build artifacts, so the
registry can serve as the shared index over both R2 buckets.

## Build And Publish Flow

The intended flow is:

1. Register raw source artifacts with `uv run arch fetch-artifact`, which
   writes local bytes, records checksums in `manifest.yaml`, and can upload the
   exact bytes to `arch-raw`. Existing manifest-declared artifacts can be
   checksum-validated, uploaded, and linked with `uv run arch publish-raw`.
   Production package specs may omit raw bytes from Git as long as the manifest
   keeps `source_url` and SHA-256 metadata; builds can fill
   `ARCH_SOURCE_ARTIFACT_CACHE_DIR` by setting `ARCH_SOURCE_ARTIFACT_FETCH=1`.
2. Validate and build a source package with `uv run arch validate-package` and
   `uv run arch build-suite`.
3. Produce local deterministic outputs: parsed rows/cells, source records,
   aggregate facts, `arch.db`, QA reports, Data Package metadata, and RO-Crate
   metadata.
4. Export relational mirror files with `uv run arch export-db-tables`.
5. Publish derived build outputs to `arch-derived`:

   ```bash
   uv run arch publish-derived \
     --dir /tmp/arch-suite \
     --source-id irs_soi \
     --package-id soi-table-1-1 \
     --year 2023 \
     --build-artifacts-out /tmp/arch-build-artifacts.jsonl
   ```

6. Bulk-load or upsert accepted relational rows into Supabase/Postgres:

   ```bash
   uv run arch load-supabase-mirror \
     --dir /tmp/arch-mirror \
     --build-artifacts /tmp/arch-build-artifacts.jsonl
   ```

The Supabase project must have the checked migration applied and the `arch`
schema exposed in PostgREST/Data API settings before the REST loader can write
to it. Use `--dry-run` to verify local JSONL files without writing.

## Non-Goals

Supabase should not store large raw binary artifacts. It should point to R2.

R2 should not be the schema authority. It stores bytes and reproducible build
files, while Arch code and checked specs define semantics.

Arch should not own Microplex source selection, aging, reconciliation,
activation profiles, or simulator-specific target mappings. Those belong in
Microplex or thin downstream adapters.
