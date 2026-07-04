# PROGRESS — ledger#69 BE source packages (branch: be-source-packages)

Agent working log. Deleted before PR. Updated every push.

## Key finding (session start)
- **PR #72 ("Add Belgium target source packages") already merged to origin/main.** BE packages
  ALREADY EXIST: statbel (2), spf_finances, onss, onem_rva, nbb, jrc (EUROMOD-BE).
- Prior branch `codex/belgium-target-packages-primary-source-only` has ONE extra commit:
  "Remove EUROMOD comparator facts from Belgium targets" — TENSION with brief acceptance #4
  (which says EUROMOD-BE comparator package must EXIST). Must reconcile.
- Therefore this task = AUDIT + VERIFY + FILL GAPS against the brief's binding contract,
  not from-scratch authoring. Cardinal risk: fabricated numbers (issue #77).

## Brief's binding contract — 6 ledger_selectors populace-be selects by
| source_name | measure | publisher | status |
|---|---|---|---|
| statbel_population_structure | people (age×sex×region, nuts1) | Statbel | AUDIT |
| statbel_fiscal_income | belgium_pit_taxable_income (commune nis2025) | Statbel | AUDIT |
| spf_finances_pit | belgium_pit_federal_and_local_tax_before_withholding | SPF Finances | AUDIT |
| onss_contributions | belgium_worker_article_17_uncapped_component_contribution | ONSS/RSZ | AUDIT |
| onem_rva_unemployment | receives_unemployment_benefit (caseload) | ONEM/RVA | AUDIT |
| nbb_national_accounts | household_disposable_income (validation band) | NBB | AUDIT |

Plus: SFPD pensions, regional child benefit, BFP outlook, EUROMOD-BE comparator (#264).

## Acceptance gates
1. validate-package passes; facts load with lineage to source cells.
2. All subnational facts carry nis_vintage; 2025 crosswalk round-trips a merged commune.
3. Resolution test: each of 6 selectors resolves to exactly one fact stream.
4. EUROMOD-BE comparator package exists w/ source URLs per row (feeds populace#264).
5. No observed values copied outside Ledger (enforced populace-side).

## Log
- [start] Worktree created at origin/main (3c80129). Reading harness + data + existing packages.
