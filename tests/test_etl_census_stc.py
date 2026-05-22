"""Tests for Census STC state income-tax collection loader."""

from sqlmodel import Session, select

from db.etl_census_stc import (
    available_census_stc_income_tax_years,
    load_census_stc_income_tax_data,
    load_census_stc_income_tax_targets,
)
from db.schema import DataSource, Stratum, Target, TargetType, init_db


def test_available_census_stc_income_tax_years():
    assert available_census_stc_income_tax_years() == [2023, 2024]


def test_load_census_stc_income_tax_data_reads_packaged_2024_source():
    data = load_census_stc_income_tax_data(2024)

    assert data["source_url"] == (
        "https://www2.census.gov/programs-surveys/stc/datasets/2024/"
        "FY2024-Flat-File.txt"
    )
    assert data["national_total"] == 479_627_360_000
    assert data["states"]["CA"] == {
        "state_fips": "06",
        "state_abbrev": "CA",
        "value": 123_101_651_000,
    }
    assert data["states"]["NY"]["value"] == 53_840_077_000
    assert data["states"]["NH"]["value"] == 183_359_000
    assert data["states"]["TX"]["value"] == 0
    assert data["states"]["WY"]["value"] == 0


def test_load_census_stc_income_tax_data_reads_packaged_2023_source():
    data = load_census_stc_income_tax_data(2023)

    assert data["source_url"] == (
        "https://www2.census.gov/programs-surveys/stc/datasets/2023/"
        "FY2023-Flat-File.txt"
    )
    assert data["national_total"] == 461_729_077_000
    assert data["states"]["CA"]["value"] == 96_379_294_000
    assert data["states"]["NY"]["value"] == 58_775_670_000
    assert data["states"]["NH"]["value"] == 149_485_000
    assert data["states"]["TX"]["value"] == 0


def test_load_census_stc_income_tax_targets_creates_state_targets(tmp_path):
    engine = init_db(tmp_path / "targets.db")

    with Session(engine) as session:
        load_census_stc_income_tax_targets(session, years=[2024])
        ca_stratum = session.exec(
            select(Stratum).where(Stratum.name == "CA state government")
        ).one()
        target = session.exec(
            select(Target).where(
                Target.stratum_id == ca_stratum.id,
                Target.variable == "state_individual_income_tax_collections",
                Target.period == 2024,
            )
        ).one()
        constraints = {
            (constraint.variable, constraint.operator, constraint.value)
            for constraint in ca_stratum.constraints
        }

    assert target.value == 123_101_651_000
    assert target.target_type == TargetType.AMOUNT
    assert target.source == DataSource.CENSUS_STC
    assert target.geographic_level == "state"
    assert constraints == {("state_fips", "==", "06")}


def test_load_census_stc_income_tax_targets_preserves_zero_states(tmp_path):
    engine = init_db(tmp_path / "targets.db")

    with Session(engine) as session:
        load_census_stc_income_tax_targets(session, years=[2024])
        tx_stratum = session.exec(
            select(Stratum).where(Stratum.name == "TX state government")
        ).one()
        target = session.exec(
            select(Target).where(
                Target.stratum_id == tx_stratum.id,
                Target.variable == "state_individual_income_tax_collections",
                Target.period == 2024,
            )
        ).one()

    assert target.value == 0
    assert target.notes is not None
    assert "item T40" in target.notes


def test_load_census_stc_income_tax_targets_is_idempotent(tmp_path):
    engine = init_db(tmp_path / "targets.db")

    with Session(engine) as session:
        load_census_stc_income_tax_targets(session, years=[2024])
        first_count = len(session.exec(select(Target)).all())
        load_census_stc_income_tax_targets(session, years=[2024])
        second_count = len(session.exec(select(Target)).all())

    assert first_count == 51
    assert second_count == first_count
