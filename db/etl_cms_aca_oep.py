"""ETL for CMS Marketplace Open Enrollment state-level PUF targets."""

from __future__ import annotations

import hashlib
from functools import lru_cache
from importlib.resources import files
from io import BytesIO
from typing import Any, TypedDict
from zipfile import ZipFile

import pandas as pd
import yaml
from sqlalchemy import delete
from sqlmodel import Session

from .etl_soi_state import STATE_FIPS
from .schema import DataSource, GeographicLevel, Jurisdiction, Target, TargetType
from .etl_soi import get_or_create_stratum

PACKAGE_DIR = "data/cms_aca/oep_state_level"
MANIFEST = "manifest.yaml"
SOURCE_TABLE = "2024 OEP State-Level Public Use File"


class ACAOEPStateData(TypedDict):
    enrollment: int
    aptc_recipients: int
    avg_monthly_aptc: float
    annual_aptc_amount: int


class ACAOEPData(TypedDict):
    source_url: str
    states: dict[str, ACAOEPStateData]


@lru_cache(maxsize=1)
def _manifest() -> dict[str, Any]:
    manifest_path = files("db").joinpath(PACKAGE_DIR, MANIFEST)
    with manifest_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def available_cms_aca_oep_years() -> list[int]:
    """Return packaged CMS Marketplace OEP state-level PUF years."""
    return sorted(int(year) for year in _manifest()["files"])


def _file_spec(year: int) -> dict[str, Any]:
    files_by_year = _manifest()["files"]
    try:
        return files_by_year[year]
    except KeyError:
        return files_by_year[str(year)]


def cms_aca_oep_source_url(year: int) -> str:
    """Return the CMS source URL for a Marketplace OEP state-level PUF year."""
    return str(_file_spec(year)["source_url"])


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
                f"CMS ACA OEP source file {year} checksum mismatch: "
                f"expected {expected_sha}, got {actual_sha}"
            )
    return content


@lru_cache(maxsize=None)
def _read_frame(year: int) -> pd.DataFrame:
    with ZipFile(BytesIO(_content(year))) as archive:
        csv_names = [name for name in archive.namelist() if name.endswith(".csv")]
        if len(csv_names) != 1:
            raise ValueError(
                f"CMS ACA OEP source file {year} should contain one CSV, "
                f"found {csv_names}"
            )
        with archive.open(csv_names[0]) as f:
            return pd.read_csv(f, dtype=str, keep_default_na=False)


def load_cms_aca_oep_data(year: int) -> ACAOEPData:
    """Parse state-level ACA APTC targets from CMS Marketplace OEP PUF."""
    states: dict[str, ACAOEPStateData] = {}
    for _, row in _read_frame(year).iterrows():
        state = str(row["State_Abrvtn"])
        if state not in STATE_FIPS:
            continue
        aptc_recipients = _count_value(row["APTC_Cnsmr"])
        avg_monthly_aptc = _money_value(row["APTC_Cnsmr_Avg_APTC"])
        states[state] = {
            "enrollment": _count_value(row["Cnsmr"]),
            "aptc_recipients": aptc_recipients,
            "avg_monthly_aptc": avg_monthly_aptc,
            "annual_aptc_amount": int(round(aptc_recipients * avg_monthly_aptc * 12)),
        }
    return {
        "source_url": cms_aca_oep_source_url(year),
        "states": states,
    }


def load_cms_aca_oep_targets(
    session: Session,
    years: list[int] | None = None,
) -> None:
    """Load CMS Marketplace OEP state-level PUF targets into the database."""
    if years is None:
        years = available_cms_aca_oep_years()
    variables = [
        "aca_marketplace_enrollment",
        "aca_aptc_recipients",
        "aca_avg_monthly_aptc",
        "aca_aptc_amount",
    ]
    session.exec(
        delete(Target).where(
            Target.source == DataSource.CMS_ACA,
            Target.source_table == SOURCE_TABLE,
            Target.period.in_(years),
            Target.variable.in_(variables),
        )
    )

    for year in years:
        if year not in available_cms_aca_oep_years():
            continue
        data = load_cms_aca_oep_data(year)
        for state_abbrev, state_data in data["states"].items():
            state_stratum = get_or_create_stratum(
                session,
                name=f"{state_abbrev} ACA Marketplace",
                jurisdiction=Jurisdiction.US,
                constraints=[("state_fips", "==", STATE_FIPS[state_abbrev])],
                description=f"ACA Marketplace plan selections in {state_abbrev}",
                stratum_group_id="cms_aca_oep_states",
            )
            _add_target(
                session,
                stratum_id=int(state_stratum.id),
                variable="aca_marketplace_enrollment",
                period=year,
                value=state_data["enrollment"],
                target_type=TargetType.COUNT,
                source_url=data["source_url"],
            )
            _add_target(
                session,
                stratum_id=int(state_stratum.id),
                variable="aca_aptc_recipients",
                period=year,
                value=state_data["aptc_recipients"],
                target_type=TargetType.COUNT,
                source_url=data["source_url"],
            )
            _add_target(
                session,
                stratum_id=int(state_stratum.id),
                variable="aca_avg_monthly_aptc",
                period=year,
                value=state_data["avg_monthly_aptc"],
                target_type=TargetType.AMOUNT,
                source_url=data["source_url"],
            )
            _add_target(
                session,
                stratum_id=int(state_stratum.id),
                variable="aca_aptc_amount",
                period=year,
                value=state_data["annual_aptc_amount"],
                target_type=TargetType.AMOUNT,
                source_url=data["source_url"],
            )
    session.commit()


def _add_target(
    session: Session,
    *,
    stratum_id: int,
    variable: str,
    period: int,
    value: float,
    target_type: TargetType,
    source_url: str,
) -> None:
    session.add(
        Target(
            stratum_id=stratum_id,
            variable=variable,
            period=period,
            value=value,
            target_type=target_type,
            geographic_level=GeographicLevel.STATE,
            source=DataSource.CMS_ACA,
            source_table=SOURCE_TABLE,
            source_url=source_url,
        )
    )


def _numeric_value(value: object) -> float:
    text = str(value).replace("$", "").replace(",", "").strip()
    if text in {"", "+", "NR"}:
        raise ValueError(f"Expected numeric CMS ACA OEP cell, got {value!r}")
    return float(text)


def _count_value(value: object) -> int:
    return int(round(_numeric_value(value)))


def _money_value(value: object) -> float:
    return float(_numeric_value(value))
