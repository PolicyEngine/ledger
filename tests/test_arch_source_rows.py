"""Tests for row-oriented source parsers."""

from __future__ import annotations

import json

import pytest

from arch.sources.cells import SourceArtifactMetadata
from arch.sources.rows import (
    source_rows_from_census_acs_s0101_age_json,
    source_rows_from_census_acs_s2201_snap_json,
    source_rows_from_census_b01001_female_age_json,
    source_rows_from_cdc_vsrr_live_births_json,
    source_rows_from_ees_permalink_table_html,
    source_rows_from_json_table,
)


def _artifact() -> SourceArtifactMetadata:
    return SourceArtifactMetadata(
        source_name="slc",
        source_table="test",
        source_file="test.html",
        url="https://example.test/test",
        vintage="test",
        sha256="abc123",
        size_bytes=10,
        extracted_at="2026-05-10",
        extraction_method="test",
    )


def _ees_html(tbody: list[list[str]]) -> bytes:
    table_json = {
        "thead": [
            [
                {"colSpan": 2, "rowSpan": 2, "tag": "td"},
                {"colSpan": 2, "text": "Plan 2", "tag": "th"},
            ],
            [
                {"text": "2025-26", "tag": "th"},
                {"text": "2024-25", "tag": "th"},
            ],
        ],
        "tbody": [
            [{"text": value, "tag": "td"} for value in row] for row in tbody
        ],
    }
    next_data = {
        "props": {
            "pageProps": {
                "data": {
                    "table": {
                        "json": table_json,
                    },
                },
            },
        },
    }
    return (
        '<script id="__NEXT_DATA__" type="application/json">'
        f"{json.dumps(next_data)}"
        "</script>"
    ).encode()


def test_ees_permalink_parser_expands_grouped_and_continuation_rows():
    rows = source_rows_from_ees_permalink_table_html(
        _ees_html(
            [
                [
                    "Higher education total",
                    "Number of borrowers liable to make repayments",
                    "9,710,000",
                    "8,940,000",
                ],
                [
                    (
                        "Number of borrowers liable to make repayments and "
                        "earning above repayment threshold"
                    ),
                    "4,460,000",
                    "3,985,000",
                ],
            ]
        ),
        _artifact(),
        sheet_name="table",
    )

    assert [row.values["row_group"] for row in rows] == [
        "Higher education total",
        "Higher education total",
    ]
    assert rows[0].values["borrower_status"] == "liable_to_repay"
    assert rows[1].values["borrower_status"] == "above_repayment_threshold"
    assert rows[0].values["value_2025"] == 8_940_000
    assert rows[1].values["value_2026"] == 4_460_000


def test_ees_permalink_parser_rejects_short_rows():
    with pytest.raises(ValueError, match="unexpected cell count"):
        source_rows_from_ees_permalink_table_html(
            _ees_html(
                [
                    [
                        "Higher education total",
                        "Number of borrowers liable to make repayments",
                    ],
                ]
            ),
            _artifact(),
        )


def test_ees_permalink_parser_rejects_continuation_before_group():
    with pytest.raises(ValueError, match="before any row group"):
        source_rows_from_ees_permalink_table_html(
            _ees_html(
                [
                    [
                        (
                            "Number of borrowers liable to make repayments and "
                            "earning above repayment threshold"
                        ),
                        "4,460,000",
                        "3,985,000",
                    ],
                ]
            ),
            _artifact(),
        )


def test_json_table_parser_reads_header_array_rows():
    rows = source_rows_from_json_table(
        json.dumps(
            [
                ["GEO_ID", "NAME", "S0101_C01_002E"],
                ["0100000US", "United States", "18365047"],
            ]
        ).encode(),
        _artifact(),
        sheet_name="api",
    )

    assert len(rows) == 1
    assert rows[0].row_number == 2
    assert rows[0].values == {
        "GEO_ID": "0100000US",
        "NAME": "United States",
        "S0101_C01_002E": 18_365_047,
    }


