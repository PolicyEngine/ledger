# Arch Fact Identity Review Packet

This packet is meant for an external architecture review before changing Arch
fact keys or letting agents populate many new source packages.

## Context

Arch is Cosilico's source-data foundation. It should preserve publisher source
artifacts, parsed source rows/cells, source-backed aggregate facts, dimensions,
constraints, concept alignments, and provenance. Microplex should consume Arch
through downstream adapters and own source selection, aging, reconciliation,
target activation, and simulator-variable mappings.

Current PE broad target coverage through the Microplex adapter is 124 of 136
target cells. The remaining 12 gaps are intentionally marked
`survey_or_model_input_deprioritized` rather than loader-ready. State coverage
is 53 of 53.

## Current Implementation

Important files:

- `arch/core.py`: aggregate fact dataclasses, validation, labels, fact keys.
- `arch/sources/specs.py`: `CellSelectorSpec`, `SourceRecordSpec`,
  compact record-set specs, resolved source records.
- `arch/source_package.py`: declarative package loading and conversion from
  source records to aggregate facts.
- `arch/database.py`: SQLite Arch DB build artifact tables and inserts.
- `arch/suite.py`: build-suite reports and agent acceptance checks.
- `docs/agent-source-package-harness.md`: agent population contract.

Current `AggregateFact` has:

- semantic dimensions: period, geography, entity, measure, aggregation, domain,
  filters, constraints;
- source provenance: source name/table/file/URL/vintage/extraction metadata;
- lineage: `source_record_id`, `source_cell_keys`, `source_row_keys`;
- layout metadata: record-set ID, groupby row ID, measure column ID, ordinals.

Current fact-key construction in `arch.core._canonical_key_payload` includes:

- period;
- geography level/id/vintage;
- entity;
- full `Measure`, including concept evidence URL, evidence notes, authority,
  relation, and legal vintage;
- aggregation;
- domain;
- filters;
- selected source provenance fields;
- constraints.

It intentionally excludes human labels and source table layout. It also
currently excludes `source_record_id`.

## Problem

The key boundary is probably wrong for agent-authored packages:

- Evidence changes can churn fact keys even when the source value identity did
  not change.
- Legal-vintage or concept-alignment metadata may be review metadata rather
  than immutable source identity.
- `source_record_id` is the most natural stable source-record identity, but it
  is not key material today.
- Artifact coordinates and parsed source-cell/source-row lineage may be better
  identity anchors than semantic metadata alone.
- Direct legacy ETL loaders can create high-coverage `targets` rows without the
  lineage and build-suite acceptance needed for production Arch facts.

## Constraints

- Arch core must remain independent of Microplex and `microplex-us`.
- Human-readable labels are metadata only.
- Source/provenance must remain first-class.
- Stable keys should not churn when review notes, labels, evidence prose, or
  downstream adapter mappings change.
- Stable keys should change when the source fact identity changes: source
  artifact, period, geography, row/column/cell, measure, value semantics, or
  aggregate constraints.
- Source packages should be reproducible from source manifests and specs, with
  accepted DB artifacts mirrored to hosted storage.

## Proposed Direction For Review

Introduce a v2 identity split:

1. `source_record_key`
   Stable identity of the publisher record/cell being interpreted.
   Candidate material:
   - source artifact ID or checksum;
   - source table/file/vintage;
   - parser namespace/version;
   - record-set spec ID and spec hash;
   - source row ID and source column/measure ID;
   - source cell keys or source row keys when available.

2. `fact_key`
   Stable identity of the Arch aggregate fact emitted from that source record.
   Candidate material:
   - `source_record_id` or `source_record_key`;
   - period;
   - geography identity;
   - entity;
   - canonical concept and unit;
   - aggregation;
   - domain;
   - first-class constraints;
   - filters that are not already represented as constraints, if still needed.

3. `concept_alignment_key`
   Evidence-bearing assertion that source concept X maps to canonical concept Y.
   Candidate material:
   - source concept;
   - canonical concept;
   - relation;
   - authority;
   - legal/source vintage if it changes the alignment meaning.
   Evidence URL and notes should be metadata unless the evidence itself is part
   of a versioned assertion.

4. Metadata excluded from `fact_key`
   - human labels;
   - evidence notes;
   - evidence URL;
   - extraction method notes;
   - source display formatting;
   - row/column labels when IDs and coordinates already identify the record;
   - downstream adapter aliases.

## Specific Review Questions

1. Should `source_record_id` be required for production aggregate facts?
2. Should `source_record_id` be part of `fact_key`, or should `fact_key` point
   to a separate `source_record_key`?
3. Should artifact checksum be key material for source records, facts, both, or
   neither?
4. Should `concept_evidence_url`, `concept_evidence_notes`, and
   `legal_vintage` be excluded from fact identity?
5. Should concept alignment be a separate versioned assertion table rather than
   embedded inside `Measure`?
6. How should legacy `targets` rows migrate into this model without pretending
   they have source-cell/source-row lineage?
7. What is the minimum lineage required before an agent-authored source package
   can be marked production-ready?
8. Should value itself be key material? If not, what prevents silent value drift
   for the same identity?

## Paste-Ready ChatGPT Pro Prompt

```text
We are building Arch as Cosilico's standalone source-data registry and build
harness. Arch should store publisher/source facts with provenance, source-row or
source-cell lineage, dimensions, constraints, concept alignments, and stable
keys. Microplex consumes Arch through downstream adapters and owns source
selection, aging, reconciliation, target activation, and simulator variable
aliases.

Please review the fact identity design below and recommend a durable v2 schema.

Current state:
- AggregateFact includes period, geography, entity, measure, aggregation, source
  provenance, filters, domain, source_record_id, source_cell_keys,
  source_row_keys, constraints, and layout metadata.
- Current fact_key includes period, geography level/id/vintage, entity, the full
  Measure object, aggregation, domain, filters, source name/table/file/vintage,
  and constraints.
- Current fact_key excludes labels, source table layout, and source_record_id.
- Measure currently includes concept, unit, source_concept, concept_relation,
  concept_authority, concept_evidence_url, concept_evidence_notes, and
  legal_vintage.
- Source packages compile source rows/cells plus SourceRecordSpec into
  AggregateFact and an Arch SQLite DB artifact.
- Legacy ETL loaders still write some direct targets rows without source-cell or
  source-row lineage; we treat those as migration/compatibility inputs, not
  production Arch facts.

Questions:
1. What should be in immutable source_record identity?
2. What should be in immutable aggregate fact identity?
3. Should source_record_id or artifact coordinates be fact-key material?
4. Which metadata should never affect stable keys?
5. Should concept alignment be separate from Measure/fact identity?
6. Should values be part of identity or only checked by content/build hashes?
7. How should legacy target rows migrate into source-package facts?
8. What minimal lineage should be required before agents populate Arch at scale?

Please answer with a concrete schema/key proposal, a migration path from the
current implementation, and the biggest failure modes to test.
```
