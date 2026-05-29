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

from arch.consumer_contract import (
    consumer_fact_rows,
    validate_consumer_fact_contract,
)
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


def test_bea_nipa_total_wages_package_preserves_bea_concept():
    package = load_source_package("bea-nipa-total-wages-salaries")
    rows = package.build_source_rows(2024)
    cells = package.build_source_cells(2024, source_rows=rows)
    records = package.build_source_records(2024, cells=cells, source_rows=rows)
    facts = package.build_facts(2024, cells=cells, source_rows=rows)
    records_by_id = {record.source_record_id: record for record in records}
    facts_by_record = {fact.source_record_id: fact for fact in facts}

    assert len(rows) == 559_069
    assert validate_source_rows(rows).valid
    assert validate_source_cells(cells).valid
    assert validate_facts(facts).valid
    assert len(cells) == 12
    assert len(facts) == 3
    assert all(fact.source_row_keys for fact in facts)
    assert all(fact.source.source_name == "bea" for fact in facts)
    assert all(fact.source.raw_r2_uri for fact in facts)

    value_2018 = "bea_nipa.cy2018.total_wages_salaries.a034rc.wages_salaries_amount"
    value_2024 = "bea_nipa.cy2024.total_wages_salaries.a034rc.wages_salaries_amount"
    assert records_by_id[value_2018].source_cell_addresses == ("C2", "C1", "B2")
    assert records_by_id[value_2024].source_cell_addresses == ("C4", "C1", "B4")
    assert facts_by_record[value_2018].value == 8_899_824_000_000
    assert facts_by_record[value_2024].value == 12_387_929_000_000
    assert facts_by_record[value_2024].measure.concept == (
        "bea_nipa.wages_and_salaries"
    )
    assert facts_by_record[value_2024].measure.source_concept == (
        "bea_nipa.a034rc_wages_and_salaries"
    )


def test_bea_nipa_personal_income_components_keep_broad_concepts_namespaced():
    package = load_source_package("bea-nipa-personal-income-components")
    facts = package.build_facts(2024)
    facts_by_record = {fact.source_record_id: fact for fact in facts}

    assert len(facts) == 18
    assert validate_facts(facts).valid
    proprietors = facts_by_record["bea_nipa.cy2024.proprietors_income.a041rc.amount"]
    interest = facts_by_record["bea_nipa.cy2024.personal_interest_income.a064rc.amount"]
    dividends = facts_by_record[
        "bea_nipa.cy2024.personal_dividend_income.b703rc.amount"
    ]

    assert proprietors.value == 2_023_080_000_000
    assert proprietors.measure.concept == (
        "bea_nipa.proprietors_income_with_inventory_valuation_and_capital_"
        "consumption_adjustments"
    )
    assert proprietors.measure.concept != "self_employment_income"
    assert interest.value == 1_926_644_000_000
    assert interest.measure.concept == "bea_nipa.personal_interest_income"
    assert dividends.value == 2_218_700_000_000
    assert dividends.measure.concept == "bea_nipa.personal_dividend_income"


def test_bea_nipa_personal_income_disposition_builds_amounts_and_rates():
    package = load_source_package("bea-nipa-personal-income-disposition")
    facts = package.build_facts(2024)
    facts_by_record = {fact.source_record_id: fact for fact in facts}

    assert len(facts) == 6
    assert validate_facts(facts).valid
    assert (
        facts_by_record["bea_nipa.cy2024.personal_income.a065rc.amount"].value
        == 24_905_900_000_000
    )
    assert (
        facts_by_record["bea_nipa.cy2024.personal_current_taxes.w055rc.amount"].value
        == 2_988_243_000_000
    )
    saving_rate = facts_by_record["bea_nipa.cy2024.personal_saving_rate.a072rc.rate"]
    assert saving_rate.value == 5.4
    assert saving_rate.measure.unit == "percent"


