# ADR: Ledger is a facts-only store

Status: accepted 2026-07-02 (supersedes the facts-plus-projections split
originally proposed in issue #71)

## Decision

Ledger stores source-published values only. The boundary is **who asserted
the value**, not level versus projection:

1. Anything a publisher asserted is a fact — including the publisher's own
   projections. "CBO's January 2026 baseline projects individual income tax
   receipts of $X in 2027" is a source-backed claim with lineage, exactly
   like an SOI observation. These facts carry
   `assertion: source_projection`; measured or administered outcomes carry
   the default `assertion: observation`.
2. Anything PolicyEngine computed — an aged, uprated, forecast, or
   reconciled level — is never a Ledger object. Such values are regenerable
   build artifacts and live in the consumer (Populace calibration owns
   aging), implemented as named, versioned models that consume growth-factor
   facts from Ledger and emit their own lineage.

Instead of projection objects, Ledger contributes three guarantees:

- **Reference-period semantics.** `PeriodDimension` identifies the period a
  value refers to; `PeriodCoverage` records non-identity provenance (start
  and end dates, basis, the publisher's period label, accounting basis) for
  cases like BE-SILC incomes that reference the year before the survey
  label.
- **Period-contract enforcement.** Resolving a profile target at a period
  other than the fact's reference period raises `PeriodContractError`
  unless the consumer passes an explicit `PeriodAlignmentDeclaration`
  (model id, version, parameters — never values). Ledger records the
  declaration in resolved rows and returns the published level untouched.
- **Basis-aware diagnostics.** Resolved rows carry `basis` (`fact` or
  `declared_alignment`), `fact_period`, `requested_period`, and the
  declaration, so downstream diagnostics distinguish "missed a published
  fact" from "missed an aged level."

## Why not facts plus projections in one schema

- **Thesis stays clean.** Thesis resolves forecasts against Ledger facts as
  official observations. If the store held PolicyEngine-computed
  projections, a forecast could be scored against partly-model output —
  circular. A facts-only store is a model-free resolution substrate.
- **Append-only stays meaningful.** Facts never churn. PolicyEngine-computed
  projections would churn on every CBO update and every aging-model version
  bump, turning an auditable ledger into a store of volatile derivations.
- **The consumer set does not need it.** Thesis does not want
  PolicyEngine-computed aging; validation comparators (TPC, JCT scores) are
  source-published and therefore facts; the only consumer of
  PolicyEngine-computed aged values is Populace calibration, so that is
  where the code belongs (PolicyEngine/populace#116).
- **The populace#212 lesson is a contract lesson.** The failure was not
  where aging lived; it was that un-aged consumption was silent — SOI
  TY2022/23 dollar levels calibrated exactly at 2024 while simulated 2025
  aggregates ran ~6–10% under current-year projections. The fix is making
  silent period mismatch impossible, which is a consumption-contract
  property, not a projection-object property.

## Consequences

- The `assertion` field enters canonical key payloads only when it is not
  the default, so every pre-existing observation fact keeps byte-identical
  v1 and v2 keys and byte-identical JSONL serialization.
- Source packages declare `assertion` and `period_coverage` per record set;
  values other than `observation` and `source_projection` fail validation
  with an error explaining that PolicyEngine-computed values are not facts.
- Consumer-contract rows always carry `assertion` explicitly, and the
  consumer artifact (`ledger build-consumer-artifact`) embeds profiles,
  fact rows, coverage diagnostics, and manifest hashes so Populace can
  build a target registry without database access or copied values
  (issue #61).
- Geography vintage translation (populace#205) follows the same pattern: a
  declared consumer-side transform over facts, never an edit to them.
