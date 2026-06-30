"""Tests for state-level SOI ETL."""

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
from db.etl_soi_state import (
    load_soi_state_targets,
    SOI_STATE_DATA,
    STATE_FIPS,
    AGI_BRACKETS,
    SOI_STATE_AGI_DATA,
)


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_soi_state.db"
        engine = init_db(db_path)
        yield engine


class TestSoiStateETL:
    """Tests for state-level SOI ETL loader."""

    def test_load_soi_state_creates_national_stratum(self, temp_db):
        """Loading state SOI data should create/reference a national stratum."""
        with Session(temp_db) as session:
            load_soi_state_targets(session, years=[2021])

            national = session.exec(
                select(Stratum).where(Stratum.name == "US All Filers")
            ).first()

            assert national is not None
            assert national.stratum_group_id == "national"

    def test_load_soi_state_creates_state_strata(self, temp_db):
        """Loading state SOI data should create state-level strata."""
        with Session(temp_db) as session:
            load_soi_state_targets(session, years=[2021])

            state_strata = session.exec(
                select(Stratum).where(Stratum.stratum_group_id == "soi_states")
            ).all()

            # Should have strata for all 50 states + DC
            expected_states = len(STATE_FIPS)
            assert len(state_strata) == expected_states
            assert expected_states == 51  # 50 states + DC

    def test_load_soi_state_creates_returns_targets(self, temp_db):
        """Loading state SOI should create tax returns count targets."""
        with Session(temp_db) as session:
            load_soi_state_targets(session, years=[2021])

            ca_stratum = session.exec(
                select(Stratum).where(Stratum.name == "CA All Filers")
            ).first()

            assert ca_stratum is not None

            returns_target = session.exec(
                select(Target)
                .where(Target.stratum_id == ca_stratum.id)
                .where(Target.variable == "tax_unit_count")
                .where(Target.period == 2021)
            ).first()

            assert returns_target is not None
            expected = SOI_STATE_DATA[2021]["CA"]["total_returns"]
            assert returns_target.value == expected
            assert returns_target.target_type == TargetType.COUNT
            assert returns_target.source == DataSource.IRS_SOI

    def test_load_soi_state_creates_agi_targets(self, temp_db):
        """Loading state SOI should create AGI amount targets."""
        with Session(temp_db) as session:
            load_soi_state_targets(session, years=[2021])

            tx_stratum = session.exec(
                select(Stratum).where(Stratum.name == "TX All Filers")
            ).first()

            agi_target = session.exec(
                select(Target)
                .where(Target.stratum_id == tx_stratum.id)
                .where(Target.variable == "adjusted_gross_income")
                .where(Target.period == 2021)
            ).first()

            assert agi_target is not None
            expected = SOI_STATE_DATA[2021]["TX"]["total_agi"]
            assert agi_target.value == expected
            assert agi_target.target_type == TargetType.AMOUNT

    def test_load_soi_state_creates_tax_liability_targets(self, temp_db):
        """Loading state SOI should create tax liability targets."""
        with Session(temp_db) as session:
            load_soi_state_targets(session, years=[2021])

            fl_stratum = session.exec(
                select(Stratum).where(Stratum.name == "FL All Filers")
            ).first()

            tax_target = session.exec(
                select(Target)
                .where(Target.stratum_id == fl_stratum.id)
                .where(Target.variable == "income_tax_liability")
                .where(Target.period == 2021)
            ).first()

            assert tax_target is not None
            expected = SOI_STATE_DATA[2021]["FL"]["total_tax_liability"]
            assert tax_target.value == expected
            assert tax_target.target_type == TargetType.AMOUNT

    def test_load_soi_state_stratum_has_state_constraint(self, temp_db):
        """State strata should have state_fips constraint."""
        with Session(temp_db) as session:
            load_soi_state_targets(session, years=[2021])

            ny_stratum = session.exec(
                select(Stratum).where(Stratum.name == "NY All Filers")
            ).first()

            # Check constraints include state_fips
            state_constraint = None
            for constraint in ny_stratum.constraints:
                if constraint.variable == "state_fips":
                    state_constraint = constraint
                    break

            assert state_constraint is not None
            assert state_constraint.operator == "=="
            assert state_constraint.value == STATE_FIPS["NY"]

    def test_load_soi_state_stratum_has_parent(self, temp_db):
        """State strata should have national stratum as parent."""
        with Session(temp_db) as session:
            load_soi_state_targets(session, years=[2021])

            national = session.exec(
                select(Stratum).where(Stratum.name == "US All Filers")
            ).first()

            pa_stratum = session.exec(
                select(Stratum).where(Stratum.name == "PA All Filers")
            ).first()

            assert pa_stratum.parent_id == national.id

    def test_load_multiple_years(self, temp_db):
        """Loading multiple years should create targets for each."""
        with Session(temp_db) as session:
            load_soi_state_targets(session, years=[2020, 2021])

            ca_stratum = session.exec(
                select(Stratum).where(Stratum.name == "CA All Filers")
            ).first()

            targets = session.exec(
                select(Target)
                .where(Target.stratum_id == ca_stratum.id)
                .where(Target.variable == "tax_unit_count")
            ).all()

            years = {t.period for t in targets}
            assert years == {2020, 2021}

    def test_load_soi_state_idempotent(self, temp_db):
        """Loading state SOI twice should not duplicate data."""
        with Session(temp_db) as session:
            load_soi_state_targets(session, years=[2021])
            load_soi_state_targets(session, years=[2021])

            ca_strata = session.exec(
                select(Stratum).where(Stratum.name == "CA All Filers")
            ).all()

            # Should only have one CA stratum
            assert len(ca_strata) == 1

    def test_all_states_loaded(self, temp_db):
        """All 50 states + DC should be loaded."""
        with Session(temp_db) as session:
            load_soi_state_targets(session, years=[2021])

            for state_abbrev in STATE_FIPS.keys():
                stratum = session.exec(
                    select(Stratum).where(Stratum.name == f"{state_abbrev} All Filers")
                ).first()

                assert stratum is not None, f"Missing stratum for {state_abbrev}"

                # Each state should have 3 targets (returns, AGI, tax liability)
                targets = session.exec(
                    select(Target).where(Target.stratum_id == stratum.id)
                ).all()

                assert len(targets) == 3

    def test_target_source_metadata(self, temp_db):
        """Targets should have correct source metadata."""
        with Session(temp_db) as session:
            load_soi_state_targets(session, years=[2021])

            ca_stratum = session.exec(
                select(Stratum).where(Stratum.name == "CA All Filers")
            ).first()

            target = session.exec(
                select(Target)
                .where(Target.stratum_id == ca_stratum.id)
                .where(Target.variable == "tax_unit_count")
            ).first()

            assert target.source == DataSource.IRS_SOI
            assert target.source_table == "Historic Table 2"
            assert "historic-table-2" in target.source_url


