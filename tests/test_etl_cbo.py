"""Tests for CBO projections ETL."""

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
from db.etl_cbo import load_cbo_targets, CBO_DATA


class TestCboETL:
    """Tests for CBO projections ETL."""

    @pytest.fixture
    def session(self, tmp_path):
        """Create a test database session."""
        db_path = tmp_path / "test.db"
        engine = init_db(db_path)
        with Session(engine) as session:
            yield session

    def test_load_creates_federal_budget_stratum(self, session):
        """Should create federal budget stratum."""
        load_cbo_targets(session, years=[2024])

        stratum = session.exec(
            select(Stratum).where(Stratum.name == "US Federal Budget")
        ).first()

        assert stratum is not None
        assert stratum.jurisdiction == Jurisdiction.US_FEDERAL

    def test_load_creates_gdp_projection(self, session):
        """Should create GDP projection targets."""
        load_cbo_targets(session, years=[2024])

        target = session.exec(
            select(Target).where(
                Target.variable == "gdp",
                Target.period == 2024,
            )
        ).first()

        assert target is not None
        assert target.value == CBO_DATA[2024]["gdp"]
        assert target.target_type == TargetType.AMOUNT
        assert target.source == DataSource.CBO

    def test_load_creates_revenue_projection(self, session):
        """Should create federal revenue projection."""
        load_cbo_targets(session, years=[2024])

        target = session.exec(
            select(Target).where(
                Target.variable == "federal_revenue",
                Target.period == 2024,
            )
        ).first()

        assert target is not None
        assert target.value == CBO_DATA[2024]["federal_revenue"]
        assert target.target_type == TargetType.AMOUNT

    def test_load_creates_outlays_projection(self, session):
        """Should create federal outlays projection."""
        load_cbo_targets(session, years=[2024])

        target = session.exec(
            select(Target).where(
                Target.variable == "federal_outlays",
                Target.period == 2024,
            )
        ).first()

        assert target is not None
        assert target.value == CBO_DATA[2024]["federal_outlays"]

    def test_load_creates_deficit_projection(self, session):
        """Should create deficit projection."""
        load_cbo_targets(session, years=[2024])

        target = session.exec(
            select(Target).where(
                Target.variable == "federal_deficit",
                Target.period == 2024,
            )
        ).first()

        assert target is not None
        assert target.value == CBO_DATA[2024]["federal_deficit"]

    def test_load_creates_economic_stratum(self, session):
        """Should create US economy stratum for macro indicators."""
        load_cbo_targets(session, years=[2024])

        stratum = session.exec(
            select(Stratum).where(Stratum.name == "US Economy")
        ).first()

        assert stratum is not None

    def test_load_creates_unemployment_projection(self, session):
        """Should create unemployment rate projection."""
        load_cbo_targets(session, years=[2025])

        target = session.exec(
            select(Target).where(
                Target.variable == "unemployment_rate",
                Target.period == 2025,
                Target.source == DataSource.CBO,
            )
        ).first()

        assert target is not None
        assert target.target_type == TargetType.RATE

    def test_load_creates_inflation_projection(self, session):
        """Should create inflation rate projection."""
        load_cbo_targets(session, years=[2024])

        target = session.exec(
            select(Target).where(
                Target.variable == "cpi_inflation",
                Target.period == 2024,
            )
        ).first()

        assert target is not None
        assert target.target_type == TargetType.RATE

    def test_load_future_years(self, session):
        """Should load projection years through 2034."""
        load_cbo_targets(session, years=[2030, 2034])

        targets_2030 = session.exec(select(Target).where(Target.period == 2030)).all()
        targets_2034 = session.exec(select(Target).where(Target.period == 2034)).all()

        assert len(targets_2030) > 0
        assert len(targets_2034) > 0

    def test_load_multiple_years(self, session):
        """Should load multiple projection years."""
        load_cbo_targets(session, years=[2024, 2025, 2026])

        targets = session.exec(select(Target)).all()
        periods = {t.period for t in targets}

        assert 2024 in periods
        assert 2025 in periods
        assert 2026 in periods

    def test_load_idempotent(self, session):
        """Loading twice should not duplicate data."""
        load_cbo_targets(session, years=[2024])
        count1 = len(session.exec(select(Target)).all())

        load_cbo_targets(session, years=[2024])
        count2 = len(session.exec(select(Target)).all())

        assert count1 == count2
