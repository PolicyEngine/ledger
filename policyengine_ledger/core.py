"""Ledger fact schema compatibility module.

New consumers should import from :mod:`policyengine_ledger.core`; the objects
are re-exported from :mod:`arch.core` until the historical namespace is retired.
"""

from arch.core import *  # noqa: F403
