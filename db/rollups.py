"""Utilities for reproducible derived target rollups."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from sqlmodel import Session, select

from .schema import DataSource, Jurisdiction, Stratum, StratumConstraint, Target

Constraint = tuple[str, str, str]


@dataclass(frozen=True)
class StateToNationalRollupResult:
    """One national target row derived from state-level target rows."""

    target_id: int
    variable: str
    period: int
    source: str
    source_table: str | None
    state_count: int
    value: float
    created: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "target_id": self.target_id,
            "variable": self.variable,
            "period": self.period,
            "source": self.source,
            "source_table": self.source_table,
            "state_count": self.state_count,
            "value": self.value,
            "created": self.created,
        }


def roll_up_state_targets_to_national(
    session: Session,
    *,
    source: DataSource | str,
    variables: Iterable[str],
    years: Iterable[int] | None = None,
    national_stratum_name: str = "US All Filers",
    national_constraints: tuple[Constraint, ...] = (("is_tax_filer", "==", "1"),),
    min_state_count: int = 50,
) -> list[StateToNationalRollupResult]:
    """Create national target rows as sums of state target records.

    This is for source families where the publisher provides state rows but no
    directly parsed national row in Arch yet. The derived row keeps the same
    source and source table while recording the rollup in notes.
    """

    source_enum = _coerce_data_source(source)
    requested_years = {int(year) for year in years} if years is not None else None
    variable_set = {str(variable) for variable in variables}
    if not variable_set:
        return []

    national_stratum = _get_or_create_stratum(
        session,
        name=national_stratum_name,
        jurisdiction=Jurisdiction.US_FEDERAL,
        constraints=national_constraints,
        description="US national rollup stratum",
        stratum_group_id="national_rollups",
    )
    constraints_by_stratum = _constraints_by_stratum(session)
    state_targets_by_key: dict[
        tuple[str, int, object, DataSource, str | None, str | None],
        dict[str, Target],
    ] = {}

    query = select(Target).where(Target.source == source_enum)
    targets = session.exec(query).all()
    for target in targets:
        if target.variable not in variable_set:
            continue
        if requested_years is not None and target.period not in requested_years:
            continue
        state_fips = _state_fips_for_stratum(
            constraints_by_stratum.get(target.stratum_id, ())
        )
        if state_fips is None:
            continue
        key = (
            target.variable,
            target.period,
            target.target_type,
            target.source,
            target.source_table,
            target.source_url,
        )
        state_targets_by_key.setdefault(key, {}).setdefault(state_fips, target)

    results: list[StateToNationalRollupResult] = []
    for key, targets_by_state in sorted(state_targets_by_key.items()):
        variable, period, target_type, target_source, source_table, source_url = key
        state_count = len(targets_by_state)
        if state_count < min_state_count:
            continue
        existing = session.exec(
            select(Target)
            .where(Target.stratum_id == national_stratum.id)
            .where(Target.variable == variable)
            .where(Target.period == period)
            .where(Target.target_type == target_type)
            .where(Target.source == target_source)
        ).first()
        value = sum(float(target.value) for target in targets_by_state.values())
        if existing is not None:
            results.append(
                StateToNationalRollupResult(
                    target_id=int(existing.id),
                    variable=variable,
                    period=period,
                    source=str(target_source.name),
                    source_table=source_table,
                    state_count=state_count,
                    value=float(existing.value),
                    created=False,
                )
            )
            continue
        rolled_up = Target(
            stratum_id=int(national_stratum.id),
            variable=variable,
            period=period,
            value=value,
            target_type=target_type,
            source=target_source,
            source_table=source_table,
            source_url=source_url,
            notes=(
                "Derived in Arch as a sum of "
                f"{state_count} state target records with state_fips constraints."
            ),
        )
        session.add(rolled_up)
        session.flush()
        results.append(
            StateToNationalRollupResult(
                target_id=int(rolled_up.id),
                variable=variable,
                period=period,
                source=str(target_source.name),
                source_table=source_table,
                state_count=state_count,
                value=value,
                created=True,
            )
        )

    session.commit()
    return results


def _get_or_create_stratum(
    session: Session,
    *,
    name: str,
    jurisdiction: Jurisdiction,
    constraints: tuple[Constraint, ...],
    description: str | None,
    stratum_group_id: str | None,
) -> Stratum:
    definition_hash = Stratum.compute_hash(list(constraints), jurisdiction)
    existing = session.exec(
        select(Stratum).where(Stratum.definition_hash == definition_hash)
    ).first()
    if existing is not None:
        return existing

    stratum = Stratum(
        name=name,
        description=description,
        jurisdiction=jurisdiction,
        definition_hash=definition_hash,
        stratum_group_id=stratum_group_id,
    )
    session.add(stratum)
    session.flush()
    for variable, operator, value in constraints:
        session.add(
            StratumConstraint(
                stratum_id=int(stratum.id),
                variable=variable,
                operator=operator,
                value=value,
            )
        )
    session.flush()
    return stratum


def _constraints_by_stratum(
    session: Session,
) -> dict[int, tuple[Constraint, ...]]:
    rows = session.exec(select(StratumConstraint)).all()
    grouped: dict[int, list[Constraint]] = {}
    for row in rows:
        grouped.setdefault(int(row.stratum_id), []).append(
            (row.variable, row.operator, row.value)
        )
    return {stratum_id: tuple(constraints) for stratum_id, constraints in grouped.items()}


def _state_fips_for_stratum(constraints: tuple[Constraint, ...]) -> str | None:
    values = [
        value
        for variable, operator, value in constraints
        if variable == "state_fips" and operator in {"==", "="}
    ]
    if len(values) != 1:
        return None
    try:
        return str(int(values[0])).zfill(2)
    except ValueError:
        return str(values[0]).zfill(2)


def _coerce_data_source(source: DataSource | str) -> DataSource:
    if isinstance(source, DataSource):
        return source
    source_text = str(source)
    try:
        return DataSource[source_text]
    except KeyError:
        return DataSource(source_text)
