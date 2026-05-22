# PE UK Source Checklist

Last updated: 2026-05-11.

This checklist tracks source-backed Arch coverage for target sources currently
used by `policyengine_uk_data.targets`. Use it as the queue for UK source
package work.

Status meanings:

- `[x]`: Arch package exists and the source-package suite has passed.
- `[ ]`: Not yet represented as an Arch source package.
- `partial`: Some source facts exist, but PE uses additional target families or
  transformations that still need source-backed representation.
- `defer`: Lower priority because the current PE target is survey-based,
  heavily derived, local preprocessed data, or not a primary source artifact yet.

## Acceptance Gate For Each Package

Each completed item should have:

- Raw publisher artifact in `db/data/...` with checksum and R2 metadata.
- Declarative package in `packages/.../source_package.yaml`.
- Full-document source parse where practical; selected-row-only parsing should
  be avoided for accepted packages.
- Source-record specs for every emitted fact.
- Canonical constraints for dimensions that matter downstream.
- `uv run arch validate-package <alias> --year <year>` passing.
- `uv run arch build-suite <alias> --year <year> --out /tmp/<alias> --replace`
  passing.
- Focused tests and `uv run ruff check` passing when code changes.

## P0: Primary Administrative Or Forecast Sources Used Nationally

- [x] OBR EFO receipts - done/partial
  - PE module: `sources/obr.py`.
  - Arch package: `obr-efo-receipts`.
  - Covers income tax, NICs total, Class 1 employee/employer NICs, combined
    Class 2/Class 4 self-employed NICs, VAT, fuel duties, CGT, SDLT.
  - Caveat: March 2026 Table 3.4 does not expose separate Class 2, Class 3,
    and Class 4 rows, so Arch should not invent those facts from the workbook.

- [x] OBR EFO expenditure - done
  - PE module: `sources/obr.py`.
  - Arch package: `obr-efo-expenditure`.
  - Covers council tax/domestic rates, welfare spending lines, UC outside cap,
    and BBC licence fee receipts.

- [x] SLC student support England 2025 - partial
  - PE module: `sources/slc.py`.
  - Arch package: `slc-student-support-england-2025`.
  - Covers maintenance loan recipients/spend, Parents Learning Allowance
    recipients/spend, and Adult Dependants Grant recipients/spend.
  - Remaining SLC work is listed separately below.

- [x] DWP UC two-child-limit statistics - done
  - PE module: `sources/dwp.py`.
  - Arch package: `dwp-uc-two-child-limit-2025`.
  - Covers official ODS tables 01, 03A-C, and 04A-C for affected households,
    children in affected households, children affected, number-of-children
    splits, claimant PIP, disabled child element, and related health/disability
    entitlement columns.
  - Caveat: Fact period is the PE target year 2026; source vintage is the DWP
    April 2025 publication.

- [x] DWP benefit cap statistics - done
  - PE module: `sources/dwp.py`.
  - Arch package: `dwp-benefit-cap-november-2025`.
  - Covers Table 4 GB point-in-time UC capped household total and monthly
    amount-capped bands from the official November 2025 ODS.
  - Caveat: Arch preserves the monthly point-in-time distribution. PE's
    annualized total reduction is a downstream derivation from these bands, not
    a publisher fact.

- [x] DWP benefit/PIP claimant counts - done for current PE targets
  - PE module: `sources/dwp.py`.
  - Current PE targets: PIP daily living standard/enhanced, ESA, contributory
    ESA, income-related ESA, JSA.
  - Sources: DWP benefit statistics February 2026 and PIP statistics to January
    2026.
  - Arch packages: `dwp-benefit-statistics-february-2026` and
    `dwp-pip-daily-living-foi-2025`.
  - Covers the DWP February 2026 summary page's August 2025 headline claimant
    counts for State Pension, UC, PIP, Attendance Allowance, Housing Benefit,
    Pension Credit, Carers Allowance, DLA, ESA, and JSA, source-lineaged ESA
    contributions-based and income-related claimant counts from the page prose,
    and DWP FOI2025/24990 PIP daily-living standard/enhanced working-age
    normal-rules claimant counts for January 2025.
  - Inventory note: the official PIP January 2026 ODS is registered under
    `db/data/dwp/pip_january_2026_england_wales`, but it does not contain the
    daily-living standard/enhanced caseload facts used by PE. The source-backed
    fallback is the DWP FOI response, mirrored by WhatDoTheyKnow, with explicit
    constraints for working age, normal rules, and England/Wales/abroad under
    DWP policy ownership.
  - Future hardening: replace or corroborate the FOI package with a direct
    Stat-Xplore cases-with-entitlement API extract once an API key is available.

