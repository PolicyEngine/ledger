"""PolicyEngine source-file inventory for Arch ingestion."""

from __future__ import annotations

import csv
import sqlite3
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from .schema import Jurisdiction
from .source_files import SourceArtifactSpec, make_slug, make_url_slug

DEFAULT_PE_US_ROOT = Path("/Users/maxghenis/PolicyEngine/policyengine-us-data")
DEFAULT_PE_UK_ROOT = Path("/Users/maxghenis/PolicyEngine/policyengine-uk-data")

SOURCE_SUFFIXES = {
    ".csv",
    ".gz",
    ".html",
    ".htm",
    ".json",
    ".ods",
    ".pdf",
    ".txt",
    ".xls",
    ".xlsx",
    ".yaml",
    ".yml",
    ".zip",
}

US_CALIBRATION_TARGET_ROOT_FILES = {
    "aca_ptc_multipliers_2022_2024.csv",
    "aca_ptc_multipliers_2022_2025.csv",
}

US_RAW_INPUT_FILES = {
    "acs5_congressional_districts_2024.json",
    "acs_S0101_district_2024.json",
    "acs_S0101_national_2024.json",
    "acs_S0101_state_2024.json",
    "acs_S2201_district_2024.json",
    "cdc_vsrr_births_2024.json",
    "census_b01001_female_15_44_2023.json",
    "census_docs_2024.json",
    "census_stc_individual_income_tax_2024.json",
    "census_stc_t40_individual_income_tax_2023.json",
    "irs_soi_22in55cmcsv.csv",
    "irs_soi_22incd.csv",
    "medicaid_enrollment_2024.csv",
    "snap_fy69tocurrent.zip",
    "tanf_caseload_2024.xlsx",
    "tanf_financial_2024.xlsx",
}

US_CALIBRATION_TARGET_FILES = {
    "aca_marketplace_state_metal_selection_2024.csv",
    "aca_spending_and_enrollment_2024.csv",
    "aca_spending_and_enrollment_2025.csv",
    "age_state.csv",
    "agi_state.csv",
    "eitc_by_agi_and_children.csv",
    "eitc_state.csv",
    "healthcare_spending.csv",
    "medicaid_enrollment_2024.csv",
    "medicaid_enrollment_2025.csv",
    "np2023_d5_mid.csv",
    "population_by_state.csv",
    "puf_filer_demographic_cell_shares_2015.csv",
    "real_estate_taxes_by_state_acs.csv",
    "snap_state.csv",
    "soi_targets.csv",
    "spm_threshold_agi.csv",
}

UK_STORAGE_TARGET_FILES = {
    "constituencies_2010.csv",
    "constituencies_2024.csv",
    "council_tax_bands_2024.csv",
    "demographics.csv",
    "dfc-ni-uc-stats-supp-tables-may-2025.ods",
    "incomes.csv",
    "incomes_projection.csv",
    "la_count_households.xlsx",
    "la_private_rents_median.xlsx",
    "la_tenure.xlsx",
    "local_authorities_2021.csv",
    "local_authority_ons_income.xlsx",
    "tax_benefit.csv",
    "uc_la_households.xlsx",
    "uc_national_payment_dist.xlsx",
    "uc_pc_households.xlsx",
}

US_CALIBRATION_SUPPORT_FILES = {
    "block_cd_distributions.csv.gz",
    "block_crosswalk.csv.gz",
    "county_cd_distributions.csv",
    "district_mapping.csv",
    "national_and_district_rents_2023.csv",
}

US_LONG_TERM_TARGET_SOURCE_FILES = {
    "oact_2025_08_05_provisional.csv",
    "oasdi_oact_20250805_nominal_delta.csv",
    "sources.json",
    "trustees_2025_current_law.csv",
}

US_LONG_TERM_ROOT_SOURCE_FILES = {
    "social_security_aux.csv",
    "SSPopJul_TR2024.csv",
}

US_LONG_TERM_REFERENCE_URLS = [
    {
        "source_id": "ssa",
        "url": "https://www.ssa.gov/oact/tr/2025/lrIndex.html",
        "filename": "ssa_2025_trustees_report_index.html",
    },
    {
        "source_id": "ssa",
        "url": "https://www.ssa.gov/oact/solvency/provisions/tables/table_run133.html",
        "filename": "ssa_solvencey_provision_table_run133.html",
    },
    {
        "source_id": "ssa",
        "url": "https://www.ssa.gov/OACT/solvency/RWyden_20250805.pdf",
        "filename": "ssa_oact_wyden_2025_08_05.pdf",
    },
]

CENSUS_STATES_AND_DC = (
    ("AL", "01", "Alabama"),
    ("AK", "02", "Alaska"),
    ("AZ", "04", "Arizona"),
    ("AR", "05", "Arkansas"),
    ("CA", "06", "California"),
    ("CO", "08", "Colorado"),
    ("CT", "09", "Connecticut"),
    ("DE", "10", "Delaware"),
    ("DC", "11", "District_of_Columbia"),
    ("FL", "12", "Florida"),
    ("GA", "13", "Georgia"),
    ("HI", "15", "Hawaii"),
    ("ID", "16", "Idaho"),
    ("IL", "17", "Illinois"),
    ("IN", "18", "Indiana"),
    ("IA", "19", "Iowa"),
    ("KS", "20", "Kansas"),
    ("KY", "21", "Kentucky"),
    ("LA", "22", "Louisiana"),
    ("ME", "23", "Maine"),
    ("MD", "24", "Maryland"),
    ("MA", "25", "Massachusetts"),
    ("MI", "26", "Michigan"),
    ("MN", "27", "Minnesota"),
    ("MS", "28", "Mississippi"),
    ("MO", "29", "Missouri"),
    ("MT", "30", "Montana"),
    ("NE", "31", "Nebraska"),
    ("NV", "32", "Nevada"),
    ("NH", "33", "New_Hampshire"),
    ("NJ", "34", "New_Jersey"),
    ("NM", "35", "New_Mexico"),
    ("NY", "36", "New_York"),
    ("NC", "37", "North_Carolina"),
    ("ND", "38", "North_Dakota"),
    ("OH", "39", "Ohio"),
    ("OK", "40", "Oklahoma"),
    ("OR", "41", "Oregon"),
    ("PA", "42", "Pennsylvania"),
    ("RI", "44", "Rhode_Island"),
    ("SC", "45", "South_Carolina"),
    ("SD", "46", "South_Dakota"),
    ("TN", "47", "Tennessee"),
    ("TX", "48", "Texas"),
    ("UT", "49", "Utah"),
    ("VT", "50", "Vermont"),
    ("VA", "51", "Virginia"),
    ("WA", "53", "Washington"),
    ("WV", "54", "West_Virginia"),
    ("WI", "55", "Wisconsin"),
    ("WY", "56", "Wyoming"),
)

