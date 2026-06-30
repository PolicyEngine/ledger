"""Tests for SSI (Supplemental Security Income) ETL."""

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
from db.etl_ssi import load_ssi_targets, SSI_DATA


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_ssi.db"
        engine = init_db(db_path)
        yield engine


class TestSsiETL:
    """Tests for SSI ETL loader."""

    def test_load_creates_national_stratum(self, temp_db):
        """Loading SSI data should create a national stratum."""
        with Session(temp_db) as session:
            load_ssi_targets(session, years=[2023])

            national = session.exec(
                select(Stratum).where(Stratum.name == "US SSI Recipients")
            ).first()

            assert national is not None
            assert national.stratum_group_id == "ssi_national"

    def test_load_creates_national_recipient_count(self, temp_db):
        """Loading SSI should create national recipient count target."""
        with Session(temp_db) as session:
            load_ssi_targets(session, years=[2023])

            national = session.exec(
                select(Stratum).where(Stratum.name == "US SSI Recipients")
            ).first()

            count = session.exec(
                select(Target)
                .where(Target.stratum_id == national.id)
                .where(Target.variable == "ssi_recipients")
                .where(Target.period == 2023)
            ).first()

            assert count is not None
            assert count.value == SSI_DATA[2023]["national"]["recipients"]
            assert count.target_type == TargetType.COUNT
            assert count.source == DataSource.SSA

    def test_load_creates_national_payments(self, temp_db):
        """Loading SSI should create national total payments target."""
        with Session(temp_db) as session:
            load_ssi_targets(session, years=[2023])

            national = session.exec(
                select(Stratum).where(Stratum.name == "US SSI Recipients")
            ).first()

            payments = session.exec(
                select(Target)
                .where(Target.stratum_id == national.id)
                .where(Target.variable == "ssi_total_payments")
            ).first()

            assert payments is not None
            assert payments.value == SSI_DATA[2023]["national"]["total_payments"]
            assert payments.target_type == TargetType.AMOUNT

    def test_load_creates_avg_monthly_payment(self, temp_db):
        """Loading SSI should create average monthly payment target."""
        with Session(temp_db) as session:
            load_ssi_targets(session, years=[2023])

            national = session.exec(
                select(Stratum).where(Stratum.name == "US SSI Recipients")
            ).first()

            avg_payment = session.exec(
                select(Target)
                .where(Target.stratum_id == national.id)
                .where(Target.variable == "ssi_avg_monthly_payment")
            ).first()

            assert avg_payment is not None
            assert (
                avg_payment.value == SSI_DATA[2023]["national"]["avg_monthly_payment"]
            )

    def test_load_creates_federal_vs_state_supplementation(self, temp_db):
        """Loading SSI should create federal and state supplementation targets."""
        with Session(temp_db) as session:
            load_ssi_targets(session, years=[2023])

            national = session.exec(
                select(Stratum).where(Stratum.name == "US SSI Recipients")
            ).first()

            federal = session.exec(
                select(Target)
                .where(Target.stratum_id == national.id)
                .where(Target.variable == "ssi_federal_payments")
            ).first()

            state_supp = session.exec(
                select(Target)
                .where(Target.stratum_id == national.id)
                .where(Target.variable == "ssi_state_supplementation")
            ).first()

            assert federal is not None
            assert federal.value == SSI_DATA[2023]["national"]["federal_payments"]

            assert state_supp is not None
            assert (
                state_supp.value == SSI_DATA[2023]["national"]["state_supplementation"]
            )

    def test_load_creates_aged_stratum(self, temp_db):
        """Loading SSI should create aged recipient stratum."""
        with Session(temp_db) as session:
            load_ssi_targets(session, years=[2023])

            aged = session.exec(
                select(Stratum).where(Stratum.name == "US SSI Aged Recipients")
            ).first()

            assert aged is not None
            assert aged.stratum_group_id == "ssi_categories"

    def test_load_creates_blind_stratum(self, temp_db):
        """Loading SSI should create blind recipient stratum."""
        with Session(temp_db) as session:
            load_ssi_targets(session, years=[2023])

            blind = session.exec(
                select(Stratum).where(Stratum.name == "US SSI Blind Recipients")
            ).first()

            assert blind is not None

    def test_load_creates_disabled_stratum(self, temp_db):
        """Loading SSI should create disabled recipient stratum."""
        with Session(temp_db) as session:
            load_ssi_targets(session, years=[2023])

            disabled = session.exec(
                select(Stratum).where(Stratum.name == "US SSI Disabled Recipients")
            ).first()

            assert disabled is not None

    def test_category_recipient_counts(self, temp_db):
        """Category recipient counts should sum approximately to total."""
        with Session(temp_db) as session:
            load_ssi_targets(session, years=[2023])

            aged = session.exec(
                select(Stratum).where(Stratum.name == "US SSI Aged Recipients")
            ).first()
            blind = session.exec(
                select(Stratum).where(Stratum.name == "US SSI Blind Recipients")
            ).first()
            disabled = session.exec(
                select(Stratum).where(Stratum.name == "US SSI Disabled Recipients")
            ).first()

            aged_count = session.exec(
                select(Target)
                .where(Target.stratum_id == aged.id)
                .where(Target.variable == "ssi_recipients")
            ).first()
            blind_count = session.exec(
                select(Target)
                .where(Target.stratum_id == blind.id)
                .where(Target.variable == "ssi_recipients")
            ).first()
            disabled_count = session.exec(
                select(Target)
                .where(Target.stratum_id == disabled.id)
                .where(Target.variable == "ssi_recipients")
            ).first()

            total_from_categories = (
                aged_count.value + blind_count.value + disabled_count.value
            )
            national_total = SSI_DATA[2023]["national"]["recipients"]

            # Categories should sum to close to (but may not exactly equal) total
            # due to some recipients qualifying under multiple categories
            assert total_from_categories > national_total * 0.95
            assert total_from_categories < national_total * 1.05

    def test_load_creates_state_strata(self, temp_db):
        """Loading SSI should create state-level strata."""
        with Session(temp_db) as session:
            load_ssi_targets(session, years=[2023])

            state_strata = session.exec(
                select(Stratum).where(Stratum.stratum_group_id == "ssi_states")
            ).all()

            # Should have strata for states in the data
            expected_states = len(SSI_DATA[2023].get("states", {}))
            assert len(state_strata) == expected_states

    def test_load_state_targets_correct(self, temp_db):
        """State-level SSI targets should have correct values."""
        with Session(temp_db) as session:
            load_ssi_targets(session, years=[2023])

            ca_stratum = session.exec(
                select(Stratum).where(Stratum.name == "CA SSI Recipients")
            ).first()

            assert ca_stratum is not None

            ca_recipients = session.exec(
                select(Target)
                .where(Target.stratum_id == ca_stratum.id)
                .where(Target.variable == "ssi_recipients")
            ).first()

            expected_ca = SSI_DATA[2023]["states"]["CA"]["recipients"]
            assert ca_recipients.value == expected_ca

    def test_load_state_category_breakdowns(self, temp_db):
        """State-level SSI should have category breakdowns."""
        with Session(temp_db) as session:
            load_ssi_targets(session, years=[2023])

            ca_aged = session.exec(
                select(Stratum).where(Stratum.name == "CA SSI Aged Recipients")
            ).first()
            ca_blind = session.exec(
                select(Stratum).where(Stratum.name == "CA SSI Blind Recipients")
            ).first()
            ca_disabled = session.exec(
                select(Stratum).where(Stratum.name == "CA SSI Disabled Recipients")
            ).first()

            assert ca_aged is not None
            assert ca_blind is not None
            assert ca_disabled is not None

            # Check aged count
            aged_count = session.exec(
                select(Target)
                .where(Target.stratum_id == ca_aged.id)
                .where(Target.variable == "ssi_recipients")
            ).first()

            assert aged_count.value == SSI_DATA[2023]["states"]["CA"]["aged"]

    def test_state_stratum_has_parent(self, temp_db):
        """State strata should have national stratum as parent."""
        with Session(temp_db) as session:
            load_ssi_targets(session, years=[2023])

            national = session.exec(
                select(Stratum).where(Stratum.name == "US SSI Recipients")
            ).first()

            ca = session.exec(
                select(Stratum).where(Stratum.name == "CA SSI Recipients")
            ).first()

            assert ca.parent_id == national.id

    def test_state_category_has_state_parent(self, temp_db):
        """State category strata should have state stratum as parent."""
        with Session(temp_db) as session:
            load_ssi_targets(session, years=[2023])

            ca_state = session.exec(
                select(Stratum).where(Stratum.name == "CA SSI Recipients")
            ).first()

            ca_aged = session.exec(
                select(Stratum).where(Stratum.name == "CA SSI Aged Recipients")
            ).first()

            assert ca_aged.parent_id == ca_state.id

    def test_load_multiple_years(self, temp_db):
        """Loading multiple years should create targets for each."""
        with Session(temp_db) as session:
            load_ssi_targets(session, years=[2021, 2022, 2023])

            national = session.exec(
                select(Stratum).where(Stratum.name == "US SSI Recipients")
            ).first()

            targets = session.exec(
                select(Target)
                .where(Target.stratum_id == national.id)
                .where(Target.variable == "ssi_recipients")
            ).all()

            years = {t.period for t in targets}
            assert years == {2021, 2022, 2023}

    def test_load_idempotent(self, temp_db):
        """Loading SSI twice should not duplicate strata."""
        with Session(temp_db) as session:
            load_ssi_targets(session, years=[2023])
            load_ssi_targets(session, years=[2023])

            national_strata = session.exec(
                select(Stratum).where(Stratum.name == "US SSI Recipients")
            ).all()

            # Should only have one national stratum
            assert len(national_strata) == 1

    def test_load_texas_data(self, temp_db):
        """Texas SSI data should load correctly."""
        with Session(temp_db) as session:
            load_ssi_targets(session, years=[2023])

            tx_stratum = session.exec(
                select(Stratum).where(Stratum.name == "TX SSI Recipients")
            ).first()

            assert tx_stratum is not None

            tx_recipients = session.exec(
                select(Target)
                .where(Target.stratum_id == tx_stratum.id)
                .where(Target.variable == "ssi_recipients")
            ).first()

            assert tx_recipients.value == SSI_DATA[2023]["states"]["TX"]["recipients"]

    def test_load_florida_data(self, temp_db):
        """Florida SSI data should load correctly."""
        with Session(temp_db) as session:
            load_ssi_targets(session, years=[2023])

            fl_stratum = session.exec(
                select(Stratum).where(Stratum.name == "FL SSI Recipients")
            ).first()

            assert fl_stratum is not None

            # Florida has high aged population
            fl_aged = session.exec(
                select(Stratum).where(Stratum.name == "FL SSI Aged Recipients")
            ).first()

            aged_count = session.exec(
                select(Target)
                .where(Target.stratum_id == fl_aged.id)
                .where(Target.variable == "ssi_recipients")
            ).first()

            assert aged_count.value == SSI_DATA[2023]["states"]["FL"]["aged"]