- [x] DWP Stat-Xplore UC national distribution - done
  - PE module: `sources/dwp.py` and local `storage/uc_national_payment_dist.xlsx`.
  - Current PE targets: UC payment distribution by family type and annual
    payment band.
  - Source: DWP Stat-Xplore.
  - Arch package: `dwp-uc-national-payment-dist-2025`.
  - Covers the May 2025 Stat-Xplore workbook export's Great Britain Universal
    Credit household counts by monthly award amount band and family type.
  - Caveat: PE converts the source monthly award bands to annual payment
    lower/upper bounds downstream; Arch preserves the source monthly award
    constraints.

- [ ] DWP Scotland UC child-under-1 household count
  - PE module: `sources/dwp.py`.
  - Current PE target: Scotland UC households with child under 1.
  - Source: DWP Stat-Xplore.
  - Arch action: pair with the Stat-Xplore UC work where possible.
  - Current evidence note: the Scottish Budget package now preserves a related
    SFC estimate for Scottish Child Payment children under 1, but that is not
    the same as the DWP Stat-Xplore count of UC households with a child under
    1. Keep this item open until the Stat-Xplore table behind the 13,992
    household target is preserved.
  - 2026-05-12 access note: the local `policyengine-uk-data` tree has the
    rounded target and test comment but no Scotland child-under-1 Stat-Xplore
    export. Direct probes of Stat-Xplore web/API endpoints still returned the
    DWP "Down for Data-loading Maintenance" page with HTTP 503, and
    `agent-secret search stat` found no agent-readable Stat-Xplore API key. This
    remains blocked pending a working Stat-Xplore export or API response.

- [x] SLC plan borrower forecasts
  - PE module: `sources/slc.py`.
  - Current PE targets: Plan 2/Plan 5 borrowers liable and above threshold.
  - Source: Explore Education Statistics permalink table 6a.
  - Arch package: `slc-student-loan-borrower-forecasts-england-2025`.
  - Covers the pinned EES permalink page as a raw HTML artifact, parsed through
    its `__NEXT_DATA__` table JSON into plan/status/year source rows.
  - Caveat: PE consumes 2025-2030 forecast values; Arch preserves them as
    SLC forecast-vintage facts from the 2025 source artifact.

- [x] SLC repayment amounts by country/plan
  - PE module: `sources/slc_repayments.py`.
  - Current PE targets: England total and plans 1/2/5/postgraduate, plus
    Scotland, Wales, Northern Ireland totals.
  - Sources: SLC England corrected workbook plus devolved SLC publications.
  - Arch packages: `slc-student-loan-repayments-england-2025`,
    `slc-student-loan-repayments-scotland-2025`,
    `slc-student-loan-repayments-wales-2025`, and
    `slc-student-loan-repayments-northern-ireland-2025`.
  - Covers the corrected England Table 1A 2024-25 source workbook for total
    higher education net repayments posted and the source plan/product columns
    Plan 1, Plan 2 full-time, Plan 2 part-time, postgraduate Masters,
    postgraduate Doctoral, Plan 5 full-time, and Plan 5 part-time.
  - Covers the Scotland, Wales, and Northern Ireland Table 1 total higher
    education net repayments posted source cells for 2024-25.
  - Caveat: PE's England Plan 2, Plan 5, and postgraduate targets are sums of
    source columns. Arch preserves the source columns; downstream target
    construction should sum them explicitly.