US_TARGET_URL_FILES = [
    # IRS SOI national workbook tables used to refresh ``soi_targets.csv``.
    *[
        {
            "source_id": "irs-soi",
            "pipeline": "national-soi-workbooks",
            "url": f"https://www.irs.gov/pub/irs-soi/{year % 100:02d}{suffix}",
            "filename": f"irs_soi_ty{year}_{table_slug}.{suffix.rsplit('.', 1)[-1]}",
            "notes": (
                "IRS Publication 1304 workbook. Arch must preserve the full "
                "workbook, not only the rows PE selects for active targets."
            ),
        }
        for year in (2021, 2022, 2023)
        for table_slug, suffix in (
            ("table_1_1", "in11si.xls"),
            ("table_1_2", "in12ms.xls"),
            ("table_1_4", "in14ar.xls"),
            ("table_2_1", "in21id.xls"),
            ("table_2_5", "in25ic.xls"),
            ("table_4_3", "in43ts.xls"),
        )
    ],
    # IRS SOI geographic files used by national/local PE calibration.
    *[
        {
            "source_id": "irs-soi",
            "pipeline": "soi-geography-files",
            "url": f"https://www.irs.gov/pub/irs-soi/{year % 100:02d}{suffix}",
            "filename": f"irs_soi_ty{year}_{filename}",
            "notes": (
                "IRS geographic SOI source file. Includes state and/or "
                "congressional-district cells; Arch should keep every column "
                "and row even when PE calibrates to a subset."
            ),
        }
        for year in (2022,)
        for suffix, filename in (
            ("in54us.xlsx", "in54us.xlsx"),
            ("in55cmcsv.csv", "in55cmcsv.csv"),
            ("incd.csv", "incd.csv"),
        )
    ],
    {
        "source_id": "irs-soi",
        "pipeline": "soi-source-pages",
        "url": "https://www.irs.gov/statistics/soi-tax-stats-individual-statistical-tables-by-size-of-adjusted-gross-income",
        "filename": "irs_soi_individual_statistical_tables_by_size_of_agi.html",
        "notes": "IRS landing page for Publication 1304 workbook source files.",
    },
    {
        "source_id": "irs-soi",
        "pipeline": "soi-source-pages",
        "url": "https://www.irs.gov/statistics/soi-tax-stats-accumulation-and-distribution-of-individual-retirement-arrangements",
        "filename": "irs_soi_ira_accumulation_distribution_tables.html",
        "notes": "IRS landing page for IRA accumulation/distribution targets.",
    },
    {
        "source_id": "irs-soi",
        "pipeline": "soi-source-pages",
        "url": "https://www.irs.gov/statistics/soi-tax-stats-individual-information-return-form-w2-statistics",
        "filename": "irs_soi_w2_statistics.html",
        "notes": "IRS W-2 statistics page used for tip-income source notes.",
    },
    {
        "source_id": "usda-snap",
        "pipeline": "snap-source-documents",
        "url": "https://www.fns.usda.gov/sites/default/files/resource-files/snap-zip-fy69tocurrent-6.zip",
        "filename": "usda_snap_fy69_to_current.zip",
        "notes": "USDA/FNS SNAP administrative workbook archive.",
    },
    {
        "source_id": "usda-snap",
        "pipeline": "snap-source-documents",
        "url": "https://www.fns.usda.gov/pd/supplemental-nutrition-assistance-program-snap",
        "filename": "usda_snap_program_data_page.html",
        "notes": "USDA/FNS SNAP program data landing page.",
    },
    {
        "source_id": "cms-aca",
        "pipeline": "aca-source-documents",
        "url": "https://www.cms.gov/marketplace/resources/data/public-use-files",
        "filename": "cms_marketplace_public_use_files.html",
        "notes": "CMS Marketplace public-use-file landing page for ACA targets.",
    },
    {
        "source_id": "cms-aca",
        "pipeline": "aca-source-documents",
        "url": "https://www.cms.gov/files/document/full-year-effectuated-enrollment.xlsx",
        "filename": "cms_full_year_effectuated_enrollment.xlsx",
        "notes": (
            "CMS Marketplace full-year effectuated enrollment workbook with "
            "state-level enrollment, APTC, CSR, and premium measures."
        ),
    },
    {
        "source_id": "cms-medicaid",
        "pipeline": "medicaid-source-documents",
        "url": "https://data.medicaid.gov/dataset/6165f45b-ca93-5bb5-9d06-db29c692a360",
        "filename": "cms_medicaid_chip_monthly_enrollment_dataset.html",
        "notes": "CMS Medicaid and CHIP monthly enrollment source page.",
    },
    {
        "source_id": "hhs-acf-tanf",
        "pipeline": "tanf-source-documents",
        "url": "https://www.acf.hhs.gov/ofa/data/tanf-caseload-data-2024",
        "filename": "acf_tanf_caseload_data_2024.html",
        "notes": "ACF TANF caseload workbook landing page.",
    },
    {
        "source_id": "hhs-acf-tanf",
        "pipeline": "tanf-source-documents",
        "url": "https://www.acf.hhs.gov/ofa/data/tanf-financial-data-fy-2024",
        "filename": "acf_tanf_financial_data_fy2024.html",
        "notes": "ACF TANF financial workbook landing page.",
    },
    {
        "source_id": "census",
        "pipeline": "census-source-documents",
        "url": "https://www2.census.gov/geo/docs/reference/codes2020/national_county2020.txt",
        "filename": "census_national_county_2020.txt",
        "notes": "Census county-code file used by PE county/CD support builders.",
    },
    {
        "source_id": "census",
        "pipeline": "local-geography-source-documents",
        "url": "https://www2.census.gov/programs-surveys/decennial/rdo/mapping-files/2019/116-congressional-district-bef/cd116.zip",
        "filename": "census_116th_congressional_district_bef.zip",
        "notes": "Census 116th Congressional District BEF used by PE district mapping.",
    },
    {
        "source_id": "census",
        "pipeline": "local-geography-source-documents",
        "url": "https://www2.census.gov/programs-surveys/decennial/rdo/mapping-files/2023/118-congressional-district-bef/cd118.zip",
        "filename": "census_118th_congressional_district_bef.zip",
        "notes": "Census block equivalency file for district mappings.",
    },
    {
        "source_id": "census",
        "pipeline": "local-geography-source-documents",
        "url": "https://www2.census.gov/programs-surveys/decennial/rdo/mapping-files/2025/119-congressional-district-befs/cd119.zip",
        "filename": "census_119th_congressional_district_bef.zip",
        "notes": "Census 119th Congressional District BEF used by PE local geography builders.",
    },
    {
        "source_id": "census",
        "pipeline": "local-geography-source-documents",
        "url": "https://www2.census.gov/geo/docs/maps-data/data/rel2020/2020_Census_Tract_to_2020_PUMA.txt",
        "filename": "census_tract_2020_to_puma_2020.txt",
        "notes": "Census tract-to-PUMA relationship file used by block crosswalks.",
    },
    {
        "source_id": "census",
        "pipeline": "local-geography-source-documents",
        "url": "https://www2.census.gov/geo/docs/maps-data/data/rel2020/zcta520/tab20_zcta520_tabblock20_natl.txt",
        "filename": "census_zcta2020_to_block2020_national.txt",
        "notes": "Census ZCTA-to-block relationship file used by block crosswalks.",
    },
    *[
        {
            "source_id": "census",
            "pipeline": "local-geography-source-documents",
            "url": (
                "https://www2.census.gov/programs-surveys/decennial/2020/"
                f"data/01-Redistricting_File--PL_94-171/{state_dir}/"
                f"{abbr.lower()}2020.pl.zip"
            ),
            "filename": f"census_2020_pl_94_171_{abbr.lower()}.zip",
            "notes": (
                "2020 Census PL 94-171 state redistricting legacy file used "
                "for block population in PE local geography builders."
            ),
        }
        for abbr, _fips, state_dir in CENSUS_STATES_AND_DC
    ],
    *[
        {
            "source_id": "census",
            "pipeline": "local-geography-source-documents",
            "url": (
                "https://www2.census.gov/geo/docs/maps-data/data/baf2020/"
                f"BlockAssign_ST{fips}_{abbr}.zip"
            ),
            "filename": f"census_2020_baf_{abbr.lower()}.zip",
            "notes": (
                "2020 Census Block Assignment File ZIP used by PE block "
                "crosswalk builders for SLDU, SLDL, place, and VTD."
            ),
        }
        for abbr, fips, _state_dir in CENSUS_STATES_AND_DC
    ],
    {
        "source_id": "jct",
        "pipeline": "tax-expenditure-source-documents",
        "url": "https://www.jct.gov/publications/2024/jcx-48-24/",
        "filename": "jct_2024_tax_expenditure_report.html",
        "notes": "JCT tax expenditure report used for deduction expenditure targets.",
    },
    {
        "source_id": "cms-health-expenditures",
        "pipeline": "health-source-documents",
        "url": "https://www.cms.gov/files/document/highlights.pdf",
        "filename": "cms_nhe_highlights.pdf",
        "notes": "CMS health spending source used for national health targets.",
    },
    {
        "source_id": "ssa",
        "pipeline": "ssa-source-documents",
        "url": "https://www.ssa.gov/OACT/STATS/table4a3.html",
        "filename": "ssa_oact_table4a3.html",
        "notes": "SSA trust fund operation table used for OASDI target notes.",
    },
    {
        "source_id": "ssa",
        "pipeline": "ssa-source-documents",
        "url": "https://www.ssa.gov/OACT/FACTS/",
        "filename": "ssa_oact_facts.html",
        "notes": "SSA facts page used for benefit-type share assumptions.",
    },
    {
        "source_id": "bea",
        "pipeline": "macro-source-documents",
        "url": "https://apps.bea.gov/national/Release/TXT/NipaDataA.txt",
        "filename": "bea_nipa_annual_data_y351rc.txt",
        "notes": (
            "BEA NIPA annual flat file; series Y351RC, table T72500 line 23. "
            "Replaces PE's FRED Y351RC1A027NBEA migration reference."
        ),
    },
    {
        "source_id": "bea",
        "pipeline": "macro-source-documents",
        "url": "https://apps.bea.gov/national/Release/TXT/NipaDataA.txt",
        "filename": "bea_nipa_annual_data_w351rc.txt",
        "notes": (
            "BEA NIPA annual flat file; series W351RC, table T61100D line 26. "
            "Replaces PE's FRED W351RC0A144NBEA migration reference."
        ),
    },
    {
        "source_id": "fred",
        "pipeline": "macro-source-documents",
        "url": "https://fred.stlouisfed.org/series/BOGZ1FL192090005Q",
        "filename": "fred_bogz1fl192090005q_household_net_worth.html",
        "notes": "Federal Reserve/FRED household net worth series used by PE national calibration.",
    },
    {
        "source_id": "fred",
        "pipeline": "macro-source-documents",
        "url": "https://fred.stlouisfed.org/graph/?g=1J0CC",
        "filename": "fred_tip_income_wage_growth_graph.html",
        "notes": "FRED graph referenced by PE for W-2 tip-income wage-growth uprating.",
    },
    {
        "source_id": "cbo",
        "pipeline": "cbo-source-documents",
        "url": "https://www.cbo.gov/publication/43767",
        "filename": "cbo_refundable_tax_credits_receipts_outlays.html",
        "notes": "CBO reference on refundable credits and receipts/outlays treatment.",
    },
    {
        "source_id": "cbo",
        "pipeline": "cbo-source-documents",
        "url": "https://www.cbo.gov/system/files/2026-02/51118-2026-02-Budget-Projections.xlsx",
        "filename": "cbo_2026_02_budget_projections.xlsx",
        "notes": "CBO February 2026 budget projections used by PolicyEngine calibration parameters.",
    },
    {
        "source_id": "cbo",
        "pipeline": "cbo-source-documents",
        "url": "https://www.cbo.gov/system/files/2026-02/51312-2026-02-snap.xlsx",
        "filename": "cbo_2026_02_snap_baseline.xlsx",
        "notes": "CBO February 2026 SNAP baseline workbook used by PolicyEngine calibration parameters.",
    },
    {
        "source_id": "cbo",
        "pipeline": "cbo-source-documents",
        "url": "https://www.cbo.gov/system/files/2026-02/51313-2026-02-ssi.xlsx",
        "filename": "cbo_2026_02_ssi_baseline.xlsx",
        "notes": "CBO February 2026 SSI baseline workbook used by PolicyEngine calibration parameters.",
    },
    {
        "source_id": "cbo",
        "pipeline": "cbo-source-documents",
        "url": "https://www.cbo.gov/system/files/2026-02/51316-2026-02-unemployment.xlsx",
        "filename": "cbo_2026_02_unemployment_baseline.xlsx",
        "notes": "CBO February 2026 unemployment compensation baseline workbook used by PolicyEngine calibration parameters.",
    },
    {
        "source_id": "treasury",
        "pipeline": "tax-expenditure-source-documents",
        "url": "https://home.treasury.gov/system/files/131/Tax-Expenditures-FY2023.pdf",
        "filename": "treasury_tax_expenditures_fy2023.pdf",
        "notes": "Treasury tax expenditure report used by PolicyEngine EITC calibration parameter.",
    },
    {
        "source_id": "hhs-acf-liheap",
        "pipeline": "liheap-source-documents",
        "url": "https://liheappm.acf.gov/sites/default/files/private/congress/profiles/2023/FY2023AllStates%28National%29Profile-508Compliant.pdf",
        "filename": "acf_liheap_fy2023_all_states_national_profile.pdf",
        "notes": "ACF LIHEAP FY2023 national profile used for PE energy-subsidy household-count target.",
    },
    {
        "source_id": "hhs-acf-liheap",
        "pipeline": "liheap-source-documents",
        "url": "https://liheappm.acf.gov/sites/default/files/private/congress/profiles/2024/FY2024_AllStates%28National%29_Profile.pdf",
        "filename": "acf_liheap_fy2024_all_states_national_profile.pdf",
        "notes": "ACF LIHEAP FY2024 national profile used for PE energy-subsidy household-count target.",
    },
    {
        "source_id": "cms-medicare",
        "pipeline": "medicare-source-documents",
        "url": "https://www.cms.gov/oact/tr/2025",
        "filename": "cms_2025_medicare_trustees_report.pdf",
        "notes": "CMS 2025 Medicare Trustees Report; Table III.C3 used for Part B premium income.",
    },
    {
        "source_id": "cms-medicare",
        "pipeline": "medicare-source-documents",
        "url": "https://www.cms.gov/medicare/medicaid-coordination/about/state-payment-premiums",
        "filename": "cms_state_payment_of_medicare_premiums.html",
        "notes": "CMS State Payment of Medicare Premiums page used for State Buy-In context.",
    },
    {
        "source_id": "cms-medicare",
        "pipeline": "medicare-source-documents",
        "url": "https://www.cms.gov/files/document/statebuyinmanualfaqs.pdf",
        "filename": "cms_state_buy_in_manual_faqs.pdf",
        "notes": "CMS State Buy-In FAQ used for Part B premium payer semantics.",
    },
    {
        "source_id": "vanguard",
        "pipeline": "retirement-source-documents",
        "url": "https://corporate.vanguard.com/content/dam/corp/research/pdf/how_america_saves_report_2024.pdf",
        "filename": "vanguard_how_america_saves_2024.pdf",
        "notes": "Vanguard How America Saves 2024 used for Roth/traditional 401(k) split assumption.",
    },
    {
        "source_id": "psca",
        "pipeline": "retirement-source-documents",
        "url": "https://www.psca.org/news/psca-news/2024/12/401k-savings-and-participation-rates-rise/",
        "filename": "psca_67th_annual_401k_survey_roth_participation.html",
        "notes": "PSCA 67th Annual Survey release referenced by PE Roth participation notes.",
    },
    {
        "source_id": "dhs-ohss",
        "pipeline": "immigration-source-documents",
        "url": "https://ohss.dhs.gov/sites/default/files/2024-06/2024_0418_ohss_estimates-of-the-unauthorized-immigrant-population-residing-in-the-united-states-january-2018%25E2%2580%2593january-2022.pdf",
        "filename": "dhs_ohss_unauthorized_immigrant_population_2018_2022.pdf",
        "notes": "DHS OHSS undocumented-population estimate referenced by PE SSN-card-type target.",
    },
    {
        "source_id": "center-for-migration-studies",
        "pipeline": "immigration-source-documents",
        "url": "https://cmsny.org/publications/the-undocumented-population-in-the-united-states-increased-to-12-million-in-2023/",
        "filename": "cmsny_undocumented_population_increased_to_12_million_2023.html",
        "notes": "Center for Migration Studies undocumented-population estimate referenced by PE SSN-card-type target.",
    },
    {
        "source_id": "reuters",
        "pipeline": "immigration-source-documents",
        "url": "https://www.reuters.com/data/who-are-immigrants-who-could-be-targeted-trumps-mass-deportation-plans-2024-12-18/",
        "filename": "reuters_2024_undocumented_population_estimate.html",
        "notes": "Reuters synthesis of undocumented-population estimates referenced by PE SSN-card-type target.",
    },
    {
        "source_id": "nber",
        "pipeline": "local-geography-source-documents",
        "url": "https://data.nber.org/cbsa-csa-fips-county-crosswalk/2023/cbsa2fipsxw_2023.csv",
        "filename": "nber_cbsa_county_crosswalk_2023.csv",
        "notes": "NBER county-to-CBSA crosswalk used by PE block assignment geography helpers.",
    },
]

