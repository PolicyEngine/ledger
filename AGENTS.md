# Ledger Agent Rules

Ledger is a source-backed fact store. It may parse publisher artifacts, normalize
representation, preserve provenance, and declare target-profile contracts.

Do not put Populace work in Ledger:

- no cross-source reconciliation
- no aging to a build year
- no imputation
- no support-aware target activation
- no solver-ready target construction
- no target values in target profiles

Only approved Ledger agent roles in `.github/ledger-agents.yml` should add or
modify source packages, target profiles, or contract schemas. Source-data PRs
need deterministic validation plus the listed Ledger judge reviews before merge.
