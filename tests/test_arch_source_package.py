"""Focused tests for declarative Arch source packages."""

from __future__ import annotations

from copy import deepcopy
import hashlib
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import openpyxl
import pytest
import yaml

from arch.core import validate_facts
from arch.source_package import (
    SOURCE_ARTIFACT_CACHE_ENV,
    SOURCE_ARTIFACT_FETCH_ENV,
    SourceArtifactSpec,
    _read_source_artifact_content,
    _source_artifact_cache_path,
    load_source_package,
    validate_source_package,
)
from arch.sources.cells import build_source_cell_key, validate_source_cells
from arch.sources.rows import validate_source_rows

REPO_ROOT = Path(__file__).resolve().parents[1]


class _InlineZipArtifactSpec(SourceArtifactSpec):
    def __init__(self, *, content: bytes, filename: str) -> None:
        super().__init__(
            source_name="test",
            source_table="Test workbook in ZIP",
            resource_package="db",
            resource_directory="data/test",
            manifest="manifest.yaml",
            vintage="test",
            extracted_at="2026-05-10",
            extraction_method="test ZIP member parse",
            parser="zip_xlsx_used_range",
        )
        object.__setattr__(self, "_content", content)
        object.__setattr__(self, "_filename", filename)

    def _artifact_content(self, year: int) -> tuple[bytes, str, str, dict[str, str]]:
        return (
            self._content,
            self._filename,
            f"https://example.test/{year}/{self._filename}",
            {
                "bucket": "arch-raw-test",
                "key": f"raw/{self._filename}",
                "uri": f"r2://arch-raw-test/raw/{self._filename}",
            },
        )


def _tiny_xlsx_bytes() -> bytes:
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Sheet1"
    sheet["A1"] = "label"
    sheet["B2"] = 123
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def _zip_with_workbook(workbook_content: bytes, *, note: str) -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr("book.xlsx", workbook_content)
        archive.writestr("note.txt", note)
    return buffer.getvalue()


class _MissingArtifactPath:
    def read_bytes(self) -> bytes:
        raise FileNotFoundError("not packaged")


def test_source_package_alias_compiles_soi_table_1_1_specs():
    package = load_source_package("soi-table-1-1")
    record_set = package.build_source_record_set_specs(2023)[0]
    specs = package.build_source_record_specs(2023)

    assert package.package_id == "soi-table-1-1"
    assert record_set.record_set_id == "irs_soi.ty2023.table_1_1"
    assert len(record_set.rows) == 20
    assert len(record_set.measures) == 4
    assert len(specs) == 80
    assert specs[0].source_record_id == "irs_soi.ty2023.table_1_1.all.return_count"
    assert specs[0].layout is not None
    assert specs[0].layout.record_set_spec_hash == "d606c87f11948c197386dfa4"


def test_empty_guard_cells_do_not_change_legacy_single_cell_hash(tmp_path):
    source_path = REPO_ROOT / "packages" / "irs_soi" / "table_1_1"
    payload = yaml.safe_load((source_path / "source_package.yaml").read_text())
    payload["record_sets"][0]["rows"][0]["guard_cells"] = []

    package_dir = tmp_path / "soi-with-empty-guards"
    package_dir.mkdir()
    (package_dir / "source_package.yaml").write_text(yaml.safe_dump(payload))

    specs = load_source_package(package_dir).build_source_record_specs(2023)

    assert specs[0].layout is not None
    assert specs[0].layout.record_set_spec_hash == "d606c87f11948c197386dfa4"


def test_guard_cell_order_does_not_change_record_set_spec_hash(tmp_path):
    source_path = REPO_ROOT / "packages" / "irs_soi" / "table_1_1"
    payload = yaml.safe_load((source_path / "source_package.yaml").read_text())
    row = payload["record_sets"][0]["rows"][0]
    row["guard_cells"] = [
        {"column": "A", "expected_value": "All returns"},
        {"column": "B", "expected_value": 160_602_107},
    ]
    reordered = deepcopy(payload)
    reordered["record_sets"][0]["rows"][0]["guard_cells"] = list(
        reversed(row["guard_cells"])
    )

    package_dir = tmp_path / "soi-original"
    reordered_dir = tmp_path / "soi-reordered-guards"
    package_dir.mkdir()
    reordered_dir.mkdir()
    (package_dir / "source_package.yaml").write_text(yaml.safe_dump(payload))
    (reordered_dir / "source_package.yaml").write_text(yaml.safe_dump(reordered))

    original_specs = load_source_package(package_dir).build_source_record_specs(2023)
    reordered_specs = load_source_package(reordered_dir).build_source_record_specs(2023)

    assert original_specs[0].layout is not None
    assert reordered_specs[0].layout is not None
    assert (
        reordered_specs[0].layout.record_set_spec_hash
        == original_specs[0].layout.record_set_spec_hash
    )


def test_guard_cell_expected_value_changes_record_set_spec_hash(tmp_path):
    source_path = REPO_ROOT / "packages" / "irs_soi" / "table_1_1"
    payload = yaml.safe_load((source_path / "source_package.yaml").read_text())
    payload["record_sets"][0]["rows"][0]["guard_cells"] = [
        {"column": "A", "expected_value": "All returns"},
    ]
    changed = deepcopy(payload)
    changed["record_sets"][0]["rows"][0]["guard_cells"][0][
        "expected_value"
    ] = "Different label"

    package_dir = tmp_path / "soi-original"
    changed_dir = tmp_path / "soi-changed-guard"
    package_dir.mkdir()
    changed_dir.mkdir()
    (package_dir / "source_package.yaml").write_text(yaml.safe_dump(payload))
    (changed_dir / "source_package.yaml").write_text(yaml.safe_dump(changed))

    original_specs = load_source_package(package_dir).build_source_record_specs(2023)
    changed_specs = load_source_package(changed_dir).build_source_record_specs(2023)

    assert original_specs[0].layout is not None
    assert changed_specs[0].layout is not None
    assert (
        changed_specs[0].layout.record_set_spec_hash
        != original_specs[0].layout.record_set_spec_hash
    )


