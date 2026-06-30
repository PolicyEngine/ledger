"""Tests for state-level calibration targets."""

import tempfile
from pathlib import Path

import pandas as pd
import pytest

# Add data/targets to path for imports
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "data" / "targets"))

from build_state_targets import (
    STATE_FIPS,
    STATE_NAMES,
    AGI_BRACKETS,
    build_state_income_distribution,
    build_state_credits_targets,
    build_state_ui_statistics,
    build_state_demographics,
    build_all_state_targets,
    save_targets,
    load_state_targets,
    convert_to_reweighter_targets,
)


class TestStateConstants:
    """Test state constants are properly defined."""

    def test_state_fips_count(self):
        """Should have 51 state FIPS codes (50 states + DC)."""
        assert len(STATE_FIPS) == 51

    def test_state_names_count(self):
        """Should have 51 state names."""
        assert len(STATE_NAMES) == 51

    def test_state_fips_format(self):
        """FIPS codes should be 2-digit strings."""
        for state, fips in STATE_FIPS.items():
            assert len(fips) == 2
            assert fips.isdigit()

    def test_agi_brackets_count(self):
        """Should have 10 AGI brackets."""
        assert len(AGI_BRACKETS) == 10

    def test_agi_brackets_contiguous(self):
        """AGI brackets should be contiguous (no gaps)."""
        for i in range(len(AGI_BRACKETS) - 1):
            _, _, current_max = AGI_BRACKETS[i]
            _, next_min, _ = AGI_BRACKETS[i + 1]
            assert current_max == next_min


class TestIncomeDistribution:
    """Test income distribution target builder."""

    def test_build_returns_dataframe(self):
        """Should return a DataFrame."""
        df = build_state_income_distribution()
        assert isinstance(df, pd.DataFrame)

    def test_has_required_columns(self):
        """Should have all required columns."""
        df = build_state_income_distribution()
        required = [
            "state_code",
            "state_fips",
            "state_name",
            "year",
            "agi_bracket",
            "agi_bracket_min",
            "agi_bracket_max",
            "target_returns",
            "target_agi",
            "target_tax_liability",
        ]
        for col in required:
            assert col in df.columns, f"Missing column: {col}"

    def test_all_states_included(self):
        """Should include all 51 states."""
        df = build_state_income_distribution()
        assert df["state_code"].nunique() == 51

    def test_all_brackets_per_state_year(self):
        """Each state/year should have all 10 AGI brackets."""
        df = build_state_income_distribution()
        for (state, year), group in df.groupby(["state_code", "year"]):
            assert len(group) == 10, f"Missing brackets for {state}/{year}"

    def test_target_values_positive(self):
        """Target values should be non-negative."""
        df = build_state_income_distribution()
        assert (df["target_returns"] >= 0).all()
        assert (df["target_agi"] >= 0).all()
        assert (df["target_tax_liability"] >= 0).all()


class TestTaxCredits:
    """Test tax credits target builder."""

    def test_build_returns_dataframe(self):
        """Should return a DataFrame."""
        df = build_state_credits_targets()
        assert isinstance(df, pd.DataFrame)

    def test_has_eitc_columns(self):
        """Should have EITC columns."""
        df = build_state_credits_targets()
        assert "eitc_claims" in df.columns
        assert "eitc_amount" in df.columns

    def test_has_ctc_columns(self):
        """Should have CTC columns."""
        df = build_state_credits_targets()
        assert "ctc_claims" in df.columns
        assert "ctc_amount" in df.columns

    def test_all_states_included(self):
        """Should include all 51 states."""
        df = build_state_credits_targets()
        assert df["state_code"].nunique() == 51


class TestUnemployment:
    """Test unemployment statistics target builder."""

    def test_build_returns_dataframe(self):
        """Should return a DataFrame."""
        df = build_state_ui_statistics()
        assert isinstance(df, pd.DataFrame)

    def test_has_claims_columns(self):
        """Should have UI claims columns."""
        df = build_state_ui_statistics()
        assert "initial_claims" in df.columns
        assert "continued_claims" in df.columns

    def test_has_benefits_columns(self):
        """Should have benefits columns."""
        df = build_state_ui_statistics()
        assert "avg_weekly_benefit" in df.columns
        assert "benefits_paid" in df.columns

    def test_unemployment_rate_valid(self):
        """Unemployment rate should be between 0 and 1."""
        df = build_state_ui_statistics()
        assert (df["unemployment_rate"] >= 0).all()
        assert (df["unemployment_rate"] <= 1).all()


