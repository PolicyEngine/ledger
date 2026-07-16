# Agent Source Package Harness

Ledger source-population agents should fill constrained source packages and let
the build suite decide whether the package is admissible. Agents should not
hand-edit Ledger DB artifacts, generated JSONL outputs, or core schema modules.

The older Python ETL loaders that write directly into the legacy `targets`
tables are compatibility and migration inputs, not the preferred agent
population path. They are useful for proving source coverage against Populace
today, but a source family should become agent-ready only after it is expressed
as a source package with full-document parsing, source-row or source-cell
lineage, provenance, constraints, and a passing `build-suite` report.

The first gate for a new package is source-artifact acquisition. Agents should
register raw source files with `uv run ledger fetch-artifact` before authoring
selectors. This writes the local artifact, captures checksum and retrieval
metadata in `manifest.yaml`, and can upload the exact bytes to the private
`ledger-raw` R2 bucket when Wrangler is authenticated. Agents can audit the local
artifact registry with `uv run ledger inventory-artifacts --root db/data`.
For already-downloaded manifest artifacts, agents should run
`uv run ledger publish-raw --root db/data` to upload checksum-verified bytes to
R2 and write `storage.r2` metadata back into each manifest entry.

Builds do not require production raw bytes to be committed to Git. Source
packages first read packaged fixture bytes, then
`LEDGER_SOURCE_ARTIFACT_CACHE_DIR` (defaulting to
`~/.cache/policyengine-ledger/source-artifacts`). If a manifest artifact is
missing locally, set `LEDGER_SOURCE_ARTIFACT_FETCH=1` to fetch it from the
manifest `source_url`, verify the declared SHA-256, and write it to that cache.
The old `LEDGER_`-prefixed environment variables remain accepted only as
migration fallbacks.

For broad PE source migration, generate the agent queue from the manifest before
assigning work:

```bash
uv run ledger plan-pe-sources \
  --manifest docs/pe-us-source-manifest.csv \
  --out docs/pe-us-source-agent-plan.json \
  --markdown docs/pe-us-source-agent-plan.md
```

The generated plan separates existing source packages, primary-source lookup
tasks, fetch/register tasks, source-cell scaffolds, and repair items. It is not
semantic acceptance; agents still need `validate-package` and `build-suite`
before a package can move past `semantic_candidate`. Aggregators such as FRED
are migration clues, not canonical Ledger source artifacts; agents should find
and register the publisher-owned artifact before source cells or target facts
become canonical.

## Source Package Contract

A source package should eventually contain the source artifact manifest, parser
or retrieval code, cell selector specs, source-record specs, and focused tests
for one source family or table. The current in-repo pilot is
`soi-table-1-1`, with `soi-table-1-4` as a second SOI wage pilot, backed by
`ledger.jurisdictions.us.soi` while the package contract stabilizes.

Agents should prefer declarative package directories over Python edits. A
minimal package has a `source_package.yaml` file that identifies the source
artifact manifest and declares compact record sets. The SOI pilots live at
`packages/irs_soi/table_1_1/source_package.yaml`,
`packages/irs_soi/table_1_4/source_package.yaml`, and
`packages/irs_soi/historic_table_2/source_package.yaml`.
For rectangular state tables, row-level geography overrides let one record set
represent repeated state rows without duplicating the measures. The first
ZIP-backed PE migration example is
`packages/cms_aca/oep_state_level/source_package.yaml`, which parses the CMS
OEP ZIP's CSV member into full source rows and emits state-level facts.

## Selector Guards

Selectors should not rely on coordinates alone once a package is ready for
semantic review. Agents should add guards that prove the selected coordinates
still mean what the source package claims they mean.

Use `guard_cells` for exact row-relative checks such as a start row label, end
row label, neighboring header, or absolute sentinel. A row guard uses an Excel
column, an expected value, and one of `row: start`, `row: end`, or a positive
integer row number. Columns must be Excel letters, and expected values must not
depend on presentation-only formatting.

