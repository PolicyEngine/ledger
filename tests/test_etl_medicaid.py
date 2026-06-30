"""Tests for Medicaid enrollment ETL."""

import tempfile
from pathlib import Path

import pytest
from sqlmodel import Session, select

from db.schema import (
    DataSource,
    Stratum,
    Target,
    TargetType,
    init_db,
)
from db.etl_medicaid import load_medicaid_targets, MEDICAID_DATA


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_medicaid.db"
        engine = init_db(db_path)
        yield engine


class TestMedicaidETL:
    """Tests for Medicaid enrollment ETL loader."""

    def test_load_medicaid_creates_national_stratum(self, temp_db):
        """Loading Medicaid data should create a national stratum."""
        with Session(temp_db) as session:
            load_medicaid_targets(session, years=[2023])

            national = session.exec(
                select(Stratum).where(Stratum.name == "US Medicaid Enrollees")
            ).first()

            assert national is not None
            assert national.stratum_group_id == "medicaid_national"

    def test_load_medicaid_creates_total_enrollment_target(self, temp_db):
        """Loading Medicaid data should create total enrollment target."""
        with Session(temp_db) as session:
            load_medicaid_targets(session, years=[2023])

            national = session.exec(
                select(Stratum).where(Stratum.name == "US Medicaid Enrollees")
            ).first()

            total_target = session.exec(
                select(Target)
                .where(Target.stratum_id == national.id)
                .where(Target.variable == "medicaid_total_enrollment")
                .where(Target.period == 2023)
            ).first()

            assert total_target is not None
            expected = MEDICAID_DATA[2023]["national"]["total_enrollment"]
            assert total_target.value == expected
            assert total_target.target_type == TargetType.COUNT
            assert total_target.source == DataSource.CMS_MEDICAID

    def test_load_medicaid_creates_chip_stratum(self, temp_db):
        """Loading Medicaid data should create CHIP stratum."""
        with Session(temp_db) as session:
            load_medicaid_targets(session, years=[2023])

            chip = session.exec(
                select(Stratum).where(Stratum.name == "US CHIP Enrollees")
            ).first()

            assert chip is not None
            assert chip.stratum_group_id == "medicaid_chip"

    def test_load_medicaid_creates_chip_enrollment_target(self, temp_db):
        """Loading Medicaid data should create CHIP enrollment target."""
        with Session(temp_db) as session:
            load_medicaid_targets(session, years=[2023])

            chip = session.exec(
                select(Stratum).where(Stratum.name == "US CHIP Enrollees")
            ).first()

            chip_target = session.exec(
                select(Target)
                .where(Target.stratum_id == chip.id)
                .where(Target.variable == "chip_enrollment")
                .where(Target.period == 2023)
            ).first()

            assert chip_target is not None
            expected = MEDICAID_DATA[2023]["national"]["chip_enrollment"]
            assert chip_target.value == expected

    def test_load_medicaid_creates_child_enrollment_target(self, temp_db):
        """Loading Medicaid data should create child enrollment target."""
        with Session(temp_db) as session:
            load_medicaid_targets(session, years=[2023])

            child_stratum = session.exec(
                select(Stratum).where(Stratum.name == "US Medicaid Children")
            ).first()

            assert child_stratum is not None

            child_target = session.exec(
                select(Target)
                .where(Target.stratum_id == child_stratum.id)
                .where(Target.variable == "medicaid_child_enrollment")
            ).first()

            assert child_target is not None
            expected = MEDICAID_DATA[2023]["national"]["children"]
            assert child_target.value == expected

    def test_load_medicaid_creates_adult_enrollment_target(self, temp_db):
        """Loading Medicaid data should create adult enrollment target."""
        with Session(temp_db) as session:
            load_medicaid_targets(session, years=[2023])

            adult_stratum = session.exec(
                select(Stratum).where(Stratum.name == "US Medicaid Adults")
            ).first()

            assert adult_stratum is not None

            adult_target = session.exec(
                select(Target)
                .where(Target.stratum_id == adult_stratum.id)
                .where(Target.variable == "medicaid_adult_enrollment")
            ).first()

            assert adult_target is not None
            expected = MEDICAID_DATA[2023]["national"]["adults"]
            assert adult_target.value == expected

    def test_load_medicaid_creates_aged_enrollment_target(self, temp_db):
        """Loading Medicaid data should create aged enrollment target for years with data."""
        with Session(temp_db) as session:
            load_medicaid_targets(session, years=[2023])

            aged_stratum = session.exec(
                select(Stratum).where(Stratum.name == "US Medicaid Aged")
            ).first()

            assert aged_stratum is not None

            aged_target = session.exec(
                select(Target)
                .where(Target.stratum_id == aged_stratum.id)
                .where(Target.variable == "medicaid_aged_enrollment")
            ).first()

            assert aged_target is not None
            expected = MEDICAID_DATA[2023]["national"]["aged"]
            assert aged_target.value == expected

    def test_load_medicaid_creates_disabled_enrollment_target(self, temp_db):
        """Loading Medicaid data should create disabled enrollment target."""
        with Session(temp_db) as session:
            load_medicaid_targets(session, years=[2023])

            disabled_stratum = session.exec(
                select(Stratum).where(Stratum.name == "US Medicaid Disabled")
            ).first()

            assert disabled_stratum is not None

            disabled_target = session.exec(
                select(Target)
                .where(Target.stratum_id == disabled_stratum.id)
                .where(Target.variable == "medicaid_disabled_enrollment")
            ).first()

            assert disabled_target is not None
            expected = MEDICAID_DATA[2023]["national"]["disabled"]
            assert disabled_target.value == expected

    def test_load_medicaid_creates_aca_expansion_target(self, temp_db):
        """Loading Medicaid data should create ACA expansion enrollment target."""
        with Session(temp_db) as session:
            load_medicaid_targets(session, years=[2023])

            expansion_stratum = session.exec(
                select(Stratum).where(
                    Stratum.name == "US Medicaid ACA Expansion Adults"
                )
            ).first()

            assert expansion_stratum is not None

            expansion_target = session.exec(
                select(Target)
                .where(Target.stratum_id == expansion_stratum.id)
                .where(Target.variable == "medicaid_aca_expansion_enrollment")
            ).first()

            assert expansion_target is not None
            expected = MEDICAID_DATA[2023]["national"]["aca_expansion_adults"]
            assert expansion_target.value == expected

    def test_load_medicaid_creates_state_strata(self, temp_db):
        """Loading Medicaid data should create state-level strata."""
        with Session(temp_db) as session:
            load_medicaid_targets(session, years=[2023])

            state_strata = session.exec(
                select(Stratum).where(Stratum.stratum_group_id == "medicaid_states")
            ).all()

            # Should have strata for states in the data
            expected_states = len(MEDICAID_DATA[2023].get("states", {}))
            assert len(state_strata) == expected_states

    def test_load_medicaid_state_targets_correct(self, temp_db):
        """State-level Medicaid targets should have correct values."""
        with Session(temp_db) as session:
            load_medicaid_targets(session, years=[2023])

            ca_stratum = session.exec(
                select(Stratum).where(Stratum.name == "CA Medicaid Enrollees")
            ).first()

            assert ca_stratum is not None

            ca_enrollment = session.exec(
                select(Target)
                .where(Target.stratum_id == ca_stratum.id)
                .where(Target.variable == "medicaid_total_enrollment")
            ).first()

            expected_ca = MEDICAID_DATA[2023]["states"]["CA"]["total"]
            assert ca_enrollment.value == expected_ca

    def test_load_multiple_years(self, temp_db):
        """Loading multiple years should create targets for each."""
        with Session(temp_db) as session:
            load_medicaid_targets(session, years=[2021, 2022, 2023])

            national = session.exec(
                select(Stratum).where(Stratum.name == "US Medicaid Enrollees")
            ).first()

            targets = session.exec(
                select(Target)
                .where(Target.stratum_id == national.id)
                .where(Target.variable == "medicaid_total_enrollment")
            ).all()

            years = {t.period for t in targets}
            assert years == {2021, 2022, 2023}

    def test_load_medicaid_idempotent(self, temp_db):
        """Loading Medicaid twice should not duplicate data."""
        with Session(temp_db) as session:
            load_medicaid_targets(session, years=[2023])
            load_medicaid_targets(session, years=[2023])

            national_strata = session.exec(
                select(Stratum).where(Stratum.name == "US Medicaid Enrollees")
            ).all()

            # Should only have one national stratum
            assert len(national_strata) == 1

    def test_state_stratum_has_parent(self, temp_db):
        """State strata should have national stratum as parent."""
        with Session(temp_db) as session:
            load_medicaid_targets(session, years=[2023])

            national = session.exec(
                select(Stratum).where(Stratum.name == "US Medicaid Enrollees")
            ).first()

            ca = session.exec(
                select(Stratum).where(Stratum.name == "CA Medicaid Enrollees")
            ).first()

            assert ca.parent_id == national.id

    def test_chip_stratum_has_parent(self, temp_db):
        """CHIP stratum should have national Medicaid stratum as parent."""
        with Session(temp_db) as session:
            load_medicaid_targets(session, years=[2023])

            national = session.exec(
                select(Stratum).where(Stratum.name == "US Medicaid Enrollees")
            ).first()

            chip = session.exec(
                select(Stratum).where(Stratum.name == "US CHIP Enrollees")
            ).first()

            assert chip.parent_id == national.id

    def test_load_2025_data(self, temp_db):
        """Loading 2025 data should work with latest enrollment figures."""
        with Session(temp_db) as session:
            load_medicaid_targets(session, years=[2025])

            national = session.exec(
                select(Stratum).where(Stratum.name == "US Medicaid Enrollees")
            ).first()

            total_target = session.exec(
                select(Target)
                .where(Target.stratum_id == national.id)
                .where(Target.variable == "medicaid_total_enrollment")
                .where(Target.period == 2025)
            ).first()

            assert total_target is not None
            # August 2025 figure from CMS
            assert total_target.value == 77_290_050