UK_TARGET_CONFIG_FILES = {
    "policyengine_uk_data/targets/sources.yaml",
}

UK_TARGET_URL_FILES = [
    {
        "source_id": "hmrc",
        "url": "https://assets.publishing.service.gov.uk/media/67cabb37ade26736dbf9ffe5/Collated_Tables_3_1_to_3_17_2223.ods",
        "filename": "hmrc_spi_collated_tables_3_1_to_3_17_2223.ods",
    },
    {
        "source_id": "hmrc",
        "url": "https://assets.publishing.service.gov.uk/media/67cabb7f8c1076c796a45bec/Collated_Tables_3_12_to_3_15a_2223.ods",
        "filename": "hmrc_spi_geography_tables_3_12_to_3_15a_2223.ods",
    },
    {
        "source_id": "hmrc",
        "url": "https://assets.publishing.service.gov.uk/media/687a294e312ee8a5f0806b6d/Tables_6_1_and_6_2.csv",
        "filename": "hmrc_salary_sacrifice_tables_6_1_and_6_2.csv",
    },
    {
        "source_id": "obr",
        "url": "https://obr.uk/download/november-2025-economic-and-fiscal-outlook-detailed-forecast-tables-receipts/",
        "filename": "obr_november_2025_efo_detailed_forecast_tables_receipts.xlsx",
    },
    {
        "source_id": "obr",
        "url": "https://obr.uk/download/november-2025-economic-and-fiscal-outlook-detailed-forecast-tables-expenditure/",
        "filename": "obr_november_2025_efo_detailed_forecast_tables_expenditure.xlsx",
    },
    {
        "source_id": "ons",
        "url": "https://www.ons.gov.uk/file?uri=/peoplepopulationandcommunity/populationandmigration/populationprojections/datasets/z1zippedpopulationprojectionsdatafilesuk/2022based/uk.zip",
        "filename": "ons_2022_based_uk_population_projection.zip",
    },
    {
        "source_id": "ons",
        "url": "https://www.ons.gov.uk/file?uri=/peoplepopulationandcommunity/birthsdeathsandmarriages/families/datasets/familiesandhouseholdsfamiliesandhouseholds/current/familiesandhouseholdsuk2024.xlsx",
        "filename": "ons_families_and_households_uk_2024.xlsx",
    },
    {
        "source_id": "ons",
        "url": "https://www.ons.gov.uk/file?uri=/peoplepopulationandcommunity/housing/datasets/subnationaldwellingstockbytenureestimates/current/subnationaldwellingsbytenure2024.xlsx",
        "filename": "ons_subnational_dwellings_by_tenure_2024.xlsx",
    },
    {
        "source_id": "ons",
        "url": "https://www.ons.gov.uk/economy/grossdomesticproductgdp/timeseries/haxv/ukea/data",
        "filename": "ons_haxv_savings_interest_timeseries.json",
    },
    {
        "source_id": "slc",
        "url": "https://explore-education-statistics.service.gov.uk/data-tables/permalink/6ff75517-7124-487c-cb4e-08de6eccf22d",
        "filename": "slc_student_loan_forecasts_permalink.html",
    },
    {
        "source_id": "dwp",
        "url": "https://stat-xplore.dwp.gov.uk/",
        "filename": "dwp_stat_xplore.html",
    },
    {
        "source_id": "dwp",
        "url": "https://www.gov.uk/government/statistics/benefit-cap-number-of-households-capped-to-february-2025/benefit-cap-number-of-households-capped-to-february-2025",
        "filename": "dwp_benefit_cap_february_2025.html",
    },
    {
        "source_id": "dwp",
        "url": "https://www.gov.uk/government/statistics/universal-credit-and-child-tax-credit-claimants-statistics-related-to-the-policy-to-provide-support-for-a-maximum-of-2-children-april-2024",
        "filename": "dwp_two_child_limit_april_2024.html",
    },
    {
        "source_id": "dwp",
        "url": "https://www.disabilityrightsuk.org/news/90-pip-standard-daily-living-component-recipients-would-fail-new-green-paper-test",
        "filename": "disability_rights_uk_pip_green_paper_test.html",
    },
    {
        "source_id": "hmrc",
        "url": "https://www.gov.uk/government/statistics/income-tax-summarised-accounts-statistics",
        "filename": "hmrc_income_tax_summarised_accounts_statistics.html",
    },
    {
        "source_id": "hmrc",
        "url": "https://www.gov.uk/government/statistics/income-and-tax-by-county-and-region-and-by-parliamentary-constituency",
        "filename": "hmrc_income_and_tax_by_area.html",
    },
    {
        "source_id": "uk-government",
        "url": "https://assets.publishing.service.gov.uk/media/67ce0e7c08e764d17a5d3c21/2025_SPP_Review.pdf",
        "filename": "uk_government_2025_spp_review.pdf",
    },
    {
        "source_id": "uk-government",
        "url": "https://www.gov.uk/government/publications/salary-sacrifice-reform-for-pension-contributions-effective-from-6-april-2029",
        "filename": "uk_government_salary_sacrifice_reform_2029.html",
    },
    {
        "source_id": "isc",
        "url": "https://www.isc.co.uk/research/annual-census/",
        "filename": "isc_annual_census.html",
    },
    {
        "source_id": "nts",
        "url": "https://www.gov.uk/government/statistics/national-travel-survey-2024",
        "filename": "nts_national_travel_survey_2024.html",
    },
    {
        "source_id": "ons",
        "url": "https://www.ons.gov.uk/peoplepopulationandcommunity/populationandmigration/populationestimates",
        "filename": "ons_population_estimates.html",
    },
    {
        "source_id": "ons",
        "url": "https://www.ons.gov.uk/economy/inflationandpriceindices/bulletins/privaterentandhousepricesuk/january2025",
        "filename": "ons_private_rent_and_house_prices_january_2025.html",
    },
    {
        "source_id": "ons",
        "url": "https://www.ons.gov.uk/employmentandlabourmarket/peopleinwork/earningsandworkinghours/datasets/smallareaincomeestimatesformiddlelayersuperoutputareasenglandandwales",
        "filename": "ons_small_area_income_estimates.html",
    },
    {
        "source_id": "ons",
        "url": "https://www.ons.gov.uk/peoplepopulationandcommunity/housing/datasets/privaterentalmarketsummarystatisticsinengland",
        "filename": "ons_private_rental_market_summary_statistics.html",
    },
    {
        "source_id": "ons",
        "url": "https://www.ons.gov.uk/peoplepopulationandcommunity/populationandmigration/populationprojections/datasets/z1zippedpopulationprojectionsdatafilesuk",
        "filename": "ons_uk_population_projection_dataset_page.html",
    },
    {
        "source_id": "ons",
        "url": "https://www.ons.gov.uk/peoplepopulationandcommunity/birthsdeathsandmarriages/families/datasets/familiesandhouseholdsfamiliesandhouseholds",
        "filename": "ons_families_and_households_dataset_page.html",
    },
    {
        "source_id": "ons",
        "url": "https://www.ons.gov.uk/economy/grossdomesticproductgdp/timeseries/haxv/ukea",
        "filename": "ons_haxv_savings_interest_timeseries_page.html",
    },
    {
        "source_id": "ons",
        "url": "https://www.ons.gov.uk/peoplepopulationandcommunity/housing/datasets/subnationaldwellingstockbytenureestimates",
        "filename": "ons_subnational_dwelling_stock_by_tenure_page.html",
    },
    {
        "source_id": "nrs",
        "url": "https://www.nrscotland.gov.uk/statistics-and-data/statistics/statistics-by-theme/population/population-estimates/mid-year-population-estimates",
        "filename": "nrs_mid_year_population_estimates.html",
    },
    {
        "source_id": "nrs",
        "url": "https://www.nrscotland.gov.uk/publications/vital-events-reference-tables-2024/",
        "filename": "nrs_vital_events_reference_tables_2024.html",
    },
    {
        "source_id": "scotland-census",
        "url": "https://www.scotlandscensus.gov.uk/census-results/at-a-glance/household-composition/",
        "filename": "scotland_census_household_composition.html",
    },
    {
        "source_id": "scottish-government",
        "url": "https://www.gov.scot/publications/scottish-budget-2026-2027/pages/6/",
        "filename": "scottish_budget_2026_2027_page_6.html",
    },
    {
        "source_id": "scottish-government",
        "url": "https://www.gov.scot/publications/council-tax-datasets/",
        "filename": "scottish_council_tax_datasets.html",
    },
    {
        "source_id": "voa",
        "url": "https://www.gov.uk/government/statistics/council-tax-stock-of-properties-2024",
        "filename": "voa_council_tax_stock_of_properties_2024.html",
    },
    {
        "source_id": "ons-housing",
        "url": "https://www.gov.uk/government/statistics/english-housing-survey-2023",
        "filename": "english_housing_survey_2023.html",
    },
]


