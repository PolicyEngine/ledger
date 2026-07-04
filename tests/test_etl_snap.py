"""Tests for SNAP ETL.

Values are asserted against the trustworthy USDA FNS source package
(``packages/usda_snap/fy69_to_current``) rather than any hardcoded table, so
the tests cannot silently bless fabricated numbers (see PolicyEngine/ledger#77).
"""

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
from db.etl_snap import load_snap_facts, load_snap_targets

# The FNS source package artifact is the FY2024 workbook.
SNAP_YEAR = 2024


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_snap.db"
        engine = init_db(db_path)
        yield engine


@pytest.fixture(scope="module")
def snap_facts():
    """Parsed SNAP facts from the trustworthy source package."""
    return load_snap_facts()


def _fact_value(facts, *, geography_id, concept):
    """Return the parsed value for a geography/concept pair."""
    for fact in facts:
        if fact.geography.id == geography_id and fact.measure.concept == concept:
            return fact.value
    raise AssertionError(f"no source fact for {geography_id} / {concept}")


class TestSnapSourceFacts:
    """The ETL must source its values from the FNS source package."""

    def test_facts_are_fiscal_year_2024(self, snap_facts):
        """Every parsed fact carries the FY2024 reference period."""
        assert snap_facts
        assert {fact.period.value for fact in snap_facts} == {SNAP_YEAR}

    def test_facts_carry_source_provenance(self, snap_facts):
        """Each parsed fact traces to the checksum-locked FNS artifact."""
        for fact in snap_facts:
            assert fact.source.source_name == "usda_snap"
            assert fact.source.source_sha256
            assert fact.source.raw_r2_uri

    def test_year_filter_excludes_absent_periods(self):
        """Filtering to a year with no facts yields nothing, not mislabeled data."""
        assert load_snap_facts([SNAP_YEAR])
        assert load_snap_facts([2021]) == []


class TestSnapETL:
    """Tests for SNAP ETL loader."""

    def test_load_snap_creates_national_stratum(self, temp_db):
        """Loading SNAP data should create a national stratum."""
        with Session(temp_db) as session:
            load_snap_targets(session, years=[SNAP_YEAR])

            national = session.exec(
                select(Stratum).where(Stratum.name == "US SNAP Recipients")
            ).first()

            assert national is not None
            assert national.stratum_group_id == "snap_national"

    def test_load_snap_creates_national_targets(self, temp_db, snap_facts):
        """National household target should match the parsed FNS value."""
        with Session(temp_db) as session:
            load_snap_targets(session, years=[SNAP_YEAR])

            national = session.exec(
                select(Stratum).where(Stratum.name == "US SNAP Recipients")
            ).first()

            hh_target = session.exec(
                select(Target)
                .where(Target.stratum_id == national.id)
                .where(Target.variable == "snap_household_count")
                .where(Target.period == SNAP_YEAR)
            ).first()

            assert hh_target is not None
            expected_hh = _fact_value(
                snap_facts,
                geography_id="0100000US",
                concept="usda_snap.average_monthly_households",
            )
            assert hh_target.value == expected_hh
            assert hh_target.target_type == TargetType.COUNT
            assert hh_target.source == DataSource.USDA_SNAP
            # Provenance must be present and cite the FNS artifact.
            assert "usda_snap" in hh_target.notes.lower() or "USDA FNS" in hh_target.notes

    def test_load_snap_creates_participant_targets(self, temp_db, snap_facts):
        """Participant target should match the parsed FNS person count."""
        with Session(temp_db) as session:
            load_snap_targets(session, years=[SNAP_YEAR])

            national = session.exec(
                select(Stratum).where(Stratum.name == "US SNAP Recipients")
            ).first()

            participant_target = session.exec(
                select(Target)
                .where(Target.stratum_id == national.id)
                .where(Target.variable == "snap_participant_count")
                .where(Target.period == SNAP_YEAR)
            ).first()

            assert participant_target is not None
            expected = _fact_value(
                snap_facts,
                geography_id="0100000US",
                concept="usda_snap.average_monthly_persons",
            )
            assert participant_target.value == expected

    def test_load_snap_creates_benefit_targets(self, temp_db, snap_facts):
        """Benefit target should match the parsed FNS total benefits."""
        with Session(temp_db) as session:
            load_snap_targets(session, years=[SNAP_YEAR])

            national = session.exec(
                select(Stratum).where(Stratum.name == "US SNAP Recipients")
            ).first()

            benefit_target = session.exec(
                select(Target)
                .where(Target.stratum_id == national.id)
                .where(Target.variable == "snap_benefits")
                .where(Target.period == SNAP_YEAR)
            ).first()

            assert benefit_target is not None
            expected = _fact_value(
                snap_facts,
                geography_id="0100000US",
                concept="usda_snap.total_benefits",
            )
            assert benefit_target.value == expected
            assert benefit_target.target_type == TargetType.AMOUNT

    def test_load_snap_creates_state_strata(self, temp_db, snap_facts):
        """Loading SNAP should create one stratum per parsed state geography."""
        with Session(temp_db) as session:
            load_snap_targets(session, years=[SNAP_YEAR])

            state_strata = session.exec(
                select(Stratum).where(Stratum.stratum_group_id == "snap_states")
            ).all()

            expected_states = {
                fact.geography.id
                for fact in snap_facts
                if fact.geography.level == "state"
            }
            assert len(state_strata) == len(expected_states)

    def test_load_snap_state_targets_correct(self, temp_db, snap_facts):
        """State-level SNAP targets should match parsed FNS values."""
        with Session(temp_db) as session:
            load_snap_targets(session, years=[SNAP_YEAR])

            ca_stratum = session.exec(
                select(Stratum).where(Stratum.name == "California SNAP Recipients")
            ).first()

            assert ca_stratum is not None

            ca_hh = session.exec(
                select(Target)
                .where(Target.stratum_id == ca_stratum.id)
                .where(Target.variable == "snap_household_count")
            ).first()

            expected_ca_hh = _fact_value(
                snap_facts,
                geography_id="0400000US06",
                concept="usda_snap.average_monthly_households",
            )
            assert ca_hh.value == expected_ca_hh

    def test_load_year_present(self, temp_db):
        """Loading the available year should create national targets for it."""
        with Session(temp_db) as session:
            load_snap_targets(session, years=[SNAP_YEAR])

            national = session.exec(
                select(Stratum).where(Stratum.name == "US SNAP Recipients")
            ).first()

            targets = session.exec(
                select(Target)
                .where(Target.stratum_id == national.id)
                .where(Target.variable == "snap_household_count")
            ).all()

            years = {t.period for t in targets}
            assert years == {SNAP_YEAR}

    def test_load_snap_idempotent(self, temp_db):
        """Loading SNAP twice should not duplicate the national stratum."""
        with Session(temp_db) as session:
            load_snap_targets(session, years=[SNAP_YEAR])
            load_snap_targets(session, years=[SNAP_YEAR])

            national_strata = session.exec(
                select(Stratum).where(Stratum.name == "US SNAP Recipients")
            ).all()

            # Should only have one national stratum
            assert len(national_strata) == 1

    def test_state_stratum_has_parent(self, temp_db):
        """State strata should have national stratum as parent."""
        with Session(temp_db) as session:
            load_snap_targets(session, years=[SNAP_YEAR])

            national = session.exec(
                select(Stratum).where(Stratum.name == "US SNAP Recipients")
            ).first()

            ca = session.exec(
                select(Stratum).where(Stratum.name == "California SNAP Recipients")
            ).first()

            assert ca.parent_id == national.id
