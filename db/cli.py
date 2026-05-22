"""CLI for managing Arch target input data."""

import argparse
import json
from pathlib import Path

from sqlalchemy import func
from sqlmodel import Session, select

from .etl_soi import load_soi_targets
from .schema import (
    DEFAULT_DB_PATH,
    SourceArtifact,
    SourceRow,
    SourceTable,
    Stratum,
    Target,
    init_db,
    get_engine,
)


def cmd_init(args):
    """Initialize the database."""
    db_path = Path(args.db) if args.db else DEFAULT_DB_PATH
    init_db(db_path)
    print(f"Initialized database at {db_path}")


def cmd_load(args):
    """Load targets from a source."""
    db_path = Path(args.db) if args.db else DEFAULT_DB_PATH
    engine = init_db(db_path)

    with Session(engine) as session:
        if args.source == "soi" or args.source == "all":
            years = [int(y) for y in args.years.split(",")] if args.years else None
            load_soi_targets(session, years=years)
            print(f"Loaded SOI targets for years: {years or 'all available'}")

        if args.source == "soi-state" or args.source == "all":
            from .etl_soi_state import load_soi_state_targets
            years = [int(y) for y in args.years.split(",")] if args.years else None
            load_soi_state_targets(session, years=years)
            print(f"Loaded state-level SOI targets for years: {years or 'all available'}")

        if args.source == "soi-historic-table-2" or args.source == "all":
            from .etl_soi_historic_table_2 import load_soi_historic_table_2_targets
            years = [int(y) for y in args.years.split(",")] if args.years else None
            load_soi_historic_table_2_targets(session, years=years)
            print(
                "Loaded SOI Historic Table 2 targets for years: "
                f"{years or 'all available'}"
            )

        if args.source == "soi-credits" or args.source == "all":
            from .etl_soi_credits import load_soi_credits_targets
            years = [int(y) for y in args.years.split(",")] if args.years else None
            load_soi_credits_targets(session, years=years)
            print(f"Loaded SOI credits targets for years: {years or 'all available'}")

        if args.source == "soi-income-sources" or args.source == "all":
            from .etl_soi_income_sources import load_soi_income_sources_targets
            years = [int(y) for y in args.years.split(",")] if args.years else None
            load_soi_income_sources_targets(session, years=years)
            print(f"Loaded SOI income sources targets for years: {years or 'all available'}")

        if args.source == "soi-w2" or args.source == "all":
            from .etl_soi_w2 import load_soi_w2_targets
            years = [int(y) for y in args.years.split(",")] if args.years else None
            load_soi_w2_targets(session, years=years)
            print(
                "Loaded SOI Form W-2 statistics targets for years: "
                f"{years or 'all available'}"
            )

        if args.source == "soi-ira" or args.source == "all":
            from .etl_soi_ira import load_soi_ira_targets
            years = [int(y) for y in args.years.split(",")] if args.years else None
            load_soi_ira_targets(session, years=years)
            print(
                "Loaded SOI IRA contribution targets for years: "
                f"{years or 'all available'}"
            )

        if args.source == "soi-deductions" or args.source == "all":
            from .etl_soi_deductions import load_soi_deductions_targets
            years = [int(y) for y in args.years.split(",")] if args.years else None
            load_soi_deductions_targets(session, years=years)
            print(f"Loaded SOI deductions targets for years: {years or 'all available'}")

        if args.source == "snap" or args.source == "all":
            from .etl_snap import load_snap_targets
            years = [int(y) for y in args.years.split(",")] if args.years else None
            load_snap_targets(session, years=years, source_zip=args.snap_fns_zip)
            print(f"Loaded SNAP targets for years: {years or 'all available'}")

        if args.source == "medicaid" or args.source == "all":
            from .etl_medicaid import load_medicaid_targets
            years = [int(y) for y in args.years.split(",")] if args.years else None
            load_medicaid_targets(session, years=years)
            print(f"Loaded Medicaid targets for years: {years or 'all available'}")

        if args.source == "cms-nhe" or args.source == "all":
            from .etl_cms_nhe import load_cms_nhe_targets
            years = [int(y) for y in args.years.split(",")] if args.years else None
            load_cms_nhe_targets(session, years=years)
            print(f"Loaded CMS NHE targets for years: {years or 'all available'}")

        if args.source == "aca" or args.source == "all":
            from .etl_aca_enrollment import load_aca_enrollment_targets
            years = [int(y) for y in args.years.split(",")] if args.years else None
            load_aca_enrollment_targets(session, years=years)
            print(f"Loaded ACA Marketplace targets for years: {years or 'all available'}")

        if args.source == "aca-oep-state" or args.source == "all":
            from .etl_cms_aca_oep import load_cms_aca_oep_targets
            years = [int(y) for y in args.years.split(",")] if args.years else None
            load_cms_aca_oep_targets(session, years=years)
            print(
                "Loaded CMS ACA OEP state-level targets for years: "
                f"{years or 'all available'}"
            )

        if args.source == "hmrc" or args.source == "all":
            from .etl_hmrc import load_hmrc_targets
            years = [int(y) for y in args.years.split(",")] if args.years else None
            load_hmrc_targets(session, years=years)
            print(f"Loaded HMRC targets for years: {years or 'all available'}")

        if args.source == "census" or args.source == "all":
            from .etl_census import load_census_targets
            years = [int(y) for y in args.years.split(",")] if args.years else None
            load_census_targets(session, years=years)
            print(f"Loaded Census targets for years: {years or 'all available'}")

        if args.source == "census-pep" or args.source == "all":
            from .etl_census_pep import load_census_pep_population_targets
            years = [int(y) for y in args.years.split(",")] if args.years else None
            load_census_pep_population_targets(session, years=years)
            print(
                "Loaded Census PEP population targets for years: "
                f"{years or 'all available'}"
            )

        if args.source == "census-stc" or args.source == "all":
            from .etl_census_stc import load_census_stc_income_tax_targets
            years = [int(y) for y in args.years.split(",")] if args.years else None
            load_census_stc_income_tax_targets(session, years=years)
            print(
                "Loaded Census STC state income-tax targets for years: "
                f"{years or 'all available'}"
            )

        if args.source == "ssa" or args.source == "all":
            from .etl_ssa import load_ssa_targets
            years = [int(y) for y in args.years.split(",")] if args.years else None
            load_ssa_targets(session, years=years)
            print(f"Loaded SSA targets for years: {years or 'all available'}")

        if args.source == "ssa-supplement" or args.source == "all":
            from .etl_ssa_supplement import load_ssa_supplement_targets
            years = [int(y) for y in args.years.split(",")] if args.years else None
            load_ssa_supplement_targets(session, years=years)
            print(
                "Loaded SSA Annual Statistical Supplement targets for years: "
                f"{years or 'all available'}"
            )

        if args.source == "ssi" or args.source == "all":
            from .etl_ssi import load_ssi_targets
            years = [int(y) for y in args.years.split(",")] if args.years else None
            load_ssi_targets(session, years=years)
            print(f"Loaded SSI targets for years: {years or 'all available'}")

        if args.source == "tanf" or args.source == "all":
            from .etl_tanf import load_tanf_targets
            years = [int(y) for y in args.years.split(",")] if args.years else None
            load_tanf_targets(session, years=years)
            print(f"Loaded TANF targets for years: {years or 'all available'}")

        if args.source == "bls" or args.source == "all":
            from .etl_bls import load_bls_targets
            years = [int(y) for y in args.years.split(",")] if args.years else None
            load_bls_targets(session, years=years)
            print(f"Loaded BLS targets for years: {years or 'all available'}")

        if args.source == "cps" or args.source == "all":
            from .etl_cps import load_cps_targets
            years = [int(y) for y in args.years.split(",")] if args.years else None
            load_cps_targets(session, years=years)
            print(f"Loaded CPS monthly targets for years: {years or 'all available'}")

        if args.source == "cbo" or args.source == "all":
            from .etl_cbo import load_cbo_targets
            years = [int(y) for y in args.years.split(",")] if args.years else None
            load_cbo_targets(session, years=years)
            print(f"Loaded CBO projections for years: {years or 'all available'}")

        if args.source == "obr" or args.source == "all":
            from .etl_obr import load_obr_targets
            years = [int(y) for y in args.years.split(",")] if args.years else None
            load_obr_targets(session, years=years)
            print(f"Loaded OBR projections for years: {years or 'all available'}")

        if args.source == "ons" or args.source == "all":
            from .etl_ons import load_ons_targets
            years = [int(y) for y in args.years.split(",")] if args.years else None
            load_ons_targets(session, years=years)
            print(f"Loaded ONS projections for years: {years or 'all available'}")


