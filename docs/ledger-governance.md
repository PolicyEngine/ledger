# Ledger Contribution Governance

Ledger is the source-of-truth layer for PolicyEngine government-statistics
release facts. Its job is to preserve publisher-backed facts with provenance.
Populace turns those facts into active, aged, reconciled calibration targets.

## Boundary

The store is facts-only, and the line is who asserted the value, not level
versus projection. A publisher's own forward-looking estimate — a CBO
baseline, a BFP outlook, an SSA trustees table, a TPC or JCT score — is a
source-backed claim like any other and enters Ledger as a fact typed
`assertion: source_projection`. A value PolicyEngine computed — an aged,
uprated, forecast, or reconciled level — is never a fact, whatever object it
hides in. This keeps three properties intact: every value in Ledger traces to
a publisher; facts never churn when models update, so append-only audit stays
meaningful; and Thesis can resolve forecasts against Ledger observations
without scoring model output against model output.

Ledger may:

- register raw publisher artifacts and checksums
- parse source rows and cells
- emit source-backed aggregate facts, including publisher projections typed
  `assertion: source_projection`
- record period-coverage provenance (reference period start/end, basis,
  source period label, accounting basis) for facts whose reference period
  needs disambiguation
- normalize representation, such as units, scales, dates, geography IDs, and
  same-source total/share arithmetic when the publisher defines that relation
- declare target profiles that select source-backed facts and measurement
  contracts without target values
- enforce the period contract at resolution: consuming a fact at a period
  other than its reference period requires the consumer's explicit
  `PeriodAlignmentDeclaration`, which Ledger records and passes through

Ledger must not:

- reconcile across sources
- age facts to a build year
- store PolicyEngine-computed values (aged, uprated, forecast, or reconciled
  levels) as facts or in any other store object
- compute an aligned value during resolution; it returns the published level
  and the consumer's declaration only
- impute missing values
- store raw survey or administrative microdata
- choose a support-aware active target subset
- build solver-ready calibration targets
- invent derived facts whose source is Ledger itself

## Approval Model

The repository uses `.github/CODEOWNERS` to route all changes through
`@PolicyEngine/core-developers`. Branch protection should require code-owner
review.

Approved agent roles live in `.github/ledger-agents.yml`. Contributions that
touch source packages, target profiles, or consumer contracts should name the
agent role used and attach the required deterministic checks and judge verdicts.

## Judge Model

Ledger follows the Axiom pattern: deterministic checks run first, then specialist
reviewers judge the source-data boundary with that evidence. The required judge
types are:

- `ledger-source-fidelity`
- `ledger-target-profile`
- `ledger-contract`
- `ledger-boundary`

The overall verdict fails if any required judge fails. A judge must fail if a
change moves reconciliation, aging, imputation, active target selection, or
solver construction from Populace into Ledger, or stores a
PolicyEngine-computed value as a fact.
