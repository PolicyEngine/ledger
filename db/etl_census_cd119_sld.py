"""Helpers for Census CD119 state-legislative district source artifacts."""

from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass
from functools import lru_cache
from importlib.resources import files
from io import BytesIO, TextIOWrapper
from typing import Any, TypedDict
from zipfile import ZipFile

import yaml

PACKAGE_DIR = "data/census/cd119_sld_2024"
MANIFEST = "manifest.yaml"
CENSUS_CD119_BASE_URL = (
    "https://www2.census.gov/programs-surveys/decennial/2020/data/"
    "119th-congressional-district-summary-file/"
)

CD119_GEO_HEADER_FIELDS: tuple[str, ...] = (
    "FILEID",
    "STUSAB",
    "SUMLEV",
    "GEOVAR",
    "GEOCOMP",
    "CHARITER",
    "CIFSN",
    "LOGRECNO",
    "GEOID",
    "GEOCODE",
    "REGION",
    "DIVISION",
    "STATE",
    "STATENS",
    "COUNTY",
    "COUNTYCC",
    "COUNTYNS",
    "COUSUB",
    "COUSUBCC",
    "COUSUBNS",
    "SUBMCD",
    "SUBMCDCC",
    "SUBMCDNS",
    "ESTATE",
    "ESTATECC",
    "ESTATENS",
    "CONCIT",
    "CONCITCC",
    "CONCITNS",
    "PLACE",
    "PLACECC",
    "PLACENS",
    "TRACT",
    "BLKGRP",
    "BLOCK",
    "AIANHH",
    "AIHHTLI",
    "AIANHHFP",
    "AIANHHCC",
    "AIANHHNS",
    "AITS",
    "AITSFP",
    "AITSCC",
    "AITSNS",
    "TTRACT",
    "TBLKGRP",
    "ANRC",
    "ANRCCC",
    "ANRCNS",
    "CBSA",
    "MEMI",
    "CSA",
    "METDIV",
    "NECTA",
    "NMEMI",
    "CNECTA",
    "NECTADIV",
    "CBSAPCI",
    "NECTAPCI",
    "UA",
    "UATYPE",
    "UR",
    "CD116",
    "CD118",
    "CD119",
    "CD120",
    "CD121",
    "SLDU18",
    "SLDU22",
    "SLDU24",
    "SLDU26",
    "SLDU28",
    "SLDL18",
    "SLDL22",
    "SLDL24",
    "SLDL26",
    "SLDL28",
    "VTD",
    "VTDI",
    "ZCTA",
    "SDELM",
    "SDSEC",
    "SDUNI",
    "PUMA",
    "AREALAND",
    "AREAWATR",
    "BASENAME",
    "NAME",
    "FUNCSTAT",
    "GCUNI",
    "POP100",
    "HU100",
    "INTPTLAT",
    "INTPTLON",
    "LSADC",
    "PARTFLAG",
    "UGA",
)

SLD_SUMMARY_LEVELS = {
    "610": ("state_legislative_district_upper", "sldu", "SLDU24"),
    "620": ("state_legislative_district_lower", "sldl", "SLDL24"),
}


@dataclass(frozen=True)
class Cd119Variable:
    """One CD119 segment field extracted for state legislative districts."""

    source_column_id: str
    source_concept: str
    statistic: str
    segment: str
    data_offset: int


CD119_SLD_VARIABLES: tuple[Cd119Variable, ...] = (
    Cd119Variable(
        source_column_id="P0010001",
        source_concept="P1 total population",
        statistic="person_count",
        segment="05",
        data_offset=0,
    ),
    Cd119Variable(
        source_column_id="H0030002",
        source_concept="H3 occupied housing units",
        statistic="household_count",
        segment="01",
        data_offset=6,
    ),
)


class CensusCd119SldRow(TypedDict):
    GEO_ID: str
    NAME: str
    geography_level: str
    state: str
    state_fips: str
    district_code: str
    source_column_id: str
    source_concept: str
    statistic: str
    value: int
    source_logrecno: str
    source_segment: str
    source_data_row_number: int
    state_name: str | None
    source_zip_url: str | None


@lru_cache(maxsize=1)
def _manifest() -> dict[str, Any]:
    manifest_path = files("db").joinpath(PACKAGE_DIR, MANIFEST)
    with manifest_path.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file)


def available_census_cd119_sld_years() -> list[int]:
    """Return packaged CD119 SLD source artifact years."""
    return sorted(int(year) for year in _manifest()["files"])


def census_cd119_sld_source_url(year: int) -> str:
    """Return the upstream Census ZIP URL for a packaged CD119 SLD artifact."""
    return str(_file_spec(year)["source_url"])


def load_census_cd119_sld_rows(year: int) -> list[CensusCd119SldRow]:
    """Load packaged compact CD119 SLD rows."""
    if year not in available_census_cd119_sld_years():
        raise ValueError(f"Census CD119 SLD year {year} is not packaged.")
    content = _content(year)
    data = json.loads(content.decode("utf-8"))
    if not isinstance(data, list):
        raise ValueError("Census CD119 SLD artifact must be a JSON array.")
    return data


