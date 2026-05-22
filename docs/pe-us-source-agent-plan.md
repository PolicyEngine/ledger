# PE Source Agent Plan

This is an agent work queue generated from the PE source manifest. It is inventory/scaffold oriented: agents should not claim semantic target readiness until `build-suite` passes for a package.

Manifest rows: 215
Planned items: 215
Batches: 23

## Counts

### by_artifact_role

- `pe_intermediate`: 37
- `pe_support`: 11
- `publisher_source`: 167

### by_arch_source_status

- `blocked`: 11
- `deferred`: 152
- `source_package`: 52

### by_format

- `.csv`: 34
- `.csv.gz`: 2
- `.html`: 18
- `.json`: 12
- `.pdf`: 9
- `.txt`: 6
- `.xls`: 18
- `.xlsx`: 8
- `.zip`: 108

### by_pipeline

- `aca-source-documents`: 2
- `calibration-support`: 5
- `cbo-source-documents`: 5
- `census-source-documents`: 1
- `database`: 17
- `health-source-documents`: 1
- `immigration-source-documents`: 3
- `legacy-loss-targets`: 18
- `liheap-source-documents`: 2
- `local-geography-source-documents`: 108
- `long-term-target-references`: 3
- `long-term-target-sources`: 6
- `macro-source-documents`: 4
- `medicaid-source-documents`: 1
- `medicare-source-documents`: 3
- `national-soi-workbooks`: 18
- `retirement-source-documents`: 2
- `snap-source-documents`: 2
- `soi-geography-files`: 3
- `soi-source-pages`: 3
- `ssa-source-documents`: 2
- `tanf-source-documents`: 2
- `tax-expenditure-source-documents`: 2
- `unified-calibration`: 2

### by_recommended_stage

- `blocked_or_deferred`: 163
- `existing_source_package`: 52

### by_publisher_hint

- `bea`: 3
- `federal_reserve`: 1
- `missing`: 211

## Batches

### pe-us-existing_source_package-001

Stage: `existing_source_package`
Items: 10

| Priority | Source | Publisher hint | Pipeline | File | Stage | Package |
|---:|---|---|---|---|---|---|
| 105 | cms-aca |  | aca-source-documents | `cms_full_year_effectuated_enrollment.xlsx` | existing_source_package | `cms-aca-effectuated-enrollment-2022` |
| 105 | cms-aca |  | aca-source-documents | `cms_marketplace_public_use_files.html` | existing_source_package | `cms-aca-oep-state-level` |
| 105 | cms-health-expenditures |  | health-source-documents | `national-health-expenditures-type-service-source-funds-cy-1960-2024.zip` | existing_source_package | `cms-nhe-historical-service-source` |
| 105 | center-for-migration-studies |  | immigration-source-documents | `cmsny_undocumented_population_increased_to_12_million_2023.html` | existing_source_package | `cmsny-undocumented-population-2023` |
| 105 | dhs-ohss |  | immigration-source-documents | `dhs_ohss_unauthorized_immigrant_population_2018_2022.pdf` | existing_source_package | `dhs-ohss-unauthorized-immigrant-population-2018-2022` |
| 105 | irs-soi |  | legacy-loss-targets | `agi_state.csv` | existing_source_package | `soi-historic-table-2-state-agi-2022` |
| 105 | irs-soi |  | legacy-loss-targets | `eitc.csv` | existing_source_package | `soi-table-2-5-eitc-children-2020` |
| 105 | irs-soi |  | legacy-loss-targets | `eitc_by_agi_and_children.csv` | existing_source_package | `soi-table-2-5-eitc-agi-children-2022` |
| 105 | irs-soi |  | legacy-loss-targets | `eitc_state.csv` | existing_source_package | `soi-historic-table-2-state-eitc-2022` |
| 105 | census-population-projections |  | legacy-loss-targets | `np2023_d5_mid.csv` | existing_source_package | `census-population-projections-2023` |

### pe-us-existing_source_package-002

Stage: `existing_source_package`
Items: 10

| Priority | Source | Publisher hint | Pipeline | File | Stage | Package |
|---:|---|---|---|---|---|---|
| 105 | hhs-acf-liheap |  | liheap-source-documents | `acf_liheap_fy2023_all_states_national_profile.pdf` | existing_source_package | `hhs-acf-liheap-fy2023-national-profile` |
| 105 | hhs-acf-liheap |  | liheap-source-documents | `acf_liheap_fy2024_all_states_national_profile.pdf` | existing_source_package | `hhs-acf-liheap-fy2024-national-profile` |
| 105 | ssa |  | long-term-target-sources | `SSPopJul_TR2024.csv` | existing_source_package | `ssa-population-projections-tr2024` |
| 105 | bea | bea | macro-source-documents | `bea_nipa_annual_data_ba06rc.txt` | existing_source_package | `bea-nipa-total-wages-salaries` |
| 105 | bea | bea | macro-source-documents | `bea_nipa_annual_data_w351rc.txt` | existing_source_package | `bea-nipa-pension-contributions` |
| 105 | bea | bea | macro-source-documents | `bea_nipa_annual_data_y351rc.txt` | existing_source_package | `bea-nipa-pension-contributions` |
| 105 | federal-reserve | federal_reserve | macro-source-documents | `federal_reserve_z1_20260319_b101.html` | existing_source_package | `federal-reserve-z1-household-net-worth` |
| 105 | cms-medicaid |  | medicaid-source-documents | `cms_medicaid_chip_monthly_enrollment_dataset.html` | existing_source_package | `cms-medicaid-chip-monthly-enrollment-dataset` |
| 105 | cms-medicare |  | medicare-source-documents | `cms_2025_medicare_trustees_report.pdf` | existing_source_package | `cms-medicare-trustees-report-2025-part-b-premium-income` |
| 105 | cms-medicare |  | medicare-source-documents | `cms_state_payment_of_medicare_premiums.html` | existing_source_package | `cms-medicare-state-payment-of-premiums` |

