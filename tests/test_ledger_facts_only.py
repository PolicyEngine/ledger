"""Tests for the facts-only schema: assertions and period coverage.

Ledger stores source-backed claims only. Publisher projections are facts
typed ``assertion: source_projection``; PolicyEngine-computed values are
rejected. Existing observation facts must keep byte-identical keys and
serialization.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import pytest

from ledger.consumer_contract import (
    build_aggregate_fact_key,
    build_semantic_fact_key,
    consumer_fact_rows,
)
from ledger.core import (
    ALLOWED_ASSERTIONS,
    AggregateFact,
    Aggregation,
    EntityDimension,
    GeographyDimension,
    Measure,
    PeriodCoverage,
    PeriodDimension,
    SourceProvenance,
    build_fact_key,
    build_label,
    fact_counts,
    validate_fact,
)
from ledger.source_package import DeclarativeRecordSet
from ledger.store import fact_from_mapping, fact_to_mapping, load_facts_jsonl

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_FACTS = ROOT / "ledger" / "fixtures" / "facts.jsonl"

# Keys computed on main before the assertion field existed. Observation
# facts must keep these exact identities forever.
GOLDEN_FACT_KEY = "ledger.fact.v1:079f0697e3b090abf422781b"
GOLDEN_AGGREGATE_FACT_KEY = "ledger.aggregate_fact.v2:13153fb8dfd73fa12d5715e9"
GOLDEN_SEMANTIC_FACT_KEY = "ledger.semantic_fact.v2:1ae4c4f93f554ec7ca14d2ad"


def _fixture_fact() -> AggregateFact:
    return load_facts_jsonl(FIXTURE_FACTS)[0]


def test_observation_fact_keys_are_byte_stable():
    fact = _fixture_fact()
    assert fact.assertion == "observation"
    assert build_fact_key(fact) == GOLDEN_FACT_KEY
    assert build_aggregate_fact_key(fact) == GOLDEN_AGGREGATE_FACT_KEY
    assert build_semantic_fact_key(fact) == GOLDEN_SEMANTIC_FACT_KEY


def test_observation_fact_serialization_omits_new_fields():
    fact = _fixture_fact()
    payload = fact_to_mapping(fact)
    assert "assertion" not in payload
    assert "period_coverage" not in payload
    assert fact_from_mapping(json.loads(json.dumps(payload))) == fact


def test_source_projection_gets_distinct_identity():
    fact = _fixture_fact()
    projection = dataclasses.replace(fact, assertion="source_projection")
    assert not validate_fact(projection)
    assert build_fact_key(projection) != build_fact_key(fact)
    assert build_aggregate_fact_key(projection) != build_aggregate_fact_key(fact)
    assert build_semantic_fact_key(projection) != build_semantic_fact_key(fact)
    assert "projected" in build_label(projection)
    assert "projected" not in build_label(fact)


def test_source_projection_round_trips():
    projection = dataclasses.replace(_fixture_fact(), assertion="source_projection")
    payload = fact_to_mapping(projection)
    assert payload["assertion"] == "source_projection"
    assert fact_from_mapping(json.loads(json.dumps(payload))) == projection


def test_policyengine_computed_assertions_are_rejected():
    for assertion in ("policyengine_aged", "aged", "projection", "forecast", ""):
        assert assertion not in ALLOWED_ASSERTIONS
        fact = dataclasses.replace(_fixture_fact(), assertion=assertion)
        issues = validate_fact(fact)
        assert any(issue.code == "malformed_assertion" for issue in issues)


def test_fact_counts_report_assertions():
    fact = _fixture_fact()
    projection = dataclasses.replace(fact, assertion="source_projection")
    counts = fact_counts([fact, projection])
    assert counts["by_assertion"] == {"observation": 1, "source_projection": 1}


def test_period_coverage_is_not_identity():
    fact = _fixture_fact()
    covered = dataclasses.replace(
        fact,
        period_coverage=PeriodCoverage(
            start_date="2023-01-01",
            end_date="2023-12-31",
            basis="calendar",
            source_period_label="SILC 2024",
        ),
    )
    assert not validate_fact(covered)
    assert build_fact_key(covered) == build_fact_key(fact)
    payload = fact_to_mapping(covered)
    assert payload["period_coverage"]["source_period_label"] == "SILC 2024"
    assert "notes" not in payload["period_coverage"]
    assert fact_from_mapping(json.loads(json.dumps(payload))) == covered


def test_period_coverage_validation():
    fact = _fixture_fact()
    inverted = dataclasses.replace(
        fact,
        period_coverage=PeriodCoverage(
            start_date="2024-01-01",
            end_date="2023-01-01",
        ),
    )
    assert any(
        issue.code == "malformed_period_coverage" for issue in validate_fact(inverted)
    )
    malformed = dataclasses.replace(
        fact,
        period_coverage=PeriodCoverage(start_date="last spring"),
    )
    assert any(
        issue.code == "malformed_period_coverage" for issue in validate_fact(malformed)
    )
    bad_basis = dataclasses.replace(
        fact,
        period_coverage=PeriodCoverage(basis="vibes"),
    )
    assert any(
        issue.code == "malformed_period_coverage" for issue in validate_fact(bad_basis)
    )


def test_consumer_rows_expose_assertion():
    fact = _fixture_fact()
    row = consumer_fact_rows([fact])[0]
    assert row["assertion"] == "observation"
    projection_row = consumer_fact_rows(
        [dataclasses.replace(fact, assertion="source_projection")]
    )[0]
    assert projection_row["assertion"] == "source_projection"


def _record_set_payload(**overrides) -> dict:
    payload = {
        "record_set_id": "cbo.cy2027.baseline.receipts",
        "record_set_spec_id": "cbo.baseline.receipts.v1",
        "source_record_id_prefix": "cbo.cy2027.baseline.receipts",
        "sheet_name": "Sheet1",
        "period_type": "calendar_year",
        "period": 2027,
        "geography_id": "0100000US",
        "geography_level": "country",
        "entity": "government",
        "domain": "federal_budget",
        "groupby_dimension": "us.budget.category",
        "rows": [
            {
                "value_id": "total",
                "label": "Total",
                "ordinal": 0,
                "row_number": 5,
            }
        ],
        "measures": [
            {
                "measure_id": "receipts",
                "label": "Receipts",
                "ordinal": 0,
                "column": "B",
                "concept": "cbo.individual_income_tax_receipts",
                "unit": "usd",
                "aggregation": "sum",
            }
        ],
    }
    payload.update(overrides)
    return payload


def test_source_package_record_sets_declare_assertions():
    record_set = DeclarativeRecordSet(
        _record_set_payload(
            assertion="source_projection",
            period_coverage={
                "basis": "projection_horizon",
                "source_period_label": "January {year} baseline",
            },
        )
    )
    spec = record_set.to_record_set_spec(2027)
    assert spec.assertion == "source_projection"
    assert spec.period_coverage.basis == "projection_horizon"
    assert spec.period_coverage.source_period_label == "January 2027 baseline"


def test_source_package_record_sets_default_to_observation():
    spec = DeclarativeRecordSet(_record_set_payload()).to_record_set_spec(2027)
    assert spec.assertion == "observation"
    assert spec.period_coverage is None


def test_source_package_rejects_policyengine_computed_assertions():
    record_set = DeclarativeRecordSet(_record_set_payload(assertion="aged"))
    with pytest.raises(ValueError, match="PolicyEngine-computed"):
        record_set.to_record_set_spec(2027)


def test_governance_docs_state_the_facts_only_boundary():
    agents = (ROOT / "AGENTS.md").read_text()
    governance = (ROOT / "docs" / "ledger-governance.md").read_text()
    for text in (agents, governance):
        assert "source_projection" in text
        assert "PolicyEngine-computed" in text


def _minimal_fact(**overrides) -> AggregateFact:
    base = dict(
        value=100,
        period=PeriodDimension(type="tax_year", value=2022),
        geography=GeographyDimension(level="country", id="0100000US"),
        entity=EntityDimension(name="tax_unit"),
        measure=Measure(concept="irs_soi.agi", unit="usd"),
        aggregation=Aggregation(method="sum"),
        source=SourceProvenance(
            source_name="irs_soi",
            source_table="Table 1.1",
            vintage="tax_year_2022",
            extracted_at="2026-05-01",
            extraction_method="test",
        ),
    )
    base.update(overrides)
    return AggregateFact(**base)


def test_assertion_default_matches_schema_default():
    fact = _minimal_fact()
    assert fact.assertion == "observation"
    assert not any(
        issue.code == "malformed_assertion" for issue in validate_fact(fact)
    )