def _is_source_file(path: Path) -> bool:
    if path.name.startswith("~$"):
        return False
    if path.name.endswith(".csv.gz"):
        return True
    return path.suffix.lower() in SOURCE_SUFFIXES


def _infer_us_source_id(path: Path) -> str:
    name = path.name.lower()
    if "irs_soi" in name or "soi" in name or "agi" in name or "eitc" in name:
        return "irs-soi"
    if (
        name.startswith("acs")
        or name.startswith("census")
        or name.startswith("age_")
        or name.startswith("population_")
        or "real_estate_taxes" in name
    ):
        return "census"
    if "snap" in name:
        return "usda-snap"
    if "medicaid" in name:
        return "cms-medicaid"
    if "aca" in name:
        return "cms-aca"
    if "tanf" in name:
        return "hhs-acf-tanf"
    if "cdc" in name or "birth" in name or "pregnancy" in name:
        return "cdc"
    if "np2023" in name:
        return "census-population-projections"
    if "puf_filer" in name:
        return "irs-puf"
    if "healthcare" in name:
        return "cms-health-expenditures"
    return "policyengine-us-target-source"


def _infer_uk_source_id(path: Path) -> str:
    name = path.name.lower()
    if "uc_" in name or "dfc-ni" in name:
        return "dwp"
    if "income" in name or "incomes" in name or "salary" in name or "spi_" in name:
        return "hmrc"
    if "council_tax" in name:
        return "voa"
    if "demographics" in name or "households" in name or "tenure" in name or name == "age.csv":
        return "ons"
    if "rent" in name or "lha" in name:
        return "ons-housing"
    if "constituenc" in name or "local_authorit" in name:
        return "ons-geography"
    if "nomis" in name:
        return "nomis"
    if "tax_benefit" in name:
        return "obr"
    if "capital_gains" in name:
        return "advani-summers"
    return "policyengine-uk-target-source"


