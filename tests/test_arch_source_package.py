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

    assert package.package_id == "soi-table-1-4"
    assert len(cells) == 8109
    assert len(facts) == 260
    assert validate_facts(facts).valid
    assert facts[0].source.source_table == "Publication 1304 Table 1.4"


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
            "measure_count": 17,
            "source_record_count": 17,
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
            "row_count": 112,
            "measure_count": 8,
            "source_record_count": 224,
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
        "soi-historic-table-2-state-eitc-2022": {
            "record_set_count": 51,
            "row_count": 51,
            "measure_count": 102,
            "source_record_count": 102,
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