def test_zip_xlsx_cell_identity_uses_inner_workbook_hash():
    workbook_content = _tiny_xlsx_bytes()
    first_zip = _zip_with_workbook(workbook_content, note="first container")
    second_zip = _zip_with_workbook(workbook_content, note="second container")

    first_cells = _InlineZipArtifactSpec(
        content=first_zip,
        filename="first.zip",
    ).build_source_cells(2024)
    second_cells = _InlineZipArtifactSpec(
        content=second_zip,
        filename="second.zip",
    ).build_source_cells(2024)

    first_cell = next(cell for cell in first_cells if cell.address == "B2")
    second_cell = next(cell for cell in second_cells if cell.address == "B2")
    workbook_sha256 = hashlib.sha256(workbook_content).hexdigest()

    assert (
        hashlib.sha256(first_zip).hexdigest() != hashlib.sha256(second_zip).hexdigest()
    )
    assert first_cell.artifact.sha256 == workbook_sha256
    assert second_cell.artifact.sha256 == workbook_sha256
    assert first_cell.artifact.source_file == "first.zip!book.xlsx"
    assert second_cell.artifact.source_file == "second.zip!book.xlsx"
    assert build_source_cell_key(first_cell) == build_source_cell_key(second_cell)
    assert "outer SHA-256" in first_cell.artifact.extraction_method


def test_source_artifact_loader_reads_content_addressed_cache(tmp_path, monkeypatch):
    content = b"cached source artifact"
    source = tmp_path / "source.csv"
    source.write_bytes(b"publisher content should not be fetched")
    spec = {
        "filename": "source.csv",
        "source_url": str(source),
        "sha256": hashlib.sha256(content).hexdigest(),
    }
    monkeypatch.setenv(SOURCE_ARTIFACT_CACHE_ENV, str(tmp_path / "cache"))
    cache_path = _source_artifact_cache_path(spec)
    cache_path.parent.mkdir(parents=True)
    cache_path.write_bytes(content)

    assert _read_source_artifact_content(_MissingArtifactPath(), spec) == content


def test_source_artifact_loader_fetches_missing_artifact_when_enabled(
    tmp_path,
    monkeypatch,
):
    content = b"publisher source artifact"
    source = tmp_path / "source.csv"
    source.write_bytes(content)
    spec = {
        "filename": "source.csv",
        "source_url": str(source),
        "sha256": hashlib.sha256(content).hexdigest(),
    }
    monkeypatch.setenv(SOURCE_ARTIFACT_CACHE_ENV, str(tmp_path / "cache"))
    monkeypatch.setenv(SOURCE_ARTIFACT_FETCH_ENV, "1")

    assert _read_source_artifact_content(_MissingArtifactPath(), spec) == content
    assert _source_artifact_cache_path(spec).read_bytes() == content


def test_source_package_path_builds_valid_soi_table_1_4_facts():
    package_path = REPO_ROOT / "packages" / "irs_soi" / "table_1_4"
    package = load_source_package(package_path)
    cells = package.build_source_cells(2023)
    facts = package.build_facts(2023, cells=cells)
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert package.package_id == "soi-table-1-4"
    assert len(cells) == 8109
    assert len(facts) == 340
    assert validate_facts(facts).valid
    assert facts[0].source.source_table == "Publication 1304 Table 1.4"
    assert (
        values_by_record[
            "irs_soi.ty2023.table_1_4.all.alimony_received_amount"
        ].value
        == 6_686_429_000
    )
    assert (
        values_by_record["irs_soi.ty2023.table_1_4.all.alimony_paid_amount"].value
        == 7_497_135_000
    )


def test_validate_source_package_reports_fixture_counts():
    report = validate_source_package("soi-table-1-1", year=2023)

    assert report.valid
    assert report.counts == {
        "measure_count": 4,
        "record_set_count": 1,
        "row_count": 20,
        "source_record_count": 80,
        "source_region_count": 1,
    }


def test_national_soi_source_package_aliases_validate_fixture_counts():
    expected_counts = {
        "soi-table-1-2": {
            "record_set_count": 1,
            "row_count": 1,
            "measure_count": 7,
            "source_record_count": 7,
            "source_region_count": 1,
        },
        "soi-table-2-1": {
            "record_set_count": 1,
            "row_count": 1,
            "measure_count": 37,
            "source_record_count": 37,
            "source_region_count": 1,
        },
        "soi-table-2-5": {
            "record_set_count": 1,
            "row_count": 1,
            "measure_count": 8,
            "source_record_count": 8,
            "source_region_count": 1,
        },
        "soi-table-2-5-eitc-agi-children-2022": {
            "record_set_count": 4,
            "row_count": 116,
            "measure_count": 8,
            "source_record_count": 232,
            "source_region_count": 4,
        },
        "soi-table-4-3": {
            "record_set_count": 1,
            "row_count": 1,
            "measure_count": 18,
            "source_record_count": 18,
            "source_region_count": 1,
        },
        "soi-historic-table-2-state-agi-2022": {
            "record_set_count": 51,
            "row_count": 459,
            "measure_count": 102,
            "source_record_count": 918,
            "source_region_count": 51,
        },
        "soi-historic-table-2-state-broad-2022": {
            "record_set_count": 51,
            "row_count": 51,
            "measure_count": 2703,
            "source_record_count": 2703,
            "source_region_count": 51,
        },
        "soi-historic-table-2-state-eitc-2022": {
            "record_set_count": 51,
            "row_count": 51,
            "measure_count": 510,
            "source_record_count": 510,
            "source_region_count": 51,
        },
        "soi-w2-statistics-2020": {
            "record_set_count": 3,
            "row_count": 3,
            "measure_count": 5,
            "source_record_count": 5,
            "source_region_count": 3,
        },
        "soi-ira-traditional-contributions-2022": {
            "record_set_count": 1,
            "row_count": 1,
            "measure_count": 2,
            "source_record_count": 2,
            "source_region_count": 1,
        },
        "soi-ira-roth-contributions-2022": {
            "record_set_count": 1,
            "row_count": 1,
            "measure_count": 2,
            "source_record_count": 2,
            "source_region_count": 1,
        },
    }

    for package_id, counts in expected_counts.items():
        report = validate_source_package(package_id, year=2023)

        assert report.valid, package_id
        assert report.counts == counts


