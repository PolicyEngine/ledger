"""ETL for USDA SNAP (Supplemental Nutrition Assistance Program) targets.

Loads SNAP participation and benefit targets into the legacy targets database.

Values are sourced from the trustworthy USDA FNS source package at
``packages/usda_snap/fy69_to_current``, which parses the FY24 workbook
(``SNAP Monthly State Participation and Benefit Summary``) cell-by-cell with
guard cells and checksum-locked provenance. This ETL previously hardcoded a
``SNAP_DATA`` dict of suspiciously round per-state values with no per-value
citation (see PolicyEngine/ledger#77); those fabricated numbers have been
removed in favor of the parsed source facts, so ``ledger load snap`` now emits
only source-backed values.

Data source page:
https://www.fns.usda.gov/pd/supplemental-nutrition-assistance-program-snap
"""

from __future__ import annotations

from collections import defaultdict

from sqlmodel import Session, select

from ledger.core import AggregateFact
from ledger.normalization import SourceFact, as_target, convert_units, target_kwargs
from ledger.source_package import load_source_package

from .schema import (
    DataSource,
    Jurisdiction,
    Stratum,
    StratumConstraint,
    Target,
    TargetType,
    init_db,
)

# Trustworthy FNS source package parsed cell-by-cell with guard cells.
SNAP_SOURCE_PACKAGE = "packages/usda_snap/fy69_to_current"

SOURCE_URL = (
    "https://www.fns.usda.gov/pd/supplemental-nutrition-assistance-program-snap"
)

# Source-package canonical concepts mapped to legacy target variables. Each
# tuple is (target variable, target type, output unit). The FNS workbook
# publishes household and person counts as absolute counts and benefits as
# absolute dollars, so no scale conversion is applied.
_MEASURE_TARGETS: dict[str, tuple[str, TargetType, str]] = {
    "usda_snap.average_monthly_households": (
        "snap_household_count",
        TargetType.COUNT,
        "count",
    ),
    "usda_snap.average_monthly_persons": (
        "snap_participant_count",
        TargetType.COUNT,
        "count",
    ),
    "usda_snap.total_benefits": (
        "snap_benefits",
        TargetType.AMOUNT,
        "dollars",
    ),
}


def _fips_from_geography_id(geography_id: str) -> str | None:
    """Extract a 2-digit state FIPS code from a Census GEOID.

    State GEOIDs look like ``0400000US06`` (California). Non-state geographies
    (e.g. the national ``0100000US``) return ``None``.
    """
    marker = "US"
    index = geography_id.rfind(marker)
    if index == -1:
        return None
    suffix = geography_id[index + len(marker) :]
    if len(suffix) == 2 and suffix.isdigit():
        return suffix
    return None


def _provenance_note(fact: AggregateFact) -> str:
    """Build a per-value provenance note from the fact's source lineage."""
    source = fact.source
    parts = [
        f"USDA FNS {source.source_table}" if source.source_table else "USDA FNS",
    ]
    if source.source_file:
        parts.append(f"source_file={source.source_file}")
    if source.vintage:
        parts.append(f"vintage={source.vintage}")
    if source.source_sha256:
        parts.append(f"sha256={source.source_sha256}")
    if source.raw_r2_uri:
        parts.append(f"raw={source.raw_r2_uri}")
    if fact.source_record_id:
        parts.append(f"record={fact.source_record_id}")
    return "; ".join(parts)


def build_snap_target(
    stratum: Stratum,
    fact: AggregateFact,
    *,
    variable: str,
    target_type: TargetType,
    output_unit: str,
    source_table: str,
) -> Target:
    """Build a SNAP target input from a parsed source fact.

    The value already arrives in its published absolute unit, so this records a
    no-op ``convert_units`` step purely to attach normalization lineage; the
    numeric value is unchanged.
    """
    source_fact = SourceFact(
        name=variable,
        value=fact.value,
        period=fact.period.value,
        unit=fact.measure.unit,
        source=DataSource.USDA_SNAP,
        jurisdiction=stratum.jurisdiction,
        source_table=source_table,
        source_url=SOURCE_URL,
    )
    converted = convert_units(source_fact, 1, output_unit)
    blueprint = as_target(
        converted,
        variable=variable,
        target_type=target_type,
        stratum_name=stratum.name,
        notes=_provenance_note(fact),
    )
    return Target(**target_kwargs(blueprint, stratum_id=stratum.id))