def test_bea_regional_state_personal_income_components_build_2024_facts():
    package = load_source_package("bea-regional-state-personal-income-components-2024")
    facts = package.build_facts(2024)
    facts_by_record = {fact.source_record_id: fact for fact in facts}

    assert len(facts) == 416
    assert validate_facts(facts).valid
    california_wages = facts_by_record[
        "bea_regional.cy2024.state_wages_salaries.ca.amount"
    ]
    assert california_wages.value == 1_769_665_607_000
    assert california_wages.geography.id == "0400000US06"
    assert california_wages.measure.concept == "bea_regional.wages_and_salaries"
    assert {
        (constraint.variable, constraint.operator, constraint.value)
        for constraint in california_wages.constraints
    } == {
        ("bea_regional.table_name", "==", "SAINC5N"),
        ("bea_regional.geo_name", "==", "California"),
        ("bea_regional.line_code", "==", 50),
    }
    assert california_wages.source.source_file == "SAINC.zip"
    assert california_wages.source.raw_r2_uri
    assert (
        facts_by_record[
            "bea_regional.cy2024.state_personal_current_transfer_receipts.us.amount"
        ].value
        == 4_555_385_000_000
    )
    assert (
        facts_by_record["bea_regional.cy2024.state_proprietors_income.tx.amount"].value
        == 273_877_560_000
    )
    california_contributions = facts_by_record[
        "bea_regional.cy2024.state_contributions_for_government_social_insurance.ca.amount"
    ]
    assert california_contributions.value == 257_766_765_000
    assert (
        california_contributions.measure.concept
        == "bea_regional.contributions_for_government_social_insurance"
    )
    assert {
        (constraint.variable, constraint.operator, constraint.value)
        for constraint in california_contributions.constraints
    } == {
        ("bea_regional.table_name", "==", "SAINC5N"),
        ("bea_regional.geo_name", "==", "California"),
        ("bea_regional.line_code", "==", 36),
    }
    california_residence_adjustment = facts_by_record[
        "bea_regional.cy2024.state_residence_adjustment.ca.amount"
    ]
    assert california_residence_adjustment.value == -2_475_104_000
    assert (
        california_residence_adjustment.measure.concept
        == "bea_regional.residence_adjustment"
    )
    assert {
        (constraint.variable, constraint.operator, constraint.value)
        for constraint in california_residence_adjustment.constraints
    } == {
        ("bea_regional.table_name", "==", "SAINC5N"),
        ("bea_regional.geo_name", "==", "California"),
        ("bea_regional.line_code", "==", 42),
    }
    assert validate_consumer_fact_contract(facts).valid


def test_bea_regional_state_personal_income_components_validate_counts():
    report = validate_source_package(
        "bea-regional-state-personal-income-components-2024",
        year=2024,
    )

    assert report.valid
    assert report.counts == {
        "measure_count": 8,
        "record_set_count": 8,
        "row_count": 416,
        "source_record_count": 416,
        "source_region_count": 8,
    }


def test_cbo_income_by_source_package_preserves_cbo_projection_concepts():
    package = load_source_package("cbo-revenue-projections-income-by-source-2026-02")
    rows = package.build_source_rows(2024)
    cells = package.build_source_cells(2024, source_rows=rows)
    records = package.build_source_records(2024, cells=cells, source_rows=rows)
    facts = package.build_facts(2024, cells=cells, source_rows=rows)
    facts_by_income_source = {fact.layout.groupby_value_id: fact for fact in facts}
    expected_sha = "8cd8edee3e76258aa67153adff9dc0dc9b9738ace426eceebcc8d5b26d319bb8"
    expected_r2_uri = (
        "r2://arch-raw/raw/cbo/"
        "cbo-revenue-projections-income-by-source-2026-02/2026/"
        f"{expected_sha}/cbo_revenue_projections_income_by_source_2026_02.csv"
    )

    assert len(rows) == 6
    assert validate_source_rows(rows).valid
    assert validate_source_cells(cells).valid
    assert validate_facts(facts).valid
    assert validate_consumer_fact_contract(facts).valid
    assert len(cells) == 126
    assert len(records) == 6
    assert len(facts) == 6
    assert all(fact.source.source_name == "cbo" for fact in facts)
    assert {fact.source.source_sha256 for fact in facts} == {expected_sha}
    assert {fact.source.source_size_bytes for fact in facts} == {2502}
    assert {fact.source.raw_r2_uri for fact in facts} == {expected_r2_uri}
    assert all(not fact.constraints for fact in facts)
    assert all(fact.layout.table_record_kind == "total" for fact in facts)

    wages = facts_by_income_source["wages_and_salaries"]
    capital_gains = facts_by_income_source["net_capital_gain"]
    qualified_dividends = facts_by_income_source["qualified_dividend_income"]
    net_business = facts_by_income_source["net_business_income"]

    assert wages.value == 10_832_700_000_000
    assert wages.measure.concept == "cbo.wages_and_salaries_projection"
    assert capital_gains.value == 1_290_900_000_000
    assert capital_gains.measure.concept == "cbo.net_capital_gain_projection"
    assert qualified_dividends.value == 354_300_000_000
    assert qualified_dividends.measure.concept == (
        "cbo.qualified_dividend_income_projection"
    )
    assert net_business.value == 1_916_000_000_000
    assert net_business.measure.concept == "cbo.net_business_income_projection"
    assert net_business.measure.concept != "self_employment_income"
    assert net_business.measure.source_concept == "cbo.net_business_income"

    consumer_rows_by_source_concept = {
        row["concept_alignment"]["source_concept"]: row
        for row in consumer_fact_rows(facts)
    }
    assert consumer_rows_by_source_concept["cbo.net_capital_gain"][
        "concept_alignment"
    ]["canonical_concept"] == "cbo.net_capital_gain_projection"
    assert consumer_rows_by_source_concept["cbo.net_business_income"][
        "concept_alignment"
    ]["canonical_concept"] == "cbo.net_business_income_projection"


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


