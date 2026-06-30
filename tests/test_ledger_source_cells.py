"""Tests for Ledger source-cell preservation."""

from __future__ import annotations

from dataclasses import replace

import pytest

from ledger.harness import (
    build_fixture_source_cell_file,
    validate_fixture_source_cells,
)
from ledger.jurisdictions.us.soi import (
    build_soi_table_1_1_source_cells,
    build_soi_table_1_1_source_record_specs,
)
from ledger.sources.cells import (
    load_source_cells_jsonl,
    source_cells_from_delimited_text,
    source_cells_from_html_tables_and_text,
    validate_source_cells,
)
from ledger.sources.cells import SourceArtifactMetadata
from ledger.sources.rows import SourceRow, source_cells_from_source_rows
from ledger.sources.specs import resolve_source_record


def test_build_soi_table_1_1_source_cells_preserves_workbook_used_range():
    cells = build_soi_table_1_1_source_cells(2023)
    report = validate_source_cells(cells)
    cells_by_address = {cell.address: cell for cell in cells}

    assert report.valid
    assert report.cell_count == 92 * 21
    assert report.counts["by_sheet"] == {"TBL11": 1932}
    assert report.counts["by_source"] == {"irs_soi": 1932}
    assert cells_by_address["A10"].raw_value == "All returns"
    assert cells_by_address["B10"].raw_value == 160_602_107
    assert cells_by_address["B10"].artifact.source_file == "23in11si.xls"


def test_build_source_cell_file_writes_jsonl(tmp_path):
    output = tmp_path / "soi-cells.jsonl"

    report = build_fixture_source_cell_file("soi-table-1-1", output, year=2023)
    cells = load_source_cells_jsonl(output)

    assert report.valid
    assert len(cells) == 1932
    assert cells[0].artifact.sha256


def test_fixture_source_cells_validate():
    report = validate_fixture_source_cells()

    assert report.valid
    assert report.cell_count == 1932
    assert report.counts["by_sheet"] == {"TBL11": 1932}


def test_source_record_selector_guard_fails_on_changed_row_header():
    cells = build_soi_table_1_1_source_cells(2023)
    spec = build_soi_table_1_1_source_record_specs(2023)[0]
    bad_spec = replace(
        spec,
        selector=replace(spec.selector, expected_row_header="Not all returns"),
    )

    with pytest.raises(ValueError, match="expected row header"):
        resolve_source_record(cells, bad_spec)


def test_delimited_source_row_selection_requires_exact_match():
    artifact = SourceArtifactMetadata(
        source_name="bea",
        source_table="test",
        source_file="test.csv",
        url="https://example.test/test.csv",
        vintage="test",
        sha256="abc123",
        size_bytes=10,
        extracted_at="2026-05-06",
        extraction_method="test",
    )
    rows = [
        SourceRow(
            artifact=artifact,
            sheet_name="NipaDataA",
            row_number=2,
            values={"Period": 2021, "SeriesCode": "W351RC", "Value": 1},
        ),
        SourceRow(
            artifact=artifact,
            sheet_name="NipaDataA",
            row_number=3,
            values={"Period": 2022, "SeriesCode": "W351RC", "Value": 2},
        ),
    ]

    with pytest.raises(ValueError, match="matched 2 rows"):
        source_cells_from_source_rows(
            rows,
            selected_rows=({"SeriesCode": "W351RC"},),
        )

    with pytest.raises(ValueError, match="matched 0 rows"):
        source_cells_from_source_rows(
            rows,
            selected_rows=({"SeriesCode": "Y351RC", "Period": "2022"},),
        )


def test_delimited_text_selected_rows_preserves_requested_order_with_shared_keys():
    artifact = SourceArtifactMetadata(
        source_name="census_pep",
        source_table="test",
        source_file="test.csv",
        url="https://example.test/test.csv",
        vintage="test",
        sha256="abc123",
        size_bytes=10,
        extracted_at="2026-05-27",
        extraction_method="test",
    )
    content = b"STATE,RACE,AGE,VALUE\n06,1,0,10\n06,1,1,11\n06,2,0,20\n"

    cells = source_cells_from_delimited_text(
        content,
        artifact,
        sheet_name="test",
        selected_rows=(
            {"STATE": "06", "RACE": "2", "AGE": "0"},
            {"STATE": "06", "RACE": "1", "AGE": "0"},
        ),
    )
    values = {
        (cell.row_number, cell.column_number): cell.raw_value
        for cell in cells
        if cell.row_number > 1
    }

    assert values[(2, 4)] == 20
    assert values[(3, 4)] == 10


def test_html_tables_and_text_parser_preserves_tables_and_document_numbers():
    artifact = SourceArtifactMetadata(
        source_name="dwp",
        source_table="test html",
        source_file="test.html",
        url="https://example.test/test.html",
        vintage="test",
        sha256="abc123",
        size_bytes=10,
        extracted_at="2026-05-10",
        extraction_method="test",
    )
    html = b"""
    <html>
      <body>
        <p>There were 620,000 ESA cases and 180,000 income-related cases.</p>
        <table>
          <thead>
            <tr><th>Benefit</th><th>Cases</th></tr>
          </thead>
          <tbody>
            <tr><td>Employment and Support Allowance</td><td>999,000</td></tr>
          </tbody>
        </table>
      </body>
    </html>
    """

    cells = source_cells_from_html_tables_and_text(html, artifact)
    cells_by_sheet_address = {(cell.sheet_name, cell.address): cell for cell in cells}

    assert validate_source_cells(cells).valid
    assert cells_by_sheet_address[("table_1", "A1")].raw_value == "Benefit"
    assert cells_by_sheet_address[("table_1", "B2")].raw_value == 999_000
    assert cells_by_sheet_address[("table_1", "B2")].display_value == "999,000"
    assert cells_by_sheet_address[("document_numbers", "D2")].raw_value == "620,000"
    assert cells_by_sheet_address[("document_numbers", "E2")].raw_value == 620_000
    assert cells_by_sheet_address[("document_numbers", "D3")].raw_value == "180,000"
    assert cells_by_sheet_address[("document_numbers", "E3")].raw_value == 180_000
