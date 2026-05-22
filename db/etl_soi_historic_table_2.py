"""ETL for IRS SOI Historic Table 2 state income-source targets."""

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

PACKAGE_DIR = "data/irs_soi/historic_table_2"
MANIFEST = "manifest.yaml"
MONEY_SCALE = 1_000

HISTORIC_TABLE_2_AGI_STUB_BRACKETS = {
    1: "under_1",
    2: "1_to_10k",
    3: "10k_to_25k",
    4: "25k_to_50k",
    5: "50k_to_75k",
    6: "75k_to_100k",
    7: "100k_to_200k",
    8: "200k_to_500k",
    9: "500k_to_1m",
    10: "1m_plus",
}

EITC_CHILD_TARGET_SPECS = {
    "0_children": {
        "count_column": "N59661",
        "amount_column": "A59661",
        "constraint": ("eitc_qualifying_children", "==", "0"),
        "label": "0 children",
    },
    "1_child": {
        "count_column": "N59662",
        "amount_column": "A59662",
        "constraint": ("eitc_qualifying_children", "==", "1"),
        "label": "1 child",
    },
    "2_children": {
        "count_column": "N59663",
        "amount_column": "A59663",
        "constraint": ("eitc_qualifying_children", "==", "2"),
        "label": "2 children",
    },
    "3plus_children": {
        "count_column": "N59664",
        "amount_column": "A59664",
        "constraint": ("eitc_qualifying_children", ">=", "3"),
        "label": "3+ children",
        "notes": (
            "SOI Historic Table 2 labels this as earned income credit with "
            "three qualifying children; PolicyEngine uses this as the 3+ "
            "EITC child-count category."
        ),
    },
}

HISTORIC_TABLE_2_TARGET_SPECS = {
    "tax_unit_count": {
        "count_column": "N1",
        "count_variable": "tax_unit_count",
    },
    "tax_filer_individual_count": {
        "count_column": "N2",
        "count_variable": "tax_filer_individual_count",
        "include_national": True,
        "notes": (
            "SOI number of individuals is based on Form 1040 filing status, "
            "dependent status, and identifying dependent information. IRS "
            "notes that state data do not represent the full U.S. population."
        ),
    },
    "adjusted_gross_income": {
        "amount_column": "A00100",
        "amount_variable": "adjusted_gross_income",
    },
    "income_tax_before_credits": {
        "count_column": "N05800",
        "count_variable": "income_tax_before_credits_returns",
        "amount_column": "A05800",
        "amount_variable": "income_tax_before_credits_amount",
        "include_national": True,
    },
    "income_tax_liability": {
        "count_column": "N06500",
        "count_variable": "income_tax_liability_returns",
        "amount_column": "A06500",
        "amount_variable": "income_tax_liability",
    },
    "premium_tax_credit": {
        "count_column": "N85770",
        "count_variable": "aca_ptc_returns",
        "amount_column": "A85770",
        "amount_variable": "premium_tax_credit_amount",
        "include_national": True,
    },
    "advance_premium_tax_credit": {
        "count_column": "N85775",
        "count_variable": "advance_premium_tax_credit_returns",
        "amount_column": "A85775",
        "amount_variable": "advance_premium_tax_credit_amount",
        "include_national": True,
    },
    "eitc": {
        "count_column": "N59660",
        "count_variable": "eitc_claims",
        "amount_column": "A59660",
        "amount_variable": "eitc_amount",
        "include_national": True,
    },
    "real_estate_taxes": {
        "count_column": "N18500",
        "count_variable": "real_estate_taxes_claims",
        "amount_column": "A18500",
        "amount_variable": "real_estate_taxes_amount",
        "include_national": True,
    },
    "limited_state_local_taxes": {
        "count_column": "N18460",
        "count_variable": "limited_state_local_taxes_returns",
        "amount_column": "A18460",
        "amount_variable": "limited_state_local_taxes_amount",
        "include_national": True,
    },
    "mortgage_interest_paid": {
        "count_column": "N19300",
        "count_variable": "mortgage_interest_paid_returns",
        "amount_column": "A19300",
        "amount_variable": "mortgage_interest_paid_amount",
        "include_national": True,
    },
    "home_mortgage_personal_seller": {
        "count_column": "N19500",
        "count_variable": "home_mortgage_personal_seller_returns",
        "amount_column": "A19500",
        "amount_variable": "home_mortgage_personal_seller_amount",
        "include_national": True,
    },
    "deductible_points": {
        "count_column": "N19530",
        "count_variable": "deductible_points_returns",
        "amount_column": "A19530",
        "amount_variable": "deductible_points_amount",
        "include_national": True,
    },
    "investment_interest_paid": {
        "count_column": "N19570",
        "count_variable": "investment_interest_paid_returns",
        "amount_column": "A19570",
        "amount_variable": "investment_interest_paid_amount",
        "include_national": True,
    },
    "interest_paid_deduction": {
        "amount_columns": ("A19300", "A19500", "A19530", "A19570"),
        "amount_variable": "interest_paid_deduction_amount",
        "include_national": True,
        "notes": (
            "Composed from Schedule A lines 8a, 8b, 8c, and 9 in "
            "Historic Table 2: mortgage interest paid, home mortgage "
            "from personal seller, deductible points, and investment "
            "interest paid."
        ),
    },
    "wages_salaries": {
        "count_column": "N00200",
        "count_variable": "wages_salaries_returns",
        "amount_column": "A00200",
        "amount_variable": "wages_salaries_amount",
    },
    "net_capital_gains": {
        "count_column": "N01000",
        "count_variable": "net_capital_gains_returns",
        "amount_column": "A01000",
        "amount_variable": "net_capital_gains_amount",
    },
    "taxable_ira_distributions": {
        "count_column": "N01400",
        "count_variable": "taxable_ira_distributions_returns",
        "amount_column": "A01400",
        "amount_variable": "taxable_ira_distributions_amount",
    },
    "taxable_pension_income": {
        "count_column": "N01700",
        "count_variable": "taxable_pension_income_returns",
        "amount_column": "A01700",
        "amount_variable": "taxable_pension_income_amount",
    },
    "unemployment_compensation": {
        "count_column": "N02300",
        "count_variable": "unemployment_compensation_returns",
        "amount_column": "A02300",
        "amount_variable": "unemployment_compensation_amount",
    },
    "taxable_social_security": {
        "count_column": "N02500",
        "count_variable": "taxable_social_security_returns",
        "amount_column": "A02500",
        "amount_variable": "taxable_social_security_amount",
    },
}


