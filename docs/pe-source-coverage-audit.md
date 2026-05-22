# PE Source Coverage Audit

Date: 2026-05-12

Objective under audit: drive PolicyEngine UK and US source coverage toward
build-suite-passing Arch source packages; prefer primary/publisher sources;
preserve raw artifacts with checksums and R2 metadata; add focused tests; and
mark source-ambiguous, inaccessible, or derived-only items as blocked or
deferred with notes.

## Success Criteria

1. Publisher-source facts that can be represented with the current parsers have
   Arch source packages and pass `arch build-suite`.
2. Raw publisher artifacts used by source packages are stored under `db/data`
   with manifest metadata, including checksums and R2 locations.
3. Source packages have focused tests or are covered by
   `tests/test_arch_source_package.py`.
4. Ambiguous, inaccessible, PDF-parser-blocked, or derived/support-only items
   are not forced into facts; they are marked blocked or deferred with notes.
5. Remaining gaps are explicit enough that the next action is a package,
   parser/access fix, or source-clarification task.

## Evidence Checked

- `docs/pe-uk-source-checklist.md`
- `docs/pe-us-source-manifest.csv`
- `docs/pe-us-source-manifest.md`
- `docs/pe-us-source-agent-plan.md`
- `arch/source_package.py`
- `tests/test_arch_source_package.py`
- Current-session commands:
  - `uv run pytest tests/test_arch_source_package.py -q`
  - `uv run ruff check arch/core.py arch/source_package.py arch/sources/specs.py arch/suite.py tests/test_arch_source_package.py`
  - `git diff --check ...`
  - `curl -L --max-time 20 -I https://www.ssa.gov/OACT/solvency/RWyden_20250805.pdf`
  - `curl -L --max-time 20 -I https://www2.census.gov/programs-surveys/popproj/datasets/2023/2023-popproj/np2023_d5_mid.csv`
  - `curl -L --max-time 15 -A 'Mozilla/5.0 ...' -I` against all five CBO
    blocked direct URLs.
  - `uv run arch plan-pe-sources --manifest docs/pe-us-source-manifest.csv --out docs/pe-us-source-agent-plan.json --markdown docs/pe-us-source-agent-plan.md`
  - `uv run arch build-suite census-stc-individual-income-tax --year 2023 --out /tmp/census-stc-individual-income-tax-2023 --replace`
  - `uv run arch build-suite census-stc-individual-income-tax --year 2024 --out /tmp/census-stc-individual-income-tax-2024 --replace`
  - `uv run arch build-suite census-acs-s0101-national-age-2024 --year 2024 --out /tmp/census-acs-s0101-national-age-2024 --replace`
  - `uv run arch build-suite census-acs-s0101-state-age-2024 --year 2024 --out /tmp/census-acs-s0101-state-age-2024 --replace`
  - `uv run arch build-suite census-acs-s0101-congressional-district-age-2024 --year 2024 --out /tmp/census-acs-s0101-congressional-district-age-2024 --replace`
  - `uv run arch build-suite census-acs-s2201-congressional-district-snap-2024 --year 2024 --out /tmp/census-acs-s2201-congressional-district-snap-2024 --replace`
  - `uv run arch build-suite census-b01001-female-age-2023 --year 2023 --out /tmp/census-b01001-female-age-2023 --replace`
  - `uv run arch build-suite cms-medicaid-chip-monthly-enrollment-december-2024 --year 2024 --out /tmp/cms-medicaid-chip-monthly-enrollment-december-2024 --replace`
  - `uv run arch build-suite ssa-population-projections-tr2024 --year 2025 --out /tmp/ssa-population-projections-tr2024 --replace`
  - `uv run arch build-suite census-population-projections-2023 --year 2025 --out /tmp/census-population-projections-2023 --replace`
  - `uv run arch build-suite soi-historic-table-2-state-agi-2022 --year 2022 --out /tmp/soi-historic-table-2-state-agi-2022 --replace`
  - `uv run arch fetch-artifact --url https://www.irs.gov/pub/irs-soi/20in25ic.xls --source-id irs_soi --package-id soi-table-2-5 --year 2020 --out-dir db/data/irs_soi/table_2_5 --source-page https://www.irs.gov/statistics/soi-tax-stats-individual-income-tax-returns-complete-report-publication-1304-basic-tables-part-2 --table "Publication 1304 Table 2.5" --upload-r2`
  - `uv run arch build-suite soi-table-2-5-eitc-children-2020 --year 2020 --out /tmp/soi-table-2-5-eitc-children-2020 --replace`
  - `uv run pytest tests/test_arch_source_package.py -q -k "ssa_population_projection or new_us_source_counts"`
  - `uv run pytest tests/test_arch_source_package.py tests/test_arch_suite.py -q -k "census_population_projection or source_cell_header_age or new_us_source_counts"`
  - `uv run pytest tests/test_arch_source_package.py -q -k "soi_historic_table_2_state_agi or new_us_source_counts"`
  - `uv run pytest tests/test_arch_source_package.py -q -k "soi_table_2_5_eitc_children_2020 or new_us_source_counts"`
  - `uv run arch fetch-artifact --url https://www2.census.gov/programs-surveys/popest/datasets/2020-2023/state/asrh/sc-est2023-alldata6.csv --source-id census_pep --package-id census-pep-2023-state-age-sex --year 2023 --out-dir db/data/census/pep_2023_state_age_sex --dataset census_pep_2023_state_age_sex --source-page https://www.census.gov/data/tables/time-series/demo/popest/2020s-state-detail.html --table "Vintage 2023 Annual State Resident Population Estimates by Single Year of Age, Sex, Race, and Hispanic Origin" --upload-r2`
  - `uv run arch fetch-artifact --url https://www2.census.gov/programs-surveys/popest/datasets/2020-2023/counties/asrh/cc-est2023-syasex-72.csv --source-id census_pep --package-id census-pep-2023-puerto-rico-age-sex --year 2023 --out-dir db/data/census/pep_2023_puerto_rico_age_sex --dataset census_pep_2023_puerto_rico_age_sex --source-page https://www.census.gov/data/tables/time-series/demo/popest/2020s-counties-detail.html --table "Vintage 2023 Puerto Rico Commonwealth Municipio Resident Population Estimates by Single Year of Age and Sex" --upload-r2`
  - `uv run arch build-suite census-pep-2023-state-age-sex --year 2023 --out /tmp/census-pep-2023-state-age-sex --replace`
  - `uv run arch build-suite census-pep-2023-puerto-rico-age-sex --year 2023 --out /tmp/census-pep-2023-puerto-rico-age-sex --replace`
  - `uv run pytest tests/test_arch_source_package.py -q -k "census_pep_2023 or new_us_source_counts"`
  - `uv run arch fetch-artifact --url https://www.cms.gov/files/zip/2022-oep-state-level-public-use-file.zip --source-id cms_aca --package-id cms-aca-oep-state-level-2022 --year 2022 --out-dir db/data/cms_aca/oep_state_level_2022 --dataset cms_marketplace_oep_state_level_2022_puf --source-page https://www.cms.gov/data-research/statistics-trends-reports/marketplace-products/2022-marketplace-open-enrollment-period-public-use-files --table "2022 OEP State-Level Public Use File" --upload-r2`
  - `uv run arch build-suite cms-aca-oep-state-level-2022 --year 2022 --out /tmp/cms-aca-oep-state-level-2022 --replace`
  - `uv run arch fetch-artifact --url https://www.cms.gov/files/zip/2025-oep-state-level-public-use-file.zip --source-id cms_aca --package-id cms-aca-oep-state-level-2025 --year 2025 --out-dir db/data/cms_aca/oep_state_level_2025 --dataset cms_marketplace_oep_state_level_2025_puf --source-page https://www.cms.gov/data-research/statistics-trends-reports/marketplace-products/2025-marketplace-open-enrollment-period-public-use-files --table "2025 OEP State-Level Public Use File" --upload-r2`
  - `uv run arch build-suite cms-aca-oep-state-level-2025 --year 2025 --out /tmp/cms-aca-oep-state-level-2025 --replace`
  - `uv run arch fetch-artifact --url https://www.kff.org/affordable-care-act/state-indicator/full-year-average-marketplace-effectuated-enrollment/ --source-id kff --package-id kff-marketplace-effectuated-enrollment --year 2024 --out-dir db/data/kff/marketplace_effectuated_enrollment --dataset kff_state_health_facts_marketplace_effectuated_enrollment --source-page https://www.kff.org/affordable-care-act/state-indicator/full-year-average-marketplace-effectuated-enrollment/ --table "Full Year Average Marketplace Effectuated Enrollment, 2017-2024" --filename full-year-average-marketplace-effectuated-enrollment.html --upload-r2`
  - `uv run arch build-suite kff-marketplace-effectuated-enrollment --year 2022 --out /tmp/kff-marketplace-effectuated-enrollment-2022 --replace`
  - `uv run arch build-suite kff-marketplace-effectuated-enrollment --year 2024 --out /tmp/kff-marketplace-effectuated-enrollment-2024 --replace`
  - `uv run pytest tests/test_arch_source_package.py -q -k "cms_aca_oep or kff_marketplace or new_us_source_counts"`
  - `uv run arch fetch-artifact --url https://www.cms.gov/files/document/full-year-effectuated-enrollment.xlsx --source-id cms_aca --package-id cms-aca-effectuated-enrollment-2022 --year 2022 --out-dir db/data/cms_aca/effectuated_enrollment_2022 --dataset cms_marketplace_full_year_effectuated_enrollment_2022 --source-page https://www.cms.gov/marketplace/resources/forms-reports-other --table "Effectuated Enrollment: Early Snapshot 2023 and Full Year 2022 Average" --upload-r2`
  - `uv run arch build-suite cms-aca-effectuated-enrollment-2022 --year 2022 --out /tmp/cms-aca-effectuated-enrollment-2022 --replace`
  - `uv run pytest tests/test_arch_source_package.py -q -k "cms_aca_effectuated_enrollment or new_us_source_counts"`
  - `uv run arch build-suite soi-historic-table-2-state-eitc-2022 --year 2022 --out /tmp/soi-historic-table-2-state-eitc-2022 --replace`
  - `uv run arch build-suite soi-table-2-5-eitc-agi-children-2022 --year 2022 --out /tmp/soi-table-2-5-eitc-agi-children-2022 --replace`
  - `uv run pytest tests/test_arch_source_package.py -q -k "state_eitc or agi_children or new_us_source_counts"`
  - `curl -L --max-time 30 -A 'Mozilla/5.0' -o /tmp/liheap2023.pdf -w '%{http_code} %{content_type} %{size_download}\n' https://liheappm.acf.gov/sites/default/files/private/congress/profiles/2023/FY2023AllStates%28National%29Profile-508Compliant.pdf`
  - `curl -L --max-time 30 -A 'Mozilla/5.0' -o /tmp/liheap2024.pdf -w '%{http_code} %{content_type} %{size_download}\n' https://liheappm.acf.gov/sites/default/files/private/congress/profiles/2024/FY2024_AllStates%28National%29_Profile.pdf`
  - `uv run arch build-suite hhs-acf-liheap-fy2023-national-profile --year 2023 --out /tmp/hhs-acf-liheap-fy2023-national-profile --replace`
  - `uv run arch build-suite hhs-acf-liheap-fy2024-national-profile --year 2024 --out /tmp/hhs-acf-liheap-fy2024-national-profile --replace`
  - `uv run pytest tests/test_arch_source_package.py -q -k "liheap or new_us_source_counts"`
  - `curl -L --max-time 30 -A 'Mozilla/5.0' -o /tmp/dhs_ohss_unauthorized.pdf -w '%{http_code} %{content_type} %{size_download}\n' https://ohss.dhs.gov/sites/default/files/2024-06/2024_0418_ohss_estimates-of-the-unauthorized-immigrant-population-residing-in-the-united-states-january-2018%25E2%2580%2593january-2022.pdf`
  - `uv run arch build-suite dhs-ohss-unauthorized-immigrant-population-2018-2022 --year 2022 --out /tmp/dhs-ohss-unauthorized-immigrant-population-2018-2022 --replace`
  - `uv run pytest tests/test_arch_source_package.py -q -k "dhs_ohss or liheap or new_us_source_counts"`
  - `curl -L --max-time 45 -A 'Mozilla/5.0' -o tmp/pdfs/cms_2025_medicare_trustees_report.pdf -w '%{http_code} %{content_type} %{size_download}\n' https://www.cms.gov/oact/tr/2025`
  - `uv run arch build-suite cms-medicare-trustees-report-2025-part-b-premium-income --year 2025 --out /tmp/cms-medicare-trustees-report-2025-part-b-premium-income --replace`
  - `curl -L --max-time 45 -A 'Mozilla/5.0' -o tmp/pdfs/treasury_tax_expenditures_fy2023.pdf -w '%{http_code} %{content_type} %{size_download}\n' https://home.treasury.gov/system/files/131/Tax-Expenditures-FY2023.pdf`
  - `uv run arch build-suite treasury-tax-expenditures-fy2023-eitc-outlays --year 2023 --out /tmp/treasury-tax-expenditures-fy2023-eitc-outlays --replace`
  - `curl -L --max-time 45 -A 'Mozilla/5.0' -o tmp/pdfs/jct_x_48_24.pdf -w '%{http_code} %{content_type} %{size_download}\n' https://www.jct.gov/getattachment/765709fb-9a4b-430a-8f9e-4d342ec97f7e/x-48-24.pdf`
  - `pdftoppm -png -f 27 -l 27 tmp/pdfs/jct_x_48_24.pdf tmp/pdfs/jct_x_48_24_page_27`
  - `uv run arch build-suite jct-tax-expenditures-2024-mortgage-interest-deduction --year 2024 --out /tmp/jct-tax-expenditures-2024-mortgage-interest-deduction --replace`
  - `curl -L --max-time 45 -A 'Mozilla/5.0' -o tmp/pdfs/vanguard_how_america_saves_2024_sa.pdf -w '%{http_code} %{content_type} %{size_download}\n' https://www.vanguardsouthamerica.com/content/dam/intl/americas/documents/latam/en/2024/07/mx-sa-3674967-how-america-saves-report-2024-v1.pdf`
  - `pdftoppm -png -f 44 -l 44 tmp/pdfs/vanguard_how_america_saves_2024_sa.pdf tmp/pdfs/vanguard_how_america_saves_2024_page_44`
  - `uv run arch build-suite vanguard-how-america-saves-2024-roth-participation --year 2024 --out /tmp/vanguard-how-america-saves-2024-roth-participation --replace`
  - `uv run pytest tests/test_arch_source_package.py -q -k "vanguard_roth_participation or jct_mortgage_interest or treasury_eitc_outlay or cms_medicare_trustees or dhs_ohss or liheap or new_us_source_counts"`
  - `uv run ruff check arch/sources/cells.py arch/source_package.py arch/suite.py tests/test_arch_source_package.py`
  - `uv run pytest tests/test_arch_pe_source_plan.py -q`
  - `uv run pytest tests/test_arch_suite.py -q`
  - `uv run ruff check arch/pe_source_plan.py arch/sources/rows.py arch/suite.py arch/source_package.py tests/test_arch_source_package.py tests/test_arch_pe_source_plan.py`
  - `uv run arch build-suite cdc-vsrr-live-births-monthly-2023 --year 2023 --out /tmp/cdc-vsrr-live-births-monthly-2023 --replace`
  - `uv run arch build-suite cdc-vsrr-live-births-monthly-2024 --year 2024 --out /tmp/cdc-vsrr-live-births-monthly-2024 --replace`
  - `uv run arch build-suite ons-small-area-income-local-authority-2020 --year 2020 --out /tmp/ons-small-area-income-local-authority-2020 --replace`
  - `curl -L --max-time 45 -A 'Mozilla/5.0' -o tmp/pdfs/isc_census_2024.pdf -w '%{http_code} %{content_type} %{size_download}\n' https://www.isc.co.uk/media/uukn4r3i/isc_census_2024_15may24.pdf`
  - `pdftoppm -png -f 6 -l 6 tmp/pdfs/isc_census_2024.pdf tmp/pdfs/isc_census_2024_page_6`
  - `uv run arch build-suite isc-census-2024-pupil-count --year 2024 --out /tmp/isc-census-2024-pupil-count --replace`
  - `uv run pytest tests/test_arch_source_package.py -q -k "isc_census_pupil_count or hmrc_salary_sacrifice_reform"`
  - `uv run ruff check arch/source_package.py arch/suite.py tests/test_arch_source_package.py`
  - `uv run python - <<'PY' ...` access recheck for the 12 US access-blocked publisher URLs: SSA still returned 403, CBO still returned DataDome 403, Reuters still returned 401, and CMSNY returned 200.
  - `uv run python - <<'PY' ...` fetched the CMSNY article HTML with browser-like headers after `curl` still returned the CMSNY 403 page.
  - `uv run arch build-suite cmsny-undocumented-population-2023 --year 2023 --out /tmp/cmsny-undocumented-population-2023 --replace`
  - `uv run pytest tests/test_arch_source_package.py -q -k "cmsny_undocumented_population or dhs_ohss or new_us_source_counts"`
  - `uv run arch plan-pe-sources --manifest docs/pe-us-source-manifest.csv --out docs/pe-us-source-agent-plan.json --markdown docs/pe-us-source-agent-plan.md`
  - `curl -sS -L --max-time 20 -A 'Mozilla/5.0' ... https://stat-xplore.dwp.gov.uk/webapi/rest/v1/info`
  - `curl -sS -L --max-time 20 -A 'Mozilla/5.0' ... https://stat-xplore.dwp.gov.uk/webapi/metadata/UC_Households/UC_Households.html`
  - `agent-secret search stat`
  - `uv run pytest tests/test_arch_source_package.py -q`
  - `uv run pytest tests/test_arch_suite.py -q`