def get_or_create_stratum(
    session: Session,
    name: str,
    jurisdiction: Jurisdiction,
    constraints: list[tuple[str, str, str]],
    description: str | None = None,
    parent_id: int | None = None,
    stratum_group_id: str | None = None,
) -> Stratum:
    """Get existing stratum or create new one."""
    definition_hash = Stratum.compute_hash(constraints, jurisdiction)

    existing = session.exec(
        select(Stratum).where(Stratum.definition_hash == definition_hash)
    ).first()

    if existing:
        return existing

    stratum = Stratum(
        name=name,
        description=description,
        jurisdiction=jurisdiction,
        definition_hash=definition_hash,
        parent_id=parent_id,
        stratum_group_id=stratum_group_id,
    )
    session.add(stratum)
    session.flush()

    for variable, operator, value in constraints:
        constraint = StratumConstraint(
            stratum_id=stratum.id,
            variable=variable,
            operator=operator,
            value=value,
        )
        session.add(constraint)

    return stratum


def load_snap_facts(years: list[int] | None = None) -> list[AggregateFact]:
    """Load source-backed SNAP facts from the trustworthy FNS source package.

    The package artifact is the FY2024 workbook, so every fact carries a
    ``fiscal_year 2024`` reference period. ``years`` optionally filters to
    matching fact reference periods; a year with no matching facts (e.g. a
    prior fiscal year not yet added to the package) simply yields nothing
    rather than mislabeling FY2024 data.
    """
    package = load_source_package(SNAP_SOURCE_PACKAGE)
    facts = package.build_facts(package.artifact.artifact_year)
    if years is not None:
        wanted = set(years)
        facts = [fact for fact in facts if fact.period.value in wanted]
    return facts


def load_snap_targets(session: Session, years: list[int] | None = None):
    """Load SNAP targets into the database from parsed FNS source facts.

    Args:
        session: Database session.
        years: Optional list of fiscal-year reference periods to include.
            Defaults to every period the source package publishes.
    """
    facts = load_snap_facts(years)

    # Group facts by geography so each stratum gets its measures together.
    by_geography: dict[str, list[AggregateFact]] = defaultdict(list)
    for fact in facts:
        by_geography[fact.geography.id].append(fact)

    national_stratum: Stratum | None = None

    # Materialize the national stratum first so state strata can parent to it.
    for geography_facts in by_geography.values():
        if geography_facts[0].geography.level != "country":
            continue

        national_stratum = get_or_create_stratum(
            session,
            name="US SNAP Recipients",
            jurisdiction=Jurisdiction.US_FEDERAL,
            constraints=[("snap", "==", "1")],
            description="All SNAP recipient households/individuals in the US",
            stratum_group_id="snap_national",
        )

        for fact in geography_facts:
            mapping = _MEASURE_TARGETS.get(fact.measure.concept)
            if mapping is None:
                continue
            variable, target_type, output_unit = mapping
            session.add(
                build_snap_target(
                    national_stratum,
                    fact,
                    variable=variable,
                    target_type=target_type,
                    output_unit=output_unit,
                    source_table="SNAP National Summary",
                )
            )

    # State-level strata and targets.
    for geography_id, geography_facts in by_geography.items():
        first = geography_facts[0]
        if first.geography.level != "state":
            continue

        fips = _fips_from_geography_id(geography_id)
        if fips is None:
            continue

        state_name = first.geography.name or geography_id
        state_stratum = get_or_create_stratum(
            session,
            name=f"{state_name} SNAP Recipients",
            jurisdiction=Jurisdiction.US,
            constraints=[
                ("snap", "==", "1"),
                ("state_fips", "==", fips),
            ],
            description=f"SNAP recipients in {state_name}",
            parent_id=national_stratum.id if national_stratum else None,
            stratum_group_id="snap_states",
        )

        for fact in geography_facts:
            mapping = _MEASURE_TARGETS.get(fact.measure.concept)
            if mapping is None:
                continue
            variable, target_type, output_unit = mapping
            session.add(
                build_snap_target(
                    state_stratum,
                    fact,
                    variable=variable,
                    target_type=target_type,
                    output_unit=output_unit,
                    source_table="SNAP State Summary",
                )
            )

    session.commit()


def run_etl(db_path=None):
    """Run the SNAP ETL pipeline."""
    from pathlib import Path

    from .schema import DEFAULT_DB_PATH

    path = Path(db_path) if db_path else DEFAULT_DB_PATH
    engine = init_db(path)

    with Session(engine) as session:
        load_snap_targets(session)
        print(f"Loaded SNAP targets to {path}")


if __name__ == "__main__":
    run_etl()
