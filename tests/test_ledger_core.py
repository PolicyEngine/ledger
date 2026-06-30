"""Tests for canonical Ledger aggregate facts."""

from __future__ import annotations

from ledger.core import (
    Aggregation,
    EntityDimension,
    GeographyDimension,
    Measure,
    PeriodDimension,
    SourceProvenance,
    SourceRecordLayout,
    AggregateFact,
    build_label,
    build_fact_key,
    validate_fact,
    validate_facts,
)


def _fact(**overrides):
    fact = AggregateFact(
        value=1000,
        period=PeriodDimension(type="tax_year", value=2023),
        geography=GeographyDimension(
            level="country",
            id="0100000US",
            vintage="2020_census",
            name="United States",
        ),
        entity=EntityDimension(name="tax_unit", role="filing_unit"),
        measure=Measure(concept="irs_soi.adjusted_gross_income", unit="usd"),
        aggregation=Aggregation(method="sum"),
        filters={"filing_status": "all"},
        source=SourceProvenance(
            source_name="irs_soi",
            source_table="Publication 1304 Table 1.1",
            source_file="23in11si.xls",
            url="https://www.irs.gov/statistics/soi-tax-stats",
            vintage="tax_year_2023",
            extracted_at="2026-05-04",
            extraction_method="fixture hand entry",
            method_notes="Fixture value for schema tests.",
        ),
        label="United States tax year 2023 sum adjusted gross income",
    )
    return AggregateFact(**{**fact.__dict__, **overrides})


def test_valid_fact_passes_validation():
    assert validate_fact(_fact()) == ()
    assert validate_facts([_fact()]).valid


def test_stable_key_ignores_human_label():
    fact = _fact()
    relabeled = _fact(label="A different display label")

    assert build_fact_key(fact) == build_fact_key(relabeled)


def test_stable_key_ignores_source_table_layout():
    fact = _fact()
    with_layout = _fact(
        layout=SourceRecordLayout(
            record_set_id="irs_soi.ty2023.table_1_1",
            groupby_value_id="all",
            groupby_ordinal=0,
            measure_id="adjusted_gross_income",
            measure_ordinal=1,
        )
    )

    assert build_fact_key(fact) == build_fact_key(with_layout)


def test_duplicate_key_is_reported():
    report = validate_facts([_fact(), _fact(label="Different label")])

    assert not report.valid
    assert [error.code for error in report.errors] == ["duplicate_key"]


def test_missing_provenance_is_reported():
    fact = _fact(
        source=SourceProvenance(
            source_name=None,
            vintage=None,
            extracted_at=None,
            extraction_method=None,
        )
    )

    error_codes = {error.code for error in validate_fact(fact)}

    assert "missing_field" in error_codes
    assert "missing_provenance" in error_codes


def test_malformed_geography_entity_and_aggregation_are_reported():
    fact = _fact(
        geography=GeographyDimension(level="planet", id="earth"),
        entity=EntityDimension(name="simulator_row"),
        aggregation=Aggregation(method="magic"),
    )

    errors = validate_fact(fact)
    error_codes = {error.code for error in errors}

    assert "malformed_geography" in error_codes
    assert "malformed_entity" in error_codes
    assert "malformed_aggregation" in error_codes


def test_source_concept_requires_relation():
    fact = _fact(
        measure=Measure(
            concept="us:statutes/26/62#adjusted_gross_income",
            unit="usd",
            source_concept="irs_soi.adjusted_gross_income",
        )
    )

    errors = validate_fact(fact)

    assert "missing_field" in {error.code for error in errors}


def test_label_generation_uses_metadata_not_key_path():
    fact = _fact(label=None)

    assert build_label(fact) == (
        "United States 2023 tax year sum irs soi adjusted gross income "
        "for tax unit (filing status=all) "
        "[irs_soi Publication 1304 Table 1.1 23in11si.xls tax_year_2023]"
    )