def test_soi_table_2_1_package_builds_itemized_deduction_details():
    package = load_source_package("soi-table-2-1")
    rows = package.build_source_rows(2023)
    cells = package.build_source_cells(2023, source_rows=rows)
    facts = package.build_facts(2023, cells=cells, source_rows=rows)
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert package.package_id == "soi-table-2-1"
    assert validate_source_rows(rows).valid
    assert validate_source_cells(cells).valid
    assert validate_facts(facts).valid
    assert len(facts) == 37

    charitable = values_by_record[
        "irs_soi.ty2023.table_2_1.itemized_all_returns.all.charitable_amount"
    ]
    interest = values_by_record[
        "irs_soi.ty2023.table_2_1.itemized_all_returns.all."
        "interest_paid_deduction_amount"
    ]
    mortgage_financial = values_by_record[
        "irs_soi.ty2023.table_2_1.itemized_all_returns.all."
        "mortgage_interest_paid_amount"
    ]
    mortgage_individual = values_by_record[
        "irs_soi.ty2023.table_2_1.itemized_all_returns.all."
        "home_mortgage_personal_seller_amount"
    ]
    deductible_points = values_by_record[
        "irs_soi.ty2023.table_2_1.itemized_all_returns.all."
        "deductible_points_amount"
    ]
    limited_salt = values_by_record[
        "irs_soi.ty2023.table_2_1.itemized_all_returns.all."
        "limited_state_local_taxes_amount"
    ]
    raw_state_local = values_by_record[
        "irs_soi.ty2023.table_2_1.itemized_all_returns.all."
        "total_state_local_taxes_amount"
    ]
    income_or_sales = values_by_record[
        "irs_soi.ty2023.table_2_1.itemized_all_returns.all."
        "state_local_income_or_sales_tax_amount"
    ]
    real_estate_taxes = values_by_record[
        "irs_soi.ty2023.table_2_1.itemized_all_returns.all."
        "real_estate_taxes_amount"
    ]

    assert charitable.value == 211_975_123_000
    assert charitable.measure.concept == "irs_soi.contributions_deduction"
    assert interest.value == 208_176_768_000
    assert mortgage_financial.value == 167_675_863_000
    assert mortgage_individual.value == 3_688_924_000
    assert deductible_points.value == 1_027_127_000
    assert limited_salt.value == 121_050_787_000
    assert raw_state_local.value == 331_823_221_000
    assert income_or_sales.value == 218_543_083_000
    assert real_estate_taxes.value == 108_606_373_000
    assert raw_state_local.source.raw_r2_uri


def test_census_stc_income_tax_package_builds_state_tax_facts():
    report = validate_source_package(
        "census-stc-individual-income-tax",
        year=2024,
    )
    package = load_source_package("census-stc-individual-income-tax")
    rows = package.build_source_rows(2024)
    cells = package.build_source_cells(2024, source_rows=rows)
    facts = package.build_facts(2024, cells=cells, source_rows=rows)
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert package.package_id == "census-stc-individual-income-tax"
    assert report.valid
    assert report.counts == {
        "record_set_count": 46,
        "row_count": 46,
        "measure_count": 46,
        "source_record_count": 46,
        "source_region_count": 46,
    }
    assert len(rows) == 25
    assert validate_source_rows(rows).valid
    assert validate_source_cells(cells).valid
    assert validate_facts(facts).valid
    assert len(cells) == 106
    assert len(facts) == 46
    assert all(fact.source_row_keys for fact in facts)
    assert all(fact.source.raw_r2_uri for fact in facts)

    ca_fact = values_by_record[
        "census_stc.fy2024.individual_income_tax_collections.ca.t40.collections"
    ]

    assert ca_fact.value == 123_101_651_000
    assert ca_fact.entity.name == "government"
    assert ca_fact.geography.id == "0400000US06"
    assert ca_fact.source.source_file == "FY2024-Flat-File.txt"
    assert not ca_fact.constraints

    rows_2023 = package.build_source_rows(2023)
    cells_2023 = package.build_source_cells(2023, source_rows=rows_2023)
    facts_2023 = package.build_facts(
        2023,
        cells=cells_2023,
        source_rows=rows_2023,
    )
    values_by_record_2023 = {fact.source_record_id: fact for fact in facts_2023}
    ca_fact_2023 = values_by_record_2023[
        "census_stc.fy2023.individual_income_tax_collections.ca.t40.collections"
    ]

    assert len(rows_2023) == 25
    assert validate_source_rows(rows_2023).valid
    assert validate_source_cells(cells_2023).valid
    assert validate_facts(facts_2023).valid
    assert len(facts_2023) == 46
    assert ca_fact_2023.value == 96_379_294_000
    assert ca_fact_2023.source.source_table == (
        "FY2023 STC Flat File item T40 Individual Income Taxes"
    )