def test_source_package_alias_builds_cms_aca_oep_state_level_facts():
    package = load_source_package("cms-aca-oep-state-level")
    rows = package.build_source_rows(2024)
    cells = package.build_source_cells(2024, source_rows=rows)
    records = package.build_source_records(2024, cells=cells, source_rows=rows)
    facts = package.build_facts(2024, cells=cells, source_rows=rows)
    records_by_id = {record.source_record_id: record for record in records}
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert package.package_id == "cms-aca-oep-state-level"
    assert len(rows) == 54
    assert validate_source_rows(rows).valid
    assert rows[0].values["State_Abrvtn"] == "AK"
    assert rows[0].values["APTC_Cnsmr_Avg_APTC"] == 865
    assert validate_source_cells(cells).valid
    assert len(cells) == 5_610
    assert len(facts) == 153
    assert validate_facts(facts).valid
    assert all(fact.source_row_keys for fact in facts)
    assert all(fact.source.source_name == "cms_aca" for fact in facts)
    assert all(fact.source.source_file.endswith(".zip") for fact in facts)
    assert all(fact.source.raw_r2_uri for fact in facts)
    assert records_by_id[
        "cms_aca.oep2024.state_marketplace.ca.marketplace_enrollment"
    ].source_cell_addresses == ("H6", "H1")
    assert (
        values_by_record[
            "cms_aca.oep2024.state_marketplace.ca.marketplace_enrollment"
        ].value
        == 1_784_653
    )
    assert (
        values_by_record["cms_aca.oep2024.state_marketplace.ca.aptc_recipients"].value
        == 1_554_271
    )
    ca_avg_aptc = values_by_record[
        "cms_aca.oep2024.state_marketplace.ca.average_monthly_aptc"
    ]
    assert ca_avg_aptc.value == 526
    assert ca_avg_aptc.geography.id == "0400000US06"
    assert ca_avg_aptc.geography.level == "state"
    assert not ca_avg_aptc.constraints


def test_source_package_alias_builds_cms_aca_oep_state_level_2022_facts():
    package = load_source_package("cms-aca-oep-state-level-2022")
    rows = package.build_source_rows(2022)
    cells = package.build_source_cells(2022, source_rows=rows)
    records = package.build_source_records(2022, cells=cells, source_rows=rows)
    facts = package.build_facts(2022, cells=cells, source_rows=rows)
    records_by_id = {record.source_record_id: record for record in records}
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert package.package_id == "cms-aca-oep-state-level-2022"
    assert len(rows) == 54
    assert validate_source_rows(rows).valid
    assert rows[0].values["State_Abrvtn"] == "AK"
    assert rows[0].values["APTC_Cnsmr_Avg_APTC"] == 692
    assert validate_source_cells(cells).valid
    assert len(cells) == 5_555
    assert len(facts) == 151
    assert validate_facts(facts).valid
    assert all(fact.source_row_keys for fact in facts)
    assert all(fact.source.source_name == "cms_aca" for fact in facts)
    assert all(fact.source.source_file.endswith(".zip") for fact in facts)
    assert all(fact.source.raw_r2_uri for fact in facts)
    assert records_by_id[
        "cms_aca.oep2022.state_marketplace.ca.average_monthly_aptc"
    ].source_cell_addresses == ("AJ6", "AJ1")
    assert (
        values_by_record[
            "cms_aca.oep2022.state_marketplace.ca.average_monthly_aptc"
        ].value
        == 459
    )
    assert (
        values_by_record[
            "cms_aca.oep2022.state_marketplace.al.average_monthly_aptc"
        ].value
        == 710
    )
    assert (
        "cms_aca.oep2022.state_marketplace.nv.average_monthly_aptc"
        not in values_by_record
    )