### pe-us-existing_source_package-003

Stage: `existing_source_package`
Items: 10

| Priority | Source | Publisher hint | Pipeline | File | Stage | Package |
|---:|---|---|---|---|---|---|
| 105 | irs-soi |  | national-soi-workbooks | `irs_soi_ty2021_table_1_1.xls` | existing_source_package | `soi-table-1-1` |
| 105 | irs-soi |  | national-soi-workbooks | `irs_soi_ty2021_table_1_2.xls` | existing_source_package | `soi-table-1-2` |
| 105 | irs-soi |  | national-soi-workbooks | `irs_soi_ty2021_table_1_4.xls` | existing_source_package | `soi-table-1-4` |
| 105 | irs-soi |  | national-soi-workbooks | `irs_soi_ty2021_table_2_1.xls` | existing_source_package | `soi-table-2-1` |
| 105 | irs-soi |  | national-soi-workbooks | `irs_soi_ty2021_table_2_5.xls` | existing_source_package | `soi-table-2-5` |
| 105 | irs-soi |  | national-soi-workbooks | `irs_soi_ty2021_table_4_3.xls` | existing_source_package | `soi-table-4-3` |
| 105 | irs-soi |  | national-soi-workbooks | `irs_soi_ty2022_table_1_1.xls` | existing_source_package | `soi-table-1-1` |
| 105 | irs-soi |  | national-soi-workbooks | `irs_soi_ty2022_table_1_2.xls` | existing_source_package | `soi-table-1-2` |
| 105 | irs-soi |  | national-soi-workbooks | `irs_soi_ty2022_table_1_4.xls` | existing_source_package | `soi-table-1-4` |
| 105 | irs-soi |  | national-soi-workbooks | `irs_soi_ty2022_table_2_1.xls` | existing_source_package | `soi-table-2-1` |

### pe-us-existing_source_package-004

Stage: `existing_source_package`
Items: 10

| Priority | Source | Publisher hint | Pipeline | File | Stage | Package |
|---:|---|---|---|---|---|---|
| 105 | irs-soi |  | national-soi-workbooks | `irs_soi_ty2022_table_2_5.xls` | existing_source_package | `soi-table-2-5` |
| 105 | irs-soi |  | national-soi-workbooks | `irs_soi_ty2022_table_4_3.xls` | existing_source_package | `soi-table-4-3` |
| 105 | irs-soi |  | national-soi-workbooks | `irs_soi_ty2023_table_1_1.xls` | existing_source_package | `soi-table-1-1` |
| 105 | irs-soi |  | national-soi-workbooks | `irs_soi_ty2023_table_1_2.xls` | existing_source_package | `soi-table-1-2` |
| 105 | irs-soi |  | national-soi-workbooks | `irs_soi_ty2023_table_1_4.xls` | existing_source_package | `soi-table-1-4` |
| 105 | irs-soi |  | national-soi-workbooks | `irs_soi_ty2023_table_2_1.xls` | existing_source_package | `soi-table-2-1` |
| 105 | irs-soi |  | national-soi-workbooks | `irs_soi_ty2023_table_2_5.xls` | existing_source_package | `soi-table-2-5` |
| 105 | irs-soi |  | national-soi-workbooks | `irs_soi_ty2023_table_4_3.xls` | existing_source_package | `soi-table-4-3` |
| 105 | psca |  | retirement-source-documents | `psca_67th_annual_401k_survey_roth_participation.html` | existing_source_package | `psca-67th-annual-401k-survey-roth-availability` |
| 105 | vanguard |  | retirement-source-documents | `vanguard_how_america_saves_2024.pdf` | existing_source_package | `vanguard-how-america-saves-2024-roth-participation` |

### pe-us-existing_source_package-005

Stage: `existing_source_package`
Items: 10