class HistoricTable2SourceData(TypedDict, total=False):
    returns: int
    amount: int


class HistoricTable2Data(TypedDict):
    source_url: str
    national: dict[str, HistoricTable2SourceData]
    national_individual_count_by_agi: dict[str, int]
    national_eitc_by_child_count: dict[str, HistoricTable2SourceData]
    national_eitc_by_agi_and_child_count: dict[
        str, dict[str, HistoricTable2SourceData]
    ]
    national_positive_agi_returns: int
    states: dict[str, dict[str, HistoricTable2SourceData]]
    state_individual_count_by_agi: dict[str, dict[str, int]]
    states_eitc_by_child_count: dict[str, dict[str, HistoricTable2SourceData]]
    states_eitc_by_agi_and_child_count: dict[
        str, dict[str, dict[str, HistoricTable2SourceData]]
    ]
    state_positive_agi_returns: dict[str, int]


@lru_cache(maxsize=1)
def _manifest() -> dict[str, Any]:
    manifest_path = files("db").joinpath(PACKAGE_DIR, MANIFEST)
    with manifest_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def available_soi_historic_table_2_years() -> list[int]:
    """Return packaged Historic Table 2 years."""
    return sorted(int(year) for year in _manifest()["files"])


def _file_spec(year: int) -> dict[str, Any]:
    files_by_year = _manifest()["files"]
    try:
        return files_by_year[year]
    except KeyError:
        return files_by_year[str(year)]


def soi_historic_table_2_source_url(year: int) -> str:
    """Return the IRS source URL for a Historic Table 2 year."""
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
                f"SOI Historic Table 2 source file {year} checksum mismatch: "
                f"expected {expected_sha}, got {actual_sha}"
            )
    return content


@lru_cache(maxsize=None)
def _read_frame(year: int) -> pd.DataFrame:
    return pd.read_csv(
        BytesIO(_content(year)),
        dtype=str,
        keep_default_na=False,
    )


