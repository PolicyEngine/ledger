"""Tests for consumer artifacts and period-contract resolution.

The load-bearing behavior: consuming a fact at a period other than its
reference period is a hard error unless the consumer declares a named,
versioned alignment. This is the schema-level guard against the
PolicyEngine/populace#212 failure, where SOI tax-year dollar levels were
calibrated un-aged at a later build year and nothing complained.
"""

from __future__ import annotations

import json

import pytest

from ledger.consumer_contract import consumer_fact_rows
from ledger.core import (
    AggregateFact,
    Aggregation,
    EntityDimension,
    GeographyDimension,
    Measure,
    PeriodDimension,
    SourceProvenance,
    SourceRecordLayout,
)
from policyengine_ledger.consumer import (
    PeriodAlignmentDeclaration,
    PeriodContractError,
    build_consumer_artifact,
    load_consumer_artifact,
    resolve_profile_targets,
)
from policyengine_ledger.target_profiles import target_profile_from_mapping

SHA = "ab" * 32


def _fact(
    *,
    value,
    period_value,
    period_type="tax_year",
    source_name="irs_soi",
    measure_id="agi",
    concept="irs_soi.adjusted_gross_income",
    assertion="observation",
):
    return AggregateFact(
        value=value,
        period=PeriodDimension(type=period_type, value=period_value),
        geography=GeographyDimension(
            level="country",
            id="0100000US",
            vintage="2020_census",
        ),
        entity=EntityDimension(name="tax_unit", role="filing_unit"),
        measure=Measure(concept=concept, unit="usd"),
        aggregation=Aggregation(method="sum"),
        source=SourceProvenance(
            source_name=source_name,
            source_table="Table T",
            source_file="t.xls",
            url="https://example.gov/t.xls",
            vintage=f"{period_type}_{period_value}",
            extracted_at="2026-05-01",
            extraction_method="test",
            source_sha256=SHA,
            source_size_bytes=10,
            raw_r2_bucket="ledger-raw",
            raw_r2_key=f"raw/{source_name}/t/{period_value}/{SHA}/t.xls",
            raw_r2_uri=f"r2://ledger-raw/raw/{source_name}/t/{period_value}/{SHA}/t.xls",
        ),
        domain="all_returns",
        source_record_id=f"{source_name}.{period_value}.t.all.{measure_id}",
        source_cell_keys=(f"ledger.source_cell.v1:{period_value}{measure_id}",),
        layout=SourceRecordLayout(
            record_set_id=f"{source_name}.{period_value}.t",
            record_set_spec_id=f"{source_name}.t.v1",
            measure_id=measure_id,
            groupby_dimension="us.agi",
        ),
        assertion=assertion,
    )


def _rows():
    return consumer_fact_rows(
        [
            _fact(value=100, period_value=2021),
            _fact(value=110, period_value=2022),
            _fact(
                value=250,
                period_value=2027,
                period_type="calendar_year",
                source_name="cbo",
                measure_id="receipts",
                concept="cbo.individual_income_tax_receipts",
                assertion="source_projection",
            ),
        ]
    )


def _profile(selector=None, target_id="soi.agi.total"):
    return target_profile_from_mapping(
        {
            "schema_version": "policyengine_ledger.target_profile.v1",
            "profile_id": "test_profile",
            "country": "us",
            "label": "Test profile",
            "defaults": {
                "base_period_policy": "latest_not_after_build_base_period",
                "operation": "sum",
            },
            "targets": [
                {
                    "target_id": target_id,
                    "family": "irs_soi",
                    "geography_levels": ["country"],
                    "ledger_selector": selector
                    or {"source_name": "irs_soi", "source_measure_id": "agi"},
                    "measurement": {
                        "entity": "tax_unit",
                        "concept": "us.agi",
                    },
                    "bindings": {
                        "populace": {"metric_name": "irs_soi/agi/total"},
                    },
                }
            ],
        }
    )


def test_resolving_at_the_fact_period_is_fact_basis():
    report = resolve_profile_targets(
        _profile(),
        _rows(),
        {"type": "tax_year", "value": 2022},
    )
    assert report.valid
    assert len(report.resolved) == 1
    row = report.resolved[0]
    assert row.basis == "fact"
    assert row.value == 110
    assert row.assertion == "observation"
    assert row.fact_period == {"type": "tax_year", "value": 2022}
    assert row.requested_period == {"type": "tax_year", "value": 2022}
    assert row.alignment is None