| Priority | Source | Publisher hint | Pipeline | File | Stage | Package |
|---:|---|---|---|---|---|---|
| 105 | usda-snap |  | snap-source-documents | `usda_snap_fy69_to_current.zip` | existing_source_package | `usda-snap-fy69-to-current` |
| 105 | usda-snap |  | snap-source-documents | `usda_snap_program_data_page.html` | existing_source_package | `usda-snap-fy69-to-current` |
| 105 | irs-soi |  | soi-geography-files | `irs_soi_ty2022_in54us.xlsx` | existing_source_package | `soi-state-2022` |
| 105 | irs-soi |  | soi-geography-files | `irs_soi_ty2022_in55cmcsv.csv` | existing_source_package | `soi-historic-table-2` |
| 105 | irs-soi |  | soi-geography-files | `irs_soi_ty2022_incd.csv` | existing_source_package | `soi-congressional-district-2022` |
| 105 | irs-soi |  | soi-source-pages | `irs_soi_individual_statistical_tables_by_size_of_agi.html` | existing_source_package | `irs-soi-individual-statistical-tables-by-size-of-agi` |
| 105 | irs-soi |  | soi-source-pages | `irs_soi_ira_accumulation_distribution_tables.html` | existing_source_package | `irs-soi-ira-accumulation-distribution-tables` |
| 105 | irs-soi |  | soi-source-pages | `irs_soi_w2_statistics.html` | existing_source_package | `soi-w2-statistics-2020` |
| 105 | hhs-acf-tanf |  | tanf-source-documents | `acf_tanf_caseload_data_2024.html` | existing_source_package | `hhs-acf-tanf-caseload-2024` |
| 105 | hhs-acf-tanf |  | tanf-source-documents | `acf_tanf_financial_data_fy2024.html` | existing_source_package | `hhs-acf-tanf-financial-2024` |

### pe-us-existing_source_package-006

Stage: `existing_source_package`
Items: 2

| Priority | Source | Publisher hint | Pipeline | File | Stage | Package |
|---:|---|---|---|---|---|---|
| 105 | jct |  | tax-expenditure-source-documents | `jct_x_48_24.pdf` | existing_source_package | `jct-tax-expenditures-2024-mortgage-interest-deduction` |
| 105 | treasury |  | tax-expenditure-source-documents | `treasury_tax_expenditures_fy2023.pdf` | existing_source_package | `treasury-tax-expenditures-fy2023-eitc-outlays` |

### pe-us-blocked_or_deferred-001

Stage: `blocked_or_deferred`
Items: 10

| Priority | Source | Publisher hint | Pipeline | File | Stage | Package |
|---:|---|---|---|---|---|---|
| 10 | policyengine-us-target-source |  | calibration-support | `block_cd_distributions.csv.gz` | blocked_or_deferred | `policyengine-us-target-source-block-cd-distributions` |
| 10 | policyengine-us-target-source |  | calibration-support | `block_crosswalk.csv.gz` | blocked_or_deferred | `policyengine-us-target-source-block-crosswalk` |
| 10 | policyengine-us-target-source |  | calibration-support | `county_cd_distributions.csv` | blocked_or_deferred | `policyengine-us-target-source-county-cd-distributions` |
| 10 | policyengine-us-target-source |  | calibration-support | `district_mapping.csv` | blocked_or_deferred | `policyengine-us-target-source-district-mapping` |
| 10 | policyengine-us-target-source |  | calibration-support | `national_and_district_rents_2023.csv` | blocked_or_deferred | `policyengine-us-target-source-national-and-district-rents-2023` |
| 10 | cbo |  | cbo-source-documents | `cbo_2026_02_budget_projections.xlsx` | blocked_or_deferred | `cbo-2026-02-budget-projections` |
| 10 | cbo |  | cbo-source-documents | `cbo_2026_02_snap_baseline.xlsx` | blocked_or_deferred | `cbo-2026-02-snap-baseline` |
| 10 | cbo |  | cbo-source-documents | `cbo_2026_02_ssi_baseline.xlsx` | blocked_or_deferred | `cbo-2026-02-ssi-baseline` |
| 10 | cbo |  | cbo-source-documents | `cbo_2026_02_unemployment_baseline.xlsx` | blocked_or_deferred | `cbo-2026-02-unemployment-baseline` |
| 10 | cbo |  | cbo-source-documents | `cbo_refundable_tax_credits_receipts_outlays.html` | blocked_or_deferred | `cbo-refundable-tax-credits-receipts-outlays` |

### pe-us-blocked_or_deferred-002

Stage: `blocked_or_deferred`
Items: 10

| Priority | Source | Publisher hint | Pipeline | File | Stage | Package |
|---:|---|---|---|---|---|---|
| 10 | census |  | census-source-documents | `census_national_county_2020.txt` | blocked_or_deferred | `census-national-county-2020` |
| 10 | census |  | database | `acs5_congressional_districts_2024.json` | blocked_or_deferred | `census-acs5-congressional-districts-2024` |
| 10 | census |  | database | `acs_S0101_district_2024.json` | blocked_or_deferred | `census-acs-s0101-district-2024` |
| 10 | census |  | database | `acs_S0101_national_2024.json` | blocked_or_deferred | `census-acs-s0101-national-2024` |
| 10 | census |  | database | `acs_S0101_state_2024.json` | blocked_or_deferred | `census-acs-s0101-state-2024` |
| 10 | census |  | database | `acs_S2201_district_2024.json` | blocked_or_deferred | `census-acs-s2201-district-2024` |
| 10 | cdc |  | database | `cdc_vsrr_births_2023.json` | blocked_or_deferred | `cdc-vsrr-births-2023` |
| 10 | cdc |  | database | `cdc_vsrr_births_2024.json` | blocked_or_deferred | `cdc-vsrr-births-2024` |
| 10 | census |  | database | `census_b01001_female_15_44_2023.json` | blocked_or_deferred | `census-b01001-female-15-44-2023` |
| 10 | census |  | database | `census_docs_2024.json` | blocked_or_deferred | `census-docs-2024` |

### pe-us-blocked_or_deferred-003

