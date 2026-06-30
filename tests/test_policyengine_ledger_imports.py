from policyengine_ledger import (
    AggregateFact,
    Aggregation,
    EntityDimension,
    GeographyDimension,
    Measure,
    PeriodDimension,
    SourceProvenance,
    build_fact_key,
    validate_fact,
)
import policyengine_ledger.normalization as ledger_normalization
from policyengine_ledger.cli import main as ledger_main
from policyengine_ledger.targets.us_poverty import hard_target_package_aliases
import pytest


def test__given_ledger_import_path__then_it_reexports_ledger_fact_schema() -> None:
    # Given
    fact = AggregateFact(
        value=1,
        period=PeriodDimension(type="calendar_year", value=2024),
        geography=GeographyDimension(level="country", id="0100000US"),
        entity=EntityDimension(name="person"),
        measure=Measure(concept="test.people", unit="count"),
        aggregation=Aggregation(method="sum"),
        source=SourceProvenance(
            source_name="test",
            source_table="Fixture",
            vintage="2024",
            extracted_at="2026-06-14",
            extraction_method="unit test",
        ),
    )

    # When
    issues = validate_fact(fact)
    key = build_fact_key(fact)

    # Then
    assert not issues
    assert key.startswith("ledger.fact.v1:")


def test__given_ledger_facts_import_path__then_it_reexports_ledger_facts() -> None:
    # When
    from ledger.facts import AggregateFact as LedgerCoreAggregateFact
    from policyengine_ledger.facts import AggregateFact as LedgerAggregateFact

    # Then
    assert LedgerAggregateFact is LedgerCoreAggregateFact


def test__given_ledger_target_import_path__then_it_reexports_target_contracts() -> None:
    # When
    aliases = hard_target_package_aliases()

    # Then
    assert "soi-table-1-1" in aliases
    assert "ssa-ssi-table-7b1-2024" in aliases


def test__given_public_ledger_namespaces__then_core_helpers_are_importable() -> None:
    from policyengine_ledger.normalization import convert_units
    from policyengine_ledger.sources import SourceFile, query_sources
    from policyengine_ledger.target_profiles import load_target_profile

    assert SourceFile is not None
    assert query_sources is not None
    assert convert_units is not None
    assert load_target_profile is not None


def test__given_public_ledger_normalization__then_target_construction_is_hidden() -> (
    None
):
    with pytest.raises(AttributeError):
        getattr(ledger_normalization, "as_target")
    with pytest.raises(AttributeError):
        getattr(ledger_normalization, "target_kwargs")


def test__given_ledger_help__then_cli_does_not_eager_load_legacy_clients(
    monkeypatch,
    capsys,
) -> None:
    # Given
    monkeypatch.setattr("sys.argv", ["ledger", "--help"])

    # When
    ledger_main()

    # Then
    output = capsys.readouterr().out
    assert "Usage: ledger <command> [options]" in output
    assert "validate-facts" in output