- [x] HMRC salary sacrifice tax and NICs relief
  - PE module: `sources/hmrc_salary_sacrifice.py`.
  - Current PE targets: income tax relief by tax band, employee/employer NICs
    relief.
  - Source: HMRC Tables 6.1 and 6.2 CSV.
  - Arch package: `hmrc-salary-sacrifice-relief-2024`.
  - Covers the 2023-24 salary-sacrificed contribution value-of-relief rows
    used by PE: income tax total/basic/higher/additional and employee/employer
    Class 1 NICs totals.

- [ ] HMRC salary sacrifice contribution amount
  - PE module: `sources/hmrc_salary_sacrifice.py`.
  - Current PE target: total salary sacrificed contributions.
  - Claimed source: SPP Review 2025 PDF.
  - Status: blocked pending source clarification. The PE reference URL is
    stale, and the current SPP paper states that HMRC figures suggest the total
    cost of National Insurance relief on pension contributions was £24.0bn in
    2023-24, with £4.1bn relating to pension salary sacrifice. That supports
    the HMRC relief facts already packaged above, but not a total salary
    sacrificed contribution amount of £24bn.
  - Arch action: do not ingest this as an Arch contribution fact until a
    primary source for the contribution amount is identified.

- [x] HMRC SPI income bands
  - PE module: `sources/hmrc_spi.py`.
  - Current PE targets: income amount/count by total-income band for employment,
    self-employment, state pension, private pensions, property, dividends.
  - Source: HMRC SPI collated ODS.
  - Arch package: `hmrc-spi-income-bands-2023`.
  - Covers source-year 2022-23 Tables 3.6 and 3.7 for the income types used by
    PE, with explicit total-income lower/upper-bound constraints.
  - Caveat: Arch preserves raw SPI property income as published. PE's 1.9x
    property-income adjustment and future-year projection CSV remain
    downstream target-construction choices, not source facts.

- [x] ONS savings interest income
  - PE module: `sources/ons_savings.py`.
  - Current PE target: household interest resources series HAXV.
  - Source: ONS time-series API/page.
  - Arch package: `ons-savings-interest-income`.
  - Covers the annual ONS UKEA HAXV observations from the frozen time-series
    JSON artifact, including 2023 and the current 2025 observation in the
    source file.
  - Caveat: Arch preserves observed annual source facts. PE's flat projection
    through 2029 remains downstream target construction.

- [x] VOA council tax bands
  - PE modules: `sources/voa_council_tax.py` and
    `sources/la_council_tax.py`.
  - Current PE targets: regional band A-H and total counts, Scotland, and
    local-authority band A-H/I counts for England and Wales.
  - Sources: VOA 2025 stock-of-properties workbook and Scottish Government
    chargeable dwellings workbook.
  - Arch packages: `voa-council-tax-bands-2025` and
    `scotgov-council-tax-bands-2025`.
  - Covers the 2025 regional A-H and total chargeable-dwelling facts, plus
    the 2,563 source-numeric local-authority band facts from `CTSOP1.0` used
    by PE. Suppressed cells such as English Band I, City of London Band A, and
    two Welsh Band H cells are omitted rather than fabricated.
  - Caveat: Arch keeps VOA and Scottish Government provenance separate.
    Downstream target construction can present the combined PE target family.

- [x] Scottish Government Scottish Child Payment spend
  - PE module: `sources/scottish_government.py`.
  - Current PE target: Scottish Child Payment spend from Scottish Budget.
  - Source: Scottish Budget 2026-27 table.
  - Arch package:
    `scotgov-scottish-budget-social-security-assistance-2026`.
  - Covers the official gov.scot Chapter 5 HTML page, Table 5.08 row for
    Scottish Child Payment: 2024-25 outturn, 2025-26 ABR budget, and
    2026-27 budget.
  - Also covers the chapter prose's Scottish Fiscal Commission estimate that
    around 12,000 children under 1 will receive the increased Scottish Child
    Payment support once paid in 2027-28, with source-cell lineage to the
    parsed document-number row.
  - Caveat: PE's 2027-2029 3% extrapolations remain downstream target
    construction, not Arch source facts.