## Current Counts

- Source package aliases: 100.
- UK checklist items: 28 total, 27 checked, 1 unchecked.
- US manifest rows: 214 total.
- US publisher-source rows: 166 total.
- US publisher-source rows with `source_package` and `build_suite_valid`: 45.
- US PE intermediate rows with `source_package` and `build_suite_valid`: 5.
- US PE support rows with `source_package` and `build_suite_valid`: 1.
- US publisher-source rows blocked or deferred: 121.
- US publisher-source rows routed to active fetch/source-cell scaffold work
  outside existing packages: 0.
- Current US manifest status counts: 51 `source_package`, 152 `deferred`,
  11 `blocked`, and 0 `row_parsed`.
- Current US agent-plan stages: 51 `existing_source_package` and 163
  `blocked_or_deferred`; no row remains routed to source-cell scaffolding.

## UK Status

The UK checklist is mostly represented as build-suite-backed source packages or
explicit partial coverage. One unchecked item is intentionally not a fact yet:

- `DWP Scotland UC child-under-1 household count`: blocked pending a working
  Stat-Xplore export/API response for the Scotland UC household target. The
  2026-05-12 recheck still returned Stat-Xplore HTTP 503 maintenance pages, and
  no agent-readable Stat-Xplore API key is available.

The salary-sacrifice contribution-amount item now has a source-backed Arch
fact from HMT Budget 2025 Policy Costings:
`hmt-budget-policy-costings-2025-salary-sacrifice` preserves the official PDF
and emits the CY2024 £32bn pension-contribution amount using salary-sacrifice
arrangements. It should not be mapped to the current PE target until PE target
construction is corrected, because the current PE target still uses a stale
£24bn base.