```yaml
rows:
  - value_id: female_0_14
    label: Female age 0 to 14
    row_number: 2
    row_end_number: 16
    expected_row_header_column: A
    expected_row_header: Females
    guard_cells:
      - column: B
        row: start
        expected_value: 0
        label: start age
      - column: A
        row: end
        expected_value: Females
        label: end sex
      - column: B
        row: end
        expected_value: 14
        label: end age
```

Use `range_label_guards` when a fact sums a dense row range and interior labels
are part of the fact definition. Endpoint guards catch off-by-one boundaries,
but they do not catch an inserted, duplicated, or shifted interior label. Range
label guards require `row_end_number` and validate every expected label in the
guard column from `row_number` through `row_end_number`.

```yaml
range_label_guards:
  - column: B
    expected_values:
      integer_range:
        start: 0
        end: 14
    label: age sequence
```

For ranges with tail labels, use `final_value` to replace the last integer and
`extra_values` to append labels after the integer range:

```yaml
range_label_guards:
  - column: B
    expected_values:
      integer_range:
        start: 0
        end: 105
        final_value: 105 - 109
        extra_values:
          - 110 and over
    label: age sequence
```

For concatenated sequences, use `parts`. A compact mapping must use exactly one
form: either `integer_range` or `parts`, not both. `null` entries are rejected
because they would otherwise behave like unguarded labels.

```yaml
range_label_guards:
  - column: B
    expected_values:
      parts:
        - integer_range:
            start: 0
            end: 105
            final_value: 105 - 109
            extra_values:
              - 110 and over
        - integer_range:
            start: 0
            end: 105
            final_value: 105 - 109
            extra_values:
              - 110 and over
    label: age sequence
```

Default rule: every selected record should have at least endpoint guards before
review. Add full range label guards for dense dimensions such as age, year,
geography, benefit band, income band, or education stage when a selected range
is interpreted as a sum over that dimension. Sparse sentinels are acceptable for
early drafts, but packages should not leave `semantic_candidate` with
coordinate-only selectors for dense summed ranges.

Guard cells and range label cells become source-cell lineage. This is useful for
auditability, but it can add hundreds of lineage cells for very dense ranges.
Use full label sequences where the interior labels are material to the aggregate
meaning; otherwise prefer endpoint guards plus a small number of sentinels.

The build suite is the review surface:

```bash
uv run ledger validate-package packages/irs_soi/table_1_1 --year 2023
uv run ledger build-suite soi-table-1-1 --year 2023 --out /tmp/ledger-suite --replace
uv run ledger build-suite packages/irs_soi/table_1_1 --year 2023 --out /tmp/ledger-suite --replace
```

For the row-oriented IRS SOI Historic Table 2 package, the 2022 national first
slice can be checked with:

```bash
uv run ledger validate-package soi-historic-table-2 --year 2022
uv run ledger build-suite soi-historic-table-2 \
  --year 2022 \
  --out /tmp/ledger-soi-historic-table-2-2022 \
  --replace
```

For the CMS Marketplace OEP state-level ZIP package, the 2024 first slice can
be checked with:

```bash
uv run ledger validate-package cms-aca-oep-state-level --year 2024
uv run ledger build-suite cms-aca-oep-state-level \
  --year 2024 \
  --out /tmp/ledger-cms-aca-oep-2024 \
  --replace
```

For the next US publisher-source packages, the 2024 slices can be checked with:

