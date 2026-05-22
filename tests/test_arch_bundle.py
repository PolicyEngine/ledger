"""Tests for merged Arch consumer bundles."""

from __future__ import annotations

import json

from arch.bundle import build_bundle, build_bundle_coverage
from arch.harness import main as harness_main


def _load_jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def test_build_bundle_writes_merged_consumer_contract(tmp_path):
    output_dir = tmp_path / "bundle"

    report = build_bundle(output_dir, year=2023)
    summary = json.loads(
        (output_dir / "reports" / "build_bundle.json").read_text()
    )
    rows = _load_jsonl(output_dir / "consumer_facts.jsonl")
    source_packages = json.loads((output_dir / "source_packages.json").read_text())
    coverage = json.loads((output_dir / "coverage.json").read_text())

    assert report.valid
    assert summary["valid"]
    assert summary["counts"] == {
        "aggregate_duplicate_key_count": 0,
        "entity_count": 3,
        "error_count": 0,
        "fact_count": 490,
        "geography_count": 2,
        "period_count": 3,
        "semantic_duplicate_key_count": 0,
        "skipped_source_count": 23,
        "source_count": 3,
        "source_package_count": 5,
        "warning_count": 0,
    }
    assert len(rows) == 490
    assert rows[0]["aggregate_fact_key"].startswith("arch.aggregate_fact.v2:")
    assert rows[0]["semantic_fact_key"].startswith("arch.semantic_fact.v2:")
    assert source_packages["source_package_count"] == 5
    assert source_packages["skipped_source_count"] == 22
    assert {source["source"] for source in source_packages["skipped_sources"]} == {
        "cms-aca-oep-state-level",
        "cms-aca-oep-state-level-2022",
        "cms-aca-oep-state-level-2025",
        "cms-aca-effectuated-enrollment-2022",
        "bea-nipa-pension-contributions",
        "dwp-benefit-cap-november-2025",
        "dwp-benefit-statistics-february-2026",
        "dwp-pip-daily-living-foi-2025",
        "dwp-uc-national-payment-dist-2025",
        "dwp-uc-two-child-limit-2025",
        "hmrc-salary-sacrifice-relief-2024",
        "obr-efo-expenditure",
        "obr-efo-receipts",
        "scotgov-council-tax-bands-2025",
        "scotgov-scottish-budget-social-security-assistance-2026",
        "slc-student-loan-borrower-forecasts-england-2025",
        "slc-student-loan-repayments-england-2025",
        "slc-student-loan-repayments-northern-ireland-2025",
        "slc-student-loan-repayments-scotland-2025",
        "slc-student-loan-repayments-wales-2025",
        "slc-student-support-england-2025",
        "soi-historic-table-2",
        "voa-council-tax-bands-2025",
    }
    assert coverage["fact_count"] == 490
    assert coverage["counts"]["by_source"] == {
        "hmrc_spi": 156,
        "irs_soi": 320,
        "ons": 14,
    }
    assert coverage["counts"]["by_source_table"] == {
        "hmrc_spi:HMRC SPI collated tables 3.6 and 3.7 2022-23": 156,
        "irs_soi:Publication 1304 Table 1.1": 80,
        "irs_soi:Publication 1304 Table 1.4": 240,
        "ons:ONS 2022-based principal population projections for the UK": 13,
        "ons:ONS UKEA HAXV households interest resources": 1,
    }
    assert coverage["counts"]["by_period"] == {
        "calendar_year:2023": 14,
        "tax_year:2022-23": 156,
        "tax_year:2023": 320,
    }
    assert coverage["counts"]["by_geography"] == {
        "country:0100000US": 320,
        "country:GBR": 170,
    }
    assert coverage["counts"]["by_entity"] == {
        "household": 1,
        "person": 169,
        "tax_unit": 320,
    }
    assert not coverage["duplicates"]["aggregate_fact_keys"]
    assert not coverage["duplicates"]["semantic_fact_keys"]
    assert (
        output_dir
        / "sources"
        / "hmrc-spi-income-bands-2023"
        / "consumer_facts.jsonl"
    ).exists()
    assert (
        output_dir
        / "sources"
        / "ons-savings-interest-income"
        / "consumer_facts.jsonl"
    ).exists()
    assert (output_dir / "sources" / "soi-table-1-1" / "consumer_facts.jsonl").exists()
    assert (
        output_dir
        / "sources"
        / "soi-table-1-4"
        / "reports"
        / "build_summary.json"
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
            "2022",
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
    assert payload["counts"]["fact_count"] == 143
    assert payload["coverage"]["counts"]["by_source_table"] == {
        "irs_soi:Historic Table 2": 143
    }
    assert (
        output_dir
        / "sources"
        / "soi-historic-table-2"
        / "source_rows.jsonl"
    ).exists()


def test_build_bundle_coverage_reports_duplicate_keys():
    rows = [
        {
            "aggregate_fact_key": "arch.aggregate_fact.v2:a",
            "semantic_fact_key": "arch.semantic_fact.v2:s",
            "legacy_fact_key": "arch.fact.v1:one",
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
            "aggregate_fact_key": "arch.aggregate_fact.v2:a",
            "semantic_fact_key": "arch.semantic_fact.v2:s",
            "legacy_fact_key": "arch.fact.v1:two",
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
                "key": "arch.aggregate_fact.v2:a",
                "count": 2,
                "sources": ["irs_soi:Publication 1304 Table 1.1"],
                "legacy_fact_keys": ["arch.fact.v1:one", "arch.fact.v1:two"],
            }
        ],
        semantic_duplicates=[
            {
                "key": "arch.semantic_fact.v2:s",
                "count": 2,
                "sources": ["irs_soi:Publication 1304 Table 1.1"],
                "legacy_fact_keys": ["arch.fact.v1:one", "arch.fact.v1:two"],
            }
        ],
    )

    assert coverage["counts"]["by_source"] == {"irs_soi": 2}
    assert coverage["duplicates"]["aggregate_fact_keys"][0]["count"] == 2
    assert coverage["duplicates"]["semantic_fact_keys"][0]["count"] == 2
