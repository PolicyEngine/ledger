"""Tests for merged Ledger consumer bundles."""

from __future__ import annotations

import json

from ledger.bundle import build_bundle, build_bundle_coverage
from ledger.harness import main as harness_main


def _load_jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def test_build_bundle_writes_merged_consumer_contract(tmp_path):
    output_dir = tmp_path / "bundle"

    report = build_bundle(output_dir, year=2023)
    summary = json.loads((output_dir / "reports" / "build_bundle.json").read_text())
    rows = _load_jsonl(output_dir / "consumer_facts.jsonl")
    source_packages = json.loads((output_dir / "source_packages.json").read_text())
    coverage = json.loads((output_dir / "coverage.json").read_text())

    assert report.valid
    assert summary["valid"]
    assert summary["counts"] == {
        "aggregate_duplicate_key_count": 0,
        "entity_count": 7,
        "error_count": 0,
        "fact_count": 36895,
        "geography_count": 483,
        "period_count": 10,
        "semantic_duplicate_key_count": 12,
        "skipped_source_count": 9,
        "source_count": 16,
        "source_package_count": 43,
        "warning_count": 1,
    }
    assert len(rows) == 36895
    assert rows[0]["aggregate_fact_key"].startswith("ledger.aggregate_fact.v2:")
    assert rows[0]["semantic_fact_key"].startswith("ledger.semantic_fact.v2:")
    assert source_packages["source_package_count"] == 43
    assert source_packages["skipped_source_count"] == 9
    assert sorted(item["source"] for item in source_packages["skipped_sources"]) == [
        "census-acs-s0101-congressional-district-age-2024",
        "census-acs-s0101-national-age-2024",
        "census-acs-s0101-state-age-2024",
        "census-acs-s2201-congressional-district-snap-2024",
        "cms-aca-effectuated-enrollment-2022",
        "cms-aca-oep-state-level",
        "cms-aca-oep-state-level-2022",
        "cms-aca-oep-state-level-2025",
        "jct-tax-expenditures-2024",
    ]
    assert coverage["fact_count"] == 36895
    assert coverage["counts"]["by_source"] == {
        "bea": 445,
        "cbo": 7,
        "census_acs": 468,
        "census_pep": 988,
        "census_population_projections": 86,
        "census_stc": 46,
        "cms_medicaid": 515,
        "cms_medicare": 1,
        "cms_nhe": 1,
        "federal_reserve": 1,
        "hhs_acf_liheap": 2,
        "hhs_acf_tanf": 110,
        "irs_soi": 33535,
        "kff": 52,
        "ssa": 422,
        "usda_snap": 216,
    }
    table_counts = coverage["counts"]["by_source_table"]
    assert len(table_counts) == 38
    assert table_counts["irs_soi:Congressional District Data 2022"] == 26880
    assert table_counts["irs_soi:Publication 1304 Table 1.1"] == 80
    assert (
        table_counts[
            "irs_soi:Publication 1304 Table 2.5 EITC by AGI and qualifying children"
        ]
        == 464
    )
    assert table_counts["bea:BEA Regional annual state personal income CSV ZIP"] == 416
    assert (
        table_counts["cbo:CBO budget and economic data, individual income tax receipts"]
        == 1
    )
    assert (
        table_counts[
            "cbo:Revenue Projections, by Category, February 2026, "
            "sheet 3.Individual Income Tax Details"
        ]
        == 6
    )
    assert (
        table_counts[
            "census_acs:ACS 2023 1-year detailed table B01001 female age bands by state"
        ]
        == 468
    )
    assert (
        table_counts[
            "cms_medicaid:State Medicaid and CHIP Applications, Eligibility "
            "Determinations, and Enrollment Data"
        ]
        == 515
    )
    assert table_counts["ssa:SSA Annual Statistical Supplement 2025 Table 7.B1"] == 416
    assert coverage["counts"]["by_period"] == {
        "calendar_year:2018": 1,
        "calendar_year:2023": 999,
        "calendar_year:2024": 1464,
        "fiscal_year:2023": 48,
        "fiscal_year:2024": 327,
        "month:2024-12": 260,
        "month:2025-12": 255,
        "tax_year:2022": 5886,
        "tax_year:2023": 27621,
        "tax_year:2024": 34,
    }
    assert coverage["counts"]["by_geography"]["country:0100000US"] == 1849
    assert coverage["counts"]["by_geography"]["state:0400000US06"] == 217
    assert (
        coverage["counts"]["by_geography"]["congressional_district:5001700US0601"] == 56
    )
    assert len(coverage["counts"]["by_geography"]) == 483
    assert coverage["counts"]["by_entity"] == {
        "family": 107,
        "government": 102,
        "household": 56,
        "institutional_sector": 1,
        "pension_plan": 2,
        "person": 3086,
        "tax_unit": 33541,
    }
    assert not coverage["duplicates"]["aggregate_fact_keys"]
    assert len(coverage["duplicates"]["semantic_fact_keys"]) == 12
    assert summary["warnings"] == [
        {
            "code": "duplicate_semantic_fact_key",
            "message": (
                "One or more semantic facts appear in multiple rows; downstream "
                "consumers should reconcile or select sources."
            ),
        }
    ]
    assert (output_dir / "sources" / "soi-table-1-1" / "consumer_facts.jsonl").exists()
    assert (
        output_dir / "sources" / "soi-table-1-4" / "reports" / "build_summary.json"
    ).exists()
    assert (
        output_dir
        / "sources"
        / "hhs-acf-liheap-fy2024-national-profile"
        / "consumer_facts.jsonl"
    ).exists()
    assert (
        output_dir
        / "sources"
        / "soi-ira-roth-contributions-2022"
        / "consumer_facts.jsonl"
    ).exists()
    assert (
        output_dir
        / "sources"
        / "census-stc-individual-income-tax"
        / "consumer_facts.jsonl"
    ).exists()
    assert (
        output_dir
        / "sources"
        / "cms-medicare-trustees-report-2025-part-b-premium-income"
        / "consumer_facts.jsonl"
    ).exists()
    assert (
        output_dir
        / "sources"
        / "cms-nhe-historical-service-source"
        / "consumer_facts.jsonl"
    ).exists()
    assert (
        output_dir
        / "sources"
        / "federal-reserve-z1-household-net-worth"
        / "consumer_facts.jsonl"
    ).exists()
    assert (
        output_dir / "sources" / "usda-snap-fy69-to-current" / "consumer_facts.jsonl"
    ).exists()
    assert (
        output_dir / "sources" / "soi-historic-table-2" / "consumer_facts.jsonl"
    ).exists()
    assert (
        output_dir / "sources" / "hhs-acf-tanf-caseload-2024" / "consumer_facts.jsonl"
    ).exists()
    assert (
        output_dir / "sources" / "hhs-acf-tanf-financial-2024" / "consumer_facts.jsonl"
    ).exists()
    assert (
        output_dir
        / "sources"
        / "soi-congressional-district-2022"
        / "consumer_facts.jsonl"
    ).exists()
    assert (
        output_dir
        / "sources"
        / "cbo-revenue-projections-income-by-source-2026-02"
        / "consumer_facts.jsonl"
    ).exists()
    assert (
        output_dir
        / "sources"
        / "bea-regional-state-personal-income-components-2024"
        / "consumer_facts.jsonl"
    ).exists()
    assert (
        output_dir / "sources" / "ssa-ssi-table-7b1-2024" / "consumer_facts.jsonl"
    ).exists()
    assert (
        output_dir
        / "sources"
        / "cms-medicaid-chip-monthly-enrollment-december-2024"
        / "consumer_facts.jsonl"
    ).exists()
    assert (
        output_dir
        / "sources"
        / "soi-historic-table-2-state-broad-2022"
        / "consumer_facts.jsonl"
    ).exists()
    assert (
        output_dir
        / "sources"
        / "kff-marketplace-effectuated-enrollment"
        / "consumer_facts.jsonl"
    ).exists()


