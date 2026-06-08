"""Tests for checked-in PolicyEngine Ledger observation facts."""

from __future__ import annotations

import json
from pathlib import Path

from arch.core import (
    AggregateFact,
    Aggregation,
    EntityDimension,
    GeographyDimension,
    Measure,
    PeriodDimension,
    SourceProvenance,
    validate_facts,
)


ROOT = Path(__file__).resolve().parents[1]
LEDGER_PATH = ROOT / "ledger" / "official_observations.jsonl"

EXPECTED_SOURCE_RECORD_IDS = {
    "bls.ces.total_nonfarm_payroll_change.may_2026.first_print",
    "bls.cps.unemployment_rate.may_2026.first_print",
    "bls.ces.average_hourly_earnings_private.may_2026.first_print",
    "statcan.lfs.unemployment_rate.canada.may_2026.first_print",
    "statcan.lfs.employment_change.canada.may_2026.first_print",
}


def _read_ledger_facts() -> list[dict]:
    return [
        json.loads(line)
        for line in LEDGER_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _to_aggregate_fact(row: dict) -> AggregateFact:
    return AggregateFact(
        value=row["value"],
        period=PeriodDimension(**row["period"]),
        geography=GeographyDimension(**row["geography"]),
        entity=EntityDimension(**row["entity"]),
        measure=Measure(**row["measure"]),
        aggregation=Aggregation(**row["aggregation"]),
        source=SourceProvenance(**row["source"]),
        filters=row.get("filters", {}),
        domain=row.get("domain", "all"),
        label=row.get("label"),
        source_record_id=row.get("source_record_id"),
        source_cell_keys=tuple(row.get("source_cell_keys", ())),
        source_row_keys=tuple(row.get("source_row_keys", ())),
    )


def test_official_observation_ledger_has_expected_rows():
    rows = _read_ledger_facts()

    assert {row["source_record_id"] for row in rows} == EXPECTED_SOURCE_RECORD_IDS
    assert len(rows) == len(EXPECTED_SOURCE_RECORD_IDS)


def test_official_observation_ledger_contains_facts_not_predictions():
    rows = _read_ledger_facts()

    for row in rows:
        assert "prediction" not in json.dumps(row).lower()
        assert "forecast" not in json.dumps(row).lower()
        assert row["source_record_id"]
        assert row["observed_at"] == "2026-06-05"
        assert row["source"]["url"].startswith("https://")
        assert row["source"]["vintage"] == "may_2026_first_print"


def test_official_observations_validate_as_aggregate_facts():
    facts = [_to_aggregate_fact(row) for row in _read_ledger_facts()]

    report = validate_facts(facts)

    assert report.valid, report.to_dict()
    assert report.counts["by_source"] == {"bls": 3, "statcan": 2}
    assert report.counts["missing_lineage"]["count"] == 0
