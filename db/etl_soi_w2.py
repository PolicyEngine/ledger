"""ETL for IRS SOI Form W-2 statistics targets."""

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
from .schema import DataSource, GeographicLevel, Jurisdiction, Target, TargetType

PACKAGE_DIR = "data/irs_soi/w2_statistics"
MANIFEST = "manifest.yaml"
PRIOR_TABLE_5A = "Table 5.A"
CURRENT_TABLE_4B = "Table 4.B"
VARIABLE = "tip_income"
SOURCE_TABLE_PREFIX = "IRS SOI Form W-2 Statistics"
SOCIAL_SECURITY_TIPS_LABEL = "Box 7: Social security tips"
MONEY_SCALE = 1_000


class SOIW2TipIncomeData(TypedDict):
    """Parsed national Form W-2 social-security tips fact."""

    source_url: str
    source_table: str
    social_security_tips: int
    returns: int
    taxpayers: int


@lru_cache(maxsize=1)
def _manifest() -> dict[str, Any]:
    manifest_path = files("db").joinpath(PACKAGE_DIR, MANIFEST)
    with manifest_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def available_soi_w2_years() -> list[int]:
    """Return packaged IRS SOI Form W-2 statistic years."""
    years: list[int] = []
    for spec in _manifest()["files"].values():
        years.extend(int(year) for year in spec["years"])
    return sorted(years)


def _file_spec(year: int) -> dict[str, Any]:
    for spec in _manifest()["files"].values():
        if year in {int(value) for value in spec["years"]}:
            return spec
    raise KeyError(f"No packaged IRS SOI Form W-2 workbook for {year}")


def soi_w2_source_url(year: int) -> str:
    """Return the IRS workbook URL for a Form W-2 statistic year."""
    return str(_file_spec(year)["source_url"])


@lru_cache(maxsize=None)
def _content(filename: str, expected_sha: str | None = None) -> bytes:
    package_path = files("db").joinpath(PACKAGE_DIR, filename)
    content = package_path.read_bytes()
    if expected_sha:
        actual_sha = hashlib.sha256(content).hexdigest()
        if actual_sha != expected_sha:
            raise ValueError(
                f"IRS SOI Form W-2 workbook {filename} checksum mismatch: "
                f"expected {expected_sha}, got {actual_sha}"
            )
    return content


@lru_cache(maxsize=None)
def _read_sheet(filename: str, sheet_name: str, expected_sha: str | None) -> pd.DataFrame:
    return pd.read_excel(
        BytesIO(_content(filename, expected_sha)),
        sheet_name=sheet_name,
        header=None,
    )


@lru_cache(maxsize=None)
def load_soi_w2_tip_income_data(year: int) -> SOIW2TipIncomeData:
    """Parse national Form W-2 Box 7 social-security tips from IRS SOI."""
    spec = _file_spec(year)
    sheet_name = str(spec["sheet_name"])
    df = _read_sheet(
        str(spec["filename"]),
        sheet_name,
        spec.get("sha256"),
    )
    row = _find_social_security_tips_row(df, year)
    return {
        "source_url": str(spec["source_url"]),
        "source_table": f"{SOURCE_TABLE_PREFIX} {spec['table']}",
        "social_security_tips": _money_value(row.iloc[3]),
        "returns": _count_value(row.iloc[1]),
        "taxpayers": _count_value(row.iloc[2]),
    }


def load_soi_w2_targets(
    session: Session,
    years: list[int] | None = None,
) -> None:
    """Load IRS SOI Form W-2 social-security tip-income targets."""
    if years is None:
        years = available_soi_w2_years()

    session.exec(
        delete(Target).where(
            Target.source == DataSource.IRS_SOI,
            Target.period.in_(years),
            Target.variable == VARIABLE,
            Target.source_table.like(f"{SOURCE_TABLE_PREFIX}%"),
        )
    )

    stratum = get_or_create_stratum(
        session,
        name="US taxpayers with Form W-2 social security tips",
        jurisdiction=Jurisdiction.US,
        constraints=[("tip_income", ">", "0")],
        description="Taxpayers reporting Form W-2 Box 7 social security tips",
        stratum_group_id="soi_w2_social_security_tips",
    )
    for year in years:
        if year not in available_soi_w2_years():
            continue
        data = load_soi_w2_tip_income_data(year)
        session.add(
            Target(
                stratum_id=int(stratum.id),
                variable=VARIABLE,
                period=year,
                value=data["social_security_tips"],
                target_type=TargetType.AMOUNT,
                geographic_level=GeographicLevel.NATIONAL,
                source=DataSource.IRS_SOI,
                source_table=data["source_table"],
                source_url=data["source_url"],
                notes=(
                    "Form W-2 Box 7 Social security tips. Source money amounts "
                    "are published in thousands of dollars."
                ),
            )
        )

    session.commit()


def _find_social_security_tips_row(df: pd.DataFrame, year: int) -> pd.Series:
    in_year_block = False
    for _, row in df.iterrows():
        first_cell = _cell_text(row.iloc[0])
        if f"Tax Year {year}" in first_cell:
            in_year_block = True
            continue
        if in_year_block and first_cell.startswith("Table "):
            break
        if in_year_block and first_cell == SOCIAL_SECURITY_TIPS_LABEL:
            return row
    raise ValueError(
        f"IRS SOI Form W-2 statistics missing {SOCIAL_SECURITY_TIPS_LABEL} for {year}"
    )


def _cell_text(value: object) -> str:
    if pd.isna(value):
        return ""
    return " ".join(str(value).split())


def _numeric_value(value: object) -> float:
    text = _cell_text(value).replace(",", "")
    if not text:
        raise ValueError("Expected numeric IRS SOI Form W-2 cell, got empty value")
    return float(text)


def _count_value(value: object) -> int:
    return int(round(_numeric_value(value)))


def _money_value(value: object) -> int:
    return int(round(_numeric_value(value) * MONEY_SCALE))
