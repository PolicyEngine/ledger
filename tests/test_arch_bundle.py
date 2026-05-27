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
        "entity_count": 1,
        "error_count": 0,
        "fact_count": 1643,
        "geography_count": 52,
        "period_count": 2,
        "semantic_duplicate_key_count": 3,
        "skipped_source_count": 0,
        "source_count": 1,
        "source_package_count": 12,
        "warning_count": 1,
    }
    assert len(rows) == 1643
    assert rows[0]["aggregate_fact_key"].startswith("arch.aggregate_fact.v2:")
    assert rows[0]["semantic_fact_key"].startswith("arch.semantic_fact.v2:")
    assert source_packages["source_package_count"] == 12
    assert source_packages["skipped_source_count"] == 0
    assert not source_packages["skipped_sources"]
    assert coverage["fact_count"] == 1643
    assert coverage["counts"]["by_source"] == {
        "irs_soi": 1643,
    }
    assert coverage["counts"]["by_source_table"] == {
        "irs_soi:Historic Table 2 state AGI facts": 918,
        "irs_soi:Historic Table 2 state EITC totals": 102,
        "irs_soi:Publication 1304 Table 1.1": 80,
        "irs_soi:Publication 1304 Table 1.2": 7,
        "irs_soi:Publication 1304 Table 1.4": 260,
        "irs_soi:Publication 1304 Table 2.1": 17,
        "irs_soi:Publication 1304 Table 2.5": 8,
        "irs_soi:Publication 1304 Table 2.5 EITC by AGI and qualifying children": 224,
        "irs_soi:Publication 1304 Table 4.3": 18,
        (
            "irs_soi:Table 4.B. Summary of Items for Taxpayers with Form W-2, "
            "by Return and Earner Type, Tax Year 2020"
        ): 5,
        (
            "irs_soi:Table 5. Taxpayers with Traditional Individual Retirement "
            "Arrangement (IRA) Plan Contributions, by Size of Contribution and "
            "Age of Taxpayer"
        ): 2,
        (
            "irs_soi:Table 6. Taxpayers with Roth Individual Retirement "
            "Arrangement (IRA) Plan Contributions, by Size of Contribution and "
            "Age of Taxpayer"
        ): 2,
    }
    assert coverage["counts"]["by_period"] == {
        "tax_year:2022": 1244,
        "tax_year:2023": 399,
    }
    assert coverage["counts"]["by_geography"]["country:0100000US"] == 623
    assert coverage["counts"]["by_geography"]["state:0400000US06"] == 20
    assert len(coverage["counts"]["by_geography"]) == 52
    assert coverage["counts"]["by_entity"] == {
        "tax_unit": 1643,
    }
    assert not coverage["duplicates"]["aggregate_fact_keys"]
    assert len(coverage["duplicates"]["semantic_fact_keys"]) == 3
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
        output_dir
        / "sources"
        / "soi-table-1-4"
        / "reports"
        / "build_summary.json"
    ).exists()
    assert (
        output_dir
        / "sources"
        / "soi-ira-roth-contributions-2022"
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