def test_build_bundle_cli_supports_explicit_sources(tmp_path, capsys):
    output_dir = tmp_path / "bundle"

    exit_code = harness_main(
        [
            "build-bundle",
            "--year",
            "2023",
            "--source",
            "soi-table-1-1",
            "--out",
            str(output_dir),
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["valid"]
    assert payload["counts"]["source_package_count"] == 1
    assert payload["counts"]["fact_count"] == 80
    assert payload["outputs"]["consumer_facts"] == str(
        output_dir / "consumer_facts.jsonl"
    )
    assert payload["coverage"]["counts"]["by_source_table"] == {
        "irs_soi:Publication 1304 Table 1.1": 80
    }


def test_build_bundle_cli_supports_historic_table_2_source(tmp_path, capsys):
    output_dir = tmp_path / "bundle"

    exit_code = harness_main(
        [
            "build-bundle",
            "--year",
            "2023",
            "--source",
            "soi-historic-table-2",
            "--out",
            str(output_dir),
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["valid"]
    assert payload["counts"]["source_package_count"] == 1
    assert payload["counts"]["fact_count"] == 605
    assert payload["coverage"]["counts"]["by_source_table"] == {
        "irs_soi:Historic Table 2": 605
    }
    assert (
        output_dir / "sources" / "soi-historic-table-2" / "source_rows.jsonl"
    ).exists()


def test_build_bundle_cli_supports_ssa_supplement_source(tmp_path, capsys):
    output_dir = tmp_path / "bundle"

    exit_code = harness_main(
        [
            "build-bundle",
            "--year",
            "2024",
            "--source",
            "ssa-annual-statistical-supplement-2025",
            "--out",
            str(output_dir),
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    rows = _load_jsonl(output_dir / "consumer_facts.jsonl")

    assert exit_code == 0
    assert payload["valid"]
    assert payload["counts"]["source_package_count"] == 1
    assert payload["counts"]["fact_count"] == 6
    assert payload["coverage"]["counts"]["by_source"] == {"ssa": 6}
    assert payload["coverage"]["counts"]["by_entity"] == {"person": 6}
    assert {row["universe_constraints"]["constraints"][0]["value"] for row in rows} == {
        "social_security_benefits",
        "social_security_retirement_benefits",
        "social_security_survivors_benefits",
        "social_security_disability_benefits",
        "social_security_dependents_benefits",
        "ssi_payments",
    }


def test_build_bundle_cli_supports_jct_tax_expenditure_source(tmp_path, capsys):
    output_dir = tmp_path / "bundle"

    exit_code = harness_main(
        [
            "build-bundle",
            "--year",
            "2024",
            "--source",
            "jct-tax-expenditures-2024",
            "--out",
            str(output_dir),
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    rows = _load_jsonl(output_dir / "consumer_facts.jsonl")

    assert exit_code == 0
    assert payload["valid"]
    assert payload["counts"]["source_package_count"] == 1
    assert payload["counts"]["fact_count"] == 5
    assert payload["coverage"]["counts"]["by_source"] == {"jct": 5}
    assert payload["coverage"]["counts"]["by_entity"] == {"tax_unit": 5}
    assert {row["lineage"]["source_record_id"] for row in rows} == {
        "jct.tax_expenditures.cy2024.salt_deduction.revenue_loss",
        "jct.tax_expenditures.cy2024.medical_expense_deduction.revenue_loss",
        "jct.tax_expenditures.cy2024.charitable_deduction.revenue_loss",
        "jct.tax_expenditures.cy2024.deductible_mortgage_interest.revenue_loss",
        "jct.tax_expenditures.cy2024.qualified_business_income_deduction.revenue_loss",
    }


def test_build_bundle_coverage_reports_duplicate_keys():
    rows = [
        {
            "aggregate_fact_key": "ledger.aggregate_fact.v2:a",
            "semantic_fact_key": "ledger.semantic_fact.v2:s",
            "legacy_fact_key": "ledger.fact.v1:one",
            "source": {
                "source_name": "irs_soi",
                "source_table": "Publication 1304 Table 1.1",
            },
            "period": {"type": "tax_year", "value": 2023},
            "geography": {"level": "country", "id": "0100000US"},
            "entity": {"name": "tax_unit"},
            "observed_measure": {
                "source_name": "irs_soi",
                "source_measure_id": "return_count",
                "source_concept": "irs_soi.individual_income_tax_returns",
            },
        },
        {
            "aggregate_fact_key": "ledger.aggregate_fact.v2:a",
            "semantic_fact_key": "ledger.semantic_fact.v2:s",
            "legacy_fact_key": "ledger.fact.v1:two",
            "source": {
                "source_name": "irs_soi",
                "source_table": "Publication 1304 Table 1.1",
            },
            "period": {"type": "tax_year", "value": 2023},
            "geography": {"level": "country", "id": "0100000US"},
            "entity": {"name": "tax_unit"},
            "observed_measure": {
                "source_name": "irs_soi",
                "source_measure_id": "return_count",
                "source_concept": "irs_soi.individual_income_tax_returns",
            },
        },
    ]

    coverage = build_bundle_coverage(
        rows,
        aggregate_duplicates=[
            {
                "key": "ledger.aggregate_fact.v2:a",
                "count": 2,
                "sources": ["irs_soi:Publication 1304 Table 1.1"],
                "legacy_fact_keys": ["ledger.fact.v1:one", "ledger.fact.v1:two"],
            }
        ],
        semantic_duplicates=[
            {
                "key": "ledger.semantic_fact.v2:s",
                "count": 2,
                "sources": ["irs_soi:Publication 1304 Table 1.1"],
                "legacy_fact_keys": ["ledger.fact.v1:one", "ledger.fact.v1:two"],
            }
        ],
    )

    assert coverage["counts"]["by_source"] == {"irs_soi": 2}
    assert coverage["duplicates"]["aggregate_fact_keys"][0]["count"] == 2
    assert coverage["duplicates"]["semantic_fact_keys"][0]["count"] == 2
