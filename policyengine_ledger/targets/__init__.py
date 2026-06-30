"""Ledger target-input helpers.

Ledger owns source-backed facts, target-eligible source inputs, and target
profiles. Consumers such as Populace decide which profile rows their support
universe can activate and how to execute calibration.
"""

__all__ = [
    "DEFAULT_DB_PATH",
    "DataSource",
    "GeographicLevel",
    "Jurisdiction",
    "Stratum",
    "StratumConstraint",
    "Target",
    "TargetSourceCoverage",
    "TargetType",
    "US_POVERTY_NONFILER_TARGET_COVERAGE",
    "coverage_entries",
    "get_engine",
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


def __getattr__(name: str):
    """Load legacy target helpers only when explicitly requested."""
    if name not in __all__:
        raise AttributeError(name)
    from ledger import targets

    return getattr(targets, name)