def test_un_aged_consumption_hard_fails():
    with pytest.raises(PeriodContractError) as excinfo:
        resolve_profile_targets(
            _profile(),
            _rows(),
            {"type": "tax_year", "value": 2025},
        )
    message = str(excinfo.value)
    assert "PeriodAlignmentDeclaration" in message
    (violation,) = excinfo.value.violations
    assert violation.fact_period == {"type": "tax_year", "value": 2022}
    assert violation.requested_period == {"type": "tax_year", "value": 2025}


def test_declared_alignment_resolves_and_is_recorded():
    declaration = PeriodAlignmentDeclaration(
        model_id="cbo_growth_factor_aging",
        model_version="2026.1",
        parameters={"factor_series": "cbo.baseline_2026_01.agi_growth"},
    )
    report = resolve_profile_targets(
        _profile(),
        _rows(),
        {"type": "tax_year", "value": 2025},
        alignments={"soi.agi.total": declaration},
    )
    assert report.valid
    (row,) = report.resolved
    assert row.basis == "declared_alignment"
    # Ledger returns the published level; the consumer applies the model.
    assert row.value == 110
    assert row.fact_period == {"type": "tax_year", "value": 2022}
    assert row.requested_period == {"type": "tax_year", "value": 2025}
    assert row.alignment["model_id"] == "cbo_growth_factor_aging"
    assert row.alignment["model_version"] == "2026.1"


def test_latest_not_after_selects_the_newest_covered_period():
    report = resolve_profile_targets(
        _profile(),
        _rows(),
        {"type": "tax_year", "value": 2021},
    )
    (row,) = report.resolved
    assert row.basis == "fact"
    assert row.value == 100


def test_wildcard_alignment_covers_all_targets():
    declaration = PeriodAlignmentDeclaration(
        model_id="cbo_growth_factor_aging",
        model_version="2026.1",
    )
    report = resolve_profile_targets(
        _profile(),
        _rows(),
        {"type": "tax_year", "value": 2025},
        alignments=declaration,
    )
    assert report.valid
    assert report.resolved[0].basis == "declared_alignment"


def test_source_projections_resolve_at_their_own_period_as_facts():
    profile = _profile(
        selector={
            "source_name": "cbo",
            "source_measure_id": "receipts",
            "assertion": "source_projection",
        },
        target_id="cbo.receipts.2027",
    )
    report = resolve_profile_targets(
        profile,
        _rows(),
        {"type": "calendar_year", "value": 2027},
    )
    (row,) = report.resolved
    assert row.basis == "fact"
    assert row.assertion == "source_projection"
    assert row.value == 250


def test_alignment_declarations_reject_values_and_runtime_hooks():
    with pytest.raises(ValueError, match="never"):
        PeriodAlignmentDeclaration(
            model_id="m",
            model_version="1",
            parameters={"target_value": 130e9},
        )
    with pytest.raises(ValueError, match="model_version"):
        PeriodAlignmentDeclaration(model_id="m", model_version=" ")
    with pytest.raises(ValueError, match="non-scalar"):
        PeriodAlignmentDeclaration(
            model_id="m",
            model_version="1",
            parameters={"factors": [1.02, 1.03]},
        )


def test_unknown_selector_keys_fail_loudly():
    profile = _profile(selector={"source_name": "irs_soi", "spreadsheet": "t.xls"})
    with pytest.raises(ValueError, match="unknown keys"):
        resolve_profile_targets(
            profile,
            _rows(),
            {"type": "tax_year", "value": 2022},
        )


def test_no_matching_facts_fails_strict_and_reports_lenient():
    profile = _profile(selector={"source_name": "nonexistent"})
    with pytest.raises(ValueError, match="matched no consumer fact rows"):
        resolve_profile_targets(
            profile,
            _rows(),
            {"type": "tax_year", "value": 2022},
        )
    report = resolve_profile_targets(
        profile,
        _rows(),
        {"type": "tax_year", "value": 2022},
        strict=False,
    )
    assert not report.valid
    assert report.issues[0].code == "no_matching_facts"