Stage: `blocked_or_deferred`
Items: 10

| Priority | Source | Publisher hint | Pipeline | File | Stage | Package |
|---:|---|---|---|---|---|---|
| 10 | census |  | database | `census_stc_individual_income_tax_2024.json` | blocked_or_deferred | `census-stc-individual-income-tax-2024` |
| 10 | census |  | database | `census_stc_t40_individual_income_tax_2023.json` | blocked_or_deferred | `census-stc-t40-individual-income-tax-2023` |
| 10 | irs-soi |  | database | `irs_soi_22in55cmcsv.csv` | blocked_or_deferred | `irs-soi-22in55cmcsv` |
| 10 | irs-soi |  | database | `irs_soi_22incd.csv` | blocked_or_deferred | `irs-soi-22incd` |
| 10 | cms-medicaid |  | database | `medicaid_enrollment_2024.csv` | blocked_or_deferred | `cms-medicaid-medicaid-enrollment-2024` |
| 10 | usda-snap |  | database | `snap_fy69tocurrent.zip` | blocked_or_deferred | `usda-snap-snap-fy69tocurrent` |
| 10 | hhs-acf-tanf |  | database | `tanf_caseload_2024.xlsx` | blocked_or_deferred | `hhs-acf-tanf-tanf-caseload-2024` |
| 10 | hhs-acf-tanf |  | database | `tanf_financial_2024.xlsx` | blocked_or_deferred | `hhs-acf-tanf-tanf-financial-2024` |
| 10 | reuters |  | immigration-source-documents | `reuters_2024_undocumented_population_estimate.html` | blocked_or_deferred | `reuters-2024-undocumented-population-estimate` |
| 10 | cms-aca |  | legacy-loss-targets | `aca_marketplace_state_metal_selection_2024.csv` | blocked_or_deferred | `cms-aca-aca-marketplace-state-metal-selection-2024` |

### pe-us-blocked_or_deferred-004

Stage: `blocked_or_deferred`
Items: 10

| Priority | Source | Publisher hint | Pipeline | File | Stage | Package |
|---:|---|---|---|---|---|---|
| 10 | cms-aca |  | legacy-loss-targets | `aca_spending_and_enrollment_2024.csv` | blocked_or_deferred | `cms-aca-aca-spending-and-enrollment-2024` |
| 10 | cms-aca |  | legacy-loss-targets | `aca_spending_and_enrollment_2025.csv` | blocked_or_deferred | `cms-aca-aca-spending-and-enrollment-2025` |
| 10 | census |  | legacy-loss-targets | `age_state.csv` | blocked_or_deferred | `census-age-state` |
| 10 | cms-health-expenditures |  | legacy-loss-targets | `healthcare_spending.csv` | blocked_or_deferred | `cms-health-expenditures-healthcare-spending` |
| 10 | cms-medicaid |  | legacy-loss-targets | `medicaid_enrollment_2024.csv` | blocked_or_deferred | `cms-medicaid-medicaid-enrollment-2024` |
| 10 | cms-medicaid |  | legacy-loss-targets | `medicaid_enrollment_2025.csv` | blocked_or_deferred | `cms-medicaid-medicaid-enrollment-2025` |
| 10 | census |  | legacy-loss-targets | `population_by_state.csv` | blocked_or_deferred | `census-population-by-state` |
| 10 | irs-puf |  | legacy-loss-targets | `puf_filer_demographic_cell_shares_2015.csv` | blocked_or_deferred | `irs-puf-puf-filer-demographic-cell-shares-2015` |
| 10 | census |  | legacy-loss-targets | `real_estate_taxes_by_state_acs.csv` | blocked_or_deferred | `census-real-estate-taxes-by-state-acs` |
| 10 | usda-snap |  | legacy-loss-targets | `snap_state.csv` | blocked_or_deferred | `usda-snap-snap-state` |

### pe-us-blocked_or_deferred-005

Stage: `blocked_or_deferred`
Items: 10

| Priority | Source | Publisher hint | Pipeline | File | Stage | Package |
|---:|---|---|---|---|---|---|
| 10 | irs-soi |  | legacy-loss-targets | `soi_targets.csv` | blocked_or_deferred | `irs-soi-soi-targets` |
| 10 | irs-soi |  | legacy-loss-targets | `spm_threshold_agi.csv` | blocked_or_deferred | `irs-soi-spm-threshold-agi` |
| 10 | census |  | local-geography-source-documents | `census_116th_congressional_district_bef.zip` | blocked_or_deferred | `census-116th-congressional-district-bef` |
| 10 | census |  | local-geography-source-documents | `census_118th_congressional_district_bef.zip` | blocked_or_deferred | `census-118th-congressional-district-bef` |
| 10 | census |  | local-geography-source-documents | `census_119th_congressional_district_bef.zip` | blocked_or_deferred | `census-119th-congressional-district-bef` |
| 10 | census |  | local-geography-source-documents | `census_2020_baf_ak.zip` | blocked_or_deferred | `census-2020-baf-ak` |
| 10 | census |  | local-geography-source-documents | `census_2020_baf_al.zip` | blocked_or_deferred | `census-2020-baf-al` |
| 10 | census |  | local-geography-source-documents | `census_2020_baf_ar.zip` | blocked_or_deferred | `census-2020-baf-ar` |
| 10 | census |  | local-geography-source-documents | `census_2020_baf_az.zip` | blocked_or_deferred | `census-2020-baf-az` |
| 10 | census |  | local-geography-source-documents | `census_2020_baf_ca.zip` | blocked_or_deferred | `census-2020-baf-ca` |