def test_source_package_alias_builds_cms_aca_oep_state_level_2025_facts():
    package = load_source_package("cms-aca-oep-state-level-2025")
    rows = package.build_source_rows(2025)
    cells = package.build_source_cells(2025, source_rows=rows)
    records = package.build_source_records(2025, cells=cells, source_rows=rows)
    facts = package.build_facts(2025, cells=cells, source_rows=rows)
    records_by_id = {record.source_record_id: record for record in records}
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert package.package_id == "cms-aca-oep-state-level-2025"
    assert len(rows) == 54
    assert validate_source_rows(rows).valid
    assert rows[0].values["State_Abrvtn"] == "AK"
    assert rows[0].values["APTC_Cnsmr_Avg_APTC"] == 1_008
    assert validate_source_cells(cells).valid
    assert len(cells) == 5_610
    assert len(facts) == 153
    assert validate_facts(facts).valid
    assert all(fact.source_row_keys for fact in facts)
    assert all(fact.source.source_name == "cms_aca" for fact in facts)
    assert all(fact.source.source_file.endswith(".zip") for fact in facts)
    assert all(fact.source.raw_r2_uri for fact in facts)
    assert records_by_id[
        "cms_aca.oep2025.state_marketplace.ca.average_monthly_aptc"
    ].source_cell_addresses == ("AK6", "AK1")
    assert (
        values_by_record[
            "cms_aca.oep2025.state_marketplace.ca.marketplace_enrollment"
        ].value
        == 1_979_504
    )
    ca_average_aptc = values_by_record[
        "cms_aca.oep2025.state_marketplace.ca.average_monthly_aptc"
    ]
    assert ca_average_aptc.value == 562
    assert ca_average_aptc.geography.id == "0400000US06"
    assert ca_average_aptc.geography.level == "state"
    assert not ca_average_aptc.constraints


def test_source_package_alias_builds_cms_aca_effectuated_enrollment_2022_facts():
    package = load_source_package("cms-aca-effectuated-enrollment-2022")
    rows = package.build_source_rows(2022)
    cells = package.build_source_cells(2022, source_rows=rows)
    records = package.build_source_records(2022, cells=cells, source_rows=rows)
    facts = package.build_facts(2022, cells=cells, source_rows=rows)
    records_by_id = {record.source_record_id: record for record in records}
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert package.package_id == "cms-aca-effectuated-enrollment-2022"
    assert rows == []
    assert validate_source_cells(cells).valid
    assert len(cells) == 15_397
    assert len(records) == 408
    assert len(facts) == 408
    assert validate_facts(facts).valid
    assert all(fact.source.source_name == "cms_aca" for fact in facts)
    assert all(fact.source.source_file.endswith(".xlsx") for fact in facts)
    assert all(fact.source.raw_r2_uri for fact in facts)
    assert records_by_id[
        "cms_aca.effectuated_enrollment.2022.state_marketplace.nv.average_monthly_aptc"
    ].source_cell_addresses == ("I39", "I2")
    nv_avg_aptc = values_by_record[
        "cms_aca.effectuated_enrollment.2022.state_marketplace.nv.average_monthly_aptc"
    ]
    assert nv_avg_aptc.value == 429.75
    assert nv_avg_aptc.geography.id == "0400000US32"
    assert not nv_avg_aptc.filters
    assert (
        values_by_record[
            "cms_aca.effectuated_enrollment.2022.state_marketplace.nv.total_enrollment"
        ].value
        == 90_397
    )
    assert (
        values_by_record[
            "cms_aca.effectuated_enrollment.2022.state_marketplace.nv.total_enrollment"
        ].measure.concept
        == "cms_aca.marketplace_effectuated_enrollment"
    )
    assert (
        values_by_record[
            "cms_aca.effectuated_enrollment.2022.state_marketplace.ca."
            "average_monthly_aptc"
        ].value
        == 469.44
    )


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


@pytest.mark.parametrize(
    ("source", "year", "cell_count", "households", "addresses", "source_file"),
    [
        (
            "hhs-acf-liheap-fy2023-national-profile",
            2023,
            360,
            5_939_605,
            ("E5", "E1", "A5", "B5", "D5", "F5"),
            "acf_liheap_fy2023_all_states_national_profile.pdf",
        ),
        (
            "hhs-acf-liheap-fy2024-national-profile",
            2024,
            348,
            5_876_646,
            ("E3", "E1", "A3", "B3", "D3", "F3"),
            "acf_liheap_fy2024_all_states_national_profile.pdf",
        ),
    ],
)
def test_hhs_acf_liheap_package_builds_household_count_fact(
    source,
    year,
    cell_count,
    households,
    addresses,
    source_file,
):
    package = load_source_package(source)
    cells = package.build_source_cells(year)
    records = package.build_source_records(year, cells=cells)
    facts = package.build_facts(year, cells=cells)
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert package.package_id == source
    assert validate_source_cells(cells).valid
    assert validate_facts(facts).valid
    assert len(cells) == cell_count
    assert len(facts) == 1
    assert all(fact.source.raw_r2_uri for fact in facts)

    record_id = (
        f"hhs_acf_liheap.fy{year}.national_profile."
        "state_programs.households_served"
    )
    assert records[0].source_cell_addresses == addresses
    assert values_by_record[record_id].value == households
    assert values_by_record[record_id].measure.concept == (
        "hhs_acf_liheap.households_served_by_state_programs"
    )
    assert values_by_record[record_id].period.value == year
    assert values_by_record[record_id].geography.id == "0100000US"
    assert values_by_record[record_id].entity.name == "household"
    assert values_by_record[record_id].source.source_file == source_file
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