The Scotland demographic special-cases item is now marked done/partial for the
NRS under-16 and live-birth packages, while the Scotland Census 3+ children
target remains blocked because the available MV104/UV113 files do not encode a
3+ dependent-child household count.

The ISC private-school pupil helper now has a PDF-backed source package,
`isc-census-2024-pupil-count`, preserving the direct ISC 2024 census PDF and
the Executive Summary count of 556,551 pupils at 1,411 ISC member schools. PE's
557k target remains a rounded downstream/static target-construction value.

## US Status

The US publisher-source manifest no longer has a simple unblocked
machine-readable publisher item in `todo` status. The remaining publisher rows
are concentrated in:

- geography support artifacts deferred as not standalone fact packages;
- access-blocked pages or workbooks, including CBO DataDome, SSA 403s,
  and Reuters 401 access failures;
- source-context PDFs that do not add standalone aggregate facts beyond
  already packaged publisher pages;
- blocked SSA Wyden PDF access, now classified with the other SSA OACT 403
  sources.

The CMSNY undocumented-population page is no longer blocked: the article HTML
is now preserved by `cmsny-undocumented-population-2023`, which parses 270 HTML
document-number source cells and emits the CY2023 US undocumented population
estimate of 12,200,000. The page slug says 12 million, while the article title
and Executive Summary state 12.2 million.