def test_federal_reserve_z1_package_builds_net_worth_fact():
    report = validate_source_package(
        "federal-reserve-z1-household-net-worth",
        year=2024,
    )
    package = load_source_package("federal-reserve-z1-household-net-worth")
    cells = package.build_source_cells(2024)
    records = package.build_source_records(2024, cells=cells)
    facts = package.build_facts(2024, cells=cells)
    records_by_id = {record.source_record_id: record for record in records}
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert package.package_id == "federal-reserve-z1-household-net-worth"
    assert report.valid
    assert report.counts == {
        "record_set_count": 1,
        "row_count": 1,
        "measure_count": 1,
        "source_record_count": 1,
        "source_region_count": 1,
    }
    assert len(cells) == 709
    assert validate_source_cells(cells).valid
    assert len(facts) == 1
    assert validate_facts(facts).valid
    assert all(fact.source.source_name == "federal_reserve" for fact in facts)
    assert all("fred" not in (fact.source.url or "") for fact in facts)
    assert all(fact.source.raw_r2_uri for fact in facts)

    record_id = (
        "federal_reserve_z1.cy2024.households_nonprofits_balance_sheet."
        "net_worth.fl152090005.amount_outstanding"
    )

    assert records_by_id[record_id].source_cell_addresses == (
        "E41",
        "E1",
        "A41",
        "C41",
    )
    assert values_by_record[record_id].value == 169_619_200_000_000
    assert values_by_record[record_id].period.value == 2024
    assert values_by_record[record_id].geography.id == "0100000US"
    assert values_by_record[record_id].entity.name == "institutional_sector"
    assert not values_by_record[record_id].filters
    assert not values_by_record[record_id].constraints


def test_cms_nhe_package_builds_medicaid_expenditure_fact():
    package = load_source_package("cms-nhe-historical-service-source")
    cells = package.build_source_cells(2024)
    facts = package.build_facts(2024, cells=cells)

    assert package.package_id == "cms-nhe-historical-service-source"
    assert validate_source_cells(cells).valid
    assert validate_facts(facts).valid
    assert len(cells) == 35_970
    assert len(facts) == 1

    fact = facts[0]
    assert fact.source_record_id == (
        "cms_nhe.cy2024.medicaid_title_xix_expenditures."
        "medicaid_title_xix.expenditure_amount"
    )
    assert fact.value == 931_692_000_000
    assert fact.measure.concept == "cms_nhe.medicaid_title_xix_expenditures"
    assert fact.period.value == 2024
    assert fact.geography.id == "0100000US"
    assert fact.entity.name == "person"
    assert fact.source.source_file.endswith(".zip!NHE2024.xls")
    assert fact.source.raw_r2_uri
    assert not fact.filters
    assert not fact.constraints


def test_cms_medicare_trustees_package_builds_part_b_premium_fact():
    package = load_source_package(
        "cms-medicare-trustees-report-2025-part-b-premium-income"
    )
    cells = package.build_source_cells(2025)
    records = package.build_source_records(2025, cells=cells)
    facts = package.build_facts(2025, cells=cells)
    records_by_id = {record.source_record_id: record for record in records}
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert (
        package.package_id
        == "cms-medicare-trustees-report-2025-part-b-premium-income"
    )
    assert len(cells) == 93_486
    assert validate_source_cells(cells).valid
    assert len(facts) == 1
    assert validate_facts(facts).valid
    assert all(fact.source.source_name == "cms_medicare" for fact in facts)
    assert all(fact.source.raw_r2_uri for fact in facts)

    record_id = (
        "cms_medicare.cy2024.part_b_premium_income."
        "premiums_from_enrollees.actual_amount"
    )
    assert records_by_id[record_id].source_cell_addresses == (
        "E3356",
        "E1",
        "A3356",
        "B3356",
        "D3356",
        "F3356",
    )
    assert values_by_record[record_id].value == 139_837_000_000
    assert values_by_record[record_id].measure.concept == (
        "cms_medicare.part_b_premium_income"
    )
    assert values_by_record[record_id].period.value == 2024
    assert values_by_record[record_id].geography.id == "0100000US"
    assert values_by_record[record_id].entity.name == "government"
    assert values_by_record[record_id].filters["amount_basis"] == "actual"
    assert values_by_record[record_id].measure.unit == "usd"


def test_hhs_acf_liheap_package_builds_household_count_fact():
    package = load_source_package("hhs-acf-liheap-fy2024-national-profile")
    cells = package.build_source_cells(2024)
    records = package.build_source_records(2024, cells=cells)
    facts = package.build_facts(2024, cells=cells)
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert package.package_id == "hhs-acf-liheap-fy2024-national-profile"
    assert validate_source_cells(cells).valid
    assert validate_facts(facts).valid
    assert len(cells) == 348
    assert len(facts) == 1
    assert all(fact.source.raw_r2_uri for fact in facts)

    record_id = (
        "hhs_acf_liheap.fy2024.national_profile."
        "state_programs.households_served"
    )
    assert records[0].source_cell_addresses == (
        "E3",
        "E1",
        "A3",
        "B3",
        "D3",
        "F3",
    )
    assert values_by_record[record_id].value == 5_876_646
    assert values_by_record[record_id].measure.concept == (
        "hhs_acf_liheap.households_served_by_state_programs"
    )
    assert values_by_record[record_id].period.value == 2024
    assert values_by_record[record_id].geography.id == "0100000US"
    assert values_by_record[record_id].entity.name == "household"
    assert (
        values_by_record[record_id].source.source_file
        == "acf_liheap_fy2024_all_states_national_profile.pdf"
    )
    assert values_by_record[record_id].constraints