```bash
uv run ledger validate-package cms-nhe-historical-service-source --year 2024
uv run ledger build-suite cms-nhe-historical-service-source \
  --year 2024 \
  --out /tmp/ledger-cms-nhe-historical-service-source-2024 \
  --replace

uv run ledger validate-package census-stc-individual-income-tax --year 2024
uv run ledger build-suite census-stc-individual-income-tax \
  --year 2024 \
  --out /tmp/ledger-census-stc-individual-income-tax-2024 \
  --replace

uv run ledger validate-package census-pep-2024-national-age-sex --year 2024
uv run ledger build-suite census-pep-2024-national-age-sex \
  --year 2024 \
  --out /tmp/ledger-census-pep-2024-national-age-sex-2024 \
  --replace

uv run ledger validate-package hhs-acf-tanf-financial-2024 --year 2024
uv run ledger build-suite hhs-acf-tanf-financial-2024 \
  --year 2024 \
  --out /tmp/ledger-hhs-acf-tanf-financial-2024 \
  --replace

uv run ledger validate-package soi-ira-traditional-contributions-2022 --year 2022
uv run ledger build-suite soi-ira-traditional-contributions-2022 \
  --year 2022 \
  --out /tmp/ledger-soi-ira-traditional-contributions-2022 \
  --replace
uv run ledger validate-package soi-ira-roth-contributions-2022 --year 2022
uv run ledger build-suite soi-ira-roth-contributions-2022 \
  --year 2022 \
  --out /tmp/ledger-soi-ira-roth-contributions-2022 \
  --replace
uv run ledger validate-package soi-w2-statistics-2020 --year 2020
uv run ledger build-suite soi-w2-statistics-2020 \
  --year 2020 \
  --out /tmp/ledger-soi-w2-statistics-2020 \
  --replace
```

For the first UK packages, OBR March 2026 EFO receipts and expenditure can be
checked with:

