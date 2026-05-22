"""Tests for SNAP ETL."""

import tempfile
import zipfile
from pathlib import Path

import pytest
from openpyxl import Workbook
from sqlmodel import Session, select

from db.etl_snap import (
    FNS_SNAP_ZIP_URL,
    SNAP_DATA,
    _fiscal_year_from_workbook_name,
    load_snap_data_from_fns_zip,
    load_snap_targets,
)
from db.schema import (
    DataSource,
    Stratum,
    Target,
    TargetType,
    init_db,
)


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_snap.db"
        engine = init_db(db_path)
        yield engine


def _create_snap_fns_zip(path: Path) -> Path:
    workbook_path = path / "FY24.xlsx"

    workbook = Workbook()
    summary = workbook.active
    summary.title = "US Summary"
    summary.append(["National Data Bank Version 8.2"])
    summary.append(["Fiscal Year 2024 Supplemental Nutrition Assistance Program"])
    summary.append([])
    summary.append([])
    summary.append([])
    summary.append([])
    summary.append([])
    summary.append(["US Summary"])
    summary.append([
        "Total",
        22_200_091.5833,
        41_690_237.75,
        93_847_365_890,
        4_227.342,
        187.5886,
    ])

    region = workbook.create_sheet("WRO")
    region.append(["Regional Office Detail"])
    region.append([])
    region.append([])
    region.append([])
    region.append([])
    region.append([])
    region.append([])
    region.append(["California"])
    region.append([
        "Total",
        3_128_639.6667,
        5_379_574.6667,
        12_377_175_489,
        3_956.209,
        191.731,
    ])

    workbook.save(workbook_path)

    zip_path = path / "snap.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.write(workbook_path, "FY24.xlsx")
    return zip_path