The CBO direct URLs were rechecked with a browser-like user agent on
2026-05-12 and still returned DataDome `HTTP 403`; exact-filename web searches
for the four 2026 CBO workbooks found no alternate official route.

The HHS ACF LIHEAP FY2023 and FY2024 national profiles now have PDF-backed
source packages, `hhs-acf-liheap-fy2023-national-profile` and
`hhs-acf-liheap-fy2024-national-profile`. They preserve the publisher PDFs,
parse 360 and 348 document-number source cells through the new `pypdf`
text-line number parser, and emit the FY2023/FY2024 national households-served
facts of 5,939,605 and 5,876,646 with checksum/R2 metadata and source-cell
lineage.

The DHS OHSS unauthorized-immigrant-population report now has a PDF-backed
source package, `dhs-ohss-unauthorized-immigrant-population-2018-2022`. It
preserves the publisher PDF, parses 8,814 document-number source cells through
the same `pypdf` text-line number parser, and emits the 2022 national rounded
summary estimate of 11,000,000 unauthorized immigrants with checksum/R2
metadata and source-cell lineage. The table-exact 2022 total is 10,990,000, so
PE target construction should choose whether to use the rounded prose estimate
or exact table value. The Reuters 2024 immigration row remains blocked by
authentication constraints.

The CMS 2025 Medicare Trustees Report now has a PDF-backed source package,
`cms-medicare-trustees-report-2025-part-b-premium-income`. It preserves the
publisher PDF, parses 93,486 document-number source cells, and emits the
CY2024 Part B premiums-from-enrollees actual amount of $139.837 billion with
checksum/R2 metadata and source-cell lineage. Government contributions in
Table III.C3 remain omitted because the PDF text extraction glues the footnote
marker into the actual amount.