```bash
uv run ledger validate-package obr-efo-receipts --year 2025
uv run ledger build-suite obr-efo-receipts \
  --year 2025 \
  --out /tmp/ledger-obr-efo-receipts-2025 \
  --replace
uv run ledger validate-package obr-efo-expenditure --year 2025
uv run ledger build-suite obr-efo-expenditure \
  --year 2025 \
  --out /tmp/ledger-obr-efo-expenditure-2025 \
  --replace
uv run ledger validate-package slc-student-support-england-2025 --year 2025
uv run ledger build-suite slc-student-support-england-2025 \
  --year 2025 \
  --out /tmp/ledger-slc-student-support-england-2025 \
  --replace
uv run ledger validate-package dwp-uc-two-child-limit-2025 --year 2026
uv run ledger build-suite dwp-uc-two-child-limit-2025 \
  --year 2026 \
  --out /tmp/ledger-dwp-uc-two-child-limit-2026 \
  --replace
uv run ledger validate-package dwp-benefit-cap-november-2025 --year 2025
uv run ledger build-suite dwp-benefit-cap-november-2025 \
  --year 2025 \
  --out /tmp/ledger-dwp-benefit-cap-2025 \
  --replace
uv run ledger validate-package dwp-benefit-statistics-february-2026 --year 2025
uv run ledger build-suite dwp-benefit-statistics-february-2026 \
  --year 2025 \
  --out /tmp/ledger-dwp-benefit-statistics-2025 \
  --replace
uv run ledger validate-package dwp-pip-daily-living-foi-2025 --year 2025
uv run ledger build-suite dwp-pip-daily-living-foi-2025 \
  --year 2025 \
  --out /tmp/ledger-dwp-pip-daily-living-foi-2025 \
  --replace

uv run ledger validate-package dwp-uc-national-payment-dist-2025 --year 2025
uv run ledger build-suite dwp-uc-national-payment-dist-2025 \
  --year 2025 \
  --out /tmp/ledger-dwp-uc-national-payment-dist-2025 \
  --replace

uv run ledger validate-package hmrc-salary-sacrifice-relief-2024 --year 2024
uv run ledger build-suite hmrc-salary-sacrifice-relief-2024 \
  --year 2024 \
  --out /tmp/ledger-hmrc-salary-sacrifice-relief-2024 \
  --replace

uv run ledger validate-package hmrc-spi-income-bands-2023 --year 2023
uv run ledger build-suite hmrc-spi-income-bands-2023 \
  --year 2023 \
  --out /tmp/ledger-hmrc-spi-income-bands-2023 \
  --replace

uv run ledger validate-package ons-savings-interest-income --year 2023
uv run ledger build-suite ons-savings-interest-income \
  --year 2023 \
  --out /tmp/ledger-ons-savings-interest-income-2023 \
  --replace

uv run ledger validate-package ons-uk-population-projections-2022 --year 2022
uv run ledger build-suite ons-uk-population-projections-2022 \
  --year 2022 \
  --out /tmp/ledger-ons-uk-population-projections-2022 \
  --replace

uv run ledger validate-package nrs-mid-year-population-estimates-2024 --year 2024
uv run ledger build-suite nrs-mid-year-population-estimates-2024 \
  --year 2024 \
  --out /tmp/ledger-nrs-mid-year-population-estimates-2024 \
  --replace

uv run ledger validate-package nrs-vital-events-reference-tables-2024 --year 2024
uv run ledger build-suite nrs-vital-events-reference-tables-2024 \
  --year 2024 \
  --out /tmp/ledger-nrs-vital-events-reference-tables-2024 \
  --replace

uv run ledger validate-package ons-subnational-dwellings-by-tenure-2024 --year 2024
uv run ledger build-suite ons-subnational-dwellings-by-tenure-2024 \
  --year 2024 \
  --out /tmp/ledger-ons-subnational-dwellings-by-tenure-2024 \
  --replace

uv run ledger validate-package ons-national-balance-sheet-land-2025 --year 2024
uv run ledger build-suite ons-national-balance-sheet-land-2025 \
  --year 2024 \
  --out /tmp/ledger-ons-national-balance-sheet-land-2025 \
  --replace

uv run ledger validate-package voa-council-tax-bands-2025 --year 2025
uv run ledger build-suite voa-council-tax-bands-2025 \
  --year 2025 \
  --out /tmp/ledger-voa-council-tax-bands-2025 \
  --replace

uv run ledger validate-package scotgov-council-tax-bands-2025 --year 2025
uv run ledger build-suite scotgov-council-tax-bands-2025 \
  --year 2025 \
  --out /tmp/ledger-scotgov-council-tax-bands-2025 \
  --replace

uv run ledger validate-package scotgov-scottish-budget-social-security-assistance-2026 --year 2026
uv run ledger build-suite scotgov-scottish-budget-social-security-assistance-2026 \
  --year 2026 \
  --out /tmp/ledger-scotgov-scottish-budget-social-security-assistance-2026 \
  --replace

uv run ledger validate-package slc-student-loan-borrower-forecasts-england-2025 --year 2025
uv run ledger build-suite slc-student-loan-borrower-forecasts-england-2025 \
  --year 2025 \
  --out /tmp/ledger-slc-student-loan-borrower-forecasts-england-2025 \
  --replace

uv run ledger validate-package slc-student-loan-repayments-england-2025 --year 2025
uv run ledger build-suite slc-student-loan-repayments-england-2025 \
  --year 2025 \
  --out /tmp/ledger-slc-student-loan-repayments-england-2025 \
  --replace
uv run ledger validate-package slc-student-loan-repayments-scotland-2025 --year 2025
uv run ledger build-suite slc-student-loan-repayments-scotland-2025 \
  --year 2025 \
  --out /tmp/ledger-slc-student-loan-repayments-scotland-2025 \
  --replace
uv run ledger validate-package slc-student-loan-repayments-wales-2025 --year 2025
uv run ledger build-suite slc-student-loan-repayments-wales-2025 \
  --year 2025 \
  --out /tmp/ledger-slc-student-loan-repayments-wales-2025 \
  --replace
uv run ledger validate-package slc-student-loan-repayments-northern-ireland-2025 --year 2025
uv run ledger build-suite slc-student-loan-repayments-northern-ireland-2025 \
  --year 2025 \
  --out /tmp/ledger-slc-student-loan-repayments-northern-ireland-2025 \
  --replace
```

