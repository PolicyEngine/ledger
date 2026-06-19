"""Tests for checked-in PolicyEngine Ledger observation facts."""

from __future__ import annotations

import json
import re
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
    "bank_of_canada.overnight_rate.after_june_2026",
    "bls.ces.total_nonfarm_payroll_change.may_2026.first_print",
    "bls.ces.average_hourly_earnings_private.may_2026.first_print",
    "bls.cpi.u.core_mom.may_2026.first_print",
    "bls.cpi.u.headline_mom.may_2026.first_print",
    "bls.cps.unemployment_rate.may_2026.first_print",
    "bls.import_price_index.all_imports_mom.may_2026.first_print",
    "bls.ppi.final_demand_monthly_change.may_2026.first_print",
    "boe.bank_rate.2026-06-18",
    "boe.bank_rate.after_mpc_june_2026.first_print",
    "boj.policy_rate_guideline.after_june_2026",
    "census.housing_starts.saar.may_2026.first_print",
    "census.marts.adv44x72.may_2026.monthly_change.advance",
    "census.mtis.total_business_inventories_level.april_2026.first_print",
    "cms.medicaid_pi.beneficiaries_renewed_total.california.feb_2026.original_submission",
    "cms.medicaid_pi.beneficiaries_renewed_ex_parte.california.feb_2026.original_submission",
    "cms.medicaid_pi.beneficiaries_disenrolled_total.california.feb_2026.original_submission",
    "cms.medicaid_pi.beneficiaries_disenrolled_procedural.california.feb_2026.original_submission",
    "dol.eta.initial_claims.sa.week_ending_2026_06_06",
    "ecb.deposit_facility_rate.after_june_2026",
    "estat.jp.cpi.core_exfreshfood.yoy.2026-05",
    "eurostat.hicp.all_items_annual_rate.euro_area.may_2026.final_first_print",
    "eurostat.industrial_production.euro_area.april_2026.first_print",
    "fed.g17.capacity_utilization.total_industry.may_2026.first_print",
    "fed.g17.industrial_production.total_index_mom.may_2026.first_print",
    "fns.snap.application_processing_timeliness.california.fy2024.official_release",
    "fns.snap.overpayment_payment_error_rate.us.fy2024.official_release",
    "fns.snap.total_payment_error_rate.us.fy2024.official_release",
    "fns.snap.underpayment_payment_error_rate.us.fy2024.official_release",
    "ons.cpi.annual_rate.may_2026.first_print",
    "ons.cpih.annual_rate.2026-05",
    "ons.gdp.monthly_growth.april_2026.first_print",
    "ons.hmrc.paye_payrolled_employees.may_2026.first_print",
    "ons.labour.unemployment_rate.february_to_april_2026.first_print",
    "ons.pusf.j5ii.public_sector_net_borrowing_ex_banks.may_2026.first_print",
    "ons.retail_sales.volume_mom.may_2026.first_print",
    "rba.cash_rate_target.after_june_2026",
    "statcan.building_permits.total_value_mom.canada.april_2026.first_print",
    "statcan.employment_insurance.regular_beneficiaries.canada.april_2026.first_print",
    "statcan.lfs.employment_change.canada.may_2026.first_print",
    "statcan.lfs.unemployment_rate.canada.may_2026.first_print",
    "statcan.retail_trade.sales_mom.canada.april_2026.first_print",
    "statcan.wholesale_trade.sales_mom_exclusions.canada.april_2026.first_print",
    "statjp.cpi.all_items_annual_rate.japan.may_2026.first_print",
    "treasury.mts.monthly_deficit.may_2026.first_print",
    "us.census.housing_starts.total_saar.2026-05",
    "us.dol.initial_claims.sa.week_2026-06-13",
    "us.fed.fomc.target_range_upper.2026-06",
    "us.frb.industrial_production.total.mom_sa.2026-05",
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
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", row["observed_at"])
        assert row["source"]["url"].startswith("https://")
        assert row["source"]["vintage"]


def test_official_observations_validate_as_aggregate_facts():
    facts = [_to_aggregate_fact(row) for row in _read_ledger_facts()]

    report = validate_facts(facts)

    assert report.valid, report.to_dict()
    assert report.counts["by_source"] == {
        "bank_of_canada": 1,
        "bls": 7,
        "boe": 2,
        "boj": 1,
        "census": 4,
        "cms": 4,
        "dol": 2,
        "ecb": 1,
        "eurostat": 2,
        "fed": 4,
        "fns": 4,
        "ons": 7,
        "rba": 1,
        "statcan": 6,
        "statjp": 2,
        "treasury": 1,
    }
    assert report.counts["missing_lineage"]["count"] == 0
