"""Tests for US poverty/nonfiler source-target coverage."""

from __future__ import annotations

from pathlib import Path

from ledger.source_package import SOURCE_PACKAGE_ALIASES, load_source_package
from ledger.targets.us_poverty import (
    coverage_entries,
    hard_target_package_aliases,
    source_gap_family_ids,
    validate_us_poverty_nonfiler_source_coverage,
    validation_only_family_ids,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_us_poverty_hard_target_aliases_are_registered_and_packaged():
    errors = validate_us_poverty_nonfiler_source_coverage(
        package_root=REPO_ROOT / "packages",
    )

    assert errors == ()


def test_us_poverty_all_named_package_aliases_are_registered():
    aliases = {alias for entry in coverage_entries() for alias in entry.package_aliases}

    assert aliases <= set(SOURCE_PACKAGE_ALIASES)


def test_us_poverty_hard_target_aliases_cover_required_sources():
    aliases = set(hard_target_package_aliases())

    assert "bea-nipa-personal-income-components" in aliases
    assert "bea-nipa-personal-income-disposition" in aliases
    assert "bea-nipa-pension-contributions" in aliases
    assert "soi-filing-season-week47-2024-eitc-total" in aliases
    assert "usda-snap-fy69-to-current" in aliases
    assert "ssa-ssi-table-7b1-2024" in aliases
    assert "hhs-acf-tanf-financial-2024" in aliases
    assert "cms-medicaid-chip-monthly-enrollment-dataset" in aliases


def test_existing_bea_pension_package_has_public_alias():
    package = load_source_package("bea-nipa-pension-contributions")

    assert SOURCE_PACKAGE_ALIASES["bea-nipa-pension-contributions"] == Path(
        "bea/nipa_pension_contributions"
    )
    assert package.package_id == "bea-nipa-pension-contributions"


def test_cps_and_dina_are_validation_only_not_hard_targets():
    hard_target_ids = {
        entry.family_id for entry in coverage_entries(role="hard_target")
    }
    validation_ids = set(validation_only_family_ids())

    assert "census_cps_spm" not in hard_target_ids
    assert "dina_distributional_accounts" not in hard_target_ids
    assert "census_cps_spm" in validation_ids
    assert "dina_distributional_accounts" in validation_ids


def test_us_poverty_source_gaps_include_spm_specific_components():
    gaps = set(source_gap_family_ids())

    assert {
        "hud_assisted_housing",
        "usda_wic",
        "usda_school_meals",
        "ocse_child_support",
        "dol_workers_compensation",
        "moop_work_childcare_costs",
    }.issubset(gaps)
