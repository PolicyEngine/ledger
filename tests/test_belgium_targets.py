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
EUROMOD_BE_COMPARATOR_ALIAS = "jrc-euromod-be-baseline-statistics-2025"


@lru_cache
def _facts(alias: str, year: int):
    return tuple(load_source_package(alias).build_facts(year))


def _csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_belgium_target_aliases_are_registered():
    aliases = {alias for alias, *_rest in BELGIUM_TARGET_STREAMS}
    aliases.add(EUROMOD_BE_COMPARATOR_ALIAS)

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


def test_belgium_euromod_comparator_has_source_urls_per_row():
    comparator_rows = _csv_rows(
        REPO_ROOT
        / "db"
        / "data"
        / "jrc"
        / "euromod_be_baseline_statistics_2025"
        / "jrc_euromod_be_baseline_statistics_2025.csv"
    )
    facts = _facts(EUROMOD_BE_COMPARATOR_ALIAS, 2025)

    assert len(comparator_rows) == 18
    assert len(facts) == 18
    assert {row["source_url"] for row in comparator_rows} == {
        "https://euromod-web.jrc.ec.europa.eu/sites/default/files/2025-02/Y15_CR_BE_final.pdf"
    }
    assert {fact.source.source_name for fact in facts} == {"jrc_euromod_be"}
    assert {fact.geography.id for fact in facts} == {"BE"}
    assert {fact.measure.unit for fact in facts} == {"eur", "percent", "ratio"}
    assert validate_facts(facts).valid


SFPD_PENSION_ALIAS = "sfpd-legal-pension-caseload-2025"
GROEIPAKKET_ALIAS = "opgroeien-groeipakket-caseload-2025"
BFP_OUTLOOK_ALIAS = "bfp-economic-outlook-2026-06"


def test_belgium_supplementary_publisher_aliases_are_registered():
    assert {SFPD_PENSION_ALIAS, GROEIPAKKET_ALIAS, BFP_OUTLOOK_ALIAS} <= set(
        SOURCE_PACKAGE_ALIASES
    )


def test_sfpd_legal_pension_caseload_matches_published_cells():
    facts = _facts(SFPD_PENSION_ALIAS, 2025)
    by_scheme = {fact.filters["sfpd.scheme"]: fact.value for fact in facts}

    # Exact published counts from PensionStat.be (SFP/SFPD), January 2025.
    assert by_scheme == {
        "all": 2674520,
        "employee": 2357954,
        "self_employed": 690590,
        "civil_servant": 604506,
    }
    # Scheme counts are per-scheme recipients (mixed careers), not a partition:
    # their sum exceeds the all-schemes total.
    scheme_sum = sum(v for k, v in by_scheme.items() if k != "all")
    assert scheme_sum > by_scheme["all"]
    assert {fact.source.source_name for fact in facts} == {"sfpd_pensions"}
    assert {fact.geography.level for fact in facts} == {"country"}
    assert {fact.measure.unit for fact in facts} == {"count"}
    assert validate_facts(facts).valid


def test_groeipakket_caseload_matches_published_component_cells():
    facts = _facts(GROEIPAKKET_ALIAS, 2025)
    children = {
        fact.filters["groeipakket.component"]: fact.value
        for fact in facts
        if fact.measure.concept == "groeipakket_children_receiving_component"
    }
    families = {
        fact.filters["groeipakket.component"]: fact.value
        for fact in facts
        if fact.measure.concept == "groeipakket_families_receiving_component"
    }

    # Exact published caseload cells from Opgroeien (Flemish agency).
    assert children == {
        "social_supplement": 522148,
        "orphan_supplement": 21741,
        "care_supplement": 51261,
        "foster_care_supplement": 7348,
        "school_allowance": 499339,
        "support_supplement": 8735,
    }
    assert families == {
        "social_supplement": 281551,
        "orphan_supplement": 14824,
        "care_supplement": 46748,
        "foster_care_supplement": 5891,
        "basic_amount": 930010,
    }
    # basisbedrag child count is published only as a rounded ">1.6M" lower bound,
    # so it is intentionally omitted from the child record set (recorded as a gap).
    assert "basic_amount" not in children
    assert {fact.geography.id for fact in facts} == {"BE2"}
    assert {fact.geography.vintage for fact in facts} == {"NUTS_2024"}
    assert validate_facts(facts).valid


def test_bfp_economic_outlook_facts_are_typed_source_projection():
    facts = _facts(BFP_OUTLOOK_ALIAS, 2026)
    by_key = {
        (fact.period.value, fact.measure.concept): fact.value for fact in facts
    }

    # Exact published headline figures from the BFP June 2026 outlook.
    assert by_key == {
        (2026, "bfp.real_gdp_growth_projection"): 0.7,
        (2026, "bfp.consumer_price_inflation_projection"): 3.4,
        (2026, "bfp.general_government_deficit_pct_gdp_projection"): 5.1,
        (2031, "bfp.consumer_price_inflation_projection"): 1.7,
        (2031, "bfp.general_government_deficit_pct_gdp_projection"): 6.4,
    }
    # Publisher projections must be typed source_projection, never observation.
    assert {fact.assertion for fact in facts} == {"source_projection"}
    assert {fact.source.source_name for fact in facts} == {"bfp_economic_outlook"}
    assert {fact.geography.id for fact in facts} == {"BE"}
    assert validate_facts(facts).valid
