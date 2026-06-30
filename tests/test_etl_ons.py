"""Tests for ONS (Office for National Statistics) projections ETL."""

import pytest
from sqlmodel import Session, select

from db.schema import (
    DataSource,
    Jurisdiction,
    Stratum,
    Target,
    TargetType,
    init_db,
)
from db.etl_ons import load_ons_targets, ONS_DATA


class TestOnsETL:
    """Tests for ONS projections ETL."""

    @pytest.fixture
    def session(self, tmp_path):
        """Create a test database session."""
        db_path = tmp_path / "test.db"
        engine = init_db(db_path)
        with Session(engine) as session:
            yield session

    def test_load_creates_uk_population_stratum(self, session):
        """Should create UK population stratum."""
        load_ons_targets(session, years=[2024])

        stratum = session.exec(
            select(Stratum).where(Stratum.name == "UK Population")
        ).first()

        assert stratum is not None
        assert stratum.jurisdiction == Jurisdiction.UK

    def test_load_creates_total_population_projection(self, session):
        """Should create UK total population projection targets."""
        load_ons_targets(session, years=[2024])

        target = session.exec(
            select(Target).where(
                Target.variable == "population_total",
                Target.period == 2024,
                Target.source == DataSource.ONS,
            )
        ).first()

        assert target is not None
        assert target.value == ONS_DATA[2024]["population_total"]
        assert target.target_type == TargetType.COUNT
        assert target.is_preliminary is True

    def test_load_creates_age_group_projections(self, session):
        """Should create population projections by age groups."""
        load_ons_targets(session, years=[2024])

        # Check 0-15 age group
        target_0_15 = session.exec(
            select(Target).where(
                Target.variable == "population_age_0_15",
                Target.period == 2024,
            )
        ).first()

        assert target_0_15 is not None
        assert target_0_15.value == ONS_DATA[2024]["population_age_0_15"]

        # Check 16-64 age group
        target_16_64 = session.exec(
            select(Target).where(
                Target.variable == "population_age_16_64",
                Target.period == 2024,
            )
        ).first()

        assert target_16_64 is not None
        assert target_16_64.value == ONS_DATA[2024]["population_age_16_64"]

        # Check 65+ age group
        target_65_plus = session.exec(
            select(Target).where(
                Target.variable == "population_age_65_plus",
                Target.period == 2024,
            )
        ).first()

        assert target_65_plus is not None
        assert target_65_plus.value == ONS_DATA[2024]["population_age_65_plus"]

    def test_load_creates_uk_households_stratum(self, session):
        """Should create UK households stratum."""
        load_ons_targets(session, years=[2024])

        stratum = session.exec(
            select(Stratum).where(Stratum.name == "UK Households")
        ).first()

        assert stratum is not None
        assert stratum.jurisdiction == Jurisdiction.UK

    def test_load_creates_household_projections(self, session):
        """Should create household count projection."""
        load_ons_targets(session, years=[2024])

        target = session.exec(
            select(Target).where(
                Target.variable == "households_total",
                Target.period == 2024,
                Target.source == DataSource.ONS,
            )
        ).first()

        assert target is not None
        assert target.value == ONS_DATA[2024]["households_total"]
        assert target.target_type == TargetType.COUNT

    def test_load_creates_average_household_size(self, session):
        """Should create average household size projection."""
        load_ons_targets(session, years=[2024])

        target = session.exec(
            select(Target).where(
                Target.variable == "average_household_size",
                Target.period == 2024,
                Target.source == DataSource.ONS,
            )
        ).first()

        assert target is not None
        assert target.value == ONS_DATA[2024]["average_household_size"]
        assert target.target_type == TargetType.RATE

    def test_load_future_years(self, session):
        """Should load projection years through 2034."""
        load_ons_targets(session, years=[2033, 2034])

        targets_2033 = session.exec(
            select(Target).where(
                Target.period == 2033,
                Target.source == DataSource.ONS,
            )
        ).all()
        targets_2034 = session.exec(
            select(Target).where(
                Target.period == 2034,
                Target.source == DataSource.ONS,
            )
        ).all()

        assert len(targets_2033) > 0
        assert len(targets_2034) > 0

    def test_load_multiple_years(self, session):
        """Should load multiple projection years."""
        load_ons_targets(session, years=[2024, 2025, 2026])

        targets = session.exec(
            select(Target).where(Target.source == DataSource.ONS)
        ).all()
        periods = {t.period for t in targets}

        assert 2024 in periods
        assert 2025 in periods
        assert 2026 in periods

    def test_load_idempotent(self, session):
        """Loading twice should not duplicate data."""
        load_ons_targets(session, years=[2024])
        count1 = len(
            session.exec(select(Target).where(Target.source == DataSource.ONS)).all()
        )

        load_ons_targets(session, years=[2024])
        count2 = len(
            session.exec(select(Target).where(Target.source == DataSource.ONS)).all()
        )

        assert count1 == count2

    def test_all_projections_marked_preliminary(self, session):
        """All ONS projections should be marked as preliminary."""
        load_ons_targets(session, years=[2024, 2030])

        targets = session.exec(
            select(Target).where(Target.source == DataSource.ONS)
        ).all()

        for target in targets:
            assert target.is_preliminary is True

    def test_load_all_years(self, session):
        """Should load all available years when years=None."""
        load_ons_targets(session, years=None)

        targets = session.exec(
            select(Target).where(Target.source == DataSource.ONS)
        ).all()
        periods = {t.period for t in targets}

        # Should have data for all years 2024-2034
        expected_years = set(range(2024, 2035))
        assert periods == expected_years
