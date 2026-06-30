"""Tests for the Ledger namespace."""

from ledger.client import get_supabase_client
from ledger.normalization import convert_units
from ledger.targets import (
    Target,
    TargetType,
    query_targets,
)
from db.schema import Target as DbTarget
from db.supabase_client import (
    LEDGER_SCHEMA,
    TARGETS_SCHEMA,
    query_targets as db_query_targets,
)


def test_ledger_targets_reexport_schema_objects():
    assert Target is DbTarget
    assert TargetType.COUNT.value == "count"


def test_ledger_targets_reexport_client_helpers():
    assert query_targets is db_query_targets


def test_ledger_client_reexports_supabase_client():
    assert callable(get_supabase_client)


def test_ledger_supabase_schema_boundaries_are_defaulted():
    assert LEDGER_SCHEMA == "ledger"
    assert TARGETS_SCHEMA == "targets"


def test_ledger_normalization_exports_helpers():
    assert callable(convert_units)