def _write_artifact_inputs(tmp_path):
    facts_path = tmp_path / "consumer_facts.jsonl"
    with facts_path.open("w") as file:
        for row in _rows():
            file.write(json.dumps(row, sort_keys=True) + "\n")
    profile_path = tmp_path / "test_profile.json"
    profile_path.write_text(
        json.dumps(
            {
                "schema_version": "policyengine_ledger.target_profile.v1",
                "profile_id": "test_profile",
                "country": "us",
                "label": "Test profile",
                "defaults": {
                    "base_period_policy": "latest_not_after_build_base_period",
                    "operation": "sum",
                },
                "targets": [
                    {
                        "target_id": "soi.agi.total",
                        "family": "irs_soi",
                        "geography_levels": ["country"],
                        "ledger_selector": {
                            "source_name": "irs_soi",
                            "source_measure_id": "agi",
                        },
                        "measurement": {"entity": "tax_unit", "concept": "us.agi"},
                        "bindings": {
                            "populace": {"metric_name": "irs_soi/agi/total"},
                        },
                    }
                ],
            }
        )
    )
    return facts_path, profile_path


def test_artifact_build_load_resolve_round_trip(tmp_path):
    facts_path, profile_path = _write_artifact_inputs(tmp_path)
    out_dir = tmp_path / "artifact"
    report = build_consumer_artifact(
        out_dir,
        facts_path=facts_path,
        profile_paths=[profile_path],
    )
    assert report.fact_row_count == 3
    assert report.profile_ids == ("test_profile",)

    artifact = load_consumer_artifact(out_dir)
    assert artifact.manifest["fact_row_count"] == 3
    resolution = artifact.resolve(
        "test_profile",
        {"type": "tax_year", "value": 2022},
    )
    assert resolution.resolved[0].value == 110

    with pytest.raises(PeriodContractError):
        artifact.resolve("test_profile", {"type": "tax_year", "value": 2025})


def test_artifact_coverage_reports_periods_and_assertions(tmp_path):
    facts_path, profile_path = _write_artifact_inputs(tmp_path)
    out_dir = tmp_path / "artifact"
    report = build_consumer_artifact(
        out_dir,
        facts_path=facts_path,
        profile_paths=[profile_path],
    )
    target_coverage = report.coverage["test_profile"]["soi.agi.total"]["country"]
    assert target_coverage["matched_row_count"] == 2
    assert target_coverage["fact_periods"] == ["tax_year:2021", "tax_year:2022"]
    assert target_coverage["assertions"] == ["observation"]
    coverage_on_disk = json.loads((out_dir / "coverage.json").read_text())
    assert coverage_on_disk == report.coverage


def test_artifact_load_rejects_tampered_facts(tmp_path):
    facts_path, profile_path = _write_artifact_inputs(tmp_path)
    out_dir = tmp_path / "artifact"
    build_consumer_artifact(
        out_dir,
        facts_path=facts_path,
        profile_paths=[profile_path],
    )
    facts_file = out_dir / "consumer_facts.jsonl"
    rows = facts_file.read_text().splitlines()
    tampered = json.loads(rows[0])
    tampered["value"] = 999
    rows[0] = json.dumps(tampered, sort_keys=True)
    facts_file.write_text("\n".join(rows) + "\n")
    with pytest.raises(ValueError, match="manifest hash"):
        load_consumer_artifact(out_dir)


def test_artifact_requires_profiles(tmp_path):
    facts_path, _ = _write_artifact_inputs(tmp_path)
    with pytest.raises(ValueError, match="at least one target profile"):
        build_consumer_artifact(
            tmp_path / "artifact",
            facts_path=facts_path,
        )


def test_artifact_is_reproducible(tmp_path):
    facts_path, profile_path = _write_artifact_inputs(tmp_path)
    first = tmp_path / "first"
    second = tmp_path / "second"
    for out_dir in (first, second):
        build_consumer_artifact(
            out_dir,
            facts_path=facts_path,
            profile_paths=[profile_path],
        )
    for name in ("manifest.json", "coverage.json", "consumer_facts.jsonl"):
        assert (first / name).read_bytes() == (second / name).read_bytes()