def load_soi_historic_table_2_data(year: int) -> HistoricTable2Data:
    """Parse state totals from IRS SOI Historic Table 2 CSV."""
    df = _read_frame(year)
    all_agi_rows = df[df["AGI_STUB"].astype(str) == "0"]
    national_rows = all_agi_rows[all_agi_rows["STATE"].astype(str) == "US"]
    if national_rows.empty:
        raise ValueError(f"SOI Historic Table 2 {year} missing US total row")

    states: dict[str, dict[str, HistoricTable2SourceData]] = {}
    state_individual_count_by_agi: dict[str, dict[str, int]] = {}
    states_eitc_by_child_count: dict[
        str, dict[str, HistoricTable2SourceData]
    ] = {}
    states_eitc_by_agi_and_child_count: dict[
        str, dict[str, dict[str, HistoricTable2SourceData]]
    ] = {}
    state_positive_agi_returns: dict[str, int] = {}
    for _, row in all_agi_rows.iterrows():
        state = str(row["STATE"])
        if state not in STATE_FIPS:
            continue
        states[state] = _parse_historic_table_2_row(row)
        state_individual_count_by_agi[state] = _parse_individual_count_by_agi_rows(
            df, state
        )
        states_eitc_by_child_count[state] = _parse_eitc_child_count_row(row)
        states_eitc_by_agi_and_child_count[state] = _parse_eitc_by_agi_rows(df, state)
        state_positive_agi_returns[state] = _positive_agi_returns(df, state)

    national_row = national_rows.iloc[0]
    return {
        "source_url": soi_historic_table_2_source_url(year),
        "national": _parse_historic_table_2_row(national_row),
        "national_individual_count_by_agi": _parse_individual_count_by_agi_rows(
            df, "US"
        ),
        "national_eitc_by_child_count": _parse_eitc_child_count_row(national_row),
        "national_eitc_by_agi_and_child_count": _parse_eitc_by_agi_rows(df, "US"),
        "national_positive_agi_returns": _positive_agi_returns(df, "US"),
        "states": states,
        "state_individual_count_by_agi": state_individual_count_by_agi,
        "states_eitc_by_child_count": states_eitc_by_child_count,
        "states_eitc_by_agi_and_child_count": states_eitc_by_agi_and_child_count,
        "state_positive_agi_returns": state_positive_agi_returns,
    }


