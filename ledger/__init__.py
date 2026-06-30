"""Ledger source-data foundation.

Ledger owns source artifacts, source-backed facts, constraints, provenance, and
microdata ingestion. Modeling choices such as source reconciliation, aging,
imputation, target activation, and calibration profiles belong in Populace
packages.
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
    "microdata",
    "normalization",
    "source_package",
    "store",
    "sources",
    "suite",
    "targets",
]