## P1: Population, Households, Land, And Other Official Series

- [x] ONS UK population projections
  - PE module: `sources/ons_demographics.py`.
  - Current PE targets: UK population and gender by age-band counts.
  - Source: ONS 2022-based UK projection ZIP/workbook.
  - Arch package: `ons-uk-population-projections-2022`.
  - Covers the principal projection workbook member
    `uk/uk_ppp_machine_readable.xlsx` inside the ONS ZIP, with range-summed
    source-cell lineage for total UK population plus PE's male/female age bands.
  - Caveat: these are ONS 2022-based projection-vintage facts, not observed
    mid-year population estimates.

- [x] ONS/NRS/Scotland demographic special cases - NRS sources done/partial
  - PE module: `sources/ons_demographics.py`.
  - Current PE targets: Scotland children under 16, babies under 1, households
    with 3+ children.
  - Sources: NRS and Scotland Census pages/tables.
  - Arch packages: `nrs-mid-year-population-estimates-2024` and
    `nrs-vital-events-reference-tables-2024`.
  - Covers NRS mid-2024 Scotland persons under 16 from Table 3: 896,833
    usual residents, with age constraints `person.age >= 0` and
    `person.age < 16`.
  - Covers NRS 2024 Scotland live births from vital-events chapter 1
    Table 1.01(b): 45,763 live births for calendar year 2024, with full
    workbook source-cell preservation and selector lineage to `Table_1.01b!E60`.
  - Blocked source note: the current Scotland Census MV104 file in
    `db/data/scotland_census/mv104_household_composition_by_dependent_children_2022`
    is by youngest dependent-child age, not by number of dependent children.
    The UV113 household-composition file only distinguishes one dependent
    child from two-or-more dependent children. Neither should be represented
    as a source-backed "3+ children" fact without a more specific primary
    Scotland Census table.

- [x] ONS families and households - done
  - PE module: `sources/ons_households.py`.
  - Current PE targets: household type counts from ONS Table 7.
  - Source: ONS Families and Households workbook.
  - Arch package: `ons-families-households-2024`.
  - Covers the exact workbook URL referenced by PE,
    `familiesandhouseholdsuk2024.xlsx`, preserving the full workbook used
    range across all sheets and emitting the 2024 Table 7 household counts for
    the 10 PE household types: one-person under 65, one-person 65 or over,
    unrelated-adult households, four couple-household child categories,
    two lone-parent categories, and multi-family households.
  - Caveat: these are ONS survey estimates in thousands. Arch preserves the
    source counts and household-type constraints; PE target construction can
    handle survey uncertainty or downstream reconciliation separately.
  - Inventory note: `db/data/ons/households_by_type_2025` contains a different
    ONS regions/countries workbook and should not be treated as PE Table 7.

- [x] ONS dwelling stock by tenure
  - PE module: `sources/ons_tenure.py`.
  - Current PE targets: England tenure counts.
  - Source: ONS subnational dwellings by tenure workbook.
  - Arch package: `ons-subnational-dwellings-by-tenure-2024`.
  - Covers 2024 England owned outright, owned with mortgage or loan, private
    rent, social rent, and total dwelling-stock facts by summing every local
    authority row in ONS Table 1a with source-cell lineage over the selected
    source range.
  - Caveat: the England totals are Arch source-cell sums over the ONS local
    authority rows; PE should keep any household-vs-dwelling reconciliation
    downstream.

- [x] ONS National Balance Sheet land values - national done/partial
  - PE modules: `sources/ons_land_values.py`, `sources/mhclg_regional_land.py`,
    and `_land.py`.
  - Current PE targets: total, household, corporate, and regional household
    land values.
  - Source: ONS National Balance Sheet 2025 plus local regional split CSV.
  - Arch package: `ons-national-balance-sheet-land-2025`.
  - Covers direct 2024 ONS AN.211 land-value facts for total economy,
    non-financial corporations, private non-financial corporations,
    households and NPISH, and households.
  - Caveat: PE's current household/corporate split and regional household-land
    targets are downstream derivations. Arch now preserves direct national ONS
    sector facts; regional split still needs a primary regional source or an
    explicitly derived downstream target-construction step.

