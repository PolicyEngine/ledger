"""Ledger source-data foundation.

Ledger owns government-statistics releases: source artifacts, source-backed
facts, constraints, provenance, and target profiles. Raw microdata storage,
source reconciliation, aging, imputation, target activation, and calibration
belong in downstream systems such as Populace.
"""

__all__ = [
    "bundle",
    "client",
    "concepts",
    "consumer_contract",
    "core",
    "database",
    "facts",
    "harness",
    "jurisdictions",
    "mirror",
    "normalization",
    "source_package",
    "store",
    "sources",
    "suite",
    "targets",
]
