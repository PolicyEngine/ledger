"""Tests for Census PEP source-backed population loader."""

from sqlmodel import Session, select

from db.etl_census_pep import (
    available_census_pep_population_years,
    load_census_pep_population_data,
    load_census_pep_population_targets,
)
from db.schema import DataSource, Stratum, Target, TargetType, init_db


def test_available_census_pep_population_years():
    assert available_census_pep_population_years() == [2020, 2021, 2022, 2023, 2024]


def test_load_census_pep_population_data_reads_packaged_2024_sources():
    data = load_census_pep_population_data(2024)

    assert data["source_urls"] == {
        "national": (
            "https://www2.census.gov/programs-surveys/popest/datasets/"
            "2020-2024/national/asrh/nc-est2024-agesex-res.csv"
        ),
        "state": (
            "https://www2.census.gov/programs-surveys/popest/datasets/"
            "2020-2024/state/asrh/sc-est2024-alldata6.csv"
        ),
    }
    assert data["national"]["total"] == 340_110_988
    assert data["national"]["age_groups"]["0_to_4"] == 18_599_314
    assert data["national"]["age_groups"]["5_to_9"] == 20_197_672
    assert data["national"]["age_groups"]["85_plus"] == 6_435_143
    assert data["states"]["CA"]["total"] == 39_431_263
    assert data["states"]["CA"]["age_groups"]["0_to_4"] == 2_087_677
    assert data["states"]["CA"]["age_groups"]["5_to_9"] == 2_316_903
    assert data["states"]["CA"]["age_groups"]["85_plus"] == 728_742


def test_load_census_pep_population_targets_creates_national_age_targets(tmp_path):
    engine = init_db(tmp_path / "targets.db")

    with Session(engine) as session:
        load_census_pep_population_targets(session, years=[2024])
        age_stratum = session.exec(
            select(Stratum).where(Stratum.name == "US resident population age 85+")
        ).one()
        age_target = session.exec(
            select(Target).where(
                Target.stratum_id == age_stratum.id,
                Target.variable == "population",
                Target.period == 2024,
            )
        ).one()

    assert age_target.value == 6_435_143
    assert age_target.target_type == TargetType.COUNT
    assert age_target.source == DataSource.CENSUS_PEP
    assert age_target.source_table == (
        "Census PEP Vintage 2024 age-sex population estimates"
    )


def test_load_census_pep_population_targets_creates_state_age_targets(tmp_path):
    engine = init_db(tmp_path / "targets.db")

    with Session(engine) as session:
        load_census_pep_population_targets(session, years=[2024])
        ca_age_stratum = session.exec(
            select(Stratum).where(Stratum.name == "CA resident population age 0-4")
        ).one()
        ca_age_target = session.exec(
            select(Target).where(
                Target.stratum_id == ca_age_stratum.id,
                Target.variable == "population",
                Target.period == 2024,
            )
        ).one()
        constraints = {
            (constraint.variable, constraint.operator, constraint.value)
            for constraint in ca_age_stratum.constraints
        }

    assert ca_age_target.value == 2_087_677
    assert ca_age_target.target_type == TargetType.COUNT
    assert ca_age_target.source == DataSource.CENSUS_PEP
    assert constraints == {
        ("age", ">=", "0"),
        ("age", "<", "5"),
        ("state_fips", "==", "06"),
    }


def test_load_census_pep_population_targets_is_idempotent(tmp_path):
    engine = init_db(tmp_path / "targets.db")

    with Session(engine) as session:
        load_census_pep_population_targets(session, years=[2024])
        first_count = len(session.exec(select(Target)).all())
        load_census_pep_population_targets(session, years=[2024])
        second_count = len(session.exec(select(Target)).all())

    assert first_count == 988
    assert second_count == first_count