def test_ssa_ssi_table_7b1_source_package_alias_validates_fixture_counts():
    report = validate_source_package("ssa-ssi-table-7b1-2024", year=2024)

    assert report.valid
    assert report.counts == {
        "record_set_count": 2,
        "row_count": 416,
        "measure_count": 2,
        "source_record_count": 416,
        "source_region_count": 2,
    }


def test_ssa_ssi_table_7b1_source_package_builds_area_category_facts():
    package = load_source_package("ssa-ssi-table-7b1-2024")
    cells = package.build_source_cells(2024)
    facts = package.build_facts(2024, cells=cells)
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert package.package_id == "ssa-ssi-table-7b1-2024"
    assert validate_source_cells(cells).valid
    assert validate_facts(facts).valid
    assert len(cells) == 1_672
    assert len(facts) == 416
    assert all(fact.source.raw_r2_uri for fact in facts)

    us_payments = values_by_record[
        "ssa_supplement.cy2024.ssi_payments.by_area_category."
        "all_areas_total.payment_amount"
    ]
    ca_disabled_recipients = values_by_record[
        "ssa_supplement.cy2024.ssi_recipients.by_area_category."
        "california_disabled.recipient_count"
    ]
    ca_disabled_payments = values_by_record[
        "ssa_supplement.cy2024.ssi_payments.by_area_category."
        "california_disabled.payment_amount"
    ]

    assert us_payments.value == 63_079_493_000
    assert us_payments.measure.concept == "ssa.ssi_payment_amount"
    assert us_payments.constraints == ()

    assert ca_disabled_recipients.value == 849_834
    assert ca_disabled_recipients.geography.id == "0400000US06"
    assert ca_disabled_recipients.measure.concept == "ssa.ssi_recipient_count"
    assert {
        (constraint.variable, constraint.operator, constraint.value)
        for constraint in ca_disabled_recipients.constraints
    } == {("ssi_category", "==", "disabled")}

    assert ca_disabled_payments.value == 9_834_761_000
    assert ca_disabled_payments.geography.id == "0400000US06"


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


def test_census_population_projections_source_package_alias_validates_counts():
    report = validate_source_package("census-population-projections-2023", year=2025)

    assert report.valid
    assert report.counts == {
        "record_set_count": 86,
        "row_count": 86,
        "measure_count": 86,
        "source_record_count": 86,
        "source_region_count": 86,
    }


def test_source_package_alias_builds_census_population_projection_age_facts():
    package = load_source_package("census-population-projections-2023")
    rows = package.build_source_rows(2025)
    cells = package.build_source_cells(2025, source_rows=rows)
    records = package.build_source_records(2025, cells=cells, source_rows=rows)
    facts = package.build_facts(2025, cells=cells, source_rows=rows)
    records_by_id = {record.source_record_id: record for record in records}
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert package.package_id == "census-population-projections-2023"
    assert len(rows) == 2_580
    assert validate_source_rows(rows).valid
    assert validate_source_cells(cells).valid
    assert len(cells) == 273
    assert len(facts) == 86
    assert validate_facts(facts).valid
    assert all(fact.source_row_keys for fact in facts)
    assert all(
        fact.source.source_name == "census_population_projections" for fact in facts
    )
    assert all(fact.source.source_file == "np2023_d5_mid.csv" for fact in facts)
    assert all(fact.source.raw_r2_uri for fact in facts)
    assert all(fact.geography.id == "0100000US" for fact in facts)
    assert {f"{fact.period.type}:{fact.period.value}" for fact in facts} == {
        "calendar_year:2025"
    }

    age_0 = "census.popproj2023.cy2025.national_population.age_0.population"
    age_85_plus = (
        "census.popproj2023.cy2025.national_population.age_85_plus.population"
    )
    assert records_by_id[age_0].source_cell_addresses == (
        "F2",
        "F3",
        "F1",
        "A2",
        "A3",
        "B2",
        "B3",
        "C2",
        "C3",
        "D2",
        "D3",
    )
    assert records_by_id[age_85_plus].source_cell_addresses == (
        "CM2",
        "CM3",
        "CM1",
        "A2",
        "A3",
        "B2",
        "B3",
        "C2",
        "C3",
        "D2",
        "D3",
    )
    assert values_by_record[age_0].value == 3_641_659
    assert values_by_record[age_85_plus].value == 7_047_043
    assert {
        (constraint.variable, constraint.operator, constraint.value)
        for constraint in values_by_record[age_0].constraints
    } == {("age", ">=", 0), ("age", "<", 1)}
    assert {
        (constraint.variable, constraint.operator, constraint.value)
        for constraint in values_by_record[age_85_plus].constraints
    } == {("age", ">=", 85)}