The Treasury FY2023 tax expenditures report now has a PDF-backed source
package, `treasury-tax-expenditures-fy2023-eitc-outlays`. It preserves the
publisher PDF, parses 52,986 document-number source cells, and emits the
FY2023 earned income tax credit outlay-effect amount of $64.44 billion with
checksum/R2 metadata and source-cell lineage.

The JCT 2024 tax expenditures report now has a PDF-backed source package,
`jct-tax-expenditures-2024-mortgage-interest-deduction`. It preserves the
official static PDF attachment with checksum/R2 metadata, parses 15,918
document-number source cells, and emits the FY2024 individual deduction for
mortgage interest on owner-occupied residences tax expenditure amount of
$24.8 billion with source-cell lineage. The publication page itself returned
HTTP 403 on 2026-05-11, but the official static PDF attachment was accessible.

The Vanguard How America Saves 2024 report now has a PDF-backed source
package, `vanguard-how-america-saves-2024-roth-participation`. It preserves
the Vanguard-hosted South America PDF mirror with checksum/R2 metadata, parses
61,308 document-number source cells, and emits the CY2023 share of offered DC
plan participants using Roth contributions, 0.17, with source-cell lineage.
The original corporate PDF URL and `?lv=true` variant returned HTML error
pages from this environment, but the regional Vanguard PDF mirror was
accessible.

