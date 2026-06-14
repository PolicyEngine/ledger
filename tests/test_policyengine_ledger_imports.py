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
from policyengine_ledger.targets.us_poverty import hard_target_package_aliases


def test__given_ledger_import_path__then_it_reexports_arch_fact_schema() -> None:
    # Given
    fact = AggregateFact(
        value=1,
        period=PeriodDimension(type="calendar_year", value=2024),
        geography=GeographyDimension(level="country", id="0100000US"),
        entity=EntityDimension(name="person"),
        measure=Measure(concept="test.people", unit="count"),
        aggregation=Aggregation(method="count"),
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
    assert key.startswith("arch.fact.v1:")


def test__given_ledger_facts_import_path__then_it_reexports_arch_facts() -> None:
    # When
    from arch.facts import AggregateFact as ArchAggregateFact
    from policyengine_ledger.facts import AggregateFact as LedgerAggregateFact

    # Then
    assert LedgerAggregateFact is ArchAggregateFact


def test__given_ledger_target_import_path__then_it_reexports_target_contracts() -> None:
    # When
    aliases = hard_target_package_aliases()

    # Then
    assert "soi-table-1-1" in aliases
    assert "ssa-ssi-table-7b1-2024" in aliases