def test_json_table_parser_reads_object_rows():
    rows = source_rows_from_json_table(
        json.dumps(
            [
                {"state": "ALABAMA", "data_value": "4932"},
                {"state": "ALASKA", "data_value": "753"},
            ]
        ).encode(),
        _artifact(),
        sheet_name="api",
    )

    assert [row.row_number for row in rows] == [1, 2]
    assert rows[0].values == {"state": "ALABAMA", "data_value": 4_932}


def test_census_acs_s0101_age_parser_unpivots_age_columns():
    rows = source_rows_from_census_acs_s0101_age_json(
        json.dumps(
            [
                [
                    "GEO_ID",
                    "NAME",
                    "S0101_C01_002E",
                    "S0101_C01_003E",
                    "S0101_C01_019E",
                ],
                ["0100000US", "United States", "18365047", "18110921", "6343153"],
            ]
        ).encode(),
        _artifact(),
        sheet_name="api",
    )

    assert len(rows) == 18
    assert rows[0].values["age"] == "Aged 0-4"
    assert rows[0].values["source_column_id"] == "S0101_C01_002E"
    assert rows[0].values["value"] == 18_365_047
    assert rows[-1].values["age"] == "Aged 85 and over"
    assert rows[-1].values["value"] == 6_343_153


def test_census_b01001_female_age_parser_unpivots_age_columns():
    rows = source_rows_from_census_b01001_female_age_json(
        json.dumps(
            [
                [
                    "B01001_030E",
                    "B01001_031E",
                    "B01001_038E",
                    "state",
                ],
                ["100354", "72341", "168164", "01"],
            ]
        ).encode(),
        _artifact(),
        sheet_name="api",
    )

    assert len(rows) == 9
    assert rows[0].values["state"] == "01"
    assert rows[0].values["geography_id"] == "0400000US01"
    assert rows[0].values["sex"] == "female"
    assert rows[0].values["source_column_id"] == "B01001_030E"
    assert rows[0].values["age"] == "Female 15 to 17 years"
    assert rows[0].values["value"] == 100_354
    assert rows[-1].values["source_column_id"] == "B01001_038E"
    assert rows[-1].values["age"] == "Female 40 to 44 years"
    assert rows[-1].values["value"] == 168_164


def test_census_acs_s2201_snap_parser_unpivots_household_columns():
    rows = source_rows_from_census_acs_s2201_snap_json(
        json.dumps(
            [
                [
                    "GEO_ID",
                    "NAME",
                    "S2201_C01_001E",
                    "S2201_C03_001E",
                    "S2201_C05_001E",
                ],
                [
                    "5001900US0101",
                    "Congressional District 1 (119th Congress), Alabama",
                    "300636",
                    "34742",
                    "265894",
                ],
            ]
        ).encode(),
        _artifact(),
        sheet_name="api",
    )

    assert len(rows) == 3
    assert rows[0].values["snap_receipt_status"] == "all"
    assert rows[0].values["source_column_id"] == "S2201_C01_001E"
    assert rows[0].values["value"] == 300_636
    assert rows[1].values["snap_receipt_status"] == "receiving_food_stamps_snap"
    assert rows[1].values["source_column_id"] == "S2201_C03_001E"
    assert rows[1].values["value"] == 34_742
    assert rows[2].values["snap_receipt_status"] == (
        "not_receiving_food_stamps_snap"
    )
    assert rows[2].values["value"] == 265_894


def test_cdc_vsrr_live_births_parser_sets_month_period():
    rows = source_rows_from_cdc_vsrr_live_births_json(
        json.dumps(
            [
                {
                    "state": "ALABAMA",
                    "year": "2024",
                    "month": "January",
                    "period": "Monthly",
                    "indicator": "Number of Live Births",
                    "data_value": "4932",
                }
            ]
        ).encode(),
        _artifact(),
        sheet_name="api",
    )

    assert len(rows) == 1
    assert rows[0].values["period"] == "2024-01"
    assert rows[0].values["frequency"] == "Monthly"
    assert rows[0].values["data_value"] == 4_932