class TestSnapETL:
    """Tests for SNAP ETL loader."""

    def test_fiscal_year_from_workbook_name_handles_archive_range(self):
        """Two-digit workbook names should cover the FY69-to-current archive."""
        assert _fiscal_year_from_workbook_name("FY69.xlsx") == 1969
        assert _fiscal_year_from_workbook_name("subdir/FY99.xlsx") == 1999
        assert _fiscal_year_from_workbook_name("FY00.xlsx") == 2000
        assert _fiscal_year_from_workbook_name("FY24.xlsx") == 2024

    def test_load_snap_data_from_fns_zip_extracts_fy2024_totals(self, tmp_path):
        """The FNS ZIP parser should extract national and state annual totals."""
        zip_path = _create_snap_fns_zip(tmp_path)

        data = load_snap_data_from_fns_zip(zip_path, years=[2024])

        assert data[2024]["source_url"] == FNS_SNAP_ZIP_URL
        assert data[2024]["national"]["households"] == pytest.approx(22_200.0915833)
        assert data[2024]["national"]["participants"] == pytest.approx(41_690.23775)
        assert data[2024]["national"]["benefits"] == pytest.approx(93_847.36589)
        assert data[2024]["states"]["CA"]["households"] == pytest.approx(
            3_128.6396667
        )
        assert data[2024]["states"]["CA"]["participants"] == pytest.approx(
            5_379.5746667
        )
        assert data[2024]["states"]["CA"]["benefits"] == pytest.approx(
            12_377.175489
        )

    def test_load_snap_targets_can_use_fns_zip_for_2024(self, temp_db, tmp_path):
        """Loading from the FNS ZIP should materialize 2024 target rows."""
        zip_path = _create_snap_fns_zip(tmp_path)

        with Session(temp_db) as session:
            load_snap_targets(session, years=[2024], source_zip=zip_path)

            national = session.exec(
                select(Stratum).where(Stratum.name == "US SNAP Recipients")
            ).first()
            national_participants = session.exec(
                select(Target)
                .where(Target.stratum_id == national.id)
                .where(Target.variable == "snap_participant_count")
                .where(Target.period == 2024)
            ).first()
            ca = session.exec(
                select(Stratum).where(Stratum.name == "CA SNAP Recipients")
            ).first()
            ca_households = session.exec(
                select(Target)
                .where(Target.stratum_id == ca.id)
                .where(Target.variable == "snap_household_count")
                .where(Target.period == 2024)
            ).first()

            assert national_participants.value == pytest.approx(41_690_237.75)
            assert national_participants.source_url == FNS_SNAP_ZIP_URL
            assert ca_households.value == pytest.approx(3_128_639.6667)
            assert ca_households.source_url == FNS_SNAP_ZIP_URL

    def test_load_snap_creates_national_stratum(self, temp_db):
        """Loading SNAP data should create a national stratum."""
        with Session(temp_db) as session:
            load_snap_targets(session, years=[2023])

            national = session.exec(
                select(Stratum).where(Stratum.name == "US SNAP Recipients")
            ).first()

            assert national is not None
            assert national.stratum_group_id == "snap_national"

    def test_load_snap_creates_national_targets(self, temp_db):
        """Loading SNAP data should create national-level targets."""
        with Session(temp_db) as session:
            load_snap_targets(session, years=[2023])

            national = session.exec(
                select(Stratum).where(Stratum.name == "US SNAP Recipients")
            ).first()

            # Check household count
            hh_target = session.exec(
                select(Target)
                .where(Target.stratum_id == national.id)
                .where(Target.variable == "snap_household_count")
                .where(Target.period == 2023)
            ).first()

            assert hh_target is not None
            expected_hh = SNAP_DATA[2023]["national"]["households"] * 1000
            assert hh_target.value == expected_hh
            assert hh_target.target_type == TargetType.COUNT
            assert hh_target.source == DataSource.USDA_SNAP
            assert "convert_units" in hh_target.notes

    def test_load_snap_creates_participant_targets(self, temp_db):
        """Loading SNAP should create participant count targets."""
        with Session(temp_db) as session:
            load_snap_targets(session, years=[2023])

            national = session.exec(
                select(Stratum).where(Stratum.name == "US SNAP Recipients")
            ).first()

            participant_target = session.exec(
                select(Target)
                .where(Target.stratum_id == national.id)
                .where(Target.variable == "snap_participant_count")
                .where(Target.period == 2023)
            ).first()

            assert participant_target is not None
            expected = SNAP_DATA[2023]["national"]["participants"] * 1000
            assert participant_target.value == expected

    def test_load_snap_creates_benefit_targets(self, temp_db):
        """Loading SNAP should create benefit amount targets."""
        with Session(temp_db) as session:
            load_snap_targets(session, years=[2023])

            national = session.exec(
                select(Stratum).where(Stratum.name == "US SNAP Recipients")
            ).first()

            benefit_target = session.exec(
                select(Target)
                .where(Target.stratum_id == national.id)
                .where(Target.variable == "snap_benefits")
                .where(Target.period == 2023)
            ).first()

            assert benefit_target is not None
            expected = SNAP_DATA[2023]["national"]["benefits"] * 1_000_000
            assert benefit_target.value == expected
            assert benefit_target.target_type == TargetType.AMOUNT
            assert "convert_units" in benefit_target.notes

    def test_load_snap_creates_state_strata(self, temp_db):
        """Loading SNAP should create state-level strata."""
        with Session(temp_db) as session:
            load_snap_targets(session, years=[2023])

            state_strata = session.exec(
                select(Stratum).where(Stratum.stratum_group_id == "snap_states")
            ).all()

            # Should have strata for states in the data
            expected_states = len(SNAP_DATA[2023].get("states", {}))
            assert len(state_strata) == expected_states

    def test_load_snap_state_targets_correct(self, temp_db):
        """State-level SNAP targets should have correct values."""
        with Session(temp_db) as session:
            load_snap_targets(session, years=[2023])

            ca_stratum = session.exec(
                select(Stratum).where(Stratum.name == "CA SNAP Recipients")
            ).first()

            assert ca_stratum is not None

            ca_hh = session.exec(
                select(Target)
                .where(Target.stratum_id == ca_stratum.id)
                .where(Target.variable == "snap_household_count")
            ).first()

            expected_ca_hh = SNAP_DATA[2023]["states"]["CA"]["households"] * 1000
            assert ca_hh.value == expected_ca_hh

    def test_load_multiple_years(self, temp_db):
        """Loading multiple years should create targets for each."""
        with Session(temp_db) as session:
            load_snap_targets(session, years=[2021, 2022, 2023])

            national = session.exec(
                select(Stratum).where(Stratum.name == "US SNAP Recipients")
            ).first()

            targets = session.exec(
                select(Target)
                .where(Target.stratum_id == national.id)
                .where(Target.variable == "snap_household_count")
            ).all()

            years = {t.period for t in targets}
            assert years == {2021, 2022, 2023}

    def test_load_snap_idempotent(self, temp_db):
        """Loading SNAP twice should not duplicate data."""
        with Session(temp_db) as session:
            load_snap_targets(session, years=[2023])
            load_snap_targets(session, years=[2023])

            national_strata = session.exec(
                select(Stratum).where(Stratum.name == "US SNAP Recipients")
            ).all()

            # Should only have one national stratum
            assert len(national_strata) == 1

    def test_state_stratum_has_parent(self, temp_db):
        """State strata should have national stratum as parent."""
        with Session(temp_db) as session:
            load_snap_targets(session, years=[2023])

            national = session.exec(
                select(Stratum).where(Stratum.name == "US SNAP Recipients")
            ).first()

            ca = session.exec(
                select(Stratum).where(Stratum.name == "CA SNAP Recipients")
            ).first()

            assert ca.parent_id == national.id