def cmd_stats(args):
    """Show database statistics."""
    db_path = Path(args.db) if args.db else DEFAULT_DB_PATH

    if not db_path.exists():
        print(f"Database not found at {db_path}")
        return

    engine = get_engine(db_path)
    with Session(engine) as session:
        strata_count = len(session.exec(select(Stratum)).all())
        targets_count = len(session.exec(select(Target)).all())

        # Get unique sources
        sources = session.exec(
            select(Target.source).distinct()
        ).all()

        # Get unique years
        years = session.exec(
            select(Target.period).distinct()
        ).all()

        print(f"Database: {db_path}")
        print(f"Strata: {strata_count}")
        print(f"Targets: {targets_count}")
        print(f"Sources: {', '.join(str(s) for s in sources)}")
        print(f"Years: {', '.join(str(y) for y in sorted(years))}")


def cmd_load_source_files(args):
    """Load full source files into the source artifact tables."""
    db_path = Path(args.db) if args.db else DEFAULT_DB_PATH
    engine = init_db(db_path)

    if args.inventory != "pe":
        raise ValueError(f"Unsupported source-file inventory: {args.inventory}")

    from .pe_source_inventory import pe_source_specs
    from .source_files import ingest_source_artifacts, prune_source_artifacts

    include_us = args.jurisdiction in {"all", "us"}
    include_uk = args.jurisdiction in {"all", "uk"}
    specs = pe_source_specs(
        pe_us_root=Path(args.pe_us_root),
        pe_uk_root=Path(args.pe_uk_root),
        include_us=include_us,
        include_uk=include_uk,
        include_missing_local=False,
    )
    if args.limit:
        specs = specs[: args.limit]

    with Session(engine) as session:
        results = ingest_source_artifacts(session, specs)
        removed = 0 if args.limit else prune_source_artifacts(session, specs)

    print(f"Loaded {len(results)} source artifacts into {db_path}")
    if removed:
        print(f"Pruned {removed} stale source artifacts")
    print(f"Parsed tables: {sum(result.table_count for result in results):,}")
    print(f"Parsed rows: {sum(result.row_count for result in results):,}")


