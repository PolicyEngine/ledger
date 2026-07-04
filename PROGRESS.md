# PROGRESS: ledger hygiene fixes (#77 / #78 / #79)

Executed by general-purpose subagent under Fable lead direction.

## Layout (per coordinator course-correction)
- Worktree: `~/PolicyEngine/_worktrees/ledger-fixes`
- Branch: `ledger-hygiene-fixes` off `origin/main` (3c80129)
- One commit per fix on this single branch. PR(s) via `gh pr create --body-file`. No merge.

## NOTE for coordinator (state reconciliation)
Coordinator believed no worktree existed ("died during setup twice"). In fact THREE
pre-existing worktrees were already on disk when I started, on origin-pushed empty
branches (each == origin/main tip, only a PROGRESS.md commit added by me this session):
  - `~/PolicyEngine/_worktrees/ledger-77`  (branch `fix/etl-snap-fabricated-data`)
  - `~/PolicyEngine/_worktrees/ledger-78`  (branch `fix/build-bundle-alias-drift`)
  - `~/PolicyEngine/_worktrees/ledger-79`  (branch `fix/source-package-label-year-keys`)
These were NOT created by me. Per the coordinator's explicit single-branch direction,
I am NOT using them and left them untouched (did not delete origin branches — not my call).
They can be pruned later if unwanted. No fix code was ever committed to them.

Protected branch `codex/thesis-ledger-facts`: UNTOUCHED (confirmed, never checked out).

## Status
- [x] #77 investigation: etl_snap.py SNAP_DATA is LIVE, not dead (evidence below) -> replace with FNS-parsed values + provenance
- [x] #77 implementation: SNAP_DATA deleted; ETL now sources FY2024 facts from packages/usda_snap; tests rewritten to assert vs source facts; 12/12 pass; ruff clean; CI `load all` verified. COMMITTED.
- [x] #78 build-bundle alias drift: FIXED (fail-loudly path). New in source_package.py: SOURCE_PACKAGE_ROOT, discover_source_package_dirs(), find_alias_map_drift(), assert_alias_map_covers_packages(), SourcePackageAliasDriftError. build_bundle() calls the assert for default (non-explicit) source lists -> raises naming any packages/* dir with no alias entry (silently-dropped) or stale alias. TDD: plant-unmapped-dir test asserts loud build_bundle failure + drift-detection unit tests on temp dirs. 7/7 new tests pass; existing 6 bundle tests still pass (38,939-row exact-count fixture intact); ruff clean. NOTE current repo alias map is already in sync (63==63), so drift examples in issue were since reconciled; this fixes the MECHANISM. TO COMMIT.
- [x] #79 source_package.py string year keys: FIXED. _render_string skips {year} templating for non-int (label) year; TDD red->green (repro'd year+1 TypeError first); int+filing_year path preserved; build_facts('extracted_targets') no longer crashes. 78/78 source_package tests pass; ruff clean. TO COMMIT.
- [ ] Full pytest suite green (pipefail-verified) + ruff  [NOTE: full suite >2min; run in background at end]
- [ ] PR(s) opened, not merged

## #77 additional evidence
CI runs `ledger load all` (.github/workflows/ci.yml:43) every push -> exercises load_snap_targets.
Fabricated vs real FY2024 (proves fabrication): fab 2023 CA hh 2,891k vs real 3,129k;
fab national benefits 112,848M vs real 93,847M. New values carry per-value provenance
(source_file, vintage, sha256, R2 URI, record id) in Target.notes.

## #77 dead-or-live evidence
`db/etl_snap.py::SNAP_DATA` feeds `load_snap_targets`, which is reachable:
1. `db/cli.py:74-79` — `ledger load snap` / `ledger load all` CLI command calls it.
2. `ledger/targets/loaders.py:12,31` — re-exports `load_snap_targets` in public loaders API.
3. `ledger/jurisdictions/us/__init__.py:10,27` — re-exports it in the US jurisdiction API.
Top-level `ledger` CLI dispatches to `db/cli.py` via `ledger/cli.py:7`.
=> LIVE. README calls this the "Legacy Target Inputs" path but it is still wired.
Trustworthy replacement source: `packages/usda_snap/fy69_to_current` parses the real
FNS FY24 workbook cell-by-cell (guard cells, sha256, R2 provenance). Validated + built
locally: 216 facts, national + state, per-value lineage.