class TestDemographics:
    """Test demographics target builder."""

    def test_build_returns_dataframe(self):
        """Should return a DataFrame."""
        df = build_state_demographics()
        assert isinstance(df, pd.DataFrame)

    def test_has_population_columns(self):
        """Should have population columns."""
        df = build_state_demographics()
        assert "total_population" in df.columns
        assert "population_under_18" in df.columns
        assert "population_18_64" in df.columns
        assert "population_65_plus" in df.columns

    def test_population_sums_correctly(self):
        """Age group populations should sum to total."""
        df = build_state_demographics()
        for _, row in df.iterrows():
            age_sum = (
                row["population_under_18"]
                + row["population_18_64"]
                + row["population_65_plus"]
            )
            assert age_sum == row["total_population"]

    def test_poverty_rate_valid(self):
        """Poverty rate should be between 0 and 1."""
        df = build_state_demographics()
        assert (df["poverty_rate"] >= 0).all()
        assert (df["poverty_rate"] <= 1).all()


class TestBuildAllTargets:
    """Test building all targets together."""

    def test_returns_dict(self):
        """Should return a dictionary of DataFrames."""
        targets = build_all_state_targets()
        assert isinstance(targets, dict)

    def test_has_all_target_types(self):
        """Should have all four target types."""
        targets = build_all_state_targets()
        expected = [
            "income_distribution",
            "tax_credits",
            "unemployment",
            "demographics",
        ]
        for name in expected:
            assert name in targets, f"Missing target type: {name}"

    def test_all_values_are_dataframes(self):
        """All values should be DataFrames."""
        targets = build_all_state_targets()
        for name, df in targets.items():
            assert isinstance(df, pd.DataFrame), f"{name} is not a DataFrame"


class TestSaveAndLoad:
    """Test saving and loading targets."""

    def test_save_and_load_roundtrip(self):
        """Saved targets should load correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            # Build and save
            targets = build_all_state_targets()
            save_targets(targets, output_dir)

            # Load back
            loaded_income = load_state_targets(
                "income_distribution", output_dir=output_dir
            )
            loaded_credits = load_state_targets("tax_credits", output_dir=output_dir)

            # Check shapes match
            assert len(loaded_income) == len(targets["income_distribution"])
            assert len(loaded_credits) == len(targets["tax_credits"])

    def test_load_with_state_filter(self):
        """Should filter by state when specified."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            targets = build_all_state_targets()
            save_targets(targets, output_dir)

            loaded = load_state_targets(
                "income_distribution",
                states=["CA", "TX"],
                output_dir=output_dir,
            )

            assert set(loaded["state_code"].unique()) == {"CA", "TX"}

    def test_load_with_year_filter(self):
        """Should filter by year when specified."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            targets = build_all_state_targets()
            save_targets(targets, output_dir)

            loaded = load_state_targets(
                "income_distribution",
                years=[2023],
                output_dir=output_dir,
            )

            assert set(loaded["year"].unique()) == {2023}

    def test_load_nonexistent_raises(self):
        """Loading nonexistent file should raise FileNotFoundError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            with pytest.raises(FileNotFoundError):
                load_state_targets("income_distribution", output_dir=output_dir)


class TestReweighterIntegration:
    """Test conversion to microplex Reweighter format."""

    def test_convert_to_reweighter_format(self):
        """Should convert to expected dict format."""
        df = pd.DataFrame(
            {
                "state_code": ["CA", "TX", "NY"],
                "target_returns": [1000, 800, 700],
            }
        )

        targets = convert_to_reweighter_targets(
            df,
            target_col="target_returns",
            category_col="state_code",
            microdata_col="state",
        )

        assert "state" in targets
        assert targets["state"]["CA"] == 1000
        assert targets["state"]["TX"] == 800
        assert targets["state"]["NY"] == 700

    def test_convert_handles_multiple_rows_same_category(self):
        """Should handle multiple rows with same category (last wins)."""
        df = pd.DataFrame(
            {
                "state_code": ["CA", "CA"],
                "target_returns": [1000, 1500],
            }
        )

        targets = convert_to_reweighter_targets(
            df,
            target_col="target_returns",
            category_col="state_code",
            microdata_col="state",
        )

        # Last value should win
        assert targets["state"]["CA"] == 1500
