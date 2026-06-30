"""Tests for the Ledger fact validation harness."""

from __future__ import annotations

import json

from ledger.harness import build_fixture_fact_file, validate_fixture_facts
from ledger.store import load_facts_jsonl


def test_fixture_facts_validate_with_counts():
    report = validate_fixture_facts()

    assert report.valid
    assert report.fact_count == 80
    assert report.counts["by_source"] == {"irs_soi": 80}
    assert report.counts["by_entity"] == {"tax_unit": 80}
    assert report.counts["by_period"] == {"tax_year:2023": 80}


def test_report_is_json_serializable():
    report = validate_fixture_facts()

    payload = json.loads(json.dumps(report.to_dict()))

    assert payload["fact_count"] == 80
    assert payload["errors"] == []


def test_build_fixture_fact_file_writes_source_backed_jsonl(tmp_path):
    output = tmp_path / "soi-facts.jsonl"

    report = build_fixture_fact_file("soi-table-1-1", output, year=2023)
    facts = load_facts_jsonl(output)

    assert report.valid
    assert len(facts) == 80
    assert facts[0].value == 160_602_107
    assert facts[0].source.source_file == "23in11si.xls"