### pe-us-blocked_or_deferred-006

Stage: `blocked_or_deferred`
Items: 10

| Priority | Source | Publisher hint | Pipeline | File | Stage | Package |
|---:|---|---|---|---|---|---|
| 10 | census |  | local-geography-source-documents | `census_2020_baf_co.zip` | blocked_or_deferred | `census-2020-baf-co` |
| 10 | census |  | local-geography-source-documents | `census_2020_baf_ct.zip` | blocked_or_deferred | `census-2020-baf-ct` |
| 10 | census |  | local-geography-source-documents | `census_2020_baf_dc.zip` | blocked_or_deferred | `census-2020-baf-dc` |
| 10 | census |  | local-geography-source-documents | `census_2020_baf_de.zip` | blocked_or_deferred | `census-2020-baf-de` |
| 10 | census |  | local-geography-source-documents | `census_2020_baf_fl.zip` | blocked_or_deferred | `census-2020-baf-fl` |
| 10 | census |  | local-geography-source-documents | `census_2020_baf_ga.zip` | blocked_or_deferred | `census-2020-baf-ga` |
| 10 | census |  | local-geography-source-documents | `census_2020_baf_hi.zip` | blocked_or_deferred | `census-2020-baf-hi` |
| 10 | census |  | local-geography-source-documents | `census_2020_baf_ia.zip` | blocked_or_deferred | `census-2020-baf-ia` |
| 10 | census |  | local-geography-source-documents | `census_2020_baf_id.zip` | blocked_or_deferred | `census-2020-baf-id` |
| 10 | census |  | local-geography-source-documents | `census_2020_baf_il.zip` | blocked_or_deferred | `census-2020-baf-il` |

### pe-us-blocked_or_deferred-007

Stage: `blocked_or_deferred`
Items: 10

| Priority | Source | Publisher hint | Pipeline | File | Stage | Package |
|---:|---|---|---|---|---|---|
| 10 | census |  | local-geography-source-documents | `census_2020_baf_in.zip` | blocked_or_deferred | `census-2020-baf-in` |
| 10 | census |  | local-geography-source-documents | `census_2020_baf_ks.zip` | blocked_or_deferred | `census-2020-baf-ks` |
| 10 | census |  | local-geography-source-documents | `census_2020_baf_ky.zip` | blocked_or_deferred | `census-2020-baf-ky` |
| 10 | census |  | local-geography-source-documents | `census_2020_baf_la.zip` | blocked_or_deferred | `census-2020-baf-la` |
| 10 | census |  | local-geography-source-documents | `census_2020_baf_ma.zip` | blocked_or_deferred | `census-2020-baf-ma` |
| 10 | census |  | local-geography-source-documents | `census_2020_baf_md.zip` | blocked_or_deferred | `census-2020-baf-md` |
| 10 | census |  | local-geography-source-documents | `census_2020_baf_me.zip` | blocked_or_deferred | `census-2020-baf-me` |
| 10 | census |  | local-geography-source-documents | `census_2020_baf_mi.zip` | blocked_or_deferred | `census-2020-baf-mi` |
| 10 | census |  | local-geography-source-documents | `census_2020_baf_mn.zip` | blocked_or_deferred | `census-2020-baf-mn` |
| 10 | census |  | local-geography-source-documents | `census_2020_baf_mo.zip` | blocked_or_deferred | `census-2020-baf-mo` |

### pe-us-blocked_or_deferred-008

Stage: `blocked_or_deferred`
Items: 10

| Priority | Source | Publisher hint | Pipeline | File | Stage | Package |
|---:|---|---|---|---|---|---|
| 10 | census |  | local-geography-source-documents | `census_2020_baf_ms.zip` | blocked_or_deferred | `census-2020-baf-ms` |
| 10 | census |  | local-geography-source-documents | `census_2020_baf_mt.zip` | blocked_or_deferred | `census-2020-baf-mt` |
| 10 | census |  | local-geography-source-documents | `census_2020_baf_nc.zip` | blocked_or_deferred | `census-2020-baf-nc` |
| 10 | census |  | local-geography-source-documents | `census_2020_baf_nd.zip` | blocked_or_deferred | `census-2020-baf-nd` |
| 10 | census |  | local-geography-source-documents | `census_2020_baf_ne.zip` | blocked_or_deferred | `census-2020-baf-ne` |
| 10 | census |  | local-geography-source-documents | `census_2020_baf_nh.zip` | blocked_or_deferred | `census-2020-baf-nh` |
| 10 | census |  | local-geography-source-documents | `census_2020_baf_nj.zip` | blocked_or_deferred | `census-2020-baf-nj` |
| 10 | census |  | local-geography-source-documents | `census_2020_baf_nm.zip` | blocked_or_deferred | `census-2020-baf-nm` |
| 10 | census |  | local-geography-source-documents | `census_2020_baf_nv.zip` | blocked_or_deferred | `census-2020-baf-nv` |
| 10 | census |  | local-geography-source-documents | `census_2020_baf_ny.zip` | blocked_or_deferred | `census-2020-baf-ny` |