def _spec(
    *,
    path: Path,
    root: Path,
    origin_project: str,
    pipeline: str,
    jurisdiction: Jurisdiction,
    source_id: str,
    notes: str,
) -> SourceArtifactSpec:
    return SourceArtifactSpec(
        slug=make_slug(origin_project, pipeline, root, path),
        path=path,
        origin_project=origin_project,
        pipeline=pipeline,
        jurisdiction=jurisdiction,
        source_id=source_id,
        source_name=source_id,
        notes=notes,
    )


def _append_spec_once(
    specs: list[SourceArtifactSpec],
    seen_slugs: set[str],
    spec: SourceArtifactSpec,
) -> None:
    if spec.slug in seen_slugs:
        return
    specs.append(spec)
    seen_slugs.add(spec.slug)


def _append_local_spec(
    specs: list[SourceArtifactSpec],
    seen_slugs: set[str],
    *,
    path: Path,
    root: Path,
    origin_project: str,
    pipeline: str,
    jurisdiction: Jurisdiction,
    source_id: str,
    notes: str,
    include_missing_local: bool,
) -> None:
    if not include_missing_local and not path.exists():
        return
    _append_spec_once(
        specs,
        seen_slugs,
        _spec(
            path=path,
            root=root,
            origin_project=origin_project,
            pipeline=pipeline,
            jurisdiction=jurisdiction,
            source_id=source_id,
            notes=notes,
        ),
    )