def cmd_source_stats(args):
    """Show source artifact statistics."""
    db_path = Path(args.db) if args.db else DEFAULT_DB_PATH

    if not db_path.exists():
        print(f"Database not found at {db_path}")
        return

    engine = get_engine(db_path)
    with Session(engine) as session:
        artifact_count = session.exec(select(func.count(SourceArtifact.id))).one()
        table_count = session.exec(select(func.count(SourceTable.id))).one()
        row_count = session.exec(select(func.count(SourceRow.id))).one()
        by_pipeline = session.exec(
            select(
                SourceArtifact.origin_project,
                SourceArtifact.pipeline,
                func.count(SourceArtifact.id),
            )
            .group_by(SourceArtifact.origin_project, SourceArtifact.pipeline)
            .order_by(SourceArtifact.origin_project, SourceArtifact.pipeline)
        ).all()
        by_source = session.exec(
            select(SourceArtifact.source_id, func.count(SourceArtifact.id))
            .group_by(SourceArtifact.source_id)
            .order_by(SourceArtifact.source_id)
        ).all()

    print(f"Database: {db_path}")
    print(f"Source artifacts: {artifact_count:,}")
    print(f"Source tables: {table_count:,}")
    print(f"Source rows: {row_count:,}")
    print("Pipelines:")
    for origin_project, pipeline, count in by_pipeline:
        print(f"  {origin_project}/{pipeline}: {count:,}")
    print("Sources:")
    for source_id, count in by_source:
        print(f"  {source_id}: {count:,}")


