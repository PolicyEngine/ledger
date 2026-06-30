"""Calibration target schema and query helpers."""

from db.schema import (
    DEFAULT_DB_PATH,
    DataSource,
    GeographicLevel,
    Jurisdiction,
    Stratum,
    StratumConstraint,
    Target,
    TargetType,
    get_engine,
    get_session,
    init_db,
)
from db.supabase_client import insert_targets_batch, query_strata, query_targets
from calibration.targets import TargetSpec, get_targets
from .us_poverty import (
    US_POVERTY_NONFILER_TARGET_COVERAGE,
    TargetSourceCoverage,
    coverage_entries,
    hard_target_package_aliases,
    source_gap_family_ids,
    validate_us_poverty_nonfiler_source_coverage,
    validation_only_family_ids,
)

__all__ = [
    "DEFAULT_DB_PATH",
    "DataSource",
    "GeographicLevel",
    "Jurisdiction",
    "Stratum",
    "StratumConstraint",
    "Target",
    "TargetSpec",
    "TargetSourceCoverage",
    "TargetType",
    "US_POVERTY_NONFILER_TARGET_COVERAGE",
    "coverage_entries",
    "get_engine",
    "get_targets",
    "get_session",
    "hard_target_package_aliases",
    "init_db",
    "insert_targets_batch",
    "query_strata",
    "query_targets",
    "source_gap_family_ids",
    "validate_us_poverty_nonfiler_source_coverage",
    "validation_only_family_ids",
]
