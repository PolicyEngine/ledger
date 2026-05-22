"""Tests for IRS SOI IRA contribution loader."""

import pytest
from sqlmodel import Session, select

from db.etl_soi_ira import (
    available_soi_ira_years,
    load_soi_ira_contribution_data,
    load_soi_ira_targets,
)
from db.schema import DataSource, GeographicLevel, StratumConstraint, Target, TargetType, init_db


def test_available_soi_ira_years():
    assert available_soi_ira_years() == [2022]
    assert available_soi_ira_years("traditional_ira_contributions") == [2022]
    assert available_soi_ira_years("roth_ira_contributions") == [2022]


def test_load_soi_ira_contribution_data_reads_packaged_sources():
    traditional = load_soi_ira_contribution_data(
        "traditional_ira_contributions",
        2022,
    )
    roth = load_soi_ira_contribution_data("roth_ira_contributions", 2022)

    assert traditional["amount"] == 23_034_199_000
    assert traditional["taxpayers"] == 5_101_648
    assert traditional["source_url"] == "https://www.irs.gov/pub/irs-soi/22in05ira.xlsx"
    assert roth["amount"] == 34_951_077_000
    assert roth["taxpayers"] == 10_036_960
    assert roth["source_url"] == "https://www.irs.gov/pub/irs-soi/22in06ira.xlsx"


def test_load_soi_ira_targets_creates_contribution_targets(tmp_path):
    engine = init_db(tmp_path / "targets.db")

    with Session(engine) as session:
        load_soi_ira_targets(session, years=[2022])
        targets = session.exec(
            select(Target).where(
                Target.period == 2022,
                Target.geographic_level == GeographicLevel.NATIONAL,
            )
        ).all()

    values = {target.variable: target.value for target in targets}
    assert values == {
        "traditional_ira_contributions": pytest.approx(23_034_199_000),
        "roth_ira_contributions": pytest.approx(34_951_077_000),
    }
    assert {target.target_type for target in targets} == {TargetType.AMOUNT}
    assert {target.source for target in targets} == {DataSource.IRS_SOI}


def test_load_soi_ira_targets_adds_positive_variable_constraints(tmp_path):
    engine = init_db(tmp_path / "targets.db")

    with Session(engine) as session:
        load_soi_ira_targets(session, years=[2022])
        target = session.exec(
            select(Target).where(Target.variable == "roth_ira_contributions")
        ).one()
        constraint = session.exec(
            select(StratumConstraint).where(
                StratumConstraint.stratum_id == target.stratum_id,
                StratumConstraint.variable == "roth_ira_contributions",
            )
        ).one()

    assert constraint.operator == ">"
    assert constraint.value == "0"


def test_load_soi_ira_targets_is_idempotent(tmp_path):
    engine = init_db(tmp_path / "targets.db")

    with Session(engine) as session:
        load_soi_ira_targets(session, years=[2022])
        load_soi_ira_targets(session, years=[2022])
        targets = session.exec(select(Target)).all()

    assert len(targets) == 2