def cmd_source_manifest(args):
    """Export a checklist of PolicyEngine source artifacts."""
    db_path = Path(args.db) if args.db else DEFAULT_DB_PATH

    if args.inventory != "pe":
        raise ValueError(f"Unsupported source-file inventory: {args.inventory}")

    from .pe_source_inventory import (
        pe_source_manifest_rows,
        pe_source_specs,
        write_pe_source_manifest_csv,
        write_pe_source_manifest_markdown,
    )

    include_us = args.jurisdiction in {"all", "us"}
    include_uk = args.jurisdiction in {"all", "uk"}
    specs = pe_source_specs(
        pe_us_root=Path(args.pe_us_root),
        pe_uk_root=Path(args.pe_uk_root),
        include_us=include_us,
        include_uk=include_uk,
    )
    rows = pe_source_manifest_rows(
        specs,
        arch_db_path=db_path,
        pe_us_root=Path(args.pe_us_root),
        pe_uk_root=Path(args.pe_uk_root),
    )

    output = Path(args.output or f"docs/pe-{args.jurisdiction}-source-manifest.csv")
    markdown = Path(
        args.markdown or f"docs/pe-{args.jurisdiction}-source-manifest.md"
    )
    write_pe_source_manifest_csv(rows, output)
    write_pe_source_manifest_markdown(rows, markdown)

    done = sum(row["status"] == "done" for row in rows)
    print(f"Wrote {len(rows)} source manifest rows to {output}")
    print(f"Wrote Markdown checklist to {markdown}")
    print(f"Parsed in Arch: {done}/{len(rows)}")


def cmd_rollup_state_to_national(args):
    """Create national target rows from complete state-level target rows."""
    db_path = Path(args.db) if args.db else DEFAULT_DB_PATH
    engine = get_engine(db_path)

    from .rollups import roll_up_state_targets_to_national

    variables = [variable.strip() for variable in args.variables.split(",")]
    years = [int(year) for year in args.years.split(",")] if args.years else None
    with Session(engine) as session:
        results = roll_up_state_targets_to_national(
            session,
            source=args.source,
            variables=variables,
            years=years,
            min_state_count=args.min_state_count,
        )

    print(json.dumps([result.to_dict() for result in results], indent=2))


def cmd_query(args):
    """Query targets."""
    db_path = Path(args.db) if args.db else DEFAULT_DB_PATH

    if not db_path.exists():
        print(f"Database not found at {db_path}")
        return

    engine = get_engine(db_path)
    with Session(engine) as session:
        query = select(Target, Stratum).join(Stratum)

        if args.variable:
            query = query.where(Target.variable == args.variable)
        if args.year:
            query = query.where(Target.period == int(args.year))
        if args.source:
            query = query.where(Target.source == args.source)

        results = session.exec(query).all()

        if not results:
            print("No targets found matching criteria")
            return

        print(f"{'Stratum':<30} {'Variable':<25} {'Year':<6} {'Value':>15} {'Source':<10}")
        print("-" * 90)
        for target, stratum in results[:args.limit]:
            print(f"{stratum.name:<30} {target.variable:<25} {target.period:<6} {target.value:>15,.0f} {target.source.value:<10}")


