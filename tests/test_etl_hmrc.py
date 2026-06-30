"""Tests for UK HMRC ETL."""

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
        db_path = Path(tmpdir) / "test_hmrc.db"
        engine = init_db(db_path)
        yield engine


class TestHmrcETL:
    """Tests for HMRC ETL loader."""

    def test_load_hmrc_creates_national_stratum(self, temp_db):
        """Loading HMRC data should create a UK national stratum."""
        from db.etl_hmrc import load_hmrc_targets

        with Session(temp_db) as session:
            load_hmrc_targets(session, years=[2022])

            national = session.exec(
                select(Stratum).where(Stratum.name == "UK All Taxpayers")
            ).first()

            assert national is not None
            assert national.jurisdiction == Jurisdiction.UK

    def test_load_hmrc_creates_income_tax_targets(self, temp_db):
        """Loading HMRC should create income tax revenue targets."""
        from db.etl_hmrc import load_hmrc_targets, HMRC_DATA

        with Session(temp_db) as session:
            load_hmrc_targets(session, years=[2022])

            national = session.exec(
                select(Stratum).where(Stratum.name == "UK All Taxpayers")
            ).first()

            income_tax = session.exec(
                select(Target)
                .where(Target.stratum_id == national.id)
                .where(Target.variable == "income_tax")
                .where(Target.period == 2022)
            ).first()

            assert income_tax is not None
            assert income_tax.value == HMRC_DATA[2022]["income_tax"]
            assert income_tax.target_type == TargetType.AMOUNT
            assert income_tax.source == DataSource.HMRC

    def test_load_hmrc_creates_ni_targets(self, temp_db):
        """Loading HMRC should create National Insurance targets."""
        from db.etl_hmrc import load_hmrc_targets, HMRC_DATA

        with Session(temp_db) as session:
            load_hmrc_targets(session, years=[2022])

            national = session.exec(
                select(Stratum).where(Stratum.name == "UK All Taxpayers")
            ).first()

            ni = session.exec(
                select(Target)
                .where(Target.stratum_id == national.id)
                .where(Target.variable == "national_insurance")
                .where(Target.period == 2022)
            ).first()

            assert ni is not None
            assert ni.value == HMRC_DATA[2022]["national_insurance"]

    def test_load_hmrc_creates_taxpayer_count(self, temp_db):
        """Loading HMRC should create taxpayer count targets."""
        from db.etl_hmrc import load_hmrc_targets, HMRC_DATA

        with Session(temp_db) as session:
            load_hmrc_targets(session, years=[2022])

            national = session.exec(
                select(Stratum).where(Stratum.name == "UK All Taxpayers")
            ).first()

            count = session.exec(
                select(Target)
                .where(Target.stratum_id == national.id)
                .where(Target.variable == "taxpayer_count")
                .where(Target.period == 2022)
            ).first()

            assert count is not None
            assert count.value == HMRC_DATA[2022]["taxpayers"]
            assert count.target_type == TargetType.COUNT

    def test_load_hmrc_creates_benefit_recipients(self, temp_db):
        """Loading HMRC should create benefit recipient targets."""
        from db.etl_hmrc import load_hmrc_targets

        with Session(temp_db) as session:
            load_hmrc_targets(session, years=[2022])

            uc_stratum = session.exec(
                select(Stratum).where(Stratum.name == "UK Universal Credit Recipients")
            ).first()

            assert uc_stratum is not None

            uc_count = session.exec(
                select(Target)
                .where(Target.stratum_id == uc_stratum.id)
                .where(Target.variable == "universal_credit_recipients")
            ).first()

            assert uc_count is not None
            assert uc_count.target_type == TargetType.COUNT

    def test_load_hmrc_creates_benefit_expenditure(self, temp_db):
        """Loading HMRC should create benefit expenditure targets."""
        from db.etl_hmrc import load_hmrc_targets, HMRC_DATA

        with Session(temp_db) as session:
            load_hmrc_targets(session, years=[2022])

            uc_stratum = session.exec(
                select(Stratum).where(Stratum.name == "UK Universal Credit Recipients")
            ).first()

            uc_spend = session.exec(
                select(Target)
                .where(Target.stratum_id == uc_stratum.id)
                .where(Target.variable == "universal_credit_expenditure")
            ).first()

            assert uc_spend is not None
            assert (
                uc_spend.value
                == HMRC_DATA[2022]["benefits"]["universal_credit"]["expenditure"]
            )
            assert uc_spend.target_type == TargetType.AMOUNT

    def test_load_multiple_years(self, temp_db):
        """Loading multiple years should create targets for each."""
        from db.etl_hmrc import load_hmrc_targets

        with Session(temp_db) as session:
            load_hmrc_targets(session, years=[2021, 2022])

            national = session.exec(
                select(Stratum).where(Stratum.name == "UK All Taxpayers")
            ).first()

            targets = session.exec(
                select(Target)
                .where(Target.stratum_id == national.id)
                .where(Target.variable == "income_tax")
            ).all()

            years = {t.period for t in targets}
            assert years == {2021, 2022}

    def test_load_hmrc_idempotent(self, temp_db):
        """Loading HMRC twice should not duplicate data."""
        from db.etl_hmrc import load_hmrc_targets

        with Session(temp_db) as session:
            load_hmrc_targets(session, years=[2022])
            load_hmrc_targets(session, years=[2022])

            national_strata = session.exec(
                select(Stratum).where(Stratum.name == "UK All Taxpayers")
            ).all()

            assert len(national_strata) == 1