def test_census_acs_s0101_source_package_aliases_validate_fixture_counts():
    expected_counts = {
        "census-acs-s0101-national-age-2024": {
            "record_set_count": 1,
            "row_count": 18,
            "measure_count": 1,
            "source_record_count": 18,
            "source_region_count": 1,
        },
        "census-acs-s0101-state-age-2024": {
            "record_set_count": 52,
            "row_count": 936,
            "measure_count": 52,
            "source_record_count": 936,
            "source_region_count": 52,
        },
        "census-acs-s0101-congressional-district-age-2024": {
            "record_set_count": 437,
            "row_count": 7_866,
            "measure_count": 437,
            "source_record_count": 7_866,
            "source_region_count": 437,
        },
    }

    for package_id, counts in expected_counts.items():
        report = validate_source_package(package_id, year=2024)

        assert report.valid
        assert report.counts == counts


def test_census_acs_s0101_congressional_district_package_builds_age_facts():
    package = load_source_package(
        "census-acs-s0101-congressional-district-age-2024"
    )
    rows = package.build_source_rows(2024)
    cells = package.build_source_cells(2024, source_rows=rows)
    facts = package.build_facts(2024, cells=cells, source_rows=rows)
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert validate_source_rows(rows).valid
    assert validate_source_cells(cells).valid
    assert validate_facts(facts).valid
    assert len(facts) == 7_866

    al01_under_5 = values_by_record[
        "census_acs.acs1_2024.s0101.congressional_district_age.0101."
        "age_0_to_4.population"
    ]
    ca52_age_85_plus = values_by_record[
        "census_acs.acs1_2024.s0101.congressional_district_age.0652."
        "age_85_plus.population"
    ]

    assert al01_under_5.value == 39_908
    assert al01_under_5.geography.id == "5001900US0101"
    assert al01_under_5.source.source_file == "acs_S0101_district_2024.json"
    assert {
        (constraint.variable, constraint.operator, constraint.value)
        for constraint in al01_under_5.constraints
    } == {("age", ">=", 0), ("age", "<", 5)}
    assert ca52_age_85_plus.value == 14_396
    assert ca52_age_85_plus.geography.name == (
        "Congressional District 52 (119th Congress), California"
    )


def test_census_b01001_female_age_source_package_builds_state_facts():
    package = load_source_package("census-b01001-female-age-2023")
    rows = package.build_source_rows(2023)
    cells = package.build_source_cells(2023, source_rows=rows)
    facts = package.build_facts(2023, cells=cells, source_rows=rows)
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert package.package_id == "census-b01001-female-age-2023"
    assert len(rows) == 468
    assert validate_source_rows(rows).valid
    assert validate_source_cells(cells).valid
    assert validate_facts(facts).valid
    assert len(cells) == 3_752
    assert len(facts) == 468
    assert {fact.geography.level for fact in facts} == {"state"}
    assert all(fact.source_row_keys for fact in facts)
    assert all(fact.source.raw_r2_uri for fact in facts)

    al_age_15_to_17 = values_by_record[
        "census_acs.acs1_2023.b01001.female_age.01."
        "age_15_to_17.female_population"
    ]
    ca_age_40_to_44 = values_by_record[
        "census_acs.acs1_2023.b01001.female_age.06."
        "age_40_to_44.female_population"
    ]
    pr_age_40_to_44 = values_by_record[
        "census_acs.acs1_2023.b01001.female_age.72."
        "age_40_to_44.female_population"
    ]

    assert al_age_15_to_17.value == 100_354
    assert al_age_15_to_17.filters == {"sex": "female"}
    assert al_age_15_to_17.geography.id == "0400000US01"
    assert al_age_15_to_17.source.source_file == (
        "census_b01001_female_15_44_2023.json"
    )
    assert {
        (constraint.variable, constraint.operator, constraint.value)
        for constraint in al_age_15_to_17.constraints
    } == {
        ("age", ">=", 15),
        ("age", "<", 18),
        ("sex", "==", "female"),
    }
    assert ca_age_40_to_44.value == 1_300_307
    assert ca_age_40_to_44.geography.name == "California"
    assert pr_age_40_to_44.value == 110_768
    assert pr_age_40_to_44.geography.id == "0400000US72"


def test_census_acs_s2201_source_package_alias_validates_fixture_counts():
    report = validate_source_package(
        "census-acs-s2201-congressional-district-snap-2024",
        year=2024,
    )

    assert report.valid
    assert report.counts == {
        "record_set_count": 437,
        "row_count": 1_311,
        "measure_count": 437,
        "source_record_count": 1_311,
        "source_region_count": 437,
    }