def load_soi_historic_table_2_targets(
    session: Session,
    years: list[int] | None = None,
) -> None:
    """Load state-level income-source targets from IRS SOI Historic Table 2."""
    if years is None:
        years = available_soi_historic_table_2_years()
    variables = _historic_table_2_target_variables()
    session.exec(
        delete(Target).where(
            Target.source == DataSource.IRS_SOI,
            Target.source_table == "Historic Table 2",
            Target.period.in_(years),
            Target.variable.in_(variables),
        )
    )

    national_stratum = get_or_create_stratum(
        session,
        name="US All Filers",
        jurisdiction=Jurisdiction.US_FEDERAL,
        constraints=[("is_tax_filer", "==", "1")],
        description="All individual income tax returns filed in the US",
        stratum_group_id="national",
    )

    for year in years:
        if year not in available_soi_historic_table_2_years():
            continue

        data = load_soi_historic_table_2_data(year)
        for source_id, source_data in data["national"].items():
            spec = HISTORIC_TABLE_2_TARGET_SPECS[source_id]
            if not spec.get("include_national"):
                continue
            _add_source_targets(
                session,
                stratum_id=int(national_stratum.id),
                source_data=source_data,
                spec=spec,
                period=year,
                source_url=data["source_url"],
                geographic_level=None,
            )
        _add_eitc_child_targets(
            session,
            parent_stratum_id=int(national_stratum.id),
            base_name="US",
            jurisdiction=Jurisdiction.US_FEDERAL,
            base_constraints=[("is_tax_filer", "==", "1")],
            source_data=data["national_eitc_by_child_count"],
            period=year,
            source_url=data["source_url"],
            geographic_level=None,
            stratum_group_id="soi_eitc_child_count",
        )
        for agi_bracket, child_data in data[
            "national_eitc_by_agi_and_child_count"
        ].items():
            _add_eitc_child_targets(
                session,
                parent_stratum_id=int(national_stratum.id),
                base_name=f"US AGI {agi_bracket}",
                jurisdiction=Jurisdiction.US_FEDERAL,
                base_constraints=[
                    ("is_tax_filer", "==", "1"),
                    ("agi_bracket", "==", agi_bracket),
                ],
                source_data=child_data,
                period=year,
                source_url=data["source_url"],
                geographic_level=None,
                stratum_group_id="soi_eitc_agi_child_count",
            )
        _add_individual_count_by_agi_targets(
            session,
            parent_stratum_id=int(national_stratum.id),
            base_name="US",
            jurisdiction=Jurisdiction.US_FEDERAL,
            base_constraints=[("is_tax_filer", "==", "1")],
            source_data=data["national_individual_count_by_agi"],
            period=year,
            source_url=data["source_url"],
            geographic_level=None,
            stratum_group_id="soi_individual_count_by_agi",
        )

        for state_abbrev, state_values in data["states"].items():
            state_stratum = get_or_create_stratum(
                session,
                name=f"{state_abbrev} All Filers",
                jurisdiction=Jurisdiction.US,
                constraints=[
                    ("is_tax_filer", "==", "1"),
                    ("state_fips", "==", STATE_FIPS[state_abbrev]),
                ],
                description=f"All individual income tax returns filed in {state_abbrev}",
                parent_id=national_stratum.id,
                stratum_group_id="soi_states",
            )
            for source_id, source_data in state_values.items():
                _add_source_targets(
                    session,
                    stratum_id=int(state_stratum.id),
                    source_data=source_data,
                    spec=HISTORIC_TABLE_2_TARGET_SPECS[source_id],
                    period=year,
                    source_url=data["source_url"],
                    geographic_level=GeographicLevel.STATE,
                )
            _add_eitc_child_targets(
                session,
                parent_stratum_id=int(state_stratum.id),
                base_name=state_abbrev,
                jurisdiction=Jurisdiction.US,
                base_constraints=[
                    ("is_tax_filer", "==", "1"),
                    ("state_fips", "==", STATE_FIPS[state_abbrev]),
                ],
                source_data=data["states_eitc_by_child_count"][state_abbrev],
                period=year,
                source_url=data["source_url"],
                geographic_level=GeographicLevel.STATE,
                stratum_group_id="soi_state_eitc_child_count",
            )
            for agi_bracket, child_data in data[
                "states_eitc_by_agi_and_child_count"
            ][state_abbrev].items():
                _add_eitc_child_targets(
                    session,
                    parent_stratum_id=int(state_stratum.id),
                    base_name=f"{state_abbrev} AGI {agi_bracket}",
                    jurisdiction=Jurisdiction.US,
                    base_constraints=[
                        ("is_tax_filer", "==", "1"),
                        ("state_fips", "==", STATE_FIPS[state_abbrev]),
                        ("agi_bracket", "==", agi_bracket),
                    ],
                    source_data=child_data,
                    period=year,
                    source_url=data["source_url"],
                    geographic_level=GeographicLevel.STATE,
                    stratum_group_id="soi_state_eitc_agi_child_count",
                )
            _add_individual_count_by_agi_targets(
                session,
                parent_stratum_id=int(state_stratum.id),
                base_name=state_abbrev,
                jurisdiction=Jurisdiction.US,
                base_constraints=[
                    ("is_tax_filer", "==", "1"),
                    ("state_fips", "==", STATE_FIPS[state_abbrev]),
                ],
                source_data=data["state_individual_count_by_agi"][state_abbrev],
                period=year,
                source_url=data["source_url"],
                geographic_level=GeographicLevel.STATE,
                stratum_group_id="soi_state_individual_count_by_agi",
            )
            positive_agi_stratum = get_or_create_stratum(
                session,
                name=f"{state_abbrev} Filers with Positive AGI",
                jurisdiction=Jurisdiction.US,
                constraints=[
                    ("is_tax_filer", "==", "1"),
                    ("state_fips", "==", STATE_FIPS[state_abbrev]),
                    ("adjusted_gross_income", ">", "0"),
                ],
                description=(
                    "Individual income tax returns filed in "
                    f"{state_abbrev} with positive adjusted gross income"
                ),
                parent_id=state_stratum.id,
                stratum_group_id="soi_states_positive_agi",
            )
            _add_target(
                session,
                stratum_id=int(positive_agi_stratum.id),
                variable="tax_unit_count",
                period=year,
                value=data["state_positive_agi_returns"][state_abbrev],
                target_type=TargetType.COUNT,
                source_url=data["source_url"],
                geographic_level=GeographicLevel.STATE,
            )

    session.commit()