The CMS State Buy-In FAQ is now
deferred as policy-context support because the CMS state payment page package
already preserves the state-paid Medicare Part A and Part B premium beneficiary
count facts.

The PE `policy_data.db` TANF workbook copies, IRS SOI CSV copies, FY2023/FY2024
Census STC individual-income-tax JSON copies, the ACS S0101 national JSON copy,
the ACS S0101 state JSON copy, the ACS S0101 congressional-district JSON copy,
the ACS S2201 congressional-district JSON copy, the Census ACS 2023 B01001
female-age JSON copy, the CDC VSRR 2023/2024 live-birth JSON copies, SNAP
archive copy, legacy SNAP state target, legacy ACS `age_state.csv`, legacy CMS
ACA spending/enrollment, legacy CMS ACA state metal-selection scaffold, legacy
CMS Medicaid enrollment target CSVs, and legacy CMS health-spending target are
now deferred as intermediate duplicates or derived-only targets because
official publisher-source packages already provide build-suite-valid facts and
source lineage for those targets or their source columns. The cached
`SSPopJul_TR2024.csv` SSA population-projection file is now represented by
`ssa-population-projections-tr2024`, which preserves 16,160 source rows from
the cached SSA Trustees Report 2024 CSV, emits 101 CY2025 single-year-age
population projection facts, and carries checksum/R2 metadata because direct
SSA OACT URLs returned HTTP 403 on 2026-05-11. For ACS S0101
national and state age bands, the
direct Census API routes returned throttling pages during this pass, so the
preserved raw artifacts are cached PE copies of the Census API responses with
checksums and R2 metadata. For ACS S0101 congressional-district age bands and
ACS S2201 congressional-district SNAP household counts, and Census B01001
female age bands, the direct Census API routes returned HTTP 429 throttling
pages during this pass, so the preserved raw artifacts are cached PE copies of
the Census API responses with checksums and R2 metadata. The standalone Census
congressional-district list and Census variables document are deferred as
support metadata, not aggregate fact packages. For CDC VSRR 2023 and 2024, the
live Socrata API responses were fetched directly and matched the PE cached row
sets. The new CMS Medicaid December 2024 package reuses the preserved April
2026 CMS administrative CSV and emits 255 December 2024 final state
Medicaid/CHIP enrollment facts with 10,608 parsed source rows, 2,288 source
cells, and zero agent-acceptance errors. The ACA PTC multiplier inputs now have
publisher-source coverage for KFF/CMS full-year average effectuated enrollment
in 2022 and 2024 via `kff-marketplace-effectuated-enrollment`, for CMS 2022
full-year average APTC via `cms-aca-effectuated-enrollment-2022`, and for the
CMS 2022 and 2025 OEP state-level average APTC values via
`cms-aca-oep-state-level-2022` and `cms-aca-oep-state-level-2025`; the CMS
full-year workbook publishes Nevada 2022 average monthly APTC as 429.75 while PE
uses 435, so that item is now a source-choice/reconciliation question rather
than a missing-source question. The preserved KFF indicator does not yet include
2025 full-year average effectuated enrollment. A 2026-05-12 recheck found CMS'
latest effectuated-enrollment source is Early Snapshot 2025 and Full Year 2024
Average, not a full-year average 2025 source, so the multiplier CSVs remain
deferred pending that source gap plus explicit `vol_mult`/`val_mult` target
construction. Missing PE-generated
ACA and long-term target CSV/JSON
intermediates are now deferred pending publisher source packages or access
fixes rather than routed to source-cell scaffolding.
The remaining local PE target/intermediate CSVs have also been moved out of the
scaffold queue: missing IRS SOI/EITC intermediate tables remain deferred pending
IRS publisher-source packages, private PUF demographic shares are deferred
pending private-source permission and metadata, ACA PTC multipliers are
deferred to remaining 2025 source clarification, Nevada source-choice
reconciliation, and target construction, and
`social_security_aux.csv` is deferred because it combines SSA/CMS long-term
sources while SSA OACT access remains HTTP 403. The Census `np2023_d5_mid.csv`
local PE intermediate is now covered
by `census-population-projections-2023`; the official Census CSV returned HTTP
200 and matched the PE cached file on 2026-05-11. The package preserves 2,580
source rows, builds 273 source cells, emits 86 CY2025 national
population-projection age facts, and extends row semantic acceptance so
`POP_0`...`POP_85` source-column headers can evidence age constraints. The
`population_by_state.csv` local PE intermediate is still deferred as a direct
publisher fact, but its raw Census inputs are now covered by
`census-pep-2023-state-age-sex` and
`census-pep-2023-puerto-rico-age-sex`. These packages preserve the official
Census Vintage 2023 state and Puerto Rico files with checksum/R2 metadata,
preserve 236,844 state source rows plus 33,541 Puerto Rico source rows, and
emit 104 build-suite-valid raw total/under-5 population facts. PE's
`population_under_5` column is a rounded-percent construction,
`round(total * round(raw_under5 / total * 100, 1) / 100)`, so this row needs
an explicit target-construction step before it can be marked as a direct
source-package match. The `agi_state.csv` local PE intermediate is now covered by
`soi-historic-table-2-state-agi-2022`, which preserves the official IRS SOI
Historic Table 2 CSV with checksum/R2 metadata, preserves 594 source rows,
builds 83,293 source cells, and emits 459 TY2022 state AGI-bracket return-count
facts matching PE `agi_state.csv`; the PE `$500,000+` bracket is represented as
the sum of SOI `AGI_STUB` 9 and 10 source rows. The `eitc.csv` local PE
intermediate is now covered by `soi-table-2-5-eitc-children-2020`, which
preserves the official IRS SOI Publication 1304 Table 2.5 `20in25ic.xls`
workbook with checksum/R2 metadata, preserves 4,293 source cells, and emits 8
TY2020 EITC return-count and total-amount facts by qualifying-child count
matching PE `eitc.csv`; the PE 3+ child category is represented by the IRS
three-or-more-qualifying-children column group. The `eitc_state.csv` local PE
intermediate is now covered by `soi-historic-table-2-state-eitc-2022`, which
preserves the official IRS SOI Historic Table 2 `22in55cmcsv.csv` file,
preserves 594 source rows, builds 8,476 source cells, and emits 102 TY2022
state EITC return-count and total-amount facts matching the Claude-worktree PE
intermediate. The `eitc_by_agi_and_children.csv` local PE intermediate is now
covered by `soi-table-2-5-eitc-agi-children-2022`, which preserves the official
IRS SOI Publication 1304 Table 2.5 `22in25ic.xls` workbook, preserves 4,293
source cells, and emits 224 TY2022 EITC return-count and total-amount facts by
AGI band and qualifying-child count matching the Claude-worktree PE
intermediate. The five PE
calibration-support crosswalk/distribution files are now deferred as support
artifacts rather than standalone aggregate fact packages.

