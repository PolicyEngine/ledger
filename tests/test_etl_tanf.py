"""Tests for HHS ACF TANF financial loader."""

import pytest
from sqlmodel import Session, select

from db.etl_tanf import (
    SOURCE_TABLE,
    VARIABLE,
    available_tanf_financial_years,
    load_tanf_financial_data,
    load_tanf_targets,
)
from db.schema import DataSource, GeographicLevel, Target, TargetType, init_db


def test_available_tanf_financial_years():
    assert available_tanf_financial_years() == [2024]


def test_load_tanf_financial_data_reads_packaged_workbook():
    data = load_tanf_financial_data(2024)

    assert data["source_url"] == "https://acf.gov/ofa/data/tanf-financial-data-fy-2024"
    assert data["national_cash_assistance"] == pytest.approx(7_788_317_474.55)
    assert data["states"]["CA"] == pytest.approx(3_742_540_224.36)
    assert data["states"]["DC"] == pytest.approx(45_666_113.50)
    assert len(data["states"]) == 51


def test_load_tanf_targets_creates_national_cash_assistance(tmp_path):
    engine = init_db(tmp_path / "targets.db")

    with Session(engine) as session:
        load_tanf_targets(session, years=[2024])
        target = session.exec(
            select(Target).where(
                Target.variable == VARIABLE,
                Target.period == 2024,
                Target.geographic_level == GeographicLevel.NATIONAL,
            )
        ).one()

    assert target.value == pytest.approx(7_788_317_474.55)
    assert target.target_type == TargetType.AMOUNT
    assert target.source == DataSource.HHS_ACF_TANF
    assert target.source_table == SOURCE_TABLE


def test_load_tanf_targets_creates_state_cash_assistance(tmp_path):
    engine = init_db(tmp_path / "targets.db")

    with Session(engine) as session:
        load_tanf_targets(session, years=[2024])
        state_targets = session.exec(
            select(Target).where(
                Target.variable == VARIABLE,
                Target.period == 2024,
                Target.geographic_level == GeographicLevel.STATE,
            )
        ).all()

    assert len(state_targets) == 51
    assert any(
        target.value == pytest.approx(3_742_540_224.36)
        and target.source == DataSource.HHS_ACF_TANF
        for target in state_targets
    )


def test_load_tanf_targets_is_idempotent(tmp_path):
    engine = init_db(tmp_path / "targets.db")

    with Session(engine) as session:
        load_tanf_targets(session, years=[2024])
        load_tanf_targets(session, years=[2024])
        targets = session.exec(
            select(Target).where(
                Target.variable == VARIABLE,
                Target.period == 2024,
            )
        ).all()

    assert len(targets) == 52
