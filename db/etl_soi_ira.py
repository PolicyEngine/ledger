"""ETL for IRS SOI IRA contribution targets."""

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

PACKAGE_DIR = "data/irs_soi/ira_contributions"
MANIFEST = "manifest.yaml"
VARIABLES = ("traditional_ira_contributions", "roth_ira_contributions")
MONEY_SCALE = 1_000


class SOIIRAContributionData(TypedDict):
    """Parsed national IRA contribution fact."""

    source_url: str
    source_table: str
    amount: int
    taxpayers: int


@lru_cache(maxsize=1)
def _manifest() -> dict[str, Any]:
    manifest_path = files("db").joinpath(PACKAGE_DIR, MANIFEST)
    with manifest_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def available_soi_ira_years(variable: str | None = None) -> list[int]:
    """Return packaged IRS SOI IRA contribution years."""
    variables = (variable,) if variable else VARIABLES
    years: set[int] = set()
    for variable_name in variables:
        years.update(int(year) for year in _manifest()["files"][variable_name])
    return sorted(years)


def _file_spec(variable: str, year: int) -> dict[str, Any]:
    if variable not in VARIABLES:
        raise KeyError(f"Unsupported IRS SOI IRA contribution variable: {variable}")
    files_by_year = _manifest()["files"][variable]
    try:
        return files_by_year[year]
    except KeyError:
        return files_by_year[str(year)]


@lru_cache(maxsize=None)
def _content(filename: str, expected_sha: str | None = None) -> bytes:
    package_path = files("db").joinpath(PACKAGE_DIR, filename)
    content = package_path.read_bytes()
    if expected_sha:
        actual_sha = hashlib.sha256(content).hexdigest()
        if actual_sha != expected_sha:
            raise ValueError(
                f"IRS SOI IRA workbook {filename} checksum mismatch: "
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
def load_soi_ira_contribution_data(
    variable: str,
    year: int,
) -> SOIIRAContributionData:
    """Parse national IRA contribution amount from IRS SOI Table 5 or 6."""
    spec = _file_spec(variable, year)
    df = _read_sheet(
        str(spec["filename"]),
        str(spec["sheet_name"]),
        spec.get("sha256"),
    )
    row = _find_all_taxpayers_row(df)
    return {
        "source_url": str(spec["source_url"]),
        "source_table": str(spec["source_table"]),
        "amount": _money_value(row.iloc[2]),
        "taxpayers": _count_value(row.iloc[1]),
    }


def load_soi_ira_targets(
    session: Session,
    years: list[int] | None = None,
) -> None:
    """Load IRS SOI traditional and Roth IRA contribution targets."""
    if years is None:
        years = sorted({year for variable in VARIABLES for year in available_soi_ira_years(variable)})

    session.exec(
        delete(Target).where(
            Target.source == DataSource.IRS_SOI,
            Target.period.in_(years),
            Target.variable.in_(VARIABLES),
        )
    )

    for variable in VARIABLES:
        stratum = get_or_create_stratum(
            session,
            name=f"US taxpayers with {variable.replace('_', ' ')}",
            jurisdiction=Jurisdiction.US,
            constraints=[(variable, ">", "0")],
            description=f"Taxpayers with positive {variable.replace('_', ' ')}",
            stratum_group_id=f"soi_ira_{variable}",
        )
        for year in years:
            if year not in available_soi_ira_years(variable):
                continue
            data = load_soi_ira_contribution_data(variable, year)
            session.add(
                Target(
                    stratum_id=int(stratum.id),
                    variable=variable,
                    period=year,
                    value=data["amount"],
                    target_type=TargetType.AMOUNT,
                    geographic_level=GeographicLevel.NATIONAL,
                    source=DataSource.IRS_SOI,
                    source_table=data["source_table"],
                    source_url=data["source_url"],
                    notes=(
                        "IRS SOI IRA contribution table total row. Source money "
                        "amounts are published in thousands of dollars."
                    ),
                )
            )
    session.commit()


def _find_all_taxpayers_row(df: pd.DataFrame) -> pd.Series:
    for _, row in df.iterrows():
        if _cell_text(row.iloc[0]) == "All taxpayers":
            return row
    raise ValueError("IRS SOI IRA workbook missing All taxpayers row")


def _cell_text(value: object) -> str:
    if pd.isna(value):
        return ""
    return " ".join(str(value).split())


def _numeric_value(value: object) -> float:
    text = _cell_text(value).replace(",", "")
    if not text or text == "d":
        raise ValueError(f"Expected numeric IRS SOI IRA cell, got {text or 'empty'}")
    return float(text)


def _count_value(value: object) -> int:
    return int(round(_numeric_value(value)))


def _money_value(value: object) -> int:
    return int(round(_numeric_value(value) * MONEY_SCALE))