class TestAgiBracketStratification:
    """Tests for AGI bracket stratification."""

    def test_agi_brackets_defined(self):
        """AGI_BRACKETS should be properly defined."""
        assert len(AGI_BRACKETS) == 10

        # Check first bracket (under $1)
        assert AGI_BRACKETS[0]["min"] == 0
        assert AGI_BRACKETS[0]["max"] == 1
        assert AGI_BRACKETS[0]["label"] == "under_1"

        # Check last bracket ($1M+)
        assert AGI_BRACKETS[-1]["min"] == 1_000_000
        assert AGI_BRACKETS[-1]["max"] is None
        assert AGI_BRACKETS[-1]["label"] == "1m_plus"

    def test_agi_brackets_contiguous(self):
        """AGI brackets should be contiguous (no gaps)."""
        for i in range(len(AGI_BRACKETS) - 1):
            current = AGI_BRACKETS[i]
            next_bracket = AGI_BRACKETS[i + 1]
            assert current["max"] == next_bracket["min"], (
                f"Gap between bracket {i} (max={current['max']}) "
                f"and bracket {i + 1} (min={next_bracket['min']})"
            )

    def test_load_soi_state_creates_agi_bracket_strata(self, temp_db):
        """Loading state SOI data should create AGI bracket strata."""
        with Session(temp_db) as session:
            load_soi_state_targets(session, years=[2021])

            # Check CA has AGI bracket strata
            bracket_strata = session.exec(
                select(Stratum).where(
                    Stratum.stratum_group_id == "soi_states_agi_brackets"
                )
            ).all()

            # Should have strata for each state x bracket combination
            expected_count = len(STATE_FIPS) * len(AGI_BRACKETS)
            assert len(bracket_strata) == expected_count

    def test_agi_bracket_stratum_has_state_and_bracket_constraints(self, temp_db):
        """AGI bracket strata should have both state_fips and agi_bracket constraints."""
        with Session(temp_db) as session:
            load_soi_state_targets(session, years=[2021])

            # Find CA $50k-$75k bracket stratum
            ca_bracket_stratum = session.exec(
                select(Stratum).where(Stratum.name == "CA Filers AGI $50k-$75k")
            ).first()

            assert ca_bracket_stratum is not None

            # Should have state_fips constraint
            constraints_dict = {
                c.variable: (c.operator, c.value)
                for c in ca_bracket_stratum.constraints
            }

            assert "state_fips" in constraints_dict
            assert constraints_dict["state_fips"] == ("==", STATE_FIPS["CA"])

            # Should have agi_bracket constraint
            assert "agi_bracket" in constraints_dict
            assert constraints_dict["agi_bracket"] == ("==", "50k_to_75k")

    def test_agi_bracket_stratum_has_state_parent(self, temp_db):
        """AGI bracket strata should have state stratum as parent."""
        with Session(temp_db) as session:
            load_soi_state_targets(session, years=[2021])

            ca_state_stratum = session.exec(
                select(Stratum).where(Stratum.name == "CA All Filers")
            ).first()

            ca_bracket_stratum = session.exec(
                select(Stratum).where(Stratum.name == "CA Filers AGI $50k-$75k")
            ).first()

            assert ca_bracket_stratum.parent_id == ca_state_stratum.id

    def test_agi_bracket_targets_created(self, temp_db):
        """AGI bracket strata should have targets for returns, AGI, and tax."""
        with Session(temp_db) as session:
            load_soi_state_targets(session, years=[2021])

            ca_bracket_stratum = session.exec(
                select(Stratum).where(Stratum.name == "CA Filers AGI $100k-$200k")
            ).first()

            assert ca_bracket_stratum is not None

            targets = session.exec(
                select(Target).where(Target.stratum_id == ca_bracket_stratum.id)
            ).all()

            # Should have 3 targets: returns, AGI, tax liability
            assert len(targets) == 3

            variables = {t.variable for t in targets}
            assert variables == {
                "tax_unit_count",
                "adjusted_gross_income",
                "income_tax_liability",
            }

    def test_agi_bracket_target_values(self, temp_db):
        """AGI bracket targets should have correct values from data."""
        with Session(temp_db) as session:
            load_soi_state_targets(session, years=[2021])

            tx_bracket_stratum = session.exec(
                select(Stratum).where(Stratum.name == "TX Filers AGI $1M+")
            ).first()

            returns_target = session.exec(
                select(Target)
                .where(Target.stratum_id == tx_bracket_stratum.id)
                .where(Target.variable == "tax_unit_count")
            ).first()

            expected = SOI_STATE_AGI_DATA[2021]["TX"]["1m_plus"]["total_returns"]
            assert returns_target.value == expected

    def test_all_brackets_for_state(self, temp_db):
        """Each state should have all 10 AGI brackets."""
        with Session(temp_db) as session:
            load_soi_state_targets(session, years=[2021])

            # Check NY has all 10 brackets
            ny_bracket_strata = session.exec(
                select(Stratum).where(Stratum.name.like("NY Filers AGI %"))
            ).all()

            assert len(ny_bracket_strata) == len(AGI_BRACKETS)

    def test_bracket_stratum_description(self, temp_db):
        """AGI bracket strata should have descriptive descriptions."""
        with Session(temp_db) as session:
            load_soi_state_targets(session, years=[2021])

            stratum = session.exec(
                select(Stratum).where(Stratum.name == "FL Filers AGI Under $1")
            ).first()

            assert stratum is not None
            assert "under $1" in stratum.description.lower()
            assert "FL" in stratum.description or "Florida" in stratum.description
