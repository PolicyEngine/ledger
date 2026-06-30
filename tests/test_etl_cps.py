"""Tests for BLS CPS (Current Population Survey) monthly employment ETL."""

import tempfile
from pathlib import Path

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


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_cps.db"
        engine = init_db(db_path)
        yield engine


class TestCpsETL:
    """Tests for CPS monthly employment ETL loader."""

    def test_load_creates_labor_force_stratum(self, temp_db):
        """Loading CPS data should create labor force stratum."""
        from db.etl_cps import load_cps_targets

        with Session(temp_db) as session:
            load_cps_targets(session, years=[2023], months=[12])

            labor_force = session.exec(
                select(Stratum).where(Stratum.name == "US Labor Force")
            ).first()

            assert labor_force is not None
            assert labor_force.jurisdiction == Jurisdiction.US
            assert labor_force.stratum_group_id == "cps_monthly"

    def test_load_creates_employment_count(self, temp_db):
        """Loading CPS should create employment count target."""
        from db.etl_cps import load_cps_targets, CPS_MONTHLY_DATA

        with Session(temp_db) as session:
            load_cps_targets(session, years=[2023], months=[12])

            labor_force = session.exec(
                select(Stratum).where(Stratum.name == "US Labor Force")
            ).first()

            # Period format: YYYYMM (202312 for December 2023)
            period = 202312

            employed = session.exec(
                select(Target)
                .where(Target.stratum_id == labor_force.id)
                .where(Target.variable == "employed")
                .where(Target.period == period)
            ).first()

            assert employed is not None
            assert employed.value == CPS_MONTHLY_DATA[2023][12]["employed"]
            assert employed.target_type == TargetType.COUNT
            assert employed.source == DataSource.BLS

    def test_load_creates_unemployment_count(self, temp_db):
        """Loading CPS should create unemployment count target."""
        from db.etl_cps import load_cps_targets, CPS_MONTHLY_DATA

        with Session(temp_db) as session:
            load_cps_targets(session, years=[2023], months=[12])

            labor_force = session.exec(
                select(Stratum).where(Stratum.name == "US Labor Force")
            ).first()

            unemployed = session.exec(
                select(Target)
                .where(Target.stratum_id == labor_force.id)
                .where(Target.variable == "unemployed")
                .where(Target.period == 202312)
            ).first()

            assert unemployed is not None
            assert unemployed.value == CPS_MONTHLY_DATA[2023][12]["unemployed"]
            assert unemployed.target_type == TargetType.COUNT

    def test_load_creates_unemployment_rate(self, temp_db):
        """Loading CPS should create unemployment rate target."""
        from db.etl_cps import load_cps_targets, CPS_MONTHLY_DATA

        with Session(temp_db) as session:
            load_cps_targets(session, years=[2023], months=[12])

            labor_force = session.exec(
                select(Stratum).where(Stratum.name == "US Labor Force")
            ).first()

            rate = session.exec(
                select(Target)
                .where(Target.stratum_id == labor_force.id)
                .where(Target.variable == "unemployment_rate")
                .where(Target.period == 202312)
            ).first()

            assert rate is not None
            assert rate.value == CPS_MONTHLY_DATA[2023][12]["unemployment_rate"]
            assert rate.target_type == TargetType.RATE

    def test_load_creates_labor_force_participation(self, temp_db):
        """Loading CPS should create LFPR target."""
        from db.etl_cps import load_cps_targets, CPS_MONTHLY_DATA

        with Session(temp_db) as session:
            load_cps_targets(session, years=[2023], months=[12])

            labor_force = session.exec(
                select(Stratum).where(Stratum.name == "US Labor Force")
            ).first()

            lfpr = session.exec(
                select(Target)
                .where(Target.stratum_id == labor_force.id)
                .where(Target.variable == "labor_force_participation_rate")
                .where(Target.period == 202312)
            ).first()

            assert lfpr is not None
            assert (
                lfpr.value
                == CPS_MONTHLY_DATA[2023][12]["labor_force_participation_rate"]
            )
            assert lfpr.target_type == TargetType.RATE

    def test_load_creates_employment_population_ratio(self, temp_db):
        """Loading CPS should create employment-population ratio target."""
        from db.etl_cps import load_cps_targets, CPS_MONTHLY_DATA

        with Session(temp_db) as session:
            load_cps_targets(session, years=[2023], months=[12])

            labor_force = session.exec(
                select(Stratum).where(Stratum.name == "US Labor Force")
            ).first()

            ratio = session.exec(
                select(Target)
                .where(Target.stratum_id == labor_force.id)
                .where(Target.variable == "employment_population_ratio")
                .where(Target.period == 202312)
            ).first()

            assert ratio is not None
            assert (
                ratio.value == CPS_MONTHLY_DATA[2023][12]["employment_population_ratio"]
            )
            assert ratio.target_type == TargetType.RATE

    def test_load_creates_not_in_labor_force(self, temp_db):
        """Loading CPS should create not-in-labor-force count target."""
        from db.etl_cps import load_cps_targets, CPS_MONTHLY_DATA

        with Session(temp_db) as session:
            load_cps_targets(session, years=[2023], months=[12])

            labor_force = session.exec(
                select(Stratum).where(Stratum.name == "US Labor Force")
            ).first()

            nilf = session.exec(
                select(Target)
                .where(Target.stratum_id == labor_force.id)
                .where(Target.variable == "not_in_labor_force")
                .where(Target.period == 202312)
            ).first()

            assert nilf is not None
            assert nilf.value == CPS_MONTHLY_DATA[2023][12]["not_in_labor_force"]
            assert nilf.target_type == TargetType.COUNT

    def test_load_multiple_months(self, temp_db):
        """Loading multiple months should create targets for each."""
        from db.etl_cps import load_cps_targets

        with Session(temp_db) as session:
            load_cps_targets(session, years=[2023], months=[1, 6, 12])

            labor_force = session.exec(
                select(Stratum).where(Stratum.name == "US Labor Force")
            ).first()

            targets = session.exec(
                select(Target)
                .where(Target.stratum_id == labor_force.id)
                .where(Target.variable == "employed")
            ).all()

            periods = {t.period for t in targets}
            # 202301 (January), 202306 (June), 202312 (December)
            assert periods == {202301, 202306, 202312}

    def test_load_multiple_years(self, temp_db):
        """Loading multiple years should create targets for each."""
        from db.etl_cps import load_cps_targets

        with Session(temp_db) as session:
            load_cps_targets(session, years=[2023, 2024], months=[12])

            labor_force = session.exec(
                select(Stratum).where(Stratum.name == "US Labor Force")
            ).first()

            targets = session.exec(
                select(Target)
                .where(Target.stratum_id == labor_force.id)
                .where(Target.variable == "employed")
            ).all()

            periods = {t.period for t in targets}
            # 202312 (Dec 2023) and 202412 (Dec 2024)
            assert periods == {202312, 202412}

    def test_load_all_data(self, temp_db):
        """Loading without filters should load all available data."""
        from db.etl_cps import load_cps_targets

        with Session(temp_db) as session:
            load_cps_targets(session)

            labor_force = session.exec(
                select(Stratum).where(Stratum.name == "US Labor Force")
            ).first()

            targets = session.exec(
                select(Target)
                .where(Target.stratum_id == labor_force.id)
                .where(Target.variable == "employed")
            ).all()

            # Should have data for multiple months across multiple years
            assert len(targets) > 5

            # Verify we have data from 2023, 2024, and 2025
            years = {t.period // 100 for t in targets}
            assert 2023 in years
            assert 2024 in years
            assert 2025 in years

    def test_load_idempotent(self, temp_db):
        """Loading twice should not duplicate strata."""
        from db.etl_cps import load_cps_targets

        with Session(temp_db) as session:
            load_cps_targets(session, years=[2023], months=[12])
            load_cps_targets(session, years=[2023], months=[12])

            labor_force_strata = session.exec(
                select(Stratum).where(Stratum.name == "US Labor Force")
            ).all()

            assert len(labor_force_strata) == 1

    def test_period_format(self, temp_db):
        """Period should be in YYYYMM format."""
        from db.etl_cps import load_cps_targets

        with Session(temp_db) as session:
            load_cps_targets(session, years=[2024], months=[11])

            labor_force = session.exec(
                select(Stratum).where(Stratum.name == "US Labor Force")
            ).first()

            target = session.exec(
                select(Target)
                .where(Target.stratum_id == labor_force.id)
                .where(Target.variable == "employed")
            ).first()

            # November 2024 should be 202411
            assert target.period == 202411
