"""Tests for OBR (Office for Budget Responsibility) projections ETL."""

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
from db.etl_obr import load_obr_targets, OBR_DATA


class TestObrETL:
    """Tests for OBR projections ETL."""

    @pytest.fixture
    def session(self, tmp_path):
        """Create a test database session."""
        db_path = tmp_path / "test.db"
        engine = init_db(db_path)
        with Session(engine) as session:
            yield session

    def test_load_creates_uk_budget_stratum(self, session):
        """Should create UK budget stratum."""
        load_obr_targets(session, years=[2024])

        stratum = session.exec(
            select(Stratum).where(Stratum.name == "UK Public Finances")
        ).first()

        assert stratum is not None
        assert stratum.jurisdiction == Jurisdiction.UK

    def test_load_creates_gdp_projection(self, session):
        """Should create UK GDP projection targets."""
        load_obr_targets(session, years=[2024])

        target = session.exec(
            select(Target).where(
                Target.variable == "gdp",
                Target.period == 2024,
                Target.source == DataSource.OBR,
            )
        ).first()

        assert target is not None
        assert target.value == OBR_DATA[2024]["gdp"]
        assert target.target_type == TargetType.AMOUNT

    def test_load_creates_receipts_projection(self, session):
        """Should create total receipts projection."""
        load_obr_targets(session, years=[2024])

        target = session.exec(
            select(Target).where(
                Target.variable == "total_receipts",
                Target.period == 2024,
            )
        ).first()

        assert target is not None
        assert target.value == OBR_DATA[2024]["total_receipts"]

    def test_load_creates_expenditure_projection(self, session):
        """Should create total managed expenditure projection."""
        load_obr_targets(session, years=[2024])

        target = session.exec(
            select(Target).where(
                Target.variable == "total_managed_expenditure",
                Target.period == 2024,
            )
        ).first()

        assert target is not None
        assert target.value == OBR_DATA[2024]["total_managed_expenditure"]

    def test_load_creates_borrowing_projection(self, session):
        """Should create public sector net borrowing projection."""
        load_obr_targets(session, years=[2024])

        target = session.exec(
            select(Target).where(
                Target.variable == "public_sector_net_borrowing",
                Target.period == 2024,
            )
        ).first()

        assert target is not None

    def test_load_creates_economy_stratum(self, session):
        """Should create UK economy stratum for macro indicators."""
        load_obr_targets(session, years=[2024])

        stratum = session.exec(
            select(Stratum).where(Stratum.name == "UK Economy")
        ).first()

        assert stratum is not None
        assert stratum.jurisdiction == Jurisdiction.UK

    def test_load_creates_unemployment_projection(self, session):
        """Should create UK unemployment rate projection."""
        load_obr_targets(session, years=[2025])

        target = session.exec(
            select(Target).where(
                Target.variable == "unemployment_rate",
                Target.period == 2025,
                Target.source == DataSource.OBR,
            )
        ).first()

        assert target is not None
        assert target.target_type == TargetType.RATE

    def test_load_creates_inflation_projection(self, session):
        """Should create CPI inflation projection."""
        load_obr_targets(session, years=[2024])

        target = session.exec(
            select(Target).where(
                Target.variable == "cpi_inflation",
                Target.period == 2024,
                Target.source == DataSource.OBR,
            )
        ).first()

        assert target is not None
        assert target.target_type == TargetType.RATE

    def test_load_future_years(self, session):
        """Should load projection years through 2029."""
        load_obr_targets(session, years=[2028, 2029])

        targets_2028 = session.exec(
            select(Target).where(
                Target.period == 2028,
                Target.source == DataSource.OBR,
            )
        ).all()
        targets_2029 = session.exec(
            select(Target).where(
                Target.period == 2029,
                Target.source == DataSource.OBR,
            )
        ).all()

        assert len(targets_2028) > 0
        assert len(targets_2029) > 0

    def test_load_multiple_years(self, session):
        """Should load multiple projection years."""
        load_obr_targets(session, years=[2024, 2025, 2026])

        targets = session.exec(
            select(Target).where(Target.source == DataSource.OBR)
        ).all()
        periods = {t.period for t in targets}

        assert 2024 in periods
        assert 2025 in periods
        assert 2026 in periods

    def test_load_idempotent(self, session):
        """Loading twice should not duplicate data."""
        load_obr_targets(session, years=[2024])
        count1 = len(
            session.exec(select(Target).where(Target.source == DataSource.OBR)).all()
        )

        load_obr_targets(session, years=[2024])
        count2 = len(
            session.exec(select(Target).where(Target.source == DataSource.OBR)).all()
        )

        assert count1 == count2
