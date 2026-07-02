"""Tests for Belgium Ledger target source packages."""

from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path

from ledger.core import validate_facts
from ledger.source_package import SOURCE_PACKAGE_ALIASES, load_source_package


REPO_ROOT = Path(__file__).resolve().parents[1]

BELGIUM_TARGET_STREAMS = (
    (
        "statbel-population-structure-2026",
        2026,
        "statbel_population_structure",
        "nuts1",
        "people",
        18,
    ),
    (
        "statbel-fiscal-income-2023-nis-2025",
        2023,
        "statbel_fiscal_income",
        "commune",
        "belgium_pit_taxable_income",
        565,
    ),
    (
        "spf-finances-pit-2023",
        2023,
        "spf_finances_pit",
        "country",
        "belgium_pit_federal_and_local_tax_before_withholding",
        1,
    ),
    (
        "onss-contributions-2024",
        2024,
        "onss_contributions",
        "country",
        "belgium_worker_article_17_uncapped_component_contribution",
        1,
    ),
    (
        "onem-rva-unemployment-2024",
        2024,
        "onem_rva_unemployment",
        "country",
        "receives_unemployment_benefit",
        1,
    ),
    (
        "nbb-national-accounts-household-disposable-income-2024",
        2024,
        "nbb_national_accounts",
        "country",
        "household_disposable_income",
        1,
    ),
)


@lru_cache
def _facts(alias: str, year: int):
    return tuple(load_source_package(alias).build_facts(year))


def _csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_belgium_target_aliases_are_registered():
    aliases = {alias for alias, *_rest in BELGIUM_TARGET_STREAMS}

    assert aliases <= set(SOURCE_PACKAGE_ALIASES)


def test_belgium_target_packages_have_expected_fact_count():
    facts = [
        fact
        for alias, year, *_rest in BELGIUM_TARGET_STREAMS
        for fact in _facts(alias, year)
    ]

    assert len(facts) == 587
    assert validate_facts(facts).valid


def test_belgium_populace_selectors_match_one_package_stream():
    facts_by_alias = {
        alias: _facts(alias, year) for alias, year, *_rest in BELGIUM_TARGET_STREAMS
    }

    for (
        expected_alias,
        _year,
        source_name,
        geography_level,
        concept,
        expected_count,
    ) in BELGIUM_TARGET_STREAMS:
        matching_aliases = {
            alias
            for alias, facts in facts_by_alias.items()
            if any(
                fact.source.source_name == source_name
                and fact.geography.level == geography_level
                and fact.measure.concept == concept
                for fact in facts
            )
        }
        matching_facts = [
            fact
            for fact in facts_by_alias[expected_alias]
            if fact.source.source_name == source_name
            and fact.geography.level == geography_level
            and fact.measure.concept == concept
        ]

        assert matching_aliases == {expected_alias}
        assert len(matching_facts) == expected_count


def test_belgium_subnational_facts_carry_current_vintages():
    population = _facts("statbel-population-structure-2026", 2026)
    fiscal = _facts("statbel-fiscal-income-2023-nis-2025", 2023)

    assert {fact.geography.vintage for fact in population} == {"NUTS_2024"}
    assert {fact.geography.level for fact in fiscal} == {"commune"}
    assert {fact.geography.vintage for fact in fiscal} == {"nis_2025"}


def test_belgium_period_basis_is_preserved_by_source():
    periods_by_alias = {
        alias: {(fact.period.type, fact.period.value) for fact in _facts(alias, year)}
        for alias, year, *_rest in BELGIUM_TARGET_STREAMS
    }

    assert periods_by_alias["statbel-population-structure-2026"] == {
        ("calendar_year", 2026)
    }
    assert periods_by_alias["statbel-fiscal-income-2023-nis-2025"] == {
        ("tax_year", 2023)
    }
    assert periods_by_alias["spf-finances-pit-2023"] == {("tax_year", 2023)}
    assert periods_by_alias["onss-contributions-2024"] == {("calendar_year", 2024)}
    assert periods_by_alias["onem-rva-unemployment-2024"] == {
        ("calendar_year", 2024)
    }
    assert periods_by_alias[
        "nbb-national-accounts-household-disposable-income-2024"
    ] == {("calendar_year", 2024)}


def test_belgium_nis_2025_crosswalk_round_trips_merged_communes():
    crosswalk = _csv_rows(
        REPO_ROOT
        / "db"
        / "data"
        / "statbel"
        / "nis_2025_commune_crosswalk"
        / "statbel_nis_2025_commune_crosswalk.csv"
    )
    fiscal_rows = _csv_rows(
        REPO_ROOT
        / "db"
        / "data"
        / "statbel"
        / "fiscal_income_commune_2023_nis_2025"
        / "statbel_fiscal_income_commune_2023_nis_2025.csv"
    )
    merged_sources_by_target: dict[str, set[str]] = {}
    for row in crosswalk:
        if row["relationship"] == "merged":
            merged_sources_by_target.setdefault(row["target_nis"], set()).add(
                row["source_nis"]
            )
    fiscal_by_geo = {row["geography_id"]: row for row in fiscal_rows}

    assert len(crosswalk) == 581
    assert sum(row["relationship"] == "merged" for row in crosswalk) == 30
    assert len(fiscal_rows) == 565
    assert merged_sources_by_target["82039"] == {"82003", "82005"}
    assert fiscal_by_geo["82039"]["source_nis_codes"] == "82003;82005"
    assert fiscal_by_geo["82039"]["geography_name"] == "Bastogne"
    assert merged_sources_by_target["46030"] == {"11056", "46003", "46013"}
    assert fiscal_by_geo["46030"]["source_nis_codes"] == "11056;46003;46013"