def test_census_acs_s2201_congressional_district_package_builds_snap_facts():
    package = load_source_package(
        "census-acs-s2201-congressional-district-snap-2024"
    )
    rows = package.build_source_rows(2024)
    cells = package.build_source_cells(2024, source_rows=rows)
    facts = package.build_facts(2024, cells=cells, source_rows=rows)
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert validate_source_rows(rows).valid
    assert validate_source_cells(cells).valid
    assert validate_facts(facts).valid
    assert len(facts) == 1_311

    al01_total = values_by_record[
        "census_acs.acs1_2024.s2201.congressional_district_snap.0101."
        "all_households.household_count"
    ]
    al01_snap = values_by_record[
        "census_acs.acs1_2024.s2201.congressional_district_snap.0101."
        "receiving_food_stamps_snap.household_count"
    ]

    assert al01_total.value == 300_636
    assert al01_total.constraints == ()
    assert al01_total.geography.id == "5001900US0101"
    assert al01_total.source.source_file == "acs_S2201_district_2024.json"
    assert al01_snap.value == 34_742
    assert {
        (constraint.variable, constraint.operator, constraint.value)
        for constraint in al01_snap.constraints
    } == {("snap_receipt_status", "==", "receiving_food_stamps_snap")}


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


def test_cms_medicaid_monthly_dataset_source_package_alias_validates_counts():
    report = validate_source_package(
        "cms-medicaid-chip-monthly-enrollment-dataset",
        year=2026,
    )

    assert report.valid
    assert report.counts == {
        "record_set_count": 1,
        "row_count": 51,
        "measure_count": 5,
        "source_record_count": 255,
        "source_region_count": 1,
    }


def test_validate_source_package_reports_cms_aca_oep_counts():
    report = validate_source_package("cms-aca-oep-state-level", year=2024)

    assert report.valid
    assert report.counts == {
        "record_set_count": 1,
        "row_count": 51,
        "measure_count": 3,
        "source_record_count": 153,
        "source_region_count": 1,
    }


def test_validate_source_package_reports_cms_aca_oep_2022_counts():
    report = validate_source_package("cms-aca-oep-state-level-2022", year=2022)

    assert report.valid
    assert report.counts == {
        "record_set_count": 2,
        "row_count": 101,
        "measure_count": 3,
        "source_record_count": 151,
        "source_region_count": 2,
    }


def test_validate_source_package_reports_cms_aca_oep_2025_counts():
    report = validate_source_package("cms-aca-oep-state-level-2025", year=2025)

    assert report.valid
    assert report.counts == {
        "record_set_count": 1,
        "row_count": 51,
        "measure_count": 3,
        "source_record_count": 153,
        "source_region_count": 1,
    }