Use [`pe-uk-source-checklist.md`](pe-uk-source-checklist.md) as the ordered
queue for UK source-package migration against PolicyEngine UK's current target
sources.

It produces source rows/cells, source-region specs, selector reports,
aggregate facts, a relational SQLite DB artifact, and per-stage JSON reports under
`/tmp/ledger-suite/reports`. It also writes `datapackage.json` and
`ro-crate-metadata.json` sidecars so the generated artifacts can be described
with common data-package conventions while Ledger keeps its native schema strict.
For downstream integration, agents should use the merged year bundle after
individual source packages pass:

```bash
uv run ledger build-bundle --year 2023 --out /tmp/ledger-us-2023 --replace
```

The bundle emits a root `consumer_facts.jsonl`, `source_packages.json`,
`coverage.json`, and `reports/build_bundle.json`, while preserving each
source-package suite under `sources/<source-package>/`.

The first agent-facing gate is now
`/tmp/ledger-suite/reports/agent_acceptance.json`; it summarizes whether raw
artifacts have R2 pointers, the full source document was parsed, facts have
provenance and source-cell/source-row lineage, expected constraints are
first-class, row-backed facts are consistent with their parsed source rows,
concept alignments have evidence, and all stage reports are valid. It also
reports whether canonical concepts were checked
against Axiom metadata. If Axiom checking is omitted, otherwise valid packages
warn with `concept_alignment_validation_skipped`; stricter agent runs can make
that warning fatal:

```bash
uv run ledger build-suite packages/irs_soi/table_1_1 \
  --year 2023 \
  --out /tmp/ledger-suite \
  --replace \
  --axiom-cli axiom \
  --axiom-root ../rules-us \
  --require-axiom-validation
```

The SQLite `ledger.db` is the source of hosted mirrors. To prepare tables for
Supabase/Postgres bulk loading, export the DB artifact rather than inserting
cells through the Supabase client:

```bash
uv run ledger export-db-tables --db /tmp/ledger-suite/ledger.db --out /tmp/ledger-mirror --replace
```

Accepted build-suite outputs can be published to the private `ledger-derived` R2
bucket after validation:

```bash
uv run ledger publish-derived \
  --dir /tmp/ledger-suite \
  --source-id irs_soi \
  --package-id soi-table-1-1 \
  --year 2023 \
  --build-artifacts-out /tmp/ledger-build-artifacts.jsonl
```

The SQL schema is checked in at
`supabase/migrations/20260504_ledger_bronze.sql`. Spreadsheet publications are
stored as immutable artifact metadata and one parsed-cell row per workbook cell.
Agents should not try to normalize irregular government worksheets into tidy
sheet tables before selector specs interpret them.

After the DB export and derived publish, agents can validate and load the
hosted mirror:

```bash
uv run ledger load-supabase-mirror \
  --dir /tmp/ledger-mirror \
  --build-artifacts /tmp/ledger-build-artifacts.jsonl \
  --dry-run
uv run ledger load-supabase-mirror \
  --dir /tmp/ledger-mirror \
  --build-artifacts /tmp/ledger-build-artifacts.jsonl
```

The live load requires `POLICYENGINE_SUPABASE_URL` and
`POLICYENGINE_SUPABASE_SERVICE_KEY`, the Ledger mirror migration applied, and the
`ledger` schema exposed by the Supabase Data API.

## Declarative Authoring Contract

Each `source_package.yaml` should declare one source artifact and one or more
record sets. The artifact block points at a checked manifest with publisher
filenames, source URLs, and checksums by year. PE migration URLs from
aggregators can remain in the agent queue as clues, but they should not back
canonical source cells or target facts. Each record set declares sheet name, period,
geography, entity, domain, groupby dimension, row definitions, measure columns,
units, aggregation methods, filters, and first-class constraints. The harness
compiles those rows and measures into atomic source records, validates selectors
against parsed cells, then emits target facts and the relational Ledger DB.