def extract_census_cd119_sld_rows(
    zip_content: bytes,
    *,
    source_zip_url: str | None = None,
    state_name: str | None = None,
) -> list[CensusCd119SldRow]:
    """Extract SLD population and occupied-household rows from a CD119 state ZIP."""
    with ZipFile(BytesIO(zip_content)) as archive:
        geo_by_logrecno = _sld_geographies_by_logrecno(archive)
        values_by_logrecno = _sld_values_by_logrecno(archive, set(geo_by_logrecno))

    rows: list[CensusCd119SldRow] = []
    for logrecno, geo in sorted(
        geo_by_logrecno.items(),
        key=lambda item: _sld_sort_key(item[1]),
    ):
        summary_level = geo["SUMLEV"]
        geography_level, chamber, district_field = SLD_SUMMARY_LEVELS[summary_level]
        values = values_by_logrecno.get(logrecno, {})
        for variable in CD119_SLD_VARIABLES:
            value_payload = values.get(variable.source_column_id)
            if value_payload is None:
                raise ValueError(
                    f"Missing {variable.source_column_id} for LOGRECNO {logrecno}."
                )
            rows.append(
                {
                    "GEO_ID": geo["GEOID"],
                    "NAME": geo["NAME"],
                    "geography_level": geography_level,
                    "state": geo["STUSAB"],
                    "state_fips": geo["STATE"],
                    "district_code": geo[district_field],
                    "source_column_id": variable.source_column_id,
                    "source_concept": variable.source_concept,
                    "statistic": variable.statistic,
                    "value": int(value_payload["value"]),
                    "source_logrecno": logrecno,
                    "source_segment": f"segment_{variable.segment}",
                    "source_data_row_number": int(value_payload["row_number"]),
                    "state_name": state_name,
                    "source_zip_url": source_zip_url,
                }
            )
    return rows


def _file_spec(year: int) -> dict[str, Any]:
    files_by_year = _manifest()["files"]
    try:
        return files_by_year[year]
    except KeyError:
        return files_by_year[str(year)]


@lru_cache(maxsize=None)
def _content(year: int) -> bytes:
    spec = _file_spec(year)
    content = files("db").joinpath(PACKAGE_DIR, spec["filename"]).read_bytes()
    expected_sha = spec.get("sha256")
    if expected_sha:
        actual_sha = hashlib.sha256(content).hexdigest()
        if actual_sha != expected_sha:
            raise ValueError(
                f"Census CD119 SLD source file {year} checksum mismatch: "
                f"expected {expected_sha}, got {actual_sha}"
            )
    return content


def _sld_geographies_by_logrecno(
    archive: ZipFile,
) -> dict[str, dict[str, str]]:
    geo_member = _required_member(archive, "geo2020.cd19")
    geographies: dict[str, dict[str, str]] = {}
    with archive.open(geo_member) as raw_file:
        reader = csv.reader(
            TextIOWrapper(raw_file, encoding="latin-1", newline=""),
            delimiter="|",
        )
        for row in reader:
            geo = {
                field: row[index] if index < len(row) else ""
                for index, field in enumerate(CD119_GEO_HEADER_FIELDS)
            }
            if geo.get("SUMLEV") in SLD_SUMMARY_LEVELS:
                geographies[geo["LOGRECNO"]] = geo
    return geographies


def _sld_values_by_logrecno(
    archive: ZipFile,
    logrecnos: set[str],
) -> dict[str, dict[str, dict[str, int]]]:
    variables_by_segment: dict[str, list[Cd119Variable]] = {}
    for variable in CD119_SLD_VARIABLES:
        variables_by_segment.setdefault(variable.segment, []).append(variable)

    values_by_logrecno: dict[str, dict[str, dict[str, int]]] = {
        logrecno: {} for logrecno in logrecnos
    }
    for segment, variables in variables_by_segment.items():
        member = _required_member(archive, f"000{segment}2020.cd19")
        with archive.open(member) as raw_file:
            reader = csv.reader(
                TextIOWrapper(raw_file, encoding="latin-1", newline=""),
                delimiter="|",
            )
            for row_number, row in enumerate(reader, start=1):
                if len(row) < 5:
                    continue
                logrecno = row[4]
                if logrecno not in logrecnos:
                    continue
                for variable in variables:
                    value_index = 5 + variable.data_offset
                    values_by_logrecno[logrecno][variable.source_column_id] = {
                        "value": int(row[value_index]),
                        "row_number": row_number,
                    }
    return values_by_logrecno


def _required_member(archive: ZipFile, suffix: str) -> str:
    suffix = suffix.lower()
    for member in archive.namelist():
        if member.lower().endswith(suffix):
            return member
    raise FileNotFoundError(f"CD119 ZIP member ending with {suffix!r} not found.")


def _sld_sort_key(geo: dict[str, str]) -> tuple[int, str, int, int | str]:
    summary_level = geo["SUMLEV"]
    _geography_level, _chamber, district_field = SLD_SUMMARY_LEVELS[summary_level]
    district_code = geo[district_field]
    try:
        return (0 if summary_level == "610" else 1, geo["STATE"], 0, int(district_code))
    except ValueError:
        return (0 if summary_level == "610" else 1, geo["STATE"], 1, district_code)
