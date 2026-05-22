"""ETL for CMS National Health Expenditure Account targets."""

from __future__ import annotations

import csv
import hashlib
from functools import lru_cache
from importlib.resources import files
from io import BytesIO, TextIOWrapper
from typing import Any, TypedDict
from zipfile import ZipFile

import yaml
from sqlalchemy import delete
from sqlmodel import Session

from .etl_soi import get_or_create_stratum
from .schema import DataSource, GeographicLevel, Jurisdiction, Target, TargetType

PACKAGE_DIR = "data/cms_nhe/historical_service_source"
MANIFEST = "manifest.yaml"
SOURCE_TABLE = (
    "National Health Expenditures by type of service and source of funds, "
    "CY 1960-2024"
)
SOURCE_KEY = "historical_service_source"
MEDICAID_ROW_LABEL = "Medicaid (Title XIX)"
MILLION_DOLLARS = 1_000_000


class CMSNHEData(TypedDict):
    """Parsed CMS NHE source facts used by Arch loaders."""

    source_url: str
    medicaid_benefits_by_year: dict[int, int]


@lru_cache(maxsize=1)
def _manifest() -> dict[str, Any]:
    manifest_path = files("db").joinpath(PACKAGE_DIR, MANIFEST)
    with manifest_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _file_spec() -> dict[str, Any]:
    return _manifest()["files"][SOURCE_KEY]


def cms_nhe_source_url() -> str:
    """Return the CMS source URL for the packaged NHE historical table."""
    return str(_file_spec()["source_url"])


@lru_cache(maxsize=1)
def _content() -> bytes:
    spec = _file_spec()
    package_path = files("db").joinpath(PACKAGE_DIR, spec["filename"])
    content = package_path.read_bytes()
    expected_sha = spec.get("sha256")
    if expected_sha:
        actual_sha = hashlib.sha256(content).hexdigest()
        if actual_sha != expected_sha:
            raise ValueError(
                "CMS NHE source file checksum mismatch: "
                f"expected {expected_sha}, got {actual_sha}"
            )
    return content


@lru_cache(maxsize=1)
def load_cms_nhe_data() -> CMSNHEData:
    """Parse Medicaid expenditure targets from the packaged CMS NHE source."""
    spec = _file_spec()
    with ZipFile(BytesIO(_content())) as archive:
        with archive.open(str(spec["csv_member"])) as raw:
            rows = list(csv.reader(TextIOWrapper(raw, encoding="cp1252")))

    header = _find_year_header(rows)
    medicaid_row = _find_medicaid_expenditure_row(rows)
    years = [int(value) for value in header[1:] if str(value).strip()]
    values = medicaid_row[1 : len(years) + 1]
    benefits_by_year: dict[int, int] = {}
    for year, value in zip(years, values, strict=True):
        parsed = _million_dollar_value(value)
        if parsed is not None:
            benefits_by_year[year] = parsed
    return {
        "source_url": cms_nhe_source_url(),
        "medicaid_benefits_by_year": benefits_by_year,
    }


def available_cms_nhe_years() -> list[int]:
    """Return years with packaged CMS NHE Medicaid expenditure values."""
    return sorted(load_cms_nhe_data()["medicaid_benefits_by_year"])


def load_cms_nhe_targets(
    session: Session,
    years: list[int] | None = None,
) -> None:
    """Load CMS NHE Medicaid expenditure targets into the database."""
    data = load_cms_nhe_data()
    if years is None:
        years = available_cms_nhe_years()

    session.exec(
        delete(Target).where(
            Target.source == DataSource.CMS_MEDICAID,
            Target.source_table == SOURCE_TABLE,
            Target.period.in_(years),
            Target.variable == "medicaid_benefits",
        )
    )

    national_stratum = get_or_create_stratum(
        session,
        name="US population",
        jurisdiction=Jurisdiction.US,
        constraints=[],
        description="United States population",
        stratum_group_id="cms_nhe_national",
    )
    for year in years:
        value = data["medicaid_benefits_by_year"].get(year)
        if value is None:
            continue
        session.add(
            Target(
                stratum_id=int(national_stratum.id),
                variable="medicaid_benefits",
                period=year,
                value=value,
                target_type=TargetType.AMOUNT,
                geographic_level=GeographicLevel.NATIONAL,
                source=DataSource.CMS_MEDICAID,
                source_table=SOURCE_TABLE,
                source_url=data["source_url"],
                notes="CMS NHE source-of-funds expenditure, converted from millions of dollars.",
            )
        )
    session.commit()


def _find_year_header(rows: list[list[str]]) -> list[str]:
    for row in rows:
        if row and row[0].strip() == "Expenditure Amount (Millions)":
            return row
    raise ValueError("Could not find CMS NHE expenditure year header")


def _find_medicaid_expenditure_row(rows: list[list[str]]) -> list[str]:
    for row in rows:
        if row and row[0].strip() == MEDICAID_ROW_LABEL:
            return row
    raise ValueError(f"Could not find CMS NHE row {MEDICAID_ROW_LABEL!r}")


def _million_dollar_value(value: str) -> int | None:
    text = str(value).replace(",", "").strip()
    if not text or text in {"-", "-   "}:
        return None
    try:
        return int(round(float(text) * MILLION_DOLLARS))
    except ValueError:
        return None
