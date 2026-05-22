"""ETL for Census Population Estimates Program age-population targets."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from functools import lru_cache
from importlib.resources import files
from io import BytesIO
from typing import Any, TypedDict

import pandas as pd
import yaml
from sqlalchemy import delete
from sqlmodel import Session

from .etl_soi import get_or_create_stratum
from .etl_soi_state import STATE_FIPS
from .schema import (
    DataSource,
    GeographicLevel,
    Jurisdiction,
    Target,
    TargetType,
)

PACKAGE_DIR = "data/census/pep_2024_age_sex"
MANIFEST = "manifest.yaml"
NATIONAL_FILE_KEY = "national_age_sex"
STATE_FILE_KEY = "state_age_sex_race_origin"


@dataclass(frozen=True)
class AgeBand:
    """Closed-open age band, except open-ended when upper is None."""

    key: str
    lower: int
    upper: int | None

    @property
    def constraints(self) -> list[tuple[str, str, str]]:
        constraints = [("age", ">=", str(self.lower))]
        if self.upper is not None:
            constraints.append(("age", "<", str(self.upper)))
        return constraints

    @property
    def label(self) -> str:
        if self.upper is None:
            return f"{self.lower}+"
        return f"{self.lower}-{self.upper - 1}"


AGE_BANDS = (
    AgeBand("0_to_4", 0, 5),
    AgeBand("5_to_9", 5, 10),
    AgeBand("10_to_14", 10, 15),
    AgeBand("15_to_19", 15, 20),
    AgeBand("20_to_24", 20, 25),
    AgeBand("25_to_29", 25, 30),
    AgeBand("30_to_34", 30, 35),
    AgeBand("35_to_39", 35, 40),
    AgeBand("40_to_44", 40, 45),
    AgeBand("45_to_49", 45, 50),
    AgeBand("50_to_54", 50, 55),
    AgeBand("55_to_59", 55, 60),
    AgeBand("60_to_64", 60, 65),
    AgeBand("65_to_69", 65, 70),
    AgeBand("70_to_74", 70, 75),
    AgeBand("75_to_79", 75, 80),
    AgeBand("80_to_84", 80, 85),
    AgeBand("85_plus", 85, None),
)

STATE_ABBREVIATIONS_BY_FIPS = {fips: state for state, fips in STATE_FIPS.items()}


class CensusPepPopulationSlice(TypedDict):
    total: int
    age_groups: dict[str, int]


class CensusPepPopulationData(TypedDict):
    source_urls: dict[str, str]
    national: CensusPepPopulationSlice
    states: dict[str, CensusPepPopulationSlice]


@lru_cache(maxsize=1)
def _manifest() -> dict[str, Any]:
    manifest_path = files("db").joinpath(PACKAGE_DIR, MANIFEST)
    with manifest_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def available_census_pep_population_years() -> list[int]:
    """Return packaged Census PEP years available for both national and state data."""
    files_by_key = _manifest()["files"]
    national_years = {int(year) for year in files_by_key[NATIONAL_FILE_KEY]["years"]}
    state_years = {int(year) for year in files_by_key[STATE_FILE_KEY]["years"]}
    return sorted(national_years & state_years)


def census_pep_source_url(file_key: str) -> str:
    """Return the Census source URL for a packaged PEP file."""
    return str(_manifest()["files"][file_key]["source_url"])


@lru_cache(maxsize=None)
def _content(file_key: str) -> bytes:
    spec = _manifest()["files"][file_key]
    package_path = files("db").joinpath(PACKAGE_DIR, spec["filename"])
    content = package_path.read_bytes()
    expected_sha = spec.get("sha256")
    if expected_sha:
        actual_sha = hashlib.sha256(content).hexdigest()
        if actual_sha != expected_sha:
            raise ValueError(
                f"Census PEP source file {file_key} checksum mismatch: "
                f"expected {expected_sha}, got {actual_sha}"
            )
    return content


@lru_cache(maxsize=1)
def _national_frame() -> pd.DataFrame:
    frame = pd.read_csv(BytesIO(_content(NATIONAL_FILE_KEY)))
    frame["AGE"] = frame["AGE"].astype(int)
    frame["SEX"] = frame["SEX"].astype(int)
    return frame


@lru_cache(maxsize=1)
def _state_frame() -> pd.DataFrame:
    frame = pd.read_csv(
        BytesIO(_content(STATE_FILE_KEY)),
        dtype={"STATE": str},
    )
    frame["STATE"] = frame["STATE"].str.zfill(2)
    frame["AGE"] = frame["AGE"].astype(int)
    frame["SEX"] = frame["SEX"].astype(int)
    frame["ORIGIN"] = frame["ORIGIN"].astype(int)
    return frame


def load_census_pep_population_data(year: int) -> CensusPepPopulationData:
    """Parse Census PEP resident population totals by national/state age band."""
    if year not in available_census_pep_population_years():
        raise ValueError(f"Census PEP year {year} is not packaged.")

    column = _population_column(year)
    national_rows = _national_frame()
    national_all_sexes = national_rows[national_rows["SEX"] == 0]
    national_total_rows = national_all_sexes[national_all_sexes["AGE"] == 999]
    if national_total_rows.empty:
        raise ValueError(f"Census PEP national file missing total row for {year}.")
    national_by_age = national_all_sexes[national_all_sexes["AGE"] != 999]

    state_rows = _state_frame()
    state_total_rows = state_rows[
        (state_rows["SEX"] == 0)
        & (state_rows["ORIGIN"] == 0)
        & (state_rows["STATE"].isin(STATE_ABBREVIATIONS_BY_FIPS))
    ]

    states: dict[str, CensusPepPopulationSlice] = {}
    for state_fips, rows in state_total_rows.groupby("STATE"):
        state_abbreviation = STATE_ABBREVIATIONS_BY_FIPS[state_fips]
        states[state_abbreviation] = {
            "total": _population_value(rows[column].sum()),
            "age_groups": _age_group_values(rows, column),
        }

    return {
        "source_urls": {
            "national": census_pep_source_url(NATIONAL_FILE_KEY),
            "state": census_pep_source_url(STATE_FILE_KEY),
        },
        "national": {
            "total": _population_value(national_total_rows[column].iloc[0]),
            "age_groups": _age_group_values(national_by_age, column),
        },
        "states": dict(sorted(states.items())),
    }


def load_census_pep_population_targets(
    session: Session,
    years: list[int] | None = None,
) -> None:
    """Load Census PEP population count targets into the Arch targets DB."""
    if years is None:
        years = available_census_pep_population_years()
    years = [year for year in years if year in available_census_pep_population_years()]
    if not years:
        return

    session.exec(
        delete(Target).where(
            Target.source == DataSource.CENSUS_PEP,
            Target.variable == "population",
            Target.period.in_(years),
        )
    )

    national_stratum = get_or_create_stratum(
        session,
        name="US resident population",
        jurisdiction=Jurisdiction.US,
        constraints=[],
        description="United States resident population",
        stratum_group_id="census_pep_national",
    )

    for year in years:
        data = load_census_pep_population_data(year)
        _add_population_target(
            session,
            stratum_id=int(national_stratum.id),
            period=year,
            value=data["national"]["total"],
            geographic_level=GeographicLevel.NATIONAL,
            source_url=data["source_urls"]["national"],
            notes="Census PEP Vintage 2024 resident population estimate.",
        )

        for age_band in AGE_BANDS:
            age_stratum = get_or_create_stratum(
                session,
                name=f"US resident population age {age_band.label}",
                jurisdiction=Jurisdiction.US,
                constraints=age_band.constraints,
                description=f"United States resident population age {age_band.label}",
                parent_id=national_stratum.id,
                stratum_group_id="census_pep_national_age",
            )
            _add_population_target(
                session,
                stratum_id=int(age_stratum.id),
                period=year,
                value=data["national"]["age_groups"][age_band.key],
                geographic_level=GeographicLevel.NATIONAL,
                source_url=data["source_urls"]["national"],
                notes="Census PEP Vintage 2024 resident population estimate by age.",
            )

        for state_abbreviation, state_values in data["states"].items():
            state_fips = STATE_FIPS[state_abbreviation]
            state_stratum = get_or_create_stratum(
                session,
                name=f"{state_abbreviation} resident population",
                jurisdiction=Jurisdiction.US,
                constraints=[("state_fips", "==", state_fips)],
                description=f"{state_abbreviation} resident population",
                parent_id=national_stratum.id,
                stratum_group_id="census_pep_state",
            )
            _add_population_target(
                session,
                stratum_id=int(state_stratum.id),
                period=year,
                value=state_values["total"],
                geographic_level=GeographicLevel.STATE,
                source_url=data["source_urls"]["state"],
                notes="Census PEP Vintage 2024 resident population estimate.",
            )

            for age_band in AGE_BANDS:
                age_stratum = get_or_create_stratum(
                    session,
                    name=f"{state_abbreviation} resident population age {age_band.label}",
                    jurisdiction=Jurisdiction.US,
                    constraints=[
                        ("state_fips", "==", state_fips),
                        *age_band.constraints,
                    ],
                    description=(
                        f"{state_abbreviation} resident population age "
                        f"{age_band.label}"
                    ),
                    parent_id=state_stratum.id,
                    stratum_group_id="census_pep_state_age",
                )
                _add_population_target(
                    session,
                    stratum_id=int(age_stratum.id),
                    period=year,
                    value=state_values["age_groups"][age_band.key],
                    geographic_level=GeographicLevel.STATE,
                    source_url=data["source_urls"]["state"],
                    notes=(
                        "Census PEP Vintage 2024 resident population estimate by age; "
                        "state source stores age 85 as 85+."
                    ),
                )

    session.commit()


def _population_column(year: int) -> str:
    column = f"POPESTIMATE{year}"
    national_columns = set(_national_frame().columns)
    state_columns = set(_state_frame().columns)
    if column not in national_columns or column not in state_columns:
        raise ValueError(f"Census PEP files do not contain {column}.")
    return column


def _age_group_values(rows: pd.DataFrame, column: str) -> dict[str, int]:
    values: dict[str, int] = {}
    for age_band in AGE_BANDS:
        if age_band.upper is None:
            selected = rows[rows["AGE"] >= age_band.lower]
        else:
            selected = rows[
                (rows["AGE"] >= age_band.lower) & (rows["AGE"] < age_band.upper)
            ]
        values[age_band.key] = _population_value(selected[column].sum())
    return values


def _population_value(value: object) -> int:
    return int(round(float(value)))


def _add_population_target(
    session: Session,
    *,
    stratum_id: int,
    period: int,
    value: int,
    geographic_level: GeographicLevel,
    source_url: str,
    notes: str,
) -> None:
    session.add(
        Target(
            stratum_id=stratum_id,
            variable="population",
            period=period,
            value=value,
            target_type=TargetType.COUNT,
            geographic_level=geographic_level,
            source=DataSource.CENSUS_PEP,
            source_table="Census PEP Vintage 2024 age-sex population estimates",
            source_url=source_url,
            notes=notes,
        )
    )