def test_validate_source_package_reports_cms_aca_effectuated_enrollment_2022_counts():
    report = validate_source_package(
        "cms-aca-effectuated-enrollment-2022",
        year=2022,
    )

    assert report.valid
    assert report.counts == {
        "record_set_count": 1,
        "row_count": 51,
        "measure_count": 8,
        "source_record_count": 408,
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


def test_cms_medicaid_monthly_dataset_builds_december_2025_state_enrollment_facts():
    package = load_source_package("cms-medicaid-chip-monthly-enrollment-dataset")
    rows = package.build_source_rows(2026)
    cells = package.build_source_cells(2026, source_rows=rows)
    records = package.build_source_records(2026, cells=cells, source_rows=rows)
    facts = package.build_facts(2026, cells=cells, source_rows=rows)
    records_by_id = {record.source_record_id: record for record in records}
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert package.package_id == "cms-medicaid-chip-monthly-enrollment-dataset"
    assert len(rows) == 10_608
    assert validate_source_rows(rows).valid
    assert rows[0].values["State Abbreviation"] == "AK"
    assert rows[0].values["Reporting Period"] == 201309
    assert validate_source_cells(cells).valid
    assert len(cells) == 2_288
    assert len(facts) == 255
    assert validate_facts(facts).valid
    assert all(fact.source_row_keys for fact in facts)
    assert all(fact.source.source_name == "cms_medicaid" for fact in facts)
    assert all(
        fact.source.source_file == "pi-dataset-april-2026-release.csv"
        for fact in facts
    )
    assert all(fact.source.raw_r2_uri for fact in facts)
    assert {f"{fact.period.type}:{fact.period.value}" for fact in facts} == {
        "month:2025-12"
    }

    ca_total = (
        "cms_medicaid.month2025_12.state_enrollment.ca."
        "total_medicaid_chip_enrollment"
    )
    ca_medicaid = (
        "cms_medicaid.month2025_12.state_enrollment.ca."
        "total_medicaid_enrollment"
    )
    ca_chip = (
        "cms_medicaid.month2025_12.state_enrollment.ca.total_chip_enrollment"
    )
    ca_child = (
        "cms_medicaid.month2025_12.state_enrollment.ca."
        "medicaid_chip_child_enrollment"
    )
    ca_adult = (
        "cms_medicaid.month2025_12.state_enrollment.ca."
        "total_adult_medicaid_enrollment"
    )
    tx_total = (
        "cms_medicaid.month2025_12.state_enrollment.tx."
        "total_medicaid_chip_enrollment"
    )
    ny_total = (
        "cms_medicaid.month2025_12.state_enrollment.ny."
        "total_medicaid_chip_enrollment"
    )

    assert records_by_id[ca_total].source_cell_addresses == (
        "U6",
        "U1",
        "C6",
        "E6",
        "F6",
    )
    assert records_by_id[ca_adult].source_cell_addresses == (
        "AA6",
        "AA1",
        "C6",
        "E6",
        "F6",
    )
    assert values_by_record[ca_total].value == 12_731_627
    assert values_by_record[ca_medicaid].value == 11_498_458
    assert values_by_record[ca_chip].value == 1_233_169
    assert values_by_record[ca_child].value == 4_628_424
    assert values_by_record[ca_adult].value == 8_103_203
    assert values_by_record[ca_total].geography.id == "0400000US06"
    assert values_by_record[tx_total].value == 4_111_374
    assert values_by_record[tx_total].geography.id == "0400000US48"
    assert values_by_record[ny_total].value == 6_550_143
    assert values_by_record[ny_total].geography.id == "0400000US36"


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


def test_soi_state_2022_source_package_alias_builds_us_totals():
    package = load_source_package("soi-state-2022")
    cells = package.build_source_cells(2022)
    facts = package.build_facts(2022, cells=cells)
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert package.package_id == "soi-state-2022"
    assert len(cells) == 668_304
    assert validate_source_cells(cells).valid
    assert len(facts) == 4
    assert validate_facts(facts).valid
    assert all(fact.source_cell_keys for fact in facts)
    assert all(fact.source.raw_r2_uri for fact in facts)
    assert (
        values_by_record[
            "irs_soi.ty2022.state_2022.us.return_count.all_returns.return_count"
        ].value
        == 159_651_330
    )
    assert (
        values_by_record[
            "irs_soi.ty2022.state_2022.us.adjusted_gross_income.all_returns.amount"
        ].value
        == 14_782_492_151_000
    )

    eitc_returns_record = (
        "irs_soi.ty2022.state_2022.us."
        "eitc_three_or_more_children_returns."
        "three_or_more_qualifying_children.return_count"
    )
    eitc_amount_record = (
        "irs_soi.ty2022.state_2022.us."
        "eitc_three_or_more_children_amount."
        "three_or_more_qualifying_children.amount"
    )

    assert values_by_record[eitc_returns_record].value == 3_080_790
    assert values_by_record[eitc_amount_record].value == 13_861_484_000
    assert {
        (constraint.variable, constraint.operator, constraint.value)
        for constraint in values_by_record[eitc_returns_record].constraints
    } == {
        ("us.tax.earned_income_credit_qualifying_children", ">=", 3),
    }


def test_soi_congressional_district_2022_builds_all_return_facts():
    package = load_source_package("soi-congressional-district-2022")
    rows = package.build_source_rows(2022)
    cells = package.build_source_cells(2022, source_rows=rows)
    facts = package.build_facts(2022, cells=cells, source_rows=rows)
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert package.package_id == "soi-congressional-district-2022"
    assert len(rows) == 4_791
    assert len(cells) == 79_365
    assert len(facts) == 1_440
    assert validate_source_rows(rows).valid
    assert validate_source_cells(cells).valid
    assert validate_facts(facts).valid
    assert {fact.geography.level for fact in facts} == {
        "country",
        "state",
        "congressional_district",
    }
    assert all(fact.source_row_keys for fact in facts)
    assert all(fact.source.raw_r2_uri for fact in facts)

    assert (
        values_by_record[
            "irs_soi.ty2022.congressional_district_2022.all_returns."
            "us.adjusted_gross_income"
        ].value
        == 14_424_810_411_000
    )
    assert (
        values_by_record[
            "irs_soi.ty2022.congressional_district_2022.all_returns."
            "al_total.return_count"
        ].value
        == 2_104_760
    )
    al_01_agi = values_by_record[
        "irs_soi.ty2022.congressional_district_2022.all_returns."
        "al_01.adjusted_gross_income"
    ]
    ca_53_returns = values_by_record[
        "irs_soi.ty2022.congressional_district_2022.all_returns."
        "ca_53.return_count"
    ]

    assert al_01_agi.value == 22_915_824_000
    assert al_01_agi.geography.id == "5001700US0101"
    assert al_01_agi.geography.name == "Alabama Congressional District 1"
    assert ca_53_returns.value == 383_160
    assert ca_53_returns.geography.id == "5001700US0653"


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
