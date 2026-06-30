"""Tests for the Ledger namespace."""

from ledger.client import get_supabase_client
from ledger.microdata import get_table_name, query_cps_asec
from ledger.normalization import convert_units
from ledger.targets import (
    Target,
    TargetSpec,
    TargetType,
    get_targets,
    query_targets,
)
from db.schema import Target as DbTarget
from db.supabase_client import (
    LEDGER_SCHEMA,
    MICRODATA_SCHEMA,
    TARGETS_SCHEMA,
    query_targets as db_query_targets,
)


def test_ledger_targets_reexport_schema_objects():
    assert Target is DbTarget
    assert TargetType.COUNT.value == "count"
    assert TargetSpec.__name__ == "TargetSpec"


def test_ledger_targets_reexport_client_helpers():
    assert query_targets is db_query_targets
    assert callable(get_targets)


def test_ledger_microdata_reexport_client_helpers():
    assert get_table_name("us", "census", "cps_asec", 2024, "person") == (
        "us_census_cps_asec_2024_person"
    )
    assert callable(query_cps_asec)


def test_ledger_client_reexports_supabase_client():
    assert callable(get_supabase_client)


def test_ledger_supabase_schema_boundaries_are_defaulted():
    assert LEDGER_SCHEMA == "ledger"
    assert MICRODATA_SCHEMA == "microdata"
    assert TARGETS_SCHEMA == "targets"


def test_ledger_normalization_exports_helpers():
    assert callable(convert_units)