def _positive_agi_returns(df: pd.DataFrame, state: str) -> int:
    rows = df[
        (df["STATE"].astype(str) == state)
        & (df["AGI_STUB"].astype(int).between(2, 10))
    ]
    if rows.empty:
        raise ValueError(f"SOI Historic Table 2 missing positive AGI rows for {state}")
    return int(sum(_count_value(value) for value in rows["N1"]))


def _parse_individual_count_by_agi_rows(
    df: pd.DataFrame,
    state: str,
) -> dict[str, int]:
    rows = df[df["STATE"].astype(str) == state]
    values: dict[str, int] = {}
    for _, row in rows.iterrows():
        agi_stub = int(row["AGI_STUB"])
        agi_bracket = HISTORIC_TABLE_2_AGI_STUB_BRACKETS.get(agi_stub)
        if agi_bracket is None:
            continue
        values[agi_bracket] = _count_value(row["N2"])
    return values


def _parse_eitc_by_agi_rows(
    df: pd.DataFrame,
    state: str,
) -> dict[str, dict[str, HistoricTable2SourceData]]:
    rows = df[df["STATE"].astype(str) == state]
    values: dict[str, dict[str, HistoricTable2SourceData]] = {}
    for _, row in rows.iterrows():
        agi_stub = int(row["AGI_STUB"])
        agi_bracket = HISTORIC_TABLE_2_AGI_STUB_BRACKETS.get(agi_stub)
        if agi_bracket is None:
            continue
        child_data = _parse_eitc_child_count_row(row)
        if child_data:
            values[agi_bracket] = child_data
    return values


def _parse_eitc_child_count_row(
    row: pd.Series,
) -> dict[str, HistoricTable2SourceData]:
    values: dict[str, HistoricTable2SourceData] = {}
    columns = set(row.index)
    for source_id, spec in EITC_CHILD_TARGET_SPECS.items():
        count_column = str(spec["count_column"])
        amount_column = str(spec["amount_column"])
        if count_column not in columns or amount_column not in columns:
            continue
        values[source_id] = {
            "returns": _count_value(row[count_column]),
            "amount": _money_value(row[amount_column]),
        }
    return values


def _parse_historic_table_2_row(row: pd.Series) -> dict[str, HistoricTable2SourceData]:
    values: dict[str, HistoricTable2SourceData] = {}
    for source_id, spec in HISTORIC_TABLE_2_TARGET_SPECS.items():
        source_values: HistoricTable2SourceData = {}
        if count_column := spec.get("count_column"):
            source_values["returns"] = _count_value(row[str(count_column)])
        if amount_column := spec.get("amount_column"):
            source_values["amount"] = _money_value(row[str(amount_column)])
        if amount_columns := spec.get("amount_columns"):
            source_values["amount"] = sum(
                _money_value(row[str(amount_column)])
                for amount_column in amount_columns
            )
        values[source_id] = source_values
    return values


def _add_eitc_child_targets(
    session: Session,
    *,
    parent_stratum_id: int,
    base_name: str,
    jurisdiction: Jurisdiction,
    base_constraints: list[tuple[str, str, str]],
    source_data: dict[str, HistoricTable2SourceData],
    period: int,
    source_url: str,
    geographic_level: GeographicLevel | None,
    stratum_group_id: str,
) -> None:
    for source_id, child_data in source_data.items():
        spec = EITC_CHILD_TARGET_SPECS[source_id]
        child_constraint = spec["constraint"]
        child_stratum = get_or_create_stratum(
            session,
            name=f"{base_name} EITC {spec['label']}",
            jurisdiction=jurisdiction,
            constraints=[*base_constraints, child_constraint],
            description=(
                f"{base_name} individual income tax returns with EITC and "
                f"{spec['label']}"
            ),
            parent_id=parent_stratum_id,
            stratum_group_id=stratum_group_id,
        )
        _add_target(
            session,
            stratum_id=int(child_stratum.id),
            variable="eitc_claims",
            period=period,
            value=child_data["returns"],
            target_type=TargetType.COUNT,
            source_url=source_url,
            geographic_level=geographic_level,
            notes=spec.get("notes"),
        )
        _add_target(
            session,
            stratum_id=int(child_stratum.id),
            variable="eitc_amount",
            period=period,
            value=child_data["amount"],
            target_type=TargetType.AMOUNT,
            source_url=source_url,
            geographic_level=geographic_level,
            notes=spec.get("notes"),
        )