def test_soi_table_2_5_eitc_child_totals_build_2022_facts():
    package = load_source_package("soi-table-2-5-eitc-agi-children-2022")
    cells = package.build_source_cells(2023)
    facts = package.build_facts(2023, cells=cells)
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert validate_source_cells(cells).valid
    assert validate_facts(facts).valid

    no_child_returns = values_by_record[
        "irs_soi.ty2022.table_2_5.eitc_by_agi_children."
        "no_qualifying_children.total.eitc_returns"
    ]
    one_child_amount = values_by_record[
        "irs_soi.ty2022.table_2_5.eitc_by_agi_children."
        "one_qualifying_child.total.eitc_total"
    ]
    two_child_returns = values_by_record[
        "irs_soi.ty2022.table_2_5.eitc_by_agi_children."
        "two_qualifying_children.total.eitc_returns"
    ]
    three_child_amount = values_by_record[
        "irs_soi.ty2022.table_2_5.eitc_by_agi_children."
        "three_or_more_qualifying_children.total.eitc_total"
    ]

    assert no_child_returns.value == 6_878_342
    assert one_child_amount.value == 21_182_747_000
    assert two_child_returns.value == 5_628_089
    assert three_child_amount.value == 14_000_930_000
    assert no_child_returns.filters == {"income_range": "all"}
    assert no_child_returns.layout.table_record_kind == "total"
    assert {
        constraint.variable for constraint in no_child_returns.constraints
    } == {"us.tax.earned_income_credit_qualifying_children"}
    assert {
        constraint.operator for constraint in three_child_amount.constraints
    } == {">="}


def test_ssa_supplement_source_package_alias_validates_fixture_counts():
    report = validate_source_package(
        "ssa-annual-statistical-supplement-2025", year=2023
    )

    assert report.valid
    assert report.counts == {
        "record_set_count": 1,
        "row_count": 6,
        "measure_count": 1,
        "source_record_count": 6,
        "source_region_count": 1,
    }


def test_census_pep_source_package_alias_validates_fixture_counts():
    report = validate_source_package("census-pep-2024-national-age-sex", year=2023)

    assert report.valid
    assert report.counts == {
        "record_set_count": 1,
        "row_count": 19,
        "measure_count": 1,
        "source_record_count": 19,
        "source_region_count": 1,
    }


def test_census_pep_state_source_package_alias_validates_fixture_counts():
    report = validate_source_package("census-pep-2024-state-age-sex", year=2023)

    assert report.valid
    assert report.counts == {
        "record_set_count": 51,
        "row_count": 969,
        "measure_count": 51,
        "source_record_count": 969,
        "source_region_count": 51,
    }


def test_cms_medicaid_source_package_alias_validates_fixture_counts():
    report = validate_source_package(
        "cms-medicaid-chip-monthly-enrollment-december-2024",
        year=2023,
    )

    assert report.valid
    assert report.counts == {
        "record_set_count": 1,
        "row_count": 52,
        "measure_count": 5,
        "source_record_count": 260,
        "source_region_count": 1,
    }


def test_cms_medicaid_package_builds_december_2024_state_enrollment_facts():
    package = load_source_package(
        "cms-medicaid-chip-monthly-enrollment-december-2024"
    )
    cells = package.build_source_cells(2023)
    records = package.build_source_records(2023, cells=cells)
    facts = package.build_facts(2023, cells=cells)
    records_by_id = {record.source_record_id: record for record in records}
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert package.package_id == "cms-medicaid-chip-monthly-enrollment-december-2024"
    assert validate_source_cells(cells).valid
    assert validate_facts(facts).valid
    assert len(cells) == 2_288
    assert len(facts) == 260
    assert all(fact.source.raw_r2_uri for fact in facts)

    us_medicaid = (
        "cms_medicaid.month2024_12.state_enrollment.us."
        "total_medicaid_enrollment"
    )
    ca_medicaid = (
        "cms_medicaid.month2024_12.state_enrollment.ca."
        "total_medicaid_enrollment"
    )
    tx_medicaid_chip = (
        "cms_medicaid.month2024_12.state_enrollment.tx."
        "total_medicaid_chip_enrollment"
    )
    ny_adult = (
        "cms_medicaid.month2024_12.state_enrollment.ny."
        "total_adult_medicaid_enrollment"
    )
    fl_child = (
        "cms_medicaid.month2024_12.state_enrollment.fl."
        "medicaid_chip_child_enrollment"
    )

    assert records_by_id[us_medicaid].source_cell_addresses[:3] == (
        "W2",
        "W3",
        "W4",
    )
    assert "W52" in records_by_id[us_medicaid].source_cell_addresses
    assert "W1" in records_by_id[us_medicaid].source_cell_addresses
    assert "A2" in records_by_id[us_medicaid].source_cell_addresses
    assert "A52" in records_by_id[us_medicaid].source_cell_addresses
    assert records_by_id[ca_medicaid].source_cell_addresses == (
        "W6",
        "W1",
        "C6",
        "E6",
        "F6",
    )
    assert records_by_id[tx_medicaid_chip].source_cell_addresses == (
        "U45",
        "U1",
        "C45",
        "E45",
        "F45",
    )
    assert values_by_record[us_medicaid].value == 71_841_081
    assert values_by_record[us_medicaid].geography.id == "0100000US"
    assert values_by_record[us_medicaid].geography.level == "country"
    assert values_by_record[ca_medicaid].value == 12_254_163
    assert values_by_record[ca_medicaid].geography.id == "0400000US06"
    assert values_by_record[ca_medicaid].domain == "medicaid_chip_enrollment"
    assert values_by_record[ca_medicaid].entity.name == "person"
    assert values_by_record[ca_medicaid].source.source_file == (
        "pi-dataset-april-2026-release.csv"
    )
    assert values_by_record[tx_medicaid_chip].value == 4_214_876
    assert values_by_record[ny_adult].value == 4_183_435
    assert values_by_record[fl_child].value == 2_423_453
    assert not values_by_record[ca_medicaid].filters
    assert not values_by_record[ca_medicaid].constraints