def main():
    parser = argparse.ArgumentParser(
        description="Manage Arch target input data"
    )
    parser.add_argument(
        "--db",
        help=f"Database path (default: {DEFAULT_DB_PATH})"
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # init
    init_parser = subparsers.add_parser("init", help="Initialize database")
    init_parser.set_defaults(func=cmd_init)

    # load
    load_parser = subparsers.add_parser("load", help="Load targets from source")
    load_parser.add_argument(
        "source",
        choices=[
            "soi",
            "soi-state",
            "soi-historic-table-2",
            "soi-credits",
            "soi-income-sources",
            "soi-w2",
            "soi-ira",
            "soi-deductions",
            "snap",
            "medicaid",
            "cms-nhe",
            "aca",
            "aca-oep-state",
            "hmrc",
            "census",
            "census-pep",
            "census-stc",
            "ssa",
            "ssa-supplement",
            "ssi",
            "tanf",
            "bls",
            "cps",
            "cbo",
            "obr",
            "ons",
            "all",
        ],
        help="Data source to load"
    )
    load_parser.add_argument(
        "--years",
        help="Comma-separated years to load (default: all)"
    )
    load_parser.add_argument(
        "--snap-fns-zip",
        type=Path,
        help="USDA FNS SNAP FY workbook ZIP to use when loading SNAP",
    )
    load_parser.set_defaults(func=cmd_load)

    # stats
    stats_parser = subparsers.add_parser("stats", help="Show database statistics")
    stats_parser.set_defaults(func=cmd_stats)

    # load-source-files
    source_parser = subparsers.add_parser(
        "load-source-files",
        help="Load full parsed source artifacts into the database",
    )
    source_parser.add_argument(
        "inventory",
        choices=["pe"],
        help="Source-file inventory to load",
    )
    source_parser.add_argument(
        "--jurisdiction",
        choices=["all", "us", "uk"],
        default="all",
        help="Limit the source-file inventory",
    )
    source_parser.add_argument(
        "--pe-us-root",
        default="/Users/maxghenis/PolicyEngine/policyengine-us-data",
        help="Path to the policyengine-us-data checkout",
    )
    source_parser.add_argument(
        "--pe-uk-root",
        default="/Users/maxghenis/PolicyEngine/policyengine-uk-data",
        help="Path to the policyengine-uk-data checkout",
    )
    source_parser.add_argument(
        "--limit",
        type=int,
        help="Load only the first N artifacts, for smoke tests",
    )
    source_parser.set_defaults(func=cmd_load_source_files)

    # source-stats
    source_stats_parser = subparsers.add_parser(
        "source-stats", help="Show source artifact statistics"
    )
    source_stats_parser.set_defaults(func=cmd_source_stats)

    # source-manifest
    manifest_parser = subparsers.add_parser(
        "source-manifest",
        help="Export a PolicyEngine source-artifact checklist",
    )
    manifest_parser.add_argument(
        "inventory",
        choices=["pe"],
        help="Source-file inventory to export",
    )
    manifest_parser.add_argument(
        "--jurisdiction",
        choices=["all", "us", "uk"],
        default="all",
        help="Limit the source-file inventory",
    )
    manifest_parser.add_argument(
        "--pe-us-root",
        default="/Users/maxghenis/PolicyEngine/policyengine-us-data",
        help="Path to the policyengine-us-data checkout",
    )
    manifest_parser.add_argument(
        "--pe-uk-root",
        default="/Users/maxghenis/PolicyEngine/policyengine-uk-data",
        help="Path to the policyengine-uk-data checkout",
    )
    manifest_parser.add_argument(
        "--output",
        default=None,
        help="CSV path to write",
    )
    manifest_parser.add_argument(
        "--markdown",
        default=None,
        help="Markdown checklist path to write",
    )
    manifest_parser.set_defaults(func=cmd_source_manifest)

    # rollup-state-to-national
    rollup_parser = subparsers.add_parser(
        "rollup-state-to-national",
        help="Create national target rows by summing state target rows",
    )
    rollup_parser.add_argument(
        "--source",
        required=True,
        help="Target source enum name or value, e.g. IRS_SOI or irs-soi",
    )
    rollup_parser.add_argument(
        "--variables",
        required=True,
        help="Comma-separated target variables to roll up",
    )
    rollup_parser.add_argument(
        "--years",
        help="Comma-separated years to roll up (default: all)",
    )
    rollup_parser.add_argument(
        "--min-state-count",
        type=int,
        default=50,
        help="Minimum distinct state_fips rows required for a rollup",
    )
    rollup_parser.set_defaults(func=cmd_rollup_state_to_national)

    # query
    query_parser = subparsers.add_parser("query", help="Query targets")
    query_parser.add_argument("--variable", help="Filter by variable name")
    query_parser.add_argument("--year", help="Filter by year")
    query_parser.add_argument("--source", help="Filter by source")
    query_parser.add_argument("--limit", type=int, default=20, help="Max results")
    query_parser.set_defaults(func=cmd_query)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
