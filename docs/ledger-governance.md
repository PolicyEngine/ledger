# Ledger Contribution Governance

Ledger is the source-of-truth layer for PolicyEngine government-statistics
release facts. Its job is to preserve publisher-backed facts with provenance.
Populace turns those facts into active, aged, reconciled calibration targets.

## Boundary

Ledger may:

- register raw publisher artifacts and checksums
- parse source rows and cells
- emit source-backed aggregate facts
- normalize representation, such as units, scales, dates, geography IDs, and
  same-source total/share arithmetic when the publisher defines that relation
- declare target profiles that select source-backed facts and measurement
  contracts without target values

Ledger must not:

- reconcile across sources
- age facts to a build year
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
solver construction from Populace into Ledger.
