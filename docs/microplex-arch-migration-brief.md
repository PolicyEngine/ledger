# Microplex Arch Migration Brief

Status: handoff brief for Microplex migration agents

## Goal

Migrate Microplex target inputs to consume Arch source facts through a thin
downstream adapter, without moving Microplex responsibilities into Arch.

Arch owns publisher facts, provenance, lineage, dimensions, constraints,
concept alignment, stable source fact keys, and reproducible source-package
builds.

Microplex owns source selection, aging, reconciliation, active target profiles,
model variable aliases, target activation, imputation, and calibrated microdata
outputs.

## First Migration Slice

Start with a read-only adapter path for IRS SOI facts, especially:

- SOI Publication 1304 Table 1.1;
- SOI Publication 1304 Table 1.4;
- tax year 2023 first, then earlier years if needed.

The first milestone is not broad source ingestion. The first milestone is an
end-to-end golden comparison where Microplex can produce its current
value/constraint-style target rows from Arch-backed SOI facts.

To generate a small Arch-owned consumer-contract fixture:

```bash
uv run arch export-consumer-facts \
  --fixture \
  --output /tmp/arch-consumer-facts.jsonl
```

For a fresh source-package build, use the build-suite output:

```bash
uv run arch build-suite soi-table-1-1 \
  --year 2023 \
  --out /tmp/arch-soi-table-1-1 \
  --replace
```

The suite writes `/tmp/arch-soi-table-1-1/consumer_facts.jsonl` and
`/tmp/arch-soi-table-1-1/reports/consumer_facts.json`. `consumer_facts.jsonl`
is the preferred migration fixture. It is not a Microplex target table export;
it is an Arch fact contract with source-specific and semantic keys.

For Microplex integration work, prefer the year-level bundle once more than one
source package is in play:

```bash
uv run arch build-bundle \
  --year 2023 \
  --out /tmp/arch-us-2023 \
  --replace
```

The bundle writes `/tmp/arch-us-2023/consumer_facts.jsonl`,
`/tmp/arch-us-2023/source_packages.json`,
`/tmp/arch-us-2023/coverage.json`, and
`/tmp/arch-us-2023/reports/build_bundle.json`. It keeps per-source suite
outputs under `/tmp/arch-us-2023/sources/`. The coverage report gives
Microplex agents counts by source, geography, entity, period, observed measure,
and concept plus duplicate Arch key diagnostics. Treat `consumer_facts.jsonl` as
the row-level contract; `coverage.json` and `source_packages.json` are bundle
diagnostic reports for gating and review.

The contract schema and tiny checked-in sample live at:

- `docs/schemas/consumer_fact.v1.schema.json`
- `arch/fixtures/consumer_facts.jsonl`

Use the schema to validate exported rows in Microplex without importing Arch.

## Microplex Should Consume From Arch

Microplex should read:

- `semantic_fact_key`: source-agnostic statistic handle;
- `aggregate_fact_key`: selected source-specific observation;
- value and unit;
- period;
- geography;
- entity/unit of analysis;
- dimensions;
- universe constraints;
- observed measure;
- canonical concept alignment when available;
- source provenance for audit display;
- source lineage keys for traceability.

Microplex should not use source row/cell keys as target identity. Source rows
and cells are lineage and audit data.

Facts in `consumer_facts.jsonl` must carry semantic constraints explicitly in
`universe_constraints`. Source-layout `dimensions` are useful metadata for
display, filtering, and source-table reconstruction, but downstream adapters
should not treat them as canonical target constraints.

## Microplex Should Not Move Into Arch

Do not add these responsibilities to Arch:

- choosing which source wins;
- aging facts to a model year;
- reconciling multiple sources;
- selecting active target profiles;
- mapping to PolicyEngine or Microplex simulator variables;
- target priority or calibration weight choices;
- imputation assumptions;
- model-specific aliases;
- calibrated microdata outputs.

Those stay in Microplex or jurisdiction-specific downstream packages.

## Adapter Shape

The Microplex adapter should map Arch facts into the same value/constraint-style
target rows Microplex currently expects.

Suggested adapter inputs:

```text
Arch AggregateFact
  aggregate_fact_key
  semantic_fact_key
  value
  unit
  period
  geography
  entity
  aggregation
  dimensions
  universe_constraints
  observed_measure
  concept_alignment
  source_provenance
```

Suggested adapter outputs:

```text
Microplex target value row
  target_id or target_key
  variable/model alias
  value
  unit
  period
  geography
  source aggregate_fact_key
  semantic_fact_key
  provenance fields

Microplex constraint rows
  target_id or target_key
  variable/concept
  operator
  value
  unit
  entity
  source aggregate_fact_key
```

The adapter may add Microplex-specific aliases and activation metadata, but
those fields should not be written back into Arch source facts.

## Golden Comparison Requirement

For the first SOI slice, build a comparison test:

1. Generate current Microplex target rows using the existing path.
2. Generate Microplex target rows using Arch-backed SOI facts.
3. Normalize row order and nonsemantic metadata.
4. Assert values, units, periods, geography, entity, model aliases, and
   constraints match.
5. Assert the Arch-backed path carries richer provenance:
   - `aggregate_fact_key`;
   - `semantic_fact_key`;
   - source release/artifact metadata;
   - source record/cell lineage when available.

The expected outcome is identical target behavior with better source audit
metadata.

## Target Inventory Categories

Before broad migration, inventory current Microplex targets into four buckets:

1. Already represented by Arch source facts.
2. Representable after a small Arch source-package addition.
3. Belongs in Microplex because it is aged, reconciled, derived, selected, or
   otherwise target-composed.
4. Survey-based or lower priority for now.

This inventory should drive the migration order.

## Key Boundary

Use the Arch identity split:

- `aggregate_fact_key`: source-specific observation in an immutable source
  release.
- `semantic_fact_key`: source-agnostic statistic for reconciliation and
  downstream selection.
- `source_record_key` and `source_cell_key`: lineage only.
- `concept_alignment_key`: reviewable source-to-canonical concept assertion.

If a Microplex target requires a different key, the adapter should create that
Microplex key downstream. Do not mutate Arch keys to match Microplex naming.

## Recommended Sequence

1. Add/read an Arch facts fixture or built artifact in Microplex tests.
2. Implement the SOI Arch-to-Microplex adapter in Microplex, not Arch core.
3. Add the golden comparison against existing SOI target generation.
4. Mark the adapter path experimental until the comparison passes.
5. Switch one Microplex profile or target family to Arch-backed SOI facts.
6. Repeat by source family.

## Done Criteria For First Slice

- Microplex can generate current SOI target rows from Arch facts.
- Existing Microplex target behavior is unchanged.
- Golden comparison passes.
- Arch provenance and keys are preserved in Microplex output metadata.
- No Microplex dependency is introduced into Arch core.
- Aging, reconciliation, source selection, and model aliases remain downstream.
