"""Tests for IRS SOI Form W-2 statistics loader."""

import pytest
from sqlmodel import Session, select

from db.etl_soi_w2 import (
    SOURCE_TABLE_PREFIX,
    VARIABLE,
    available_soi_w2_years,
    load_soi_w2_targets,
    load_soi_w2_tip_income_data,
)
from db.schema import DataSource, GeographicLevel, StratumConstraint, Target, TargetType, init_db


def test_available_soi_w2_years():
    assert available_soi_w2_years() == [
        2008,
        2009,
        2010,
        2011,
        2012,
        2013,
        2014,
        2015,
        2016,
        2017,
        2018,
        2020,
    ]


def test_load_soi_w2_tip_income_data_reads_packaged_sources():
    prior = load_soi_w2_tip_income_data(2018)
    current = load_soi_w2_tip_income_data(2020)

    assert prior["source_url"] == "https://www.irs.gov/pub/irs-soi/18inallw2.xls"
    assert prior["source_table"] == f"{SOURCE_TABLE_PREFIX} Table 5.A"
    assert prior["social_security_tips"] == 38_316_190_000
    assert prior["returns"] == 6_056_757
    assert prior["taxpayers"] == 6_131_222
    assert current["source_url"] == "https://www.irs.gov/pub/irs-soi/20in04w2all.xlsx"
    assert current["source_table"] == f"{SOURCE_TABLE_PREFIX} Table 4.B"
    assert current["social_security_tips"] == 26_786_522_000


def test_load_soi_w2_targets_creates_tip_income_target(tmp_path):
    engine = init_db(tmp_path / "targets.db")

    with Session(engine) as session:
        load_soi_w2_targets(session, years=[2020])
        target = session.exec(
            select(Target).where(
                Target.variable == VARIABLE,
                Target.period == 2020,
                Target.geographic_level == GeographicLevel.NATIONAL,
            )
        ).one()
        tip_constraint = session.exec(
            select(StratumConstraint).where(
                StratumConstraint.stratum_id == target.stratum_id,
                StratumConstraint.variable == "tip_income",
            )
        ).one()

    assert target.value == pytest.approx(26_786_522_000)
    assert target.target_type == TargetType.AMOUNT
    assert target.source == DataSource.IRS_SOI
    assert target.source_table == f"{SOURCE_TABLE_PREFIX} Table 4.B"
    assert tip_constraint.operator == ">"
    assert tip_constraint.value == "0"


def test_load_soi_w2_targets_is_idempotent(tmp_path):
    engine = init_db(tmp_path / "targets.db")

    with Session(engine) as session:
        load_soi_w2_targets(session, years=[2018, 2020])
        load_soi_w2_targets(session, years=[2018, 2020])
        targets = session.exec(
            select(Target).where(Target.variable == VARIABLE)
        ).all()

    assert len(targets) == 2