def test_usda_snap_source_package_alias_validates_fixture_counts():
    report = validate_source_package("usda-snap-fy69-to-current", year=2023)

    assert report.valid
    assert report.counts == {
        "record_set_count": 24,
        "row_count": 162,
        "measure_count": 32,
        "source_record_count": 216,
        "source_region_count": 24,
    }


def test_soi_historic_table_2_source_package_alias_validates_fixture_counts():
    report = validate_source_package("soi-historic-table-2", year=2023)

    assert report.valid
    assert report.counts == {
        "record_set_count": 1,
        "row_count": 11,
        "measure_count": 55,
        "source_record_count": 605,
        "source_region_count": 1,
    }


def test_soi_historic_table_2_package_builds_2022_national_facts():
    package = load_source_package("soi-historic-table-2")
    rows = package.build_source_rows(2023)
    cells = package.build_source_cells(2023, source_rows=rows)
    facts = package.build_facts(2023, cells=cells, source_rows=rows)
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert package.package_id == "soi-historic-table-2"
    assert len(rows) == 594
    assert validate_source_rows(rows).valid
    assert rows[0].values["STATE"] == "US"
    assert rows[0].values["AGI_STUB"] == 0
    assert validate_source_cells(cells).valid
    assert validate_facts(facts).valid
    assert len(cells) == 1_956
    assert len(facts) == 605
    assert all(fact.source_row_keys for fact in facts)

    tax_filers = values_by_record[
        "irs_soi.ty2022.historic_table_2.us.all.tax_filer_individual_count"
    ]
    ptc_returns = values_by_record[
        "irs_soi.ty2022.historic_table_2.us.all.premium_tax_credit_returns"
    ]
    eitc_amount = values_by_record[
        "irs_soi.ty2022.historic_table_2.us.all.eitc_amount"
    ]
    real_estate_taxes = values_by_record[
        "irs_soi.ty2022.historic_table_2.us.all.real_estate_taxes_amount"
    ]
    qualified_dividends = values_by_record[
        "irs_soi.ty2022.historic_table_2.us.all.qualified_dividends_amount"
    ]
    schedule_c_returns = values_by_record[
        "irs_soi.ty2022.historic_table_2.us.all.schedule_c_income_returns"
    ]
    partnership_scorp = values_by_record[
        "irs_soi.ty2022.historic_table_2.us.all.partnership_scorp_income_amount"
    ]
    medical_dental = values_by_record[
        "irs_soi.ty2022.historic_table_2.us.all.medical_dental_expense_amount"
    ]
    qbi = values_by_record[
        "irs_soi.ty2022.historic_table_2.us.all.qbi_amount"
    ]
    rental = values_by_record[
        "irs_soi.ty2022.historic_table_2.us.all.rental_royalty_income_amount"
    ]
    ctc = values_by_record[
        "irs_soi.ty2022.historic_table_2.us.all.ctc_amount"
    ]
    actc = values_by_record[
        "irs_soi.ty2022.historic_table_2.us.all.actc_amount"
    ]
    agi_bracket_eitc_claims = values_by_record[
        "irs_soi.ty2022.historic_table_2.us.1_to_10k.eitc_claims"
    ]

    assert tax_filers.value == 293_617_150
    assert ptc_returns.value == 7_841_370
    assert eitc_amount.value == 59_204_588_000
    assert real_estate_taxes.value == 106_195_956_000
    assert qualified_dividends.value == 309_355_739_000
    assert schedule_c_returns.value == 30_354_680
    assert partnership_scorp.value == 1_033_254_282_000
    assert medical_dental.value == 80_235_875_000
    assert qbi.value == 31_307_205_000
    assert rental.value == 85_642_801_000
    assert ctc.value == 82_862_736_000
    assert actc.value == 33_857_987_000
    assert agi_bracket_eitc_claims.value == 5_013_220
    assert {constraint.operator for constraint in agi_bracket_eitc_claims.constraints} == {
        "<",
        ">=",
    }


def test_soi_historic_table_2_state_broad_package_builds_2022_state_facts():
    package = load_source_package("soi-historic-table-2-state-broad-2022")
    rows = package.build_source_rows(2023)
    cells = package.build_source_cells(2023, source_rows=rows)
    facts = package.build_facts(2023, cells=cells, source_rows=rows)
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert package.package_id == "soi-historic-table-2-state-broad-2022"
    assert len(rows) == 594
    assert validate_source_rows(rows).valid
    assert validate_source_cells(cells).valid
    assert validate_facts(facts).valid
    assert len(cells) == 8_476
    assert len(facts) == 2_703

    ca_returns = values_by_record[
        "irs_soi.ty2022.historic_table_2.state_broad.ca.all.return_count"
    ]
    ca_agi = values_by_record[
        "irs_soi.ty2022.historic_table_2.state_broad.ca.all.adjusted_gross_income"
    ]
    ca_ptc = values_by_record[
        "irs_soi.ty2022.historic_table_2.state_broad.ca.all.premium_tax_credit_amount"
    ]
    ca_partnership = values_by_record[
        "irs_soi.ty2022.historic_table_2.state_broad.ca.all.partnership_scorp_income_amount"
    ]
    ca_medical = values_by_record[
        "irs_soi.ty2022.historic_table_2.state_broad.ca.all.medical_dental_expense_amount"
    ]
    ca_qbi = values_by_record[
        "irs_soi.ty2022.historic_table_2.state_broad.ca.all.qbi_amount"
    ]
    ca_rental = values_by_record[
        "irs_soi.ty2022.historic_table_2.state_broad.ca.all.rental_royalty_income_amount"
    ]
    ca_ctc = values_by_record[
        "irs_soi.ty2022.historic_table_2.state_broad.ca.all.ctc_amount"
    ]
    ca_actc = values_by_record[
        "irs_soi.ty2022.historic_table_2.state_broad.ca.all.actc_amount"
    ]

    assert ca_returns.value == 18_487_690
    assert ca_agi.value == 1_987_000_701_000
    assert ca_ptc.value == 6_379_623_000
    assert ca_partnership.value == 125_930_370_000
    assert ca_medical.value == 11_456_144_000
    assert ca_qbi.value == 4_400_400_000
    assert ca_rental.value == 14_331_993_000
    assert ca_ctc.value == 9_724_583_000
    assert ca_actc.value == 3_605_628_000
    assert ca_returns.geography.id == "0400000US06"
    assert ca_partnership.layout.source_column_id == "A26270"


