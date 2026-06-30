"""Tests for state-level SOI deduction targets ETL."""

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
from db.etl_soi_deductions import (
    load_soi_deductions_targets,
    SOI_DEDUCTIONS_DATA,
    STATE_FIPS,
    SOURCE_URL,
    DEDUCTION_TYPES,
)


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_soi_deductions.db"
        engine = init_db(db_path)
        yield engine


class TestSoiDeductionsETL:
    """Tests for state-level SOI deductions ETL loader."""

    def test_load_soi_deductions_creates_national_stratum(self, temp_db):
        """Loading deduction data should create/reference a national stratum."""
        with Session(temp_db) as session:
            load_soi_deductions_targets(session, years=[2021])

            national = session.exec(
                select(Stratum).where(Stratum.name == "US All Filers")
            ).first()

            assert national is not None
            assert national.stratum_group_id == "national"

    def test_load_soi_deductions_creates_state_strata(self, temp_db):
        """Loading deduction data should create state-level strata."""
        with Session(temp_db) as session:
            load_soi_deductions_targets(session, years=[2021])

            state_strata = session.exec(
                select(Stratum).where(Stratum.stratum_group_id == "soi_states")
            ).all()

            # Should have strata for all 50 states + DC
            expected_states = len(STATE_FIPS)
            assert len(state_strata) == expected_states
            assert expected_states == 51  # 50 states + DC

    def test_load_salt_claims_targets(self, temp_db):
        """Loading deductions should create SALT claims count targets."""
        with Session(temp_db) as session:
            load_soi_deductions_targets(session, years=[2021])

            ca_stratum = session.exec(
                select(Stratum).where(Stratum.name == "CA All Filers")
            ).first()

            assert ca_stratum is not None

            salt_claims_target = session.exec(
                select(Target)
                .where(Target.stratum_id == ca_stratum.id)
                .where(Target.variable == "salt_claims")
                .where(Target.period == 2021)
            ).first()

            assert salt_claims_target is not None
            expected = SOI_DEDUCTIONS_DATA[2021]["CA"]["salt_claims"]
            assert salt_claims_target.value == expected
            assert salt_claims_target.target_type == TargetType.COUNT
            assert salt_claims_target.source == DataSource.IRS_SOI

    def test_load_salt_amount_targets(self, temp_db):
        """Loading deductions should create SALT amount targets."""
        with Session(temp_db) as session:
            load_soi_deductions_targets(session, years=[2021])

            tx_stratum = session.exec(
                select(Stratum).where(Stratum.name == "TX All Filers")
            ).first()

            salt_amount_target = session.exec(
                select(Target)
                .where(Target.stratum_id == tx_stratum.id)
                .where(Target.variable == "salt_amount")
                .where(Target.period == 2021)
            ).first()

            assert salt_amount_target is not None
            expected = SOI_DEDUCTIONS_DATA[2021]["TX"]["salt_amount"]
            assert salt_amount_target.value == expected
            assert salt_amount_target.target_type == TargetType.AMOUNT
            assert SOURCE_URL in salt_amount_target.source_url

    def test_load_mortgage_interest_claims_targets(self, temp_db):
        """Loading deductions should create mortgage interest claims targets."""
        with Session(temp_db) as session:
            load_soi_deductions_targets(session, years=[2021])

            fl_stratum = session.exec(
                select(Stratum).where(Stratum.name == "FL All Filers")
            ).first()

            mortgage_claims_target = session.exec(
                select(Target)
                .where(Target.stratum_id == fl_stratum.id)
                .where(Target.variable == "mortgage_interest_claims")
                .where(Target.period == 2021)
            ).first()

            assert mortgage_claims_target is not None
            expected = SOI_DEDUCTIONS_DATA[2021]["FL"]["mortgage_interest_claims"]
            assert mortgage_claims_target.value == expected
            assert mortgage_claims_target.target_type == TargetType.COUNT

    def test_load_mortgage_interest_amount_targets(self, temp_db):
        """Loading deductions should create mortgage interest amount targets."""
        with Session(temp_db) as session:
            load_soi_deductions_targets(session, years=[2021])

            ny_stratum = session.exec(
                select(Stratum).where(Stratum.name == "NY All Filers")
            ).first()

            mortgage_amount_target = session.exec(
                select(Target)
                .where(Target.stratum_id == ny_stratum.id)
                .where(Target.variable == "mortgage_interest_amount")
                .where(Target.period == 2021)
            ).first()

            assert mortgage_amount_target is not None
            expected = SOI_DEDUCTIONS_DATA[2021]["NY"]["mortgage_interest_amount"]
            assert mortgage_amount_target.value == expected
            assert mortgage_amount_target.target_type == TargetType.AMOUNT

    def test_load_charitable_claims_targets(self, temp_db):
        """Loading deductions should create charitable contribution claims targets."""
        with Session(temp_db) as session:
            load_soi_deductions_targets(session, years=[2021])

            ga_stratum = session.exec(
                select(Stratum).where(Stratum.name == "GA All Filers")
            ).first()

            charitable_claims_target = session.exec(
                select(Target)
                .where(Target.stratum_id == ga_stratum.id)
                .where(Target.variable == "charitable_claims")
                .where(Target.period == 2021)
            ).first()

            assert charitable_claims_target is not None
            expected = SOI_DEDUCTIONS_DATA[2021]["GA"]["charitable_claims"]
            assert charitable_claims_target.value == expected
            assert charitable_claims_target.target_type == TargetType.COUNT

    def test_load_charitable_amount_targets(self, temp_db):
        """Loading deductions should create charitable contribution amount targets."""
        with Session(temp_db) as session:
            load_soi_deductions_targets(session, years=[2021])

            pa_stratum = session.exec(
                select(Stratum).where(Stratum.name == "PA All Filers")
            ).first()

            charitable_amount_target = session.exec(
                select(Target)
                .where(Target.stratum_id == pa_stratum.id)
                .where(Target.variable == "charitable_amount")
                .where(Target.period == 2021)
            ).first()

            assert charitable_amount_target is not None
            expected = SOI_DEDUCTIONS_DATA[2021]["PA"]["charitable_amount"]
            assert charitable_amount_target.value == expected
            assert charitable_amount_target.target_type == TargetType.AMOUNT

    def test_load_medical_claims_targets(self, temp_db):
        """Loading deductions should create medical expense claims targets."""
        with Session(temp_db) as session:
            load_soi_deductions_targets(session, years=[2021])

            oh_stratum = session.exec(
                select(Stratum).where(Stratum.name == "OH All Filers")
            ).first()

            medical_claims_target = session.exec(
                select(Target)
                .where(Target.stratum_id == oh_stratum.id)
                .where(Target.variable == "medical_claims")
                .where(Target.period == 2021)
            ).first()

            assert medical_claims_target is not None
            expected = SOI_DEDUCTIONS_DATA[2021]["OH"]["medical_claims"]
            assert medical_claims_target.value == expected
            assert medical_claims_target.target_type == TargetType.COUNT

    def test_load_medical_amount_targets(self, temp_db):
        """Loading deductions should create medical expense amount targets."""
        with Session(temp_db) as session:
            load_soi_deductions_targets(session, years=[2021])

            il_stratum = session.exec(
                select(Stratum).where(Stratum.name == "IL All Filers")
            ).first()

            medical_amount_target = session.exec(
                select(Target)
                .where(Target.stratum_id == il_stratum.id)
                .where(Target.variable == "medical_amount")
                .where(Target.period == 2021)
            ).first()

            assert medical_amount_target is not None
            expected = SOI_DEDUCTIONS_DATA[2021]["IL"]["medical_amount"]
            assert medical_amount_target.value == expected
            assert medical_amount_target.target_type == TargetType.AMOUNT

    def test_load_qbi_claims_targets(self, temp_db):
        """Loading deductions should create QBI deduction claims targets."""
        with Session(temp_db) as session:
            load_soi_deductions_targets(session, years=[2021])

            wa_stratum = session.exec(
                select(Stratum).where(Stratum.name == "WA All Filers")
            ).first()

            qbi_claims_target = session.exec(
                select(Target)
                .where(Target.stratum_id == wa_stratum.id)
                .where(Target.variable == "qbi_claims")
                .where(Target.period == 2021)
            ).first()

            assert qbi_claims_target is not None
            expected = SOI_DEDUCTIONS_DATA[2021]["WA"]["qbi_claims"]
            assert qbi_claims_target.value == expected
            assert qbi_claims_target.target_type == TargetType.COUNT

    def test_load_qbi_amount_targets(self, temp_db):
        """Loading deductions should create QBI deduction amount targets."""
        with Session(temp_db) as session:
            load_soi_deductions_targets(session, years=[2021])

            co_stratum = session.exec(
                select(Stratum).where(Stratum.name == "CO All Filers")
            ).first()

            qbi_amount_target = session.exec(
                select(Target)
                .where(Target.stratum_id == co_stratum.id)
                .where(Target.variable == "qbi_amount")
                .where(Target.period == 2021)
            ).first()

            assert qbi_amount_target is not None
            expected = SOI_DEDUCTIONS_DATA[2021]["CO"]["qbi_amount"]
            assert qbi_amount_target.value == expected
            assert qbi_amount_target.target_type == TargetType.AMOUNT

    def test_load_soi_deductions_stratum_has_state_constraint(self, temp_db):
        """State strata should have state_fips constraint."""
        with Session(temp_db) as session:
            load_soi_deductions_targets(session, years=[2021])

            nj_stratum = session.exec(
                select(Stratum).where(Stratum.name == "NJ All Filers")
            ).first()

            # Check constraints include state_fips
            state_constraint = None
            for constraint in nj_stratum.constraints:
                if constraint.variable == "state_fips":
                    state_constraint = constraint
                    break

            assert state_constraint is not None
            assert state_constraint.operator == "=="
            assert state_constraint.value == STATE_FIPS["NJ"]

    def test_load_soi_deductions_stratum_has_parent(self, temp_db):
        """State strata should have national stratum as parent."""
        with Session(temp_db) as session:
            load_soi_deductions_targets(session, years=[2021])

            national = session.exec(
                select(Stratum).where(Stratum.name == "US All Filers")
            ).first()

            ma_stratum = session.exec(
                select(Stratum).where(Stratum.name == "MA All Filers")
            ).first()

            assert ma_stratum.parent_id == national.id

    def test_load_soi_deductions_idempotent(self, temp_db):
        """Loading deductions twice should not duplicate data."""
        with Session(temp_db) as session:
            load_soi_deductions_targets(session, years=[2021])
            load_soi_deductions_targets(session, years=[2021])

            ca_strata = session.exec(
                select(Stratum).where(Stratum.name == "CA All Filers")
            ).all()

            # Should only have one CA stratum
            assert len(ca_strata) == 1

    def test_all_states_loaded(self, temp_db):
        """All 50 states + DC should be loaded with 10 deduction targets each."""
        with Session(temp_db) as session:
            load_soi_deductions_targets(session, years=[2021])

            for state_abbrev in STATE_FIPS.keys():
                stratum = session.exec(
                    select(Stratum).where(Stratum.name == f"{state_abbrev} All Filers")
                ).first()

                assert stratum is not None, f"Missing stratum for {state_abbrev}"

                # Each state should have 10 targets (5 deductions x 2 (claims + amount))
                targets = session.exec(
                    select(Target).where(Target.stratum_id == stratum.id)
                ).all()

                # 5 deduction types x 2 (claims + amount) = 10 targets
                assert len(targets) == 10, (
                    f"Expected 10 targets for {state_abbrev}, got {len(targets)}"
                )

    def test_target_source_metadata(self, temp_db):
        """Targets should have correct source metadata."""
        with Session(temp_db) as session:
            load_soi_deductions_targets(session, years=[2021])

            ca_stratum = session.exec(
                select(Stratum).where(Stratum.name == "CA All Filers")
            ).first()

            salt_target = session.exec(
                select(Target)
                .where(Target.stratum_id == ca_stratum.id)
                .where(Target.variable == "salt_claims")
            ).first()

            assert salt_target.source == DataSource.IRS_SOI
            assert (
                salt_target.source_table
                == "SOI Individual Returns - Itemized Deductions"
            )
            assert "soi-tax-stats" in salt_target.source_url

    def test_national_totals_are_reasonable(self, temp_db):
        """National totals should match expected ranges."""
        with Session(temp_db) as session:
            load_soi_deductions_targets(session, years=[2021])

            # Sum all SALT claims across states - should be around 12M
            all_salt_claims = sum(
                state_data["salt_claims"]
                for state_data in SOI_DEDUCTIONS_DATA[2021].values()
            )
            assert 10_000_000 < all_salt_claims < 20_000_000

            # Sum all SALT amounts - should be around $150B
            all_salt_amount = sum(
                state_data["salt_amount"]
                for state_data in SOI_DEDUCTIONS_DATA[2021].values()
            )
            assert 100_000_000_000 < all_salt_amount < 200_000_000_000

            # Sum all mortgage interest claims - should be around 10M
            all_mortgage_claims = sum(
                state_data["mortgage_interest_claims"]
                for state_data in SOI_DEDUCTIONS_DATA[2021].values()
            )
            assert 8_000_000 < all_mortgage_claims < 15_000_000

            # Sum all mortgage interest amounts - should be around $80B
            all_mortgage_amount = sum(
                state_data["mortgage_interest_amount"]
                for state_data in SOI_DEDUCTIONS_DATA[2021].values()
            )
            assert 60_000_000_000 < all_mortgage_amount < 100_000_000_000

            # Sum all charitable claims - should be around 25M
            all_charitable_claims = sum(
                state_data["charitable_claims"]
                for state_data in SOI_DEDUCTIONS_DATA[2021].values()
            )
            assert 20_000_000 < all_charitable_claims < 35_000_000

            # Sum all charitable amounts - should be around $50B
            all_charitable_amount = sum(
                state_data["charitable_amount"]
                for state_data in SOI_DEDUCTIONS_DATA[2021].values()
            )
            assert 40_000_000_000 < all_charitable_amount < 70_000_000_000

            # Sum all medical claims - should be around 5M
            all_medical_claims = sum(
                state_data["medical_claims"]
                for state_data in SOI_DEDUCTIONS_DATA[2021].values()
            )
            assert 4_000_000 < all_medical_claims < 10_000_000

            # Sum all medical amounts - should be around $30B
            all_medical_amount = sum(
                state_data["medical_amount"]
                for state_data in SOI_DEDUCTIONS_DATA[2021].values()
            )
            assert 20_000_000_000 < all_medical_amount < 50_000_000_000

            # Sum all QBI claims - should be around 10M
            all_qbi_claims = sum(
                state_data["qbi_claims"]
                for state_data in SOI_DEDUCTIONS_DATA[2021].values()
            )
            assert 8_000_000 < all_qbi_claims < 15_000_000

            # Sum all QBI amounts - should be around $70B
            all_qbi_amount = sum(
                state_data["qbi_amount"]
                for state_data in SOI_DEDUCTIONS_DATA[2021].values()
            )
            assert 50_000_000_000 < all_qbi_amount < 100_000_000_000

    def test_large_states_have_higher_claims(self, temp_db):
        """Larger states should have more claims than smaller states."""
        with Session(temp_db) as session:
            load_soi_deductions_targets(session, years=[2021])

            # California (large) vs Wyoming (small)
            ca_data = SOI_DEDUCTIONS_DATA[2021]["CA"]
            wy_data = SOI_DEDUCTIONS_DATA[2021]["WY"]

            assert ca_data["salt_claims"] > wy_data["salt_claims"]
            assert (
                ca_data["mortgage_interest_claims"]
                > wy_data["mortgage_interest_claims"]
            )
            assert ca_data["charitable_claims"] > wy_data["charitable_claims"]
            assert ca_data["medical_claims"] > wy_data["medical_claims"]
            assert ca_data["qbi_claims"] > wy_data["qbi_claims"]

            # Texas (large) vs Vermont (small)
            tx_data = SOI_DEDUCTIONS_DATA[2021]["TX"]
            vt_data = SOI_DEDUCTIONS_DATA[2021]["VT"]

            assert tx_data["salt_claims"] > vt_data["salt_claims"]
            assert (
                tx_data["mortgage_interest_claims"]
                > vt_data["mortgage_interest_claims"]
            )

    def test_deduction_types_constant(self, temp_db):
        """DEDUCTION_TYPES should contain all 5 deduction types."""
        assert len(DEDUCTION_TYPES) == 5
        assert "salt" in DEDUCTION_TYPES
        assert "mortgage_interest" in DEDUCTION_TYPES
        assert "charitable" in DEDUCTION_TYPES
        assert "medical" in DEDUCTION_TYPES
        assert "qbi" in DEDUCTION_TYPES
