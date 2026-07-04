# PROGRESS — ledger#69 BE source packages (branch: be-source-packages)

Agent working log. Deleted before PR. Updated every push.

## Session 2 start (fresh agent, predecessor died ~15 tool calls in)

Picked up predecessor's worktree/branch as-is (nothing to commit, clean).
Predecessor's PROGRESS.md correctly identified: PR #72 (merged to main) already
authored 7 BE packages. Re-verified everything from scratch below.

## RESOLVED: the EUROMOD tension flagged by predecessor

Predecessor's note and my own dispatch brief both claimed "ledger#80 ... just
enforced" removal of EUROMOD comparator facts. **This is factually wrong as of
this session**: ledger PR #80 ("Remove EUROMOD comparator facts from Belgium
targets") is **OPEN, unreviewed, unmerged** (checked via `gh pr view 80`).
Meanwhile:
- Issue #69's own binding brief (comment, 2026-07-02, MaxGhenis) acceptance #4:
  "The EUROMOD-BE comparator package exists with source URLs per row (feeds
  populace#264's reform_validation.json)."
- `tests/test_belgium_targets.py` on current `origin/main` HAS
  `test_belgium_euromod_comparator_has_source_urls_per_row` and it PASSES.
- `tests/test_ledger_bundle.py` bakes in `"jrc_euromod_be": 18` fact count.
- README boundary rule: "Everything a publisher asserted ... is a fact" —
  JRC published the EUROMOD-BE Country Report; it's `entity_role:
  validation_comparator`, never a calibration target (only the 6 primary
  streams are targets per BELGIUM_TARGET_STREAMS). No AGENTS.md rule
  restricts facts to *government* publishers specifically — the boundary is
  "who asserted the value," and JRC did.

**Decision: kept the JRC/EUROMOD-BE package. Did NOT touch/rebase/adopt PR
#80's branch.** Flagging this conflict prominently in the PR body and final
report for the lead — #80 should probably be closed as contradicting the
issue's own binding acceptance criteria, but that's the lead's call, not mine
to unilaterally close someone else's open PR.

## Audit results (before any new authoring)

All 7 existing BE packages pass `uv run ledger validate-package <id> --year
<Y>` with `"valid": true`, zero errors:
| package_id | rows | valid |
|---|---|---|
| statbel-fiscal-income-2023-nis-2025 | 565 | true |
| statbel-population-structure-2026 | 18 | true |
| spf-finances-pit-2023 | 1 | true |
| onss-contributions-2024 | 1 | true |
| onem-rva-unemployment-2024 | 1 | true |
| nbb-national-accounts-household-disposable-income-2024 | 1 | true |
| jrc-euromod-be-baseline-statistics-2025 | 18 | true |

`uv run pytest -q tests/test_belgium_targets.py` — 7 passed (all acceptance
criteria #1-#4 already encoded as tests and green):
- resolution test (6 selectors -> exactly 1 stream each): PASS
- NIS 2025 crosswalk round-trips Bastogne (82039) and a 3-way merge (46030): PASS
- subnational geography_vintage present (NUTS_2024 for population, nis_2025
  for fiscal income): PASS
- EUROMOD comparator has source URLs per row: PASS

## Gap vs. issue body (NOT part of the 6 binding selectors, but issue lists them)

Issue #69 body lists 3 more packages beyond the 6-selector + EUROMOD set,
confirmed ABSENT from the repo (grep found nothing):
- SFPD pension caseloads/expenditure (pensionstat.be)
- Regional child benefit / Groeipakket + FWB/German-speaking counterparts
- BFP economic outlook (plan.be) — the OBR-analog + reform costings

These aren't in populace's binding `ledger_selector` list (the brief's table
of 6), so they don't block populace-be's core calibration path today, but the
issue explicitly asks for them and "boil the ocean" applies. Authoring all
three now.

## Log
- [session 2 start] Re-verified predecessor's findings; resolved EUROMOD
  question; ran validate-package on all 7; all green. Starting research for
  SFPD/child-benefit/BFP primary sources.