def test_soi_historic_table_2_state_eitc_package_builds_child_count_facts():
    package = load_source_package("soi-historic-table-2-state-eitc-2022")
    rows = package.build_source_rows(2023)
    cells = package.build_source_cells(2023, source_rows=rows)
    facts = package.build_facts(2023, cells=cells, source_rows=rows)
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert package.package_id == "soi-historic-table-2-state-eitc-2022"
    assert validate_source_rows(rows).valid
    assert validate_source_cells(cells).valid
    assert validate_facts(facts).valid
    assert len(facts) == 510

    ca_one_child_amount = values_by_record[
        "irs_soi.ty2022.historic_table_2.state_eitc.ca.ca."
        "eitc_one_child_amount"
    ]
    ca_two_children_claims = values_by_record[
        "irs_soi.ty2022.historic_table_2.state_eitc.ca.ca."
        "eitc_two_children_claims"
    ]
    ca_three_or_more_amount = values_by_record[
        "irs_soi.ty2022.historic_table_2.state_eitc.ca.ca."
        "eitc_three_or_more_children_amount"
    ]

    assert ca_one_child_amount.value == 2_117_692_000
    assert ca_two_children_claims.value == 550_910
    assert ca_three_or_more_amount.value == 1_266_651_000
    assert ca_one_child_amount.filters["eitc_child_count"] == 1
    assert {
        constraint.variable for constraint in ca_one_child_amount.constraints
    } == {"us.tax.earned_income_credit_qualifying_children"}
    assert {
        constraint.operator for constraint in ca_three_or_more_amount.constraints
    } == {">="}
    assert ca_one_child_amount.geography.id == "0400000US06"


def test_usda_snap_source_package_builds_fy24_national_and_state_facts():
    package = load_source_package("usda-snap-fy69-to-current")
    cells = package.build_source_cells(2023)
    records = package.build_source_records(2023, cells=cells)
    facts = package.build_facts(2023, cells=cells)
    records_by_id = {record.source_record_id: record for record in records}
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert package.package_id == "usda-snap-fy69-to-current"
    assert validate_source_cells(cells).valid
    assert validate_facts(facts).valid
    assert len(cells) == 6_288
    assert len(facts) == 216
    assert all(fact.source.raw_r2_uri for fact in facts)

    households = (
        "usda_snap.fy2024.national_average_monthly_households."
        "national_total.average_monthly_households"
    )
    persons = (
        "usda_snap.fy2024.national_average_monthly_persons."
        "national_total.average_monthly_persons"
    )
    per_person = (
        "usda_snap.fy2024.national_average_monthly_persons."
        "national_total.average_monthly_benefit_per_person"
    )
    benefits = "usda_snap.fy2024.national_benefits.national_total.total_benefits"
    ca_households = (
        "usda_snap.fy2024.state_average_monthly_households."
        "wro.ca.average_monthly_households"
    )
    tx_persons = (
        "usda_snap.fy2024.state_average_monthly_persons.swro.tx.average_monthly_persons"
    )
    fl_benefits = "usda_snap.fy2024.state_benefits.sero.fl.total_benefits"

    assert records_by_id[households].source_cell_addresses == (
        "B21",
        "B7",
        "A2",
        "A8",
    )
    assert records_by_id[benefits].source_cell_addresses == (
        "D21",
        "D6",
        "A2",
        "A8",
    )
    assert records_by_id[ca_households].source_cell_addresses == (
        "B51",
        "B7",
        "A2",
        "A38",
    )
    assert records_by_id[tx_persons].source_cell_addresses == (
        "C96",
        "C7",
        "A2",
        "A83",
    )

    assert values_by_record[households].value == pytest.approx(22_200_091.5833)
    assert values_by_record[persons].value == pytest.approx(41_690_237.75)
    assert values_by_record[per_person].value == pytest.approx(187.5886)
    assert values_by_record[benefits].value == 93_847_365_890
    assert values_by_record[ca_households].value == pytest.approx(3_128_639.6667)
    assert values_by_record[tx_persons].value == pytest.approx(3_193_008.5833)
    assert values_by_record[fl_benefits].value == 6_604_797_454
    assert values_by_record[ca_households].geography.id == "0400000US06"
    assert values_by_record[tx_persons].geography.id == "0400000US48"
    assert values_by_record[fl_benefits].geography.id == "0400000US12"
    assert values_by_record[benefits].source.source_file == (
        "snap-zip-fy69tocurrent-6.zip!FY24.xlsx"
    )
    assert not values_by_record[benefits].constraints


def test_hhs_acf_tanf_source_package_aliases_validate_fixture_counts():
    expected_counts = {
        "hhs-acf-tanf-financial-2024": {
            "record_set_count": 52,
            "row_count": 52,
            "measure_count": 52,
            "source_record_count": 52,
            "source_region_count": 52,
        },
        "hhs-acf-tanf-caseload-2024": {
            "record_set_count": 3,
            "row_count": 53,
            "measure_count": 8,
            "source_record_count": 58,
            "source_region_count": 3,
        },
    }

    for package_id, counts in expected_counts.items():
        report = validate_source_package(package_id, year=2023)

        assert report.valid, package_id
        assert report.counts == counts


