"""ETL for Census State Tax Collections individual income-tax targets."""

from __future__ import annotations

import hashlib
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

PACKAGE_DIR = "data/census/stc_individual_income_tax"
MANIFEST = "manifest.yaml"
STC_INDIVIDUAL_INCOME_TAX_ITEM = "T40"
STC_NOT_AVAILABLE = "X"
MONEY_SCALE = 1_000


class CensusStcIncomeTaxRow(TypedDict):
    state_fips: str
    state_abbrev: str
    value: int


class CensusStcIncomeTaxData(TypedDict):
    source_url: str
    national_total: int
    states: dict[str, CensusStcIncomeTaxRow]


@lru_cache(maxsize=1)
def _manifest() -> dict[str, Any]:
    manifest_path = files("db").joinpath(PACKAGE_DIR, MANIFEST)
    with manifest_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def available_census_stc_income_tax_years() -> list[int]:
    """Return packaged Census STC years."""
    return sorted(int(year) for year in _manifest()["files"])


def census_stc_income_tax_source_url(year: int) -> str:
    """Return the Census source URL for a packaged STC year."""
    return str(_file_spec(year)["source_url"])


def _file_spec(year: int) -> dict[str, Any]:
    files_by_year = _manifest()["files"]
    try:
        return files_by_year[year]
    except KeyError:
        return files_by_year[str(year)]


@lru_cache(maxsize=None)
def _content(year: int) -> bytes:
    spec = _file_spec(year)
    package_path = files("db").joinpath(PACKAGE_DIR, spec["filename"])
    content = package_path.read_bytes()
    expected_sha = spec.get("sha256")
    if expected_sha:
        actual_sha = hashlib.sha256(content).hexdigest()
        if actual_sha != expected_sha:
            raise ValueError(
                f"Census STC source file {year} checksum mismatch: "
                f"expected {expected_sha}, got {actual_sha}"
            )
    return content


@lru_cache(maxsize=None)
def _read_frame(year: int) -> pd.DataFrame:
    return pd.read_csv(BytesIO(_content(year)), dtype=str, keep_default_na=False)


def load_census_stc_income_tax_data(year: int) -> CensusStcIncomeTaxData:
    """Parse STC item T40 individual income-tax collections for one fiscal year."""
    if year not in available_census_stc_income_tax_years():
        raise ValueError(f"Census STC year {year} is not packaged.")

    frame = _read_frame(year)
    item_rows = frame[frame["ITEM"] == STC_INDIVIDUAL_INCOME_TAX_ITEM]
    if len(item_rows) != 1:
        raise ValueError(
            f"Expected exactly one Census STC {STC_INDIVIDUAL_INCOME_TAX_ITEM} "
            f"row for {year}, found {len(item_rows)}."
        )
    row = item_rows.iloc[0]
    states: dict[str, CensusStcIncomeTaxRow] = {}
    for state_abbrev, state_fips in STATE_FIPS.items():
        raw_value = row[state_abbrev]
        states[state_abbrev] = {
            "state_fips": state_fips,
            "state_abbrev": state_abbrev,
            "value": _stc_money_value(raw_value),
        }

    return {
        "source_url": census_stc_income_tax_source_url(year),
        "national_total": _stc_money_value(row["US"]),
        "states": dict(sorted(states.items())),
    }


def load_census_stc_income_tax_targets(
    session: Session,
    years: list[int] | None = None,
) -> None:
    """Load state individual income-tax collection targets from Census STC."""
    if years is None:
        years = available_census_stc_income_tax_years()
    years = [year for year in years if year in available_census_stc_income_tax_years()]
    if not years:
        return

    session.exec(
        delete(Target).where(
            Target.source == DataSource.CENSUS_STC,
            Target.variable == "state_individual_income_tax_collections",
            Target.period.in_(years),
        )
    )

    for year in years:
        data = load_census_stc_income_tax_data(year)
        for state_abbrev, state_data in data["states"].items():
            state_stratum = get_or_create_stratum(
                session,
                name=f"{state_abbrev} state government",
                jurisdiction=Jurisdiction.US,
                constraints=[("state_fips", "==", state_data["state_fips"])],
                description=f"{state_abbrev} state government geography",
                stratum_group_id="census_stc_states",
            )
            session.add(
                Target(
                    stratum_id=int(state_stratum.id),
                    variable="state_individual_income_tax_collections",
                    period=year,
                    value=state_data["value"],
                    target_type=TargetType.AMOUNT,
                    geographic_level=GeographicLevel.STATE,
                    source=DataSource.CENSUS_STC,
                    source_table=(
                        f"FY{year} STC Flat File item T40 Individual Income Taxes"
                    ),
                    source_url=data["source_url"],
                    notes=(
                        "Census State Tax Collections item T40, individual income "
                        "taxes; source values are reported in thousands of dollars."
                    ),
                )
            )

    session.commit()


def _stc_money_value(value: object) -> int:
    raw_value = str(value).strip()
    if not raw_value or raw_value == STC_NOT_AVAILABLE:
        return 0
    return int(raw_value) * MONEY_SCALE