def _url_spec(
    *,
    origin_project: str,
    pipeline: str,
    jurisdiction: Jurisdiction,
    source_id: str,
    url: str,
    filename: str,
    notes: str,
) -> SourceArtifactSpec:
    return SourceArtifactSpec(
        slug=make_url_slug(origin_project, pipeline, filename),
        origin_project=origin_project,
        pipeline=pipeline,
        jurisdiction=jurisdiction,
        source_id=source_id,
        source_name=source_id,
        source_url=url,
        filename=filename,
        notes=notes,
    )


def pe_us_source_specs(
    pe_us_root: Path = DEFAULT_PE_US_ROOT,
    *,
    include_missing_local: bool = True,
) -> list[SourceArtifactSpec]:
    """Return public PE-US target source files available in a local checkout."""
    root = pe_us_root / "policyengine_us_data" / "storage"
    specs: list[SourceArtifactSpec] = []
    seen_slugs: set[str] = set()

    raw_inputs = root / "calibration" / "raw_inputs"
    for filename in sorted(US_RAW_INPUT_FILES):
        path = raw_inputs / filename
        _append_local_spec(
            specs,
            seen_slugs,
            path=path,
            root=pe_us_root,
            origin_project="policyengine-us-data",
            pipeline="database",
            jurisdiction=Jurisdiction.US,
            source_id=_infer_us_source_id(path),
            notes="PE-US policy_data.db source artifact",
            include_missing_local=include_missing_local,
        )
    if raw_inputs.exists():
        for path in sorted(raw_inputs.iterdir()):
            if not path.is_file() or not _is_source_file(path):
                continue
            _append_spec_once(
                specs,
                seen_slugs,
                _spec(
                    path=path,
                    root=pe_us_root,
                    origin_project="policyengine-us-data",
                    pipeline="database",
                    jurisdiction=Jurisdiction.US,
                    source_id=_infer_us_source_id(path),
                    notes="PE-US policy_data.db source artifact",
                )
            )

    calibration_targets = root / "calibration_targets"
    for filename in sorted(US_CALIBRATION_TARGET_FILES):
        path = calibration_targets / filename
        _append_local_spec(
            specs,
            seen_slugs,
            path=path,
            root=pe_us_root,
            origin_project="policyengine-us-data",
            pipeline="legacy-loss-targets",
            jurisdiction=Jurisdiction.US,
            source_id=_infer_us_source_id(path),
            notes="PE-US legacy loss/calibration target source artifact",
            include_missing_local=include_missing_local,
        )
    if calibration_targets.exists():
        for path in sorted(calibration_targets.iterdir()):
            if not path.is_file() or not _is_source_file(path):
                continue
            _append_spec_once(
                specs,
                seen_slugs,
                _spec(
                    path=path,
                    root=pe_us_root,
                    origin_project="policyengine-us-data",
                    pipeline="legacy-loss-targets",
                    jurisdiction=Jurisdiction.US,
                    source_id=_infer_us_source_id(path),
                    notes="PE-US legacy loss/calibration target source artifact",
                )
            )

    for filename in sorted(US_CALIBRATION_SUPPORT_FILES):
        path = root / filename
        _append_local_spec(
            specs,
            seen_slugs,
            path=path,
            root=pe_us_root,
            origin_project="policyengine-us-data",
            pipeline="calibration-support",
            jurisdiction=Jurisdiction.US,
            source_id=_infer_us_source_id(path),
            notes="PE-US calibration support source artifact",
            include_missing_local=include_missing_local,
        )

    long_term_root = root / "long_term_target_sources"
    for filename in sorted(US_LONG_TERM_TARGET_SOURCE_FILES):
        path = long_term_root / filename
        _append_local_spec(
            specs,
            seen_slugs,
            path=path,
            root=pe_us_root,
            origin_project="policyengine-us-data",
            pipeline="long-term-target-sources",
            jurisdiction=Jurisdiction.US,
            source_id=_infer_us_source_id(path),
            notes="PE-US long-term calibration target source artifact",
            include_missing_local=include_missing_local,
        )

    for filename in sorted(US_LONG_TERM_ROOT_SOURCE_FILES):
        path = root / filename
        _append_local_spec(
            specs,
            seen_slugs,
            path=path,
            root=pe_us_root,
            origin_project="policyengine-us-data",
            pipeline="long-term-target-sources",
            jurisdiction=Jurisdiction.US,
            source_id="ssa",
            notes="PE-US long-term calibration source artifact",
            include_missing_local=include_missing_local,
        )

    for item in US_LONG_TERM_REFERENCE_URLS:
        specs.append(
            _url_spec(
                origin_project="policyengine-us-data",
                pipeline="long-term-target-references",
                jurisdiction=Jurisdiction.US,
                source_id=item["source_id"],
                url=item["url"],
                filename=item["filename"],
                notes="PE-US long-term calibration reference source artifact",
            )
        )

    for filename in sorted(US_CALIBRATION_TARGET_ROOT_FILES):
        path = root / filename
        _append_local_spec(
            specs,
            seen_slugs,
            path=path,
            root=pe_us_root,
            origin_project="policyengine-us-data",
            pipeline="unified-calibration",
            jurisdiction=Jurisdiction.US,
            source_id=_infer_us_source_id(path),
            notes="PE-US unified calibration source artifact",
            include_missing_local=include_missing_local,
        )

    for item in US_TARGET_URL_FILES:
        specs.append(
            _url_spec(
                origin_project="policyengine-us-data",
                pipeline=item["pipeline"],
                jurisdiction=Jurisdiction.US,
                source_id=item["source_id"],
                url=item["url"],
                filename=item["filename"],
                notes=item["notes"],
            )
        )

    return specs


