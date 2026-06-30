"""Ledger fact schema compatibility module.

New consumers should import from :mod:`policyengine_ledger.core`; the objects
are re-exported from :mod:`ledger.core` until the historical namespace is retired.
"""

from ledger.core import *  # noqa: F403