### pe-us-blocked_or_deferred-009

Stage: `blocked_or_deferred`
Items: 10

| Priority | Source | Publisher hint | Pipeline | File | Stage | Package |
|---:|---|---|---|---|---|---|
| 10 | census |  | local-geography-source-documents | `census_2020_baf_oh.zip` | blocked_or_deferred | `census-2020-baf-oh` |
| 10 | census |  | local-geography-source-documents | `census_2020_baf_ok.zip` | blocked_or_deferred | `census-2020-baf-ok` |
| 10 | census |  | local-geography-source-documents | `census_2020_baf_or.zip` | blocked_or_deferred | `census-2020-baf-or` |
| 10 | census |  | local-geography-source-documents | `census_2020_baf_pa.zip` | blocked_or_deferred | `census-2020-baf-pa` |
| 10 | census |  | local-geography-source-documents | `census_2020_baf_ri.zip` | blocked_or_deferred | `census-2020-baf-ri` |
| 10 | census |  | local-geography-source-documents | `census_2020_baf_sc.zip` | blocked_or_deferred | `census-2020-baf-sc` |
| 10 | census |  | local-geography-source-documents | `census_2020_baf_sd.zip` | blocked_or_deferred | `census-2020-baf-sd` |
| 10 | census |  | local-geography-source-documents | `census_2020_baf_tn.zip` | blocked_or_deferred | `census-2020-baf-tn` |
| 10 | census |  | local-geography-source-documents | `census_2020_baf_tx.zip` | blocked_or_deferred | `census-2020-baf-tx` |
| 10 | census |  | local-geography-source-documents | `census_2020_baf_ut.zip` | blocked_or_deferred | `census-2020-baf-ut` |

### pe-us-blocked_or_deferred-010

Stage: `blocked_or_deferred`
Items: 10

| Priority | Source | Publisher hint | Pipeline | File | Stage | Package |
|---:|---|---|---|---|---|---|
| 10 | census |  | local-geography-source-documents | `census_2020_baf_va.zip` | blocked_or_deferred | `census-2020-baf-va` |
| 10 | census |  | local-geography-source-documents | `census_2020_baf_vt.zip` | blocked_or_deferred | `census-2020-baf-vt` |
| 10 | census |  | local-geography-source-documents | `census_2020_baf_wa.zip` | blocked_or_deferred | `census-2020-baf-wa` |
| 10 | census |  | local-geography-source-documents | `census_2020_baf_wi.zip` | blocked_or_deferred | `census-2020-baf-wi` |
| 10 | census |  | local-geography-source-documents | `census_2020_baf_wv.zip` | blocked_or_deferred | `census-2020-baf-wv` |
| 10 | census |  | local-geography-source-documents | `census_2020_baf_wy.zip` | blocked_or_deferred | `census-2020-baf-wy` |
| 10 | census |  | local-geography-source-documents | `census_2020_pl_94_171_ak.zip` | blocked_or_deferred | `census-2020-pl-94-171-ak` |
| 10 | census |  | local-geography-source-documents | `census_2020_pl_94_171_al.zip` | blocked_or_deferred | `census-2020-pl-94-171-al` |
| 10 | census |  | local-geography-source-documents | `census_2020_pl_94_171_ar.zip` | blocked_or_deferred | `census-2020-pl-94-171-ar` |
| 10 | census |  | local-geography-source-documents | `census_2020_pl_94_171_az.zip` | blocked_or_deferred | `census-2020-pl-94-171-az` |

### pe-us-blocked_or_deferred-011

Stage: `blocked_or_deferred`
Items: 10

| Priority | Source | Publisher hint | Pipeline | File | Stage | Package |
|---:|---|---|---|---|---|---|
| 10 | census |  | local-geography-source-documents | `census_2020_pl_94_171_ca.zip` | blocked_or_deferred | `census-2020-pl-94-171-ca` |
| 10 | census |  | local-geography-source-documents | `census_2020_pl_94_171_co.zip` | blocked_or_deferred | `census-2020-pl-94-171-co` |
| 10 | census |  | local-geography-source-documents | `census_2020_pl_94_171_ct.zip` | blocked_or_deferred | `census-2020-pl-94-171-ct` |
| 10 | census |  | local-geography-source-documents | `census_2020_pl_94_171_dc.zip` | blocked_or_deferred | `census-2020-pl-94-171-dc` |
| 10 | census |  | local-geography-source-documents | `census_2020_pl_94_171_de.zip` | blocked_or_deferred | `census-2020-pl-94-171-de` |
| 10 | census |  | local-geography-source-documents | `census_2020_pl_94_171_fl.zip` | blocked_or_deferred | `census-2020-pl-94-171-fl` |
| 10 | census |  | local-geography-source-documents | `census_2020_pl_94_171_ga.zip` | blocked_or_deferred | `census-2020-pl-94-171-ga` |
| 10 | census |  | local-geography-source-documents | `census_2020_pl_94_171_hi.zip` | blocked_or_deferred | `census-2020-pl-94-171-hi` |
| 10 | census |  | local-geography-source-documents | `census_2020_pl_94_171_ia.zip` | blocked_or_deferred | `census-2020-pl-94-171-ia` |
| 10 | census |  | local-geography-source-documents | `census_2020_pl_94_171_id.zip` | blocked_or_deferred | `census-2020-pl-94-171-id` |

