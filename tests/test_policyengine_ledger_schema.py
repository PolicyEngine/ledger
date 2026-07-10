"""Tests for the packaged consumer-fact row schema and its validator.

The packaged schema is the single source of truth used by artifact builds and
loads. These tests pin it byte-for-byte to ``docs/schemas`` so the two copies
cannot drift, and exercise the validator's precise error reporting.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from policyengine_ledger.schema import (
    CONSUMER_FACT_SCHEMA_SHA256,
    consumer_fact_schema,
    validate_consumer_fact_row,
)

_REPO_ROOT = Path(__file__).parents[1]
_DOCS_SCHEMA_PATH = _REPO_ROOT / "docs" / "schemas" / "consumer_fact.v1.schema.json"
_PACKAGED_SCHEMA_PATH = (
    _REPO_ROOT
    / "policyengine_ledger"
    / "schemas"
    / "consumer_fact.v1.schema.json"
)
_SAMPLE_PATH = _REPO_ROOT / "ledger" / "fixtures" / "consumer_facts.jsonl"


def test_packaged_schema_is_byte_identical_to_docs_schema():
    docs_bytes = _DOCS_SCHEMA_PATH.read_bytes()
    packaged_bytes = _PACKAGED_SCHEMA_PATH.read_bytes()

    assert packaged_bytes == docs_bytes
    assert hashlib.sha256(packaged_bytes).hexdigest() == CONSUMER_FACT_SCHEMA_SHA256


def test_consumer_fact_schema_is_the_v1_contract_row():
    schema = consumer_fact_schema()

    assert schema["title"] == "Ledger consumer fact contract row"
    assert schema["additionalProperties"] is False
    assert schema["properties"]["schema_version"]["const"] == "ledger.consumer_fact.v1"


def test_valid_fixture_rows_pass_validation():
    rows = [
        json.loads(line)
        for line in _SAMPLE_PATH.read_text().splitlines()
        if line.strip()
    ]

    assert len(rows) == 3
    for line_number, row in enumerate(rows, start=1):
        validate_consumer_fact_row(row, line_number, _SAMPLE_PATH)


def test_missing_nested_required_field_names_field_and_location():
    row = json.loads(_SAMPLE_PATH.read_text().splitlines()[0])
    del row["observed_measure"]["unit"]

    with pytest.raises(ValueError) as excinfo:
        validate_consumer_fact_row(row, 4, "sample.jsonl")

    message = str(excinfo.value)
    assert "row 4 of sample.jsonl" in message
    assert "observed_measure" in message
    assert "unit" in message


def test_unknown_extra_field_is_rejected():
    row = json.loads(_SAMPLE_PATH.read_text().splitlines()[0])
    row["surprise_field"] = "unexpected"

    with pytest.raises(ValueError, match="surprise_field"):
        validate_consumer_fact_row(row, 1, "sample.jsonl")
