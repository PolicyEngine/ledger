"""Tests for source-backed SSA Annual Statistical Supplement loader."""

from sqlmodel import Session, select

from db.etl_ssa_supplement import (
    available_ssa_supplement_years,
    load_ssa_supplement_data,
    load_ssa_supplement_targets,
)
from db.schema import DataSource, GeographicLevel, Target, TargetType, init_db


def test_available_ssa_supplement_years():
    assert available_ssa_supplement_years() == [2024]


def test_load_ssa_supplement_data_reads_packaged_rows():
    rows = {row["variable"]: row for row in load_ssa_supplement_data()}

    assert rows["social_security_benefits"]["value"] == 1_471_195_000_000
    assert rows["social_security_retirement_benefits"]["value"] == 1_111_728_000_000
    assert rows["social_security_survivors_benefits"]["value"] == 161_218_000_000
    assert rows["social_security_disability_benefits"]["value"] == 147_174_000_000
    assert rows["social_security_dependents_benefits"]["value"] == 51_075_000_000
    assert rows["ssi_payments"]["value"] == 63_079_493_000


def test_load_ssa_supplement_targets_creates_national_targets(tmp_path):
    engine = init_db(tmp_path / "targets.db")

    with Session(engine) as session:
        load_ssa_supplement_targets(session, years=[2024])
        target = session.exec(
            select(Target).where(
                Target.variable == "social_security_dependents_benefits",
                Target.period == 2024,
            )
        ).one()

    assert target.value == 51_075_000_000
    assert target.target_type == TargetType.AMOUNT
    assert target.geographic_level == GeographicLevel.NATIONAL
    assert target.source == DataSource.SSA
    assert target.source_table == "SSA Annual Statistical Supplement 2025 Table 4.A5 and 4.A6"


def test_load_ssa_supplement_targets_is_idempotent(tmp_path):
    engine = init_db(tmp_path / "targets.db")

    with Session(engine) as session:
        load_ssa_supplement_targets(session, years=[2024])
        load_ssa_supplement_targets(session, years=[2024])
        targets = session.exec(
            select(Target).where(
                Target.variable == "social_security_benefits",
                Target.period == 2024,
            )
        ).all()

    assert len(targets) == 1