### pe-us-blocked_or_deferred-012

Stage: `blocked_or_deferred`
Items: 10

| Priority | Source | Publisher hint | Pipeline | File | Stage | Package |
|---:|---|---|---|---|---|---|
| 10 | census |  | local-geography-source-documents | `census_2020_pl_94_171_il.zip` | blocked_or_deferred | `census-2020-pl-94-171-il` |
| 10 | census |  | local-geography-source-documents | `census_2020_pl_94_171_in.zip` | blocked_or_deferred | `census-2020-pl-94-171-in` |
| 10 | census |  | local-geography-source-documents | `census_2020_pl_94_171_ks.zip` | blocked_or_deferred | `census-2020-pl-94-171-ks` |
| 10 | census |  | local-geography-source-documents | `census_2020_pl_94_171_ky.zip` | blocked_or_deferred | `census-2020-pl-94-171-ky` |
| 10 | census |  | local-geography-source-documents | `census_2020_pl_94_171_la.zip` | blocked_or_deferred | `census-2020-pl-94-171-la` |
| 10 | census |  | local-geography-source-documents | `census_2020_pl_94_171_ma.zip` | blocked_or_deferred | `census-2020-pl-94-171-ma` |
| 10 | census |  | local-geography-source-documents | `census_2020_pl_94_171_md.zip` | blocked_or_deferred | `census-2020-pl-94-171-md` |
| 10 | census |  | local-geography-source-documents | `census_2020_pl_94_171_me.zip` | blocked_or_deferred | `census-2020-pl-94-171-me` |
| 10 | census |  | local-geography-source-documents | `census_2020_pl_94_171_mi.zip` | blocked_or_deferred | `census-2020-pl-94-171-mi` |
| 10 | census |  | local-geography-source-documents | `census_2020_pl_94_171_mn.zip` | blocked_or_deferred | `census-2020-pl-94-171-mn` |

### pe-us-blocked_or_deferred-013

Stage: `blocked_or_deferred`
Items: 10

| Priority | Source | Publisher hint | Pipeline | File | Stage | Package |
|---:|---|---|---|---|---|---|
| 10 | census |  | local-geography-source-documents | `census_2020_pl_94_171_mo.zip` | blocked_or_deferred | `census-2020-pl-94-171-mo` |
| 10 | census |  | local-geography-source-documents | `census_2020_pl_94_171_ms.zip` | blocked_or_deferred | `census-2020-pl-94-171-ms` |
| 10 | census |  | local-geography-source-documents | `census_2020_pl_94_171_mt.zip` | blocked_or_deferred | `census-2020-pl-94-171-mt` |
| 10 | census |  | local-geography-source-documents | `census_2020_pl_94_171_nc.zip` | blocked_or_deferred | `census-2020-pl-94-171-nc` |
| 10 | census |  | local-geography-source-documents | `census_2020_pl_94_171_nd.zip` | blocked_or_deferred | `census-2020-pl-94-171-nd` |
| 10 | census |  | local-geography-source-documents | `census_2020_pl_94_171_ne.zip` | blocked_or_deferred | `census-2020-pl-94-171-ne` |
| 10 | census |  | local-geography-source-documents | `census_2020_pl_94_171_nh.zip` | blocked_or_deferred | `census-2020-pl-94-171-nh` |
| 10 | census |  | local-geography-source-documents | `census_2020_pl_94_171_nj.zip` | blocked_or_deferred | `census-2020-pl-94-171-nj` |
| 10 | census |  | local-geography-source-documents | `census_2020_pl_94_171_nm.zip` | blocked_or_deferred | `census-2020-pl-94-171-nm` |
| 10 | census |  | local-geography-source-documents | `census_2020_pl_94_171_nv.zip` | blocked_or_deferred | `census-2020-pl-94-171-nv` |

### pe-us-blocked_or_deferred-014

Stage: `blocked_or_deferred`
Items: 10

| Priority | Source | Publisher hint | Pipeline | File | Stage | Package |
|---:|---|---|---|---|---|---|
| 10 | census |  | local-geography-source-documents | `census_2020_pl_94_171_ny.zip` | blocked_or_deferred | `census-2020-pl-94-171-ny` |
| 10 | census |  | local-geography-source-documents | `census_2020_pl_94_171_oh.zip` | blocked_or_deferred | `census-2020-pl-94-171-oh` |
| 10 | census |  | local-geography-source-documents | `census_2020_pl_94_171_ok.zip` | blocked_or_deferred | `census-2020-pl-94-171-ok` |
| 10 | census |  | local-geography-source-documents | `census_2020_pl_94_171_or.zip` | blocked_or_deferred | `census-2020-pl-94-171-or` |
| 10 | census |  | local-geography-source-documents | `census_2020_pl_94_171_pa.zip` | blocked_or_deferred | `census-2020-pl-94-171-pa` |
| 10 | census |  | local-geography-source-documents | `census_2020_pl_94_171_ri.zip` | blocked_or_deferred | `census-2020-pl-94-171-ri` |
| 10 | census |  | local-geography-source-documents | `census_2020_pl_94_171_sc.zip` | blocked_or_deferred | `census-2020-pl-94-171-sc` |
| 10 | census |  | local-geography-source-documents | `census_2020_pl_94_171_sd.zip` | blocked_or_deferred | `census-2020-pl-94-171-sd` |
| 10 | census |  | local-geography-source-documents | `census_2020_pl_94_171_tn.zip` | blocked_or_deferred | `census-2020-pl-94-171-tn` |
| 10 | census |  | local-geography-source-documents | `census_2020_pl_94_171_tx.zip` | blocked_or_deferred | `census-2020-pl-94-171-tx` |