def pe_uk_source_specs(pe_uk_root: Path = DEFAULT_PE_UK_ROOT) -> list[SourceArtifactSpec]:
    """Return public PE-UK target source files available in a local checkout."""
    storage = pe_uk_root / "policyengine_uk_data" / "storage"
    specs: list[SourceArtifactSpec] = []

    for filename in sorted(UK_TARGET_CONFIG_FILES):
        path = pe_uk_root / filename
        if path.exists() and _is_source_file(path):
            specs.append(
                _spec(
                    path=path,
                    root=pe_uk_root,
                    origin_project="policyengine-uk-data",
                    pipeline="target-registry-config",
                    jurisdiction=Jurisdiction.UK,
                    source_id="policyengine-uk",
                    notes="PE-UK target source registry configuration",
                )
            )

    for filename in sorted(UK_STORAGE_TARGET_FILES):
        path = storage / filename
        if path.exists() and _is_source_file(path):
            specs.append(
                _spec(
                    path=path,
                    root=pe_uk_root,
                    origin_project="policyengine-uk-data",
                    pipeline="target-registry",
                    jurisdiction=Jurisdiction.UK,
                    source_id=_infer_uk_source_id(path),
                    notes="PE-UK target registry source artifact",
                )
            )

    local_area_root = pe_uk_root / "policyengine_uk_data" / "datasets" / "local_areas"
    for path in sorted(local_area_root.glob("*/targets/*")):
        if not path.is_file() or not _is_source_file(path):
            continue
        specs.append(
            _spec(
                path=path,
                root=pe_uk_root,
                origin_project="policyengine-uk-data",
                pipeline="local-area-targets",
                jurisdiction=Jurisdiction.UK,
                source_id=_infer_uk_source_id(path),
                notes="PE-UK local-area target source artifact",
            )
        )

    for item in UK_TARGET_URL_FILES:
        specs.append(
            _url_spec(
                origin_project="policyengine-uk-data",
                pipeline="target-registry-live-sources",
                jurisdiction=Jurisdiction.UK,
                source_id=item["source_id"],
                url=item["url"],
                filename=item["filename"],
                notes="PE-UK target registry live source artifact",
            )
        )

    return specs


def pe_source_specs(
    pe_us_root: Path = DEFAULT_PE_US_ROOT,
    pe_uk_root: Path = DEFAULT_PE_UK_ROOT,
    include_us: bool = True,
    include_uk: bool = True,
    include_missing_local: bool = True,
) -> list[SourceArtifactSpec]:
    """Return source files used by the PE-US and PE-UK calibration pipelines."""
    specs: list[SourceArtifactSpec] = []
    if include_us:
        specs.extend(
            pe_us_source_specs(
                pe_us_root,
                include_missing_local=include_missing_local,
            )
        )
    if include_uk and pe_uk_root.exists():
        specs.extend(pe_uk_source_specs(pe_uk_root))
    return specs


MANIFEST_COLUMNS = [
    "status",
    "origin_project",
    "jurisdiction",
    "pipeline",
    "source_id",
    "artifact_role",
    "artifact_kind",
    "artifact",
    "filename",
    "format",
    "exists_locally",
    "arch_source_status",
    "source_cell_status",
    "target_construction_status",
    "value_capture_policy",
    "notes",
]


PE_INTERMEDIATE_PIPELINES = {
    "database",
    "legacy-loss-targets",
    "unified-calibration",
}

PE_SUPPORT_PIPELINES = {
    "calibration-support",
    "long-term-target-sources",
    "target-registry",
    "target-registry-config",
    "local-area-targets",
}


def _artifact_role_for_spec(spec: SourceArtifactSpec) -> str:
    if spec.pipeline in PE_INTERMEDIATE_PIPELINES:
        return "pe_intermediate"
    if spec.pipeline in PE_SUPPORT_PIPELINES:
        return "pe_support"
    if spec.source_url:
        return "publisher_source"
    return "local_source_artifact"


@dataclass(frozen=True)
class ArchArtifactState:
    source_url: str | None
    local_path: str | None
    table_count: int
    row_count: int
    has_fetch_error: bool


def _arch_artifact_states(
    db_path: Path | None,
) -> tuple[dict[str, ArchArtifactState], str | None]:
    if db_path is None or not db_path.exists():
        return {}, None
    try:
        with sqlite3.connect(db_path) as conn:
            rows = conn.execute(
                """
                SELECT
                    a.slug,
                    a.source_url,
                    a.local_path,
                    COUNT(t.id) AS table_count,
                    COALESCE(SUM(t.row_count), 0) AS row_count,
                    MAX(CASE WHEN t.name LIKE '%.fetch_error.yaml' THEN 1 ELSE 0 END)
                        AS has_fetch_error
                FROM source_artifacts AS a
                LEFT JOIN source_tables AS t
                    ON t.artifact_id = a.id
                GROUP BY a.slug
                """
            ).fetchall()
    except sqlite3.Error as exc:
        return {}, str(exc)

    states: dict[str, ArchArtifactState] = {}
    for slug, source_url, local_path, table_count, row_count, has_fetch_error in rows:
        states[slug] = ArchArtifactState(
            source_url=source_url,
            local_path=local_path,
            table_count=int(table_count or 0),
            row_count=int(row_count or 0),
            has_fetch_error=bool(has_fetch_error),
        )
    return states, None