## P2: Defer Or Requires More Source Discipline

- [x] NTS vehicle ownership - source rates done/partial
  - PE module: `sources/nts_vehicles.py`.
  - Current PE targets: no vehicle, one vehicle, two-plus vehicle households.
  - Source: National Travel Survey 2024 plus derived household total.
  - Arch package: `dft-nts-household-car-availability-2024`.
  - Covers the official DfT NTS 2024 GOV.UK publication page, preserving 660
    parsed document-number source cells and emitting England household
    car-or-van availability shares: 22% no cars, 44% one car, and 34% two or
    more cars.
  - Caveat: PE's household-count targets multiply these survey shares by a
    separate approximate UK household total. Arch preserves the publisher
    rates only; downstream target construction should handle the household
    total and England-vs-UK geography reconciliation explicitly.

- [x] Housing affordability totals - rent source amounts done/partial
  - PE module: `sources/housing.py`.
  - Current PE targets: total mortgage payments, private rent, social rent.
  - Sources: ONS PRHI, English Housing Survey, devolved/renter counts.
  - Arch packages: `ons-private-rent-house-prices-march-2026` and
    `mhclg-english-housing-survey-rented-sectors-2023-24`.
  - Covers the official ONS Private rent and house prices, UK: March 2026
    bulletin's February 2026 UK average monthly private rent of £1,374, with
    full parsed-document source-cell preservation and a private-rent tenure
    constraint. Also covers the official English Housing Survey 2023-24 rented
    sectors report's England mean weekly social rent of £118, with
    parsed-document source-cell preservation and a social-rent tenure
    constraint.
  - Caveat: PE's private rent target multiplies the ONS monthly rent by 12 and
    an approximate 5.4m UK private-renter count. PE's social-rent target
    multiplies the EHS England weekly amount by 52 and an approximate 5.0m UK
    social-renter count. Mortgage totals, renter counts, annualization, and
    tenure/geography reconciliation remain downstream target-construction work.

- [x] OBR/static salary-sacrifice and private-school helper targets - salary-sacrifice users and ISC pupil count done/partial
  - PE module: `sources/obr.py`.
  - Current PE targets: salary-sacrifice NI relief/headcount, private school
    pupils.
  - Sources/comments reference OBR/SPP/ISC assumptions.
  - Arch packages: `hmrc-salary-sacrifice-reform-2025`,
    `hmrc-salary-sacrifice-relief-2024`, and
    `isc-census-2024-pupil-count`.
  - Covers the official GOV.UK/HMRC tax information and impact note's current
    pension salary-sacrifice user estimates: 7.7m total employees, 3.3m
    sacrificing more than £2,000, and 4.3m fully protected by the £2,000
    threshold, with parsed-document source-cell preservation and explicit
    salary-sacrifice contribution-band constraints.
  - Caveat: PE's 2024-2031 salary-sacrifice headcount targets grow the
    publication-vintage estimates by a 2.4% annual assumption. Arch preserves
    the GOV.UK/HMRC source estimates only; downstream target construction
    should apply any base-year mapping and growth explicitly. Salary-sacrifice
    NI relief facts are covered by `hmrc-salary-sacrifice-relief-2024`.
  - Covers the official ISC Census and Annual Report 2024 PDF's Executive
    Summary pupil count: 556,551 pupils at 1,411 ISC member schools, with
    PDF-derived source-cell preservation and independent/ISC-member school
    constraints.
  - Caveat: PE's private-school pupil target uses a static 557k rounded ISC
    assumption. Arch preserves the exact source count; downstream target
    construction should apply rounding and any model-year mapping explicitly.

## Local-Area Calibration Helpers

These do not all expose `get_targets()`, but PE UK calibration code reads them
directly for constituency/local-authority calibration. They should be handled
after national P0 packages unless local calibration is the immediate goal.