### pe-us-blocked_or_deferred-015

Stage: `blocked_or_deferred`
Items: 10

| Priority | Source | Publisher hint | Pipeline | File | Stage | Package |
|---:|---|---|---|---|---|---|
| 10 | census |  | local-geography-source-documents | `census_2020_pl_94_171_ut.zip` | blocked_or_deferred | `census-2020-pl-94-171-ut` |
| 10 | census |  | local-geography-source-documents | `census_2020_pl_94_171_va.zip` | blocked_or_deferred | `census-2020-pl-94-171-va` |
| 10 | census |  | local-geography-source-documents | `census_2020_pl_94_171_vt.zip` | blocked_or_deferred | `census-2020-pl-94-171-vt` |
| 10 | census |  | local-geography-source-documents | `census_2020_pl_94_171_wa.zip` | blocked_or_deferred | `census-2020-pl-94-171-wa` |
| 10 | census |  | local-geography-source-documents | `census_2020_pl_94_171_wi.zip` | blocked_or_deferred | `census-2020-pl-94-171-wi` |
| 10 | census |  | local-geography-source-documents | `census_2020_pl_94_171_wv.zip` | blocked_or_deferred | `census-2020-pl-94-171-wv` |
| 10 | census |  | local-geography-source-documents | `census_2020_pl_94_171_wy.zip` | blocked_or_deferred | `census-2020-pl-94-171-wy` |
| 10 | census |  | local-geography-source-documents | `census_tract_2020_to_puma_2020.txt` | blocked_or_deferred | `census-tract-2020-to-puma-2020` |
| 10 | census |  | local-geography-source-documents | `census_zcta2020_to_block2020_national.txt` | blocked_or_deferred | `census-zcta2020-to-block2020-national` |
| 10 | nber |  | local-geography-source-documents | `nber_cbsa_county_crosswalk_2023.csv` | blocked_or_deferred | `nber-cbsa-county-crosswalk-2023` |

### pe-us-blocked_or_deferred-016

Stage: `blocked_or_deferred`
Items: 10

| Priority | Source | Publisher hint | Pipeline | File | Stage | Package |
|---:|---|---|---|---|---|---|
| 10 | ssa |  | long-term-target-references | `ssa_2025_trustees_report_index.html` | blocked_or_deferred | `ssa-2025-trustees-report-index` |
| 10 | ssa |  | long-term-target-references | `ssa_oact_wyden_2025_08_05.pdf` | blocked_or_deferred | `ssa-oact-wyden-2025-08-05` |
| 10 | ssa |  | long-term-target-references | `ssa_solvencey_provision_table_run133.html` | blocked_or_deferred | `ssa-solvencey-provision-table-run133` |
| 10 | policyengine-us-target-source |  | long-term-target-sources | `oact_2025_08_05_provisional.csv` | blocked_or_deferred | `policyengine-us-target-source-oact-2025-08-05-provisional` |
| 10 | policyengine-us-target-source |  | long-term-target-sources | `oasdi_oact_20250805_nominal_delta.csv` | blocked_or_deferred | `policyengine-us-target-source-oasdi-oact-20250805-nominal-delta` |
| 10 | ssa |  | long-term-target-sources | `social_security_aux.csv` | blocked_or_deferred | `ssa-social-security-aux` |
| 10 | policyengine-us-target-source |  | long-term-target-sources | `sources.json` | blocked_or_deferred | `policyengine-us-target-source-sources` |
| 10 | policyengine-us-target-source |  | long-term-target-sources | `trustees_2025_current_law.csv` | blocked_or_deferred | `policyengine-us-target-source-trustees-2025-current-law` |
| 10 | cms-medicare |  | medicare-source-documents | `cms_state_buy_in_manual_faqs.pdf` | blocked_or_deferred | `cms-medicare-cms-state-buy-in-manual-faqs` |
| 10 | ssa |  | ssa-source-documents | `ssa_oact_facts.html` | blocked_or_deferred | `ssa-oact-facts` |

### pe-us-blocked_or_deferred-017

Stage: `blocked_or_deferred`
Items: 3

| Priority | Source | Publisher hint | Pipeline | File | Stage | Package |
|---:|---|---|---|---|---|---|
| 10 | ssa |  | ssa-source-documents | `ssa_oact_table4a3.html` | blocked_or_deferred | `ssa-oact-table4a3` |
| 10 | cms-aca |  | unified-calibration | `aca_ptc_multipliers_2022_2024.csv` | blocked_or_deferred | `cms-aca-aca-ptc-multipliers-2022-2024` |
| 10 | cms-aca |  | unified-calibration | `aca_ptc_multipliers_2022_2025.csv` | blocked_or_deferred | `cms-aca-aca-ptc-multipliers-2022-2025` |