def test_hhs_acf_tanf_financial_package_builds_fy24_cash_assistance_facts():
    package = load_source_package("hhs-acf-tanf-financial-2024")
    cells = package.build_source_cells(2023)
    facts = package.build_facts(2023, cells=cells)
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert package.package_id == "hhs-acf-tanf-financial-2024"
    assert validate_source_cells(cells).valid
    assert validate_facts(facts).valid
    assert len(cells) == 41_390
    assert len(facts) == 52
    assert all(fact.source.raw_r2_uri for fact in facts)

    national_fact = values_by_record[
        "hhs_acf_tanf.fy2024.cash_assistance.us."
        "basic_assistance_excluding_relative_foster_care_and_adoption_guardianship."
        "all_funds"
    ]
    ca_fact = values_by_record[
        "hhs_acf_tanf.fy2024.cash_assistance.ca."
        "basic_assistance_excluding_relative_foster_care_and_adoption_guardianship."
        "all_funds"
    ]

    assert national_fact.value == pytest.approx(7_788_317_474.55)
    assert ca_fact.value == pytest.approx(3_742_540_224.36)
    assert ca_fact.geography.id == "0400000US06"
    assert not ca_fact.filters
    assert not ca_fact.constraints


def test_hhs_acf_tanf_caseload_package_builds_fy24_family_and_recipient_facts():
    package = load_source_package("hhs-acf-tanf-caseload-2024")
    cells = package.build_source_cells(2023)
    records = package.build_source_records(2023, cells=cells)
    facts = package.build_facts(2023, cells=cells)
    records_by_id = {record.source_record_id: record for record in records}
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert package.package_id == "hhs-acf-tanf-caseload-2024"
    assert validate_source_cells(cells).valid
    assert validate_facts(facts).valid
    assert len(cells) == 91_748
    assert len(facts) == 58
    assert all(fact.source.raw_r2_uri for fact in facts)

    total_families = (
        "hhs_acf_tanf.fy2024.average_monthly_families.us.us_total.total_families"
    )
    child_recipients = (
        "hhs_acf_tanf.fy2024.average_monthly_recipients.us.us_total.child_recipients"
    )
    ca_total_families = (
        "hhs_acf_tanf.fy2024.average_monthly_families.state.ca.total_families"
    )

    assert records_by_id[total_families].source_cell_addresses == (
        "D6",
        "D5",
        "C6",
        "C3",
    )
    assert records_by_id[ca_total_families].source_cell_addresses == (
        "D11",
        "D5",
    )
    assert values_by_record[total_families].value == pytest.approx(841_208.6666666666)
    assert values_by_record[ca_total_families].value == pytest.approx(290_247.75)
    assert values_by_record[ca_total_families].geography.id == "0400000US06"
    assert values_by_record[ca_total_families].geography.level == "state"
    assert values_by_record[child_recipients].value == pytest.approx(1_500_843.75)
    assert values_by_record[child_recipients].entity.name == "person"
    assert values_by_record[child_recipients].geography.id == "0100000US"
    assert not values_by_record[child_recipients].filters
    assert not values_by_record[child_recipients].constraints


def test_kff_marketplace_effectuated_enrollment_alias_validates_fixture_counts():
    report = validate_source_package(
        "kff-marketplace-effectuated-enrollment",
        year=2023,
    )

    assert report.valid
    assert report.counts == {
        "record_set_count": 1,
        "row_count": 52,
        "measure_count": 1,
        "source_record_count": 52,
        "source_region_count": 1,
    }


def test_kff_marketplace_effectuated_enrollment_builds_2024_state_facts():
    package = load_source_package("kff-marketplace-effectuated-enrollment")
    rows = package.build_source_rows(2023)
    cells = package.build_source_cells(2023, source_rows=rows)
    records = package.build_source_records(2023, cells=cells, source_rows=rows)
    facts = package.build_facts(2023, cells=cells, source_rows=rows)
    records_by_id = {record.source_record_id: record for record in records}
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert package.package_id == "kff-marketplace-effectuated-enrollment"
    assert len(rows) == 416
    assert validate_source_rows(rows).valid
    assert rows[0].values == {
        "Year": 2024,
        "Geography": "United States",
        "Total Effectuated Marketplace Enrollment": 20_968_847,
        "Unit": "Number",
        "KFF table row": 3,
    }
    assert validate_source_cells(cells).valid
    assert validate_facts(facts).valid
    assert len(cells) == 260
    assert len(facts) == 52
    assert all(fact.source_row_keys for fact in facts)
    assert all(fact.source.source_name == "kff" for fact in facts)
    assert all(fact.source.source_file.endswith(".html") for fact in facts)
    assert all(fact.source.raw_r2_uri for fact in facts)

    us = (
        "kff.marketplace_effectuated_enrollment.2024.state.us."
        "total_effectuated_marketplace_enrollment"
    )
    al = (
        "kff.marketplace_effectuated_enrollment.2024.state.al."
        "total_effectuated_marketplace_enrollment"
    )
    ca = (
        "kff.marketplace_effectuated_enrollment.2024.state.ca."
        "total_effectuated_marketplace_enrollment"
    )

    assert records_by_id[us].source_cell_addresses[:3] == ("C2", "C3", "C4")
    assert "C52" in records_by_id[us].source_cell_addresses
    assert "C1" in records_by_id[us].source_cell_addresses
    assert "B2" in records_by_id[us].source_cell_addresses
    assert "B52" in records_by_id[us].source_cell_addresses
    assert records_by_id[al].source_cell_addresses == ("C2", "C1")
    assert values_by_record[us].value == 20_968_847
    assert values_by_record[us].geography.id == "0100000US"
    assert values_by_record[us].geography.level == "country"
    assert values_by_record[al].value == 396_750
    assert values_by_record[ca].value == 1_795_695