def _arch_source_status_for_spec(
    spec: SourceArtifactSpec,
    state: ArchArtifactState | None,
) -> str:
    if state is None:
        return "not_loaded"
    if spec.source_url is not None and state.source_url != spec.source_url:
        return "identity_mismatch"
    if spec.path is not None and state.local_path != str(spec.path):
        return "identity_mismatch"
    if state.has_fetch_error:
        return "fetch_error"
    if state.table_count == 0:
        return "fetched_unparsed"
    if state.row_count == 0:
        return "parsed_no_rows"
    return "row_parsed"


def _source_cell_status_for_arch_status(arch_source_status: str) -> str:
    if arch_source_status == "row_parsed":
        return "not_started"
    return "blocked_by_artifact_status"


def _artifact_display(spec: SourceArtifactSpec, root: Path | None) -> str:
    if spec.path is not None:
        if root is not None:
            try:
                return str(spec.path.relative_to(root))
            except ValueError:
                pass
        return str(spec.path)
    return spec.source_url or ""


def _format_for_spec(spec: SourceArtifactSpec) -> str:
    name = spec.filename or (spec.path.name if spec.path is not None else "")
    if name.endswith(".csv.gz"):
        return ".csv.gz"
    return Path(name).suffix.lower() or "url"


def pe_source_manifest_rows(
    specs: Sequence[SourceArtifactSpec],
    *,
    arch_db_path: Path | None = None,
    pe_us_root: Path | None = DEFAULT_PE_US_ROOT,
    pe_uk_root: Path | None = DEFAULT_PE_UK_ROOT,
) -> list[dict[str, str]]:
    """Return checklist rows for PE source coverage in Arch.

    The manifest is deliberately source-artifact oriented: a row is "done" only
    when Arch has ingested the exact expected artifact instance and row-parsed it
    into ``source_artifacts`` / ``source_tables`` / ``source_rows``. Fetch
    errors, identity mismatches, and empty parses are visible states, not loaded
    artifacts. Target extraction can then happen in a separate pass without
    losing rows PE omitted.
    """

    arch_states, arch_inventory_error = _arch_artifact_states(arch_db_path)
    rows: list[dict[str, str]] = []
    for spec in specs:
        root = pe_us_root if spec.origin_project == "policyengine-us-data" else pe_uk_root
        exists_locally = (
            "yes"
            if spec.path is not None and spec.path.exists()
            else "n/a"
                if spec.source_url
                else "no"
        )
        arch_source_status = (
            "inventory_error"
            if arch_inventory_error is not None
            else _arch_source_status_for_spec(
                spec,
                arch_states.get(spec.slug),
            )
        )
        loaded = arch_source_status == "row_parsed"
        source_cell_status = _source_cell_status_for_arch_status(arch_source_status)
        rows.append(
            {
                "status": "done" if loaded else "todo",
                "origin_project": spec.origin_project,
                "jurisdiction": (
                    spec.jurisdiction.value
                    if hasattr(spec.jurisdiction, "value")
                    else str(spec.jurisdiction)
                ),
                "pipeline": spec.pipeline,
                "source_id": spec.source_id,
                "artifact_role": _artifact_role_for_spec(spec),
                "artifact_kind": "url" if spec.source_url else "local_file",
                "artifact": _artifact_display(spec, root),
                "filename": spec.filename or (spec.path.name if spec.path else ""),
                "format": _format_for_spec(spec),
                "exists_locally": exists_locally,
                "arch_source_status": arch_source_status,
                "source_cell_status": source_cell_status,
                "target_construction_status": "not_ready",
                "value_capture_policy": (
                    "full source artifact; preserve all rows/sheets/cells, "
                    "including values PE omits from active calibration"
                ),
                "notes": spec.notes or "",
            }
        )
    return rows


def write_pe_source_manifest_csv(
    rows: Iterable[dict[str, str]],
    path: Path,
) -> None:
    """Write PE source manifest rows to CSV."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=MANIFEST_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def write_pe_source_manifest_markdown(
    rows: Sequence[dict[str, str]],
    path: Path,
    *,
    title: str = "PolicyEngine Source Manifest",
) -> None:
    """Write a compact Markdown checklist grouped by pipeline."""

    path.parent.mkdir(parents=True, exist_ok=True)
    total = len(rows)
    done = sum(row["status"] == "done" for row in rows)
    publisher_rows = [
        row for row in rows if row["artifact_role"] == "publisher_source"
    ]
    publisher_done = sum(row["status"] == "done" for row in publisher_rows)
    pe_intermediate_rows = [
        row
        for row in rows
        if row["artifact_role"] in {"pe_intermediate", "pe_support"}
    ]
    pe_intermediate_done = sum(row["status"] == "done" for row in pe_intermediate_rows)
    by_pipeline: dict[tuple[str, str], list[dict[str, str]]] = {}
    for row in rows:
        by_pipeline.setdefault(
            (row["origin_project"], row["pipeline"]),
            [],
        ).append(row)

    lines = [
        f"# {title}",
        "",
        "Arch should ingest the full source artifact behind each PolicyEngine "
        "calibration source, not only the active target rows PE happens to use.",
        "",
        f"Row-parsed coverage: {done}/{total} manifest artifacts parsed in Arch.",
        "",
        (
            "Publisher-source coverage: "
            f"{publisher_done}/{len(publisher_rows)} "
            "publisher/source artifacts row-parsed."
        ),
        (
            "PE intermediate/support coverage: "
            f"{pe_intermediate_done}/{len(pe_intermediate_rows)} "
            "PE-derived or support artifacts row-parsed."
        ),
        "",
        "Row-parsed does not mean source-cell-complete, selector-ready, or "
        "target-construction-ready. Source-cell and target-construction "
        "readiness are tracked separately.",
        "",
        "Columns: status, source, role, artifact, Arch status, source-cell "
        "status, target status, and notes. The corresponding CSV contains the "
        "full machine-readable manifest.",
        "",
    ]

    for (origin_project, pipeline), group in sorted(by_pipeline.items()):
        group_done = sum(row["status"] == "done" for row in group)
        lines.extend(
            [
                f"## {origin_project} / {pipeline}",
                "",
                f"{group_done}/{len(group)} row-parsed.",
                "",
                (
                    "| Status | Source | Role | Artifact | Arch status | "
                    "Source-cell status | Target status | Notes |"
                ),
                "|---|---|---|---|---|---|---|---|",
            ]
        )
        for row in group:
            checkbox = "x" if row["status"] == "done" else " "
            artifact = row["filename"] or row["artifact"]
            notes = row["notes"].replace("|", "\\|")
            lines.append(
                f"| [{checkbox}] | {row['source_id']} | {row['artifact_role']} | "
                f"`{artifact}` | {row['arch_source_status']} | "
                f"{row['source_cell_status']} | "
                f"{row['target_construction_status']} | {notes} |"
            )
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