def _add_individual_count_by_agi_targets(
    session: Session,
    *,
    parent_stratum_id: int,
    base_name: str,
    jurisdiction: Jurisdiction,
    base_constraints: list[tuple[str, str, str]],
    source_data: dict[str, int],
    period: int,
    source_url: str,
    geographic_level: GeographicLevel | None,
    stratum_group_id: str,
) -> None:
    spec = HISTORIC_TABLE_2_TARGET_SPECS["tax_filer_individual_count"]
    for agi_bracket, value in source_data.items():
        agi_stratum = get_or_create_stratum(
            session,
            name=f"{base_name} AGI {agi_bracket}",
            jurisdiction=jurisdiction,
            constraints=[*base_constraints, ("agi_bracket", "==", agi_bracket)],
            description=(
                f"{base_name} individuals on individual income tax returns "
                f"with AGI in the {agi_bracket} bracket"
            ),
            parent_id=parent_stratum_id,
            stratum_group_id=stratum_group_id,
        )
        _add_target(
            session,
            stratum_id=int(agi_stratum.id),
            variable="tax_filer_individual_count",
            period=period,
            value=value,
            target_type=TargetType.COUNT,
            source_url=source_url,
            geographic_level=geographic_level,
            notes=spec.get("notes"),
        )


def _historic_table_2_target_variables() -> list[str]:
    variables: list[str] = []
    for spec in HISTORIC_TABLE_2_TARGET_SPECS.values():
        if count_variable := spec.get("count_variable"):
            variables.append(str(count_variable))
        if amount_variable := spec.get("amount_variable"):
            variables.append(str(amount_variable))
    return variables


def _add_source_targets(
    session: Session,
    *,
    stratum_id: int,
    source_data: HistoricTable2SourceData,
    spec: dict[str, Any],
    period: int,
    source_url: str,
    geographic_level: GeographicLevel | None,
) -> None:
    if "returns" in source_data and (count_variable := spec.get("count_variable")):
        _add_target(
            session,
            stratum_id=stratum_id,
            variable=str(count_variable),
            period=period,
            value=source_data["returns"],
            target_type=TargetType.COUNT,
            source_url=source_url,
            geographic_level=geographic_level,
            notes=spec.get("notes"),
        )
    if "amount" in source_data and (amount_variable := spec.get("amount_variable")):
        _add_target(
            session,
            stratum_id=stratum_id,
            variable=str(amount_variable),
            period=period,
            value=source_data["amount"],
            target_type=TargetType.AMOUNT,
            source_url=source_url,
            geographic_level=geographic_level,
            notes=spec.get("notes"),
        )


def _add_target(
    session: Session,
    *,
    stratum_id: int,
    variable: str,
    period: int,
    value: float,
    target_type: TargetType,
    source_url: str,
    geographic_level: GeographicLevel | None,
    notes: str | None = None,
) -> None:
    session.add(
        Target(
            stratum_id=stratum_id,
            variable=variable,
            period=period,
            value=value,
            target_type=target_type,
            geographic_level=geographic_level,
            source=DataSource.IRS_SOI,
            source_table="Historic Table 2",
            source_url=source_url,
            notes=notes,
        )
    )


def _numeric_value(value: object) -> float:
    return float(str(value).replace(",", "").strip())


def _count_value(value: object) -> int:
    return int(round(_numeric_value(value)))


def _money_value(value: object) -> int:
    return int(round(_numeric_value(value) * MONEY_SCALE))