Every record set must declare a `provenance_class`; there is no default. The
closed vocabulary describes the publisher's measurement basis:

- `administrative` for program, tax, collection, caseload, or payment records;
- `census` for full-enumeration or census-controlled counts;
- `survey_aggregate` for published sample-survey tabulations; and
- `model_output` for model-based estimates, outlooks, baselines, and other
  evaluation/oracle outputs.

A `survey_aggregate` record set must also name its source survey in a non-empty
`survey_instrument` string. `survey_instrument` is forbidden for every other
class. Missing, unknown, wrongly typed, and misplaced values fail package load
and build validation.

```yaml
record_sets:
  - record_set_id: census_acs.acs1_{year}.s0101.national_age
    provenance_class: survey_aggregate
    survey_instrument: ACS 1-year
    record_set_spec_id: census_acs.s0101.national_age.v1
```

Agents may add new package directories and YAML specs. They should not modify
`ledger.core`, `ledger.database`, or `ledger.suite` unless the package cannot be
expressed in the current contract and the failure is documented in the build
report or PR notes.

Agents can scaffold a new package before filling the table-specific fields:

```bash
uv run ledger scaffold-package --source-id irs_soi --package-id soi-table-1-2 \
  --out packages/irs_soi/table_1_2 \
  --source-table "Publication 1304 Table 1.2" \
  --resource-directory data/irs_soi/table_1_2
```

`validate-package` is the first gate. It checks required YAML fields, artifact
manifest and year availability, duplicate row and measure identifiers, malformed
Excel columns, malformed guard specs, missing row constraints, and missing
evidence for exact concept alignments. `build-suite` remains the full gate
because it parses cells, resolves selectors, builds facts, and emits the SQLite
DB artifact.
For delimited full-row sources, selected-row criteria must match exactly one
parsed source row, and row-backed filters and constraints must be evidenced by
columns in that parsed row.

## Status Levels

Agents should move source packages through explicit statuses rather than claim
production readiness immediately:

| Status | Meaning |
|--------|---------|
| `inventory` | Source artifact is identified with publisher, URL/path, vintage, checksum, local path, optional R2 key, and notes. |
| `parsed` | The artifact is preserved as parsed source rows or source cells with provenance. |
| `selected` | `validate-package` passes, source regions cover parsed cells, and cell selectors resolve with endpoint guards. |
| `semantic_candidate` | Source-record specs interpret selected cells as aggregate facts. |
| `validated` | Facts, constraints, lineage, provenance, dense-range guards, and concept checks pass. |
| `production` | A human reviewed the source family and accepted the semantics. |

## Required Gates

Before a source package can leave `semantic_candidate`, the build summary should
show zero validation errors for source cells, source records, targets, DB build,
and concept alignments. It should also report complete lineage coverage unless
the package has an explicit documented exception.

Exact source-to-canonical concept alignments require evidence notes or an
evidence URL. When the canonical concept is an Axiom ID, the package should run
the suite with `--axiom-cli` and `--axiom-root` once the corresponding Axiom
concept exists. For agent-populated packages that are ready for review, run the
same command with `--require-axiom-validation` so unresolved or unchecked
canonical concepts fail `agent_acceptance.json`.

## Review Checklist

Reviewers should inspect `reports/build_summary.json` first, then only drill
into the stage report that failed. A valid source package should make it easy to
answer these questions:

- Which source artifact was parsed, and what exact vintage/checksum backed it?
- How many rows/cells were preserved, and were any source-row or source-cell
  keys duplicated?
- Which rectangular source regions were selected, and how many cells did they cover?
- Did every source-record selector resolve to the expected cell, endpoint guard,
  and dense range label guard where applicable?
- Did every aggregate fact have provenance, dimensions, unit, aggregation, and
  source-cell or source-row lineage?
- Are constraints first-class, queryable, and simulator-neutral?
- Are exact concept alignments evidence-bearing and externally validated where
  possible?
