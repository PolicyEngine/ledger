"""ETL for source-backed SSA Annual Statistical Supplement targets."""

from __future__ import annotations

import csv
from functools import lru_cache
from importlib.resources import files
from typing import Any, TypedDict

import yaml
from sqlalchemy import delete
from sqlmodel import Session

from .etl_soi import get_or_create_stratum
from .schema import DataSource, GeographicLevel, Jurisdiction, Target, TargetType

PACKAGE_DIR = "data/ssa/annual_statistical_supplement_2025"
MANIFEST = "manifest.yaml"
SOURCE_KEY = "extracted_targets"


class SSASupplementTarget(TypedDict):
    """One source-backed SSA target row."""

    variable: str
    period: int
    value: int
    source_table: str
    source_url: str
    notes: str


@lru_cache(maxsize=1)
def _manifest() -> dict[str, Any]:
    manifest_path = files("db").joinpath(PACKAGE_DIR, MANIFEST)
    with manifest_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _file_spec() -> dict[str, Any]:
    return _manifest()["files"][SOURCE_KEY]


@lru_cache(maxsize=1)
def load_ssa_supplement_data() -> tuple[SSASupplementTarget, ...]:
    """Read packaged SSA Annual Statistical Supplement extracted rows."""
    csv_path = files("db").joinpath(PACKAGE_DIR, _file_spec()["filename"])
    with csv_path.open("r", encoding="utf-8", newline="") as f:
        rows = tuple(csv.DictReader(f))
    return tuple(
        {
            "variable": str(row["variable"]),
            "period": int(row["period"]),
            "value": int(row["value"]),
            "source_table": str(row["source_table"]),
            "source_url": str(row["source_url"]),
            "notes": str(row["notes"]),
        }
        for row in rows
    )


def available_ssa_supplement_years() -> list[int]:
    """Return years with packaged SSA supplement target rows."""
    return sorted({row["period"] for row in load_ssa_supplement_data()})


def load_ssa_supplement_targets(
    session: Session,
    years: list[int] | None = None,
) -> None:
    """Load source-backed SSA Annual Statistical Supplement targets."""
    if years is None:
        years = available_ssa_supplement_years()
    rows = tuple(row for row in load_ssa_supplement_data() if row["period"] in years)
    variables = sorted({row["variable"] for row in rows})
    if variables:
        session.exec(
            delete(Target).where(
                Target.source == DataSource.SSA,
                Target.period.in_(years),
                Target.variable.in_(variables),
            )
        )

    national_stratum = get_or_create_stratum(
        session,
        name="US population",
        jurisdiction=Jurisdiction.US,
        constraints=[],
        description="United States population",
        stratum_group_id="ssa_supplement_national",
    )
    for row in rows:
        session.add(
            Target(
                stratum_id=int(national_stratum.id),
                variable=row["variable"],
                period=row["period"],
                value=row["value"],
                target_type=TargetType.AMOUNT,
                geographic_level=GeographicLevel.NATIONAL,
                source=DataSource.SSA,
                source_table=row["source_table"],
                source_url=row["source_url"],
                notes=row["notes"],
            )
        )
    session.commit()