## Completion Finding

The active goal is complete for the current pass.

Completion audit evidence:

- Objective criteria were decomposed as: package publisher-source facts that
  current parsers/access can represent; preserve raw artifacts with checksums
  and R2 metadata; add focused tests; and classify source-ambiguous,
  inaccessible, derived-only, support, or geography-only rows as blocked or
  deferred with notes.
- US manifest audit: 214 rows total; 51 `source_package`, 152 `deferred`, and
  11 `blocked`; 0 rows have missing/unknown Arch status; 0 blocked/deferred
  rows lack notes; 0 source-package rows lack `build_suite_valid` target
  status.
- US publisher-source audit: 166 rows total; 45 rows have `source_package` and
  `build_suite_valid`; 121 rows are explicitly blocked/deferred because they
  are geography/support artifacts, access-blocked sources, superseded
  duplicates, policy-context sources, derived intermediates, or
  target-construction work.
- UK checklist audit: 28 rows total; 27 checked; the 1 unchecked row is a
  documented blocker (`DWP Scotland UC child-under-1 household count` pending
  working Stat-Xplore access/API key). `HMRC/HMT salary sacrifice contribution
  amount` now has an HMT source-backed Arch fact but remains a PE target-value
  mismatch until PE's stale £24bn base is corrected.
- Focused and full verification passed: `tests/test_arch_source_package.py`
  (`227 passed`), `tests/test_arch_suite.py` (`13 passed`), targeted package
  build suites for the newly added ISC and CMSNY packages, and full source-plan
  tests.
- Raw-artifact metadata for the newly added source packages is present in
  manifests with checksums and R2 metadata; direct fact builds for the newly
  added/recent PDF and HTML packages emit facts whose provenance includes
  `raw_r2_uri`.

Residual future work is watch-list work, not unmet scope for this pass: recheck
SSA/CBO/Reuters and Stat-Xplore when browser-authenticated or alternate
publisher access is available, and add packages/tests if any blocked/deferred
item becomes packageable.
