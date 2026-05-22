"""Tests for target rollup utilities."""

from pathlib import Path

import pytest
from sqlmodel import Session, select

from db.rollups import roll_up_state_targets_to_national
from db.schema import (
    DataSource,
    Jurisdiction,
    Stratum,
    StratumConstraint,
    Target,
    TargetType,
    init_db,
)


@pytest.fixture
def session(tmp_path):
    engine = init_db(Path(tmp_path) / "targets.db")
    with Session(engine) as session:
        yield session


def _state_stratum(
    session: Session,
    *,
    state_fips: str,
    name: str,
) -> Stratum:
    constraints = [("is_tax_filer", "==", "1"), ("state_fips", "==", state_fips)]
    stratum = Stratum(
        name=name,
        jurisdiction=Jurisdiction.US,
        definition_hash=Stratum.compute_hash(constraints, Jurisdiction.US),
    )
    session.add(stratum)
    session.flush()
    for variable, operator, value in constraints:
        session.add(
            StratumConstraint(
                stratum_id=stratum.id,
                variable=variable,
                operator=operator,
                value=value,
            )
        )
    session.flush()
    return stratum


def test_roll_up_state_targets_to_national_sums_one_value_per_state(session):
    ca = _state_stratum(session, state_fips="06", name="CA Filers")
    ny = _state_stratum(session, state_fips="36", name="NY Filers")
    session.add_all(
        [
            Target(
                stratum_id=ca.id,
                variable="medical_claims",
                period=2021,
                value=10,
                target_type=TargetType.COUNT,
                source=DataSource.IRS_SOI,
                source_table="State itemized deductions",
            ),
            Target(
                stratum_id=ny.id,
                variable="medical_claims",
                period=2021,
                value=15,
                target_type=TargetType.COUNT,
                source=DataSource.IRS_SOI,
                source_table="State itemized deductions",
            ),
        ]
    )
    session.commit()

    results = roll_up_state_targets_to_national(
        session,
        source=DataSource.IRS_SOI,
        variables=["medical_claims"],
        years=[2021],
        min_state_count=2,
    )

    assert len(results) == 1
    assert results[0].created is True
    assert results[0].state_count == 2
    assert results[0].value == 25

    national = session.exec(
        select(Stratum).where(Stratum.name == "US All Filers")
    ).first()
    target = session.exec(
        select(Target)
        .where(Target.stratum_id == national.id)
        .where(Target.variable == "medical_claims")
    ).one()
    assert target.value == 25
    assert target.notes.startswith("Derived in Arch as a sum of 2 state")


def test_roll_up_state_targets_to_national_is_idempotent(session):
    ca = _state_stratum(session, state_fips="06", name="CA Filers")
    ny = _state_stratum(session, state_fips="36", name="NY Filers")
    for stratum, value in ((ca, 10), (ny, 15)):
        session.add(
            Target(
                stratum_id=stratum.id,
                variable="qbi_amount",
                period=2021,
                value=value,
                target_type=TargetType.AMOUNT,
                source=DataSource.IRS_SOI,
                source_table="State deductions",
            )
        )
    session.commit()

    roll_up_state_targets_to_national(
        session,
        source="IRS_SOI",
        variables=["qbi_amount"],
        years=[2021],
        min_state_count=2,
    )
    second = roll_up_state_targets_to_national(
        session,
        source="IRS_SOI",
        variables=["qbi_amount"],
        years=[2021],
        min_state_count=2,
    )

    assert second[0].created is False
    assert len(
        session.exec(select(Target).where(Target.variable == "qbi_amount")).all()
    ) == 3


def test_roll_up_state_targets_to_national_respects_min_state_count(session):
    ca = _state_stratum(session, state_fips="06", name="CA Filers")
    session.add(
        Target(
            stratum_id=ca.id,
            variable="salt_amount",
            period=2021,
            value=10,
            target_type=TargetType.AMOUNT,
            source=DataSource.IRS_SOI,
            source_table="State deductions",
        )
    )
    session.commit()

    results = roll_up_state_targets_to_national(
        session,
        source=DataSource.IRS_SOI,
        variables=["salt_amount"],
        years=[2021],
        min_state_count=2,
    )

    assert results == []