- [x] Local age targets - local-authority source done/partial
  - PE helper: `sources/local_age.py`.
  - Sources: ONS mid-year population estimates and preprocessed local CSVs.
  - Arch package: `ons-nomis-local-authority-population-2024`.
  - Covers official ONS/Nomis `NM_2002_1` 2024 mid-year population estimates
    for current local authorities (`TYPE424`, April 2023 geography), emitting
    10-year age-band facts from age 0-9 through 70-79 for all 361 local
    authorities, including Ards and North Down, with full source-row and
    source-cell lineage.
  - Caveat: PE's current local-age helper uses 360 local-authority target rows
    and omits Ards and North Down. Constituency age targets still rely on
    House of Commons Library 2020/preprocessed/mapped source work; Arch does
    not yet preserve those constituency raw or boundary-mapping artifacts.

- [x] Local income targets - direct SPI area facts done/partial
  - PE helper: `sources/local_income.py`.
  - Sources: HMRC SPI local-area tables and preprocessed CSVs.
  - Arch package: `hmrc-spi-local-income-2022`.
  - Covers HMRC SPI 2021-22 collated ODS Tables 3.14 and 3.15 for
    self-employment and employment income taxpayer counts and mean income by
    local authority and 2010 parliamentary constituency, with full workbook
    source-cell preservation and explicit income-source constraints.
  - Caveat: PE's local CSV amount targets are derived as count times mean, and
    its 2025 calibration path applies separate national consistency scaling.
    Arch preserves the direct publisher count and mean facts only. The HMRC
    workbook marks Isles of Scilly and Torbay local-authority values as not
    available; PE imputes those rows, so Arch does not emit those imputed
    source facts.

- [x] Local UC household targets - NI constituency and district sources done/partial
  - PE helper: `sources/local_uc.py`.
  - Sources: DWP Stat-Xplore exports and preprocessed UC workbooks.
  - Arch package: `dfc-ni-uc-statistics-may-2025`.
  - Covers the official Department for Communities NI Universal Credit
    supplementary ODS Table 5b May 2025 claimant counts for all 18 Northern
    Ireland 2024 Westminster parliamentary constituencies and Table 5c May
    2025 claimant counts for all 11 NI local government districts, with full
    workbook source-cell preservation and geography IDs.
  - Caveat: PE's local UC helper currently reads the Table 5b claimant table
    into a `household_count` column, combines it with GB Stat-Xplore local
    household exports, scales the combined local totals to the national UC
    payment-distribution total, and skips Ards and North Down in the local
    authority path to match its current 10-district NI target dataset. Arch
    preserves the DfC NI claimant counts only; GB local Stat-Xplore exports,
    household-vs-claimant reconciliation, scaling, and children-count split
    assumptions remain downstream or separate source-package work.

- [x] Local authority income/tenure/rent extras - ONS income source done/partial
  - PE helper: `sources/local_la_extras.py`.
  - Sources: ONS small area income, Census household counts, EHS tenure,
    ONS/VOA private rents.
  - Arch package: `ons-small-area-income-local-authority-2020`.
  - Covers the official ONS financial year ending 2020 small-area income
    workbook, aggregating MSOA rows to 348 England and Wales local authorities
    for total annual household income, net income before housing costs, and net
    income after housing costs, with full workbook source-cell preservation.
  - Caveat: PE uprates BHC and housing-cost factors downstream to 2025; Arch
    preserves the FYE 2020 publisher facts only. The household-count workbook
    is weak/empty in the local PE storage copy, and tenure/private-rent local
    workbooks remain source-ambiguous until their exact publisher artifacts are
    identified. A checked ONS private-rent summary workbook did not match PE's
    `Figure 3` chart-data workbook or values, so that rent component is
    deferred rather than converted from a mismatched source.

## Suggested Processing Order

1. DWP UC two-child-limit statistics.
2. DWP benefit cap statistics.
3. SLC repayments.
4. SLC plan borrower forecasts.
5. HMRC salary sacrifice relief.
6. HMRC SPI income bands.
7. ONS savings interest.
8. VOA council tax bands.
9. ONS population projections.
