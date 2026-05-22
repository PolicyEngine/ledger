"""Tests for declarative Arch source packages."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import hashlib
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import openpyxl
import pytest
import yaml

from arch.consumer_contract import validate_consumer_fact_contract
from arch.core import validate_facts
from arch.harness import main as harness_main
from arch.source_package import (
    SourceArtifactSpec,
    load_source_package,
    scaffold_source_package,
    validate_source_package,
)
from arch.sources.cells import build_source_cell_key, validate_source_cells
from arch.sources.rows import validate_source_rows
from arch.sources.specs import resolve_source_record
from arch.suite import build_source_suite

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
    source_path = REPO_ROOT / "packages" / "ons" / "uk_population_projections_2022"
    payload = yaml.safe_load((source_path / "source_package.yaml").read_text())
    reordered = deepcopy(payload)
    reordered["record_sets"][0]["rows"][0]["guard_cells"] = list(
        reversed(reordered["record_sets"][0]["rows"][0]["guard_cells"])
    )

    package_dir = tmp_path / "ons-original"
    reordered_dir = tmp_path / "ons-reordered-guards"
    package_dir.mkdir()
    reordered_dir.mkdir()
    (package_dir / "source_package.yaml").write_text(yaml.safe_dump(payload))
    (reordered_dir / "source_package.yaml").write_text(yaml.safe_dump(reordered))

    original_specs = load_source_package(package_dir).build_source_record_specs(2022)
    reordered_specs = load_source_package(reordered_dir).build_source_record_specs(2022)

    assert original_specs[0].layout is not None
    assert reordered_specs[0].layout is not None
    assert (
        reordered_specs[0].layout.record_set_spec_hash
        == original_specs[0].layout.record_set_spec_hash
    )


def test_guard_cell_expected_value_changes_record_set_spec_hash(tmp_path):
    source_path = REPO_ROOT / "packages" / "ons" / "uk_population_projections_2022"
    payload = yaml.safe_load((source_path / "source_package.yaml").read_text())
    changed = deepcopy(payload)
    changed["record_sets"][0]["rows"][0]["guard_cells"][0]["expected_value"] = 1

    package_dir = tmp_path / "ons-original"
    changed_dir = tmp_path / "ons-changed-guard"
    package_dir.mkdir()
    changed_dir.mkdir()
    (package_dir / "source_package.yaml").write_text(yaml.safe_dump(payload))
    (changed_dir / "source_package.yaml").write_text(yaml.safe_dump(changed))

    original_specs = load_source_package(package_dir).build_source_record_specs(2022)
    changed_specs = load_source_package(changed_dir).build_source_record_specs(2022)

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


def test_bea_nipa_wages_package_uses_all_worker_wage_series():
    package = load_source_package("bea-nipa-total-wages-salaries")
    facts = package.build_facts(2024)
    values_by_record = {fact.source_record_id: fact.value for fact in facts}
    facts_by_record = {fact.source_record_id: fact for fact in facts}
    source_record_id = (
        "bea_nipa.cy2024.total_wages_salaries.a034rc.wages_salaries_amount"
    )

    assert values_by_record[source_record_id] == 12_387_929_000_000
    assert facts_by_record[source_record_id].measure.concept == (
        "bea_nipa.wages_and_salaries"
    )
    assert facts_by_record[source_record_id].measure.source_concept == (
        "bea_nipa.a034rc_wages_and_salaries"
    )


def test_bea_nipa_personal_income_components_build_2024_facts():
    package = load_source_package("bea-nipa-personal-income-components")
    facts = package.build_facts(2024)
    values_by_record = {fact.source_record_id: fact.value for fact in facts}

    assert len(facts) == 18
    assert validate_facts(facts).valid
    assert values_by_record == {
        ("bea_nipa.cy2024.proprietors_income.a041rc.amount"): 2_023_080_000_000,
        ("bea_nipa.cy2024.rental_income_of_persons.a048rc.amount"): 1_078_149_000_000,
        ("bea_nipa.cy2024.personal_interest_income.a064rc.amount"): 1_926_644_000_000,
        ("bea_nipa.cy2024.personal_dividend_income.b703rc.amount"): 2_218_700_000_000,
        (
            "bea_nipa.cy2024.supplements_to_wages_and_salaries.a038rc.amount"
        ): 2_639_130_000_000,
        (
            "bea_nipa.cy2024.employer_pension_and_insurance_contributions.b040rc.amount"
        ): 1_772_686_000_000,
        (
            "bea_nipa.cy2024."
            "employer_government_social_insurance_contributions."
            "b039rc.amount"
        ): 866_444_000_000,
        ("bea_nipa.cy2024.farm_proprietors_income.b042rc.amount"): 57_843_000_000,
        ("bea_nipa.cy2024.nonfarm_proprietors_income.a045rc.amount"): 1_965_237_000_000,
        (
            "bea_nipa.cy2024.government_social_benefits_to_persons.a063rc.amount"
        ): 4_455_695_000_000,
        ("bea_nipa.cy2024.social_security_benefits.w823rc.amount"): 1_447_965_000_000,
        ("bea_nipa.cy2024.medicare_benefits.w824rc.amount"): 1_102_358_000_000,
        ("bea_nipa.cy2024.medicaid_benefits.w729rc.amount"): 938_191_000_000,
        (
            "bea_nipa.cy2024.unemployment_insurance_benefits.w825rc.amount"
        ): 36_468_000_000,
        ("bea_nipa.cy2024.veterans_benefits.w826rc.amount"): 229_990_000_000,
        (
            "bea_nipa.cy2024.other_government_social_benefits.w827rc.amount"
        ): 700_722_000_000,
        (
            "bea_nipa.cy2024.business_current_transfer_receipts.b931rc.amount"
        ): 99_724_000_000,
        (
            "bea_nipa.cy2024.personal_current_transfer_receipts.a577rc.amount"
        ): 4_555_419_000_000,
    }


def test_bea_nipa_personal_income_disposition_build_2024_facts():
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
    assert (
        facts_by_record[
            "bea_nipa.cy2024.disposable_personal_income.a067rc.amount"
        ].value
        == 21_917_657_000_000
    )
    assert (
        facts_by_record["bea_nipa.cy2024.personal_saving.a071rc.amount"].value
        == 1_193_230_000_000
    )
    saving_rate = facts_by_record["bea_nipa.cy2024.personal_saving_rate.a072rc.rate"]
    assert saving_rate.value == 5.4
    assert saving_rate.measure.unit == "percent"


def test_cbo_revenue_projections_income_by_source_preserve_concepts():
    package = load_source_package("cbo-revenue-projections-income-by-source-2026-02")
    facts = package.build_facts(2024)
    facts_by_record = {fact.source_record_id: fact for fact in facts}

    assert package.package_id == "cbo-revenue-projections-income-by-source-2026-02"
    assert validate_source_package(
        "cbo-revenue-projections-income-by-source-2026-02",
        year=2024,
    ).valid
    assert len(facts) == 6
    assert validate_facts(facts).valid

    interest_and_ordinary_dividends = facts_by_record[
        "cbo.revenue_projection.ty2024.income_by_source."
        "taxable_interest_and_ordinary_dividends_excluding_qualified_dividends."
        "projected_amount"
    ]
    qualified_dividends = facts_by_record[
        "cbo.revenue_projection.ty2024.income_by_source."
        "qualified_dividend_income.projected_amount"
    ]
    net_business_income = facts_by_record[
        "cbo.revenue_projection.ty2024.income_by_source."
        "net_business_income.projected_amount"
    ]

    assert interest_and_ordinary_dividends.value == 309_700_000_000
    assert qualified_dividends.value == 354_300_000_000
    assert net_business_income.value == 1_916_000_000_000
    assert interest_and_ordinary_dividends.period.value == 2024
    assert interest_and_ordinary_dividends.layout.source_column_id == "year_2024"
    assert interest_and_ordinary_dividends.source.source_file == (
        "cbo_revenue_projections_income_by_source_2026_02.csv"
    )
    assert interest_and_ordinary_dividends.source.source_sha256 == (
        "8cd8edee3e76258aa67153adff9dc0dc9b9738ace426eceebcc8d5b26d319bb8"
    )

    interest_constraints = {
        (constraint.variable, constraint.operator, constraint.value)
        for constraint in interest_and_ordinary_dividends.constraints
    }
    business_constraints = {
        (constraint.variable, constraint.operator, constraint.value)
        for constraint in net_business_income.constraints
    }
    assert (
        "cbo.income_source",
        "==",
        "taxable_interest_and_ordinary_dividends_excluding_qualified_dividends",
    ) in interest_constraints
    assert ("cbo.income_source", "==", "net_business_income") in business_constraints
    assert all(
        constraint.value != "dividend_income"
        for constraint in interest_and_ordinary_dividends.constraints
    )
    assert all(
        constraint.value != "self_employment_income"
        for constraint in net_business_income.constraints
    )


def test_cbo_revenue_projections_income_by_source_build_future_year():
    package = load_source_package("cbo-revenue-projections-income-by-source-2026-02")
    facts = package.build_facts(2036)
    values_by_record = {fact.source_record_id: fact for fact in facts}
    record_id = (
        "cbo.revenue_projection.ty2036.income_by_source."
        "taxable_interest_and_ordinary_dividends_excluding_qualified_dividends."
        "projected_amount"
    )

    assert validate_source_package(
        "cbo-revenue-projections-income-by-source-2026-02",
        year=2036,
    ).valid
    assert len(facts) == 6
    assert validate_facts(facts).valid
    assert values_by_record[record_id].value == 535_100_000_000
    assert values_by_record[record_id].layout.source_column_id == "year_2036"
    assert values_by_record[record_id].period.value == 2036


def test_bea_regional_state_personal_income_components_build_2024_facts():
    package = load_source_package("bea-regional-state-personal-income-components-2024")
    facts = package.build_facts(2024)
    facts_by_record = {fact.source_record_id: fact for fact in facts}

    assert len(facts) == 312
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
    assert validate_consumer_fact_contract(facts).valid


def test_source_package_builds_soi_table_1_4_2021_layout():
    package = load_source_package("soi-table-1-4")
    facts = package.build_facts(2021)
    values_by_record = {fact.source_record_id: fact.value for fact in facts}

    assert len(facts) == 260
    assert (
        values_by_record[
            "irs_soi.ty2021.table_1_4.all.taxable_ira_distributions_amount"
        ]
        == 408_382_461_000
    )
    assert (
        values_by_record["irs_soi.ty2021.table_1_4.all.taxable_social_security_amount"]
        == 412_830_233_000
    )
    assert (
        values_by_record[
            "irs_soi.ty2021.table_1_4.all."
            "self_employed_pension_contribution_ald"
        ]
        == 28_919_016_000
    )


@pytest.mark.parametrize(
    (
        "source",
        "year",
        "record_id",
        "fact_count",
        "source_file",
        "expected_value",
    ),
    [
        (
            "soi-table-1-1",
            2021,
            "irs_soi.ty2021.table_1_1.all.return_count",
            80,
            "21in11si.xls",
            160_824_340,
        ),
        (
            "soi-table-1-1",
            2022,
            "irs_soi.ty2022.table_1_1.all.adjusted_gross_income",
            80,
            "22in11si.xls",
            14_833_956_956_000,
        ),
        (
            "soi-table-1-4",
            2021,
            "irs_soi.ty2021.table_1_4.all.wages_salaries_amount",
            260,
            "21in14ar.xls",
            9_022_352_941_000,
        ),
        (
            "soi-table-1-4",
            2022,
            "irs_soi.ty2022.table_1_4.all.taxable_social_security_amount",
            260,
            "22in14ar.xls",
            458_513_595_000,
        ),
        (
            "soi-table-1-2",
            2021,
            "irs_soi.ty2021.table_1_2.all_returns.all.taxable_income_amount",
            7,
            "21in12ms.xls",
            11_767_185_281_000,
        ),
        (
            "soi-table-1-2",
            2022,
            "irs_soi.ty2022.table_1_2.all_returns.all.standard_deduction_amount",
            7,
            "22in12ms.xls",
            2_609_228_480_000,
        ),
        (
            "soi-table-2-1",
            2021,
            "irs_soi.ty2021.table_2_1.itemized_all_returns."
            "all.total_itemized_deductions_amount",
            17,
            "21in21id.xls",
            659_680_547_000,
        ),
        (
            "soi-table-2-1",
            2022,
            "irs_soi.ty2022.table_2_1.itemized_all_returns."
            "all.taxable_pension_income_amount",
            17,
            "22in21id.xls",
            175_935_867_000,
        ),
        (
            "soi-table-2-5",
            2021,
            "irs_soi.ty2021.table_2_5.eitc_all_returns."
            "total.total_earned_income_credit_amount",
            8,
            "21in25ic.xls",
            65_684_435_000,
        ),
        (
            "soi-table-2-5",
            2022,
            "irs_soi.ty2022.table_2_5.eitc_all_returns."
            "total.eic_refundable_portion_amount",
            8,
            "22in25ic.xls",
            50_312_596_000,
        ),
        (
            "soi-table-4-3",
            2021,
            "irs_soi.ty2021.table_4_3.all_returns_excluding_dependents."
            "all.itemized_deductions_amount",
            18,
            "21in43ts.xls",
            659_147_733_000,
        ),
        (
            "soi-table-4-3",
            2022,
            "irs_soi.ty2022.table_4_3.all_returns_excluding_dependents."
            "all.total_income_tax_amount",
            18,
            "22in43ts.xls",
            2_136_332_548_000,
        ),
    ],
)
def test_source_package_alias_builds_multiyear_soi_workbook_facts(
    source,
    year,
    record_id,
    fact_count,
    source_file,
    expected_value,
):
    package = load_source_package(source)
    facts = package.build_facts(year)
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert len(facts) == fact_count
    assert validate_facts(facts).valid
    assert all(fact.source.raw_r2_uri for fact in facts)
    fact = values_by_record[record_id]
    assert fact.value == expected_value
    assert fact.source.source_file == source_file
    assert fact.source_cell_keys


def test_source_package_alias_builds_soi_table_1_2_facts():
    package = load_source_package("soi-table-1-2")
    cells = package.build_source_cells(2023)
    records = package.build_source_records(2023, cells=cells)
    facts = package.build_facts(2023, cells=cells)
    records_by_id = {record.source_record_id: record for record in records}
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert package.package_id == "soi-table-1-2"
    assert validate_source_cells(cells).valid
    assert validate_facts(facts).valid
    assert len(cells) == 3_087
    assert len(facts) == 7
    assert all(fact.source.raw_r2_uri for fact in facts)
    itemized_deductions = (
        "irs_soi.ty2023.table_1_2.all_returns.all.total_itemized_deductions_amount"
    )
    standard_deduction = (
        "irs_soi.ty2023.table_1_2.all_returns.all.standard_deduction_amount"
    )
    taxable_income = "irs_soi.ty2023.table_1_2.all_returns.all.taxable_income_amount"
    assert records_by_id[itemized_deductions].source_cell_addresses == (
        "E9",
        "E5",
        "B3",
    )
    assert values_by_record[itemized_deductions].value == 690_845_489_000
    assert values_by_record[standard_deduction].value == 2_797_528_430_000
    assert values_by_record[taxable_income].value == 11_944_446_990_000
    assert values_by_record[taxable_income].source.source_file == "23in12ms.xls"
    assert not values_by_record[taxable_income].constraints


def test_source_package_alias_builds_soi_table_2_1_facts():
    package = load_source_package("soi-table-2-1")
    cells = package.build_source_cells(2023)
    records = package.build_source_records(2023, cells=cells)
    facts = package.build_facts(2023, cells=cells)
    records_by_id = {record.source_record_id: record for record in records}
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert package.package_id == "soi-table-2-1"
    assert validate_source_cells(cells).valid
    assert validate_facts(facts).valid
    assert len(cells) == 6_486
    assert len(facts) == 17
    assert all(fact.source.raw_r2_uri for fact in facts)
    itemized_returns = (
        "irs_soi.ty2023.table_2_1.itemized_all_returns.all.itemized_return_count"
    )
    total_wages = "irs_soi.ty2023.table_2_1.itemized_all_returns.all.total_wages_amount"
    taxable_pensions = (
        "irs_soi.ty2023.table_2_1.itemized_all_returns."
        "all.taxable_pension_income_amount"
    )
    itemized_deductions = (
        "irs_soi.ty2023.table_2_1.itemized_all_returns."
        "all.total_itemized_deductions_amount"
    )
    assert records_by_id[total_wages].source_cell_addresses == (
        "G10",
        "G7",
        "A1",
    )
    assert records_by_id[itemized_deductions].source_cell_addresses == (
        "BT10",
        "BT4",
        "A1",
    )
    assert values_by_record[itemized_returns].value == 15_106_257
    assert values_by_record[total_wages].value == 2_384_390_017_000
    assert values_by_record[taxable_pensions].value == 167_205_724_000
    assert values_by_record[itemized_deductions].value == 690_845_489_000
    assert values_by_record[total_wages].source.source_file == "23in21id.xls"
    assert values_by_record[total_wages].domain == (
        "individual_income_tax_returns_with_itemized_deductions"
    )
    assert not values_by_record[total_wages].constraints


def test_source_package_alias_builds_soi_table_2_5_facts():
    package = load_source_package("soi-table-2-5")
    cells = package.build_source_cells(2023)
    records = package.build_source_records(2023, cells=cells)
    facts = package.build_facts(2023, cells=cells)
    records_by_id = {record.source_record_id: record for record in records}
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert package.package_id == "soi-table-2-5"
    assert validate_source_cells(cells).valid
    assert validate_facts(facts).valid
    assert len(cells) == 4_293
    assert len(facts) == 8
    assert all(fact.source.raw_r2_uri for fact in facts)
    eitc_returns = "irs_soi.ty2023.table_2_5.eitc_all_returns.total.eitc_return_count"
    total_eitc = (
        "irs_soi.ty2023.table_2_5.eitc_all_returns."
        "total.total_earned_income_credit_amount"
    )
    refundable_eitc = (
        "irs_soi.ty2023.table_2_5.eitc_all_returns.total.eic_refundable_portion_amount"
    )
    assert records_by_id[total_eitc].source_cell_addresses == (
        "K9",
        "K6",
        "A1",
    )
    assert records_by_id[refundable_eitc].source_cell_addresses == (
        "Q9",
        "Q6",
        "A1",
    )
    assert values_by_record[eitc_returns].value == 24_439_936
    assert values_by_record[total_eitc].value == 66_270_000_000
    assert values_by_record[refundable_eitc].value == 55_883_268_000
    assert values_by_record[total_eitc].source.source_file == "23in25ic.xls"
    assert values_by_record[total_eitc].domain == (
        "individual_income_tax_returns_with_earned_income_credit"
    )
    assert not values_by_record[total_eitc].constraints


def test_source_package_alias_builds_soi_table_2_5_eitc_children_2020_facts():
    package = load_source_package("soi-table-2-5-eitc-children-2020")
    cells = package.build_source_cells(2020)
    records = package.build_source_records(2020, cells=cells)
    facts = package.build_facts(2020, cells=cells)
    records_by_id = {record.source_record_id: record for record in records}
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert package.package_id == "soi-table-2-5-eitc-children-2020"
    assert validate_source_cells(cells).valid
    assert validate_facts(facts).valid
    assert len(cells) == 4_293
    assert len(facts) == 8
    assert all(fact.source.source_file == "20in25ic.xls" for fact in facts)
    assert all(fact.source.raw_r2_uri for fact in facts)

    expected_values = {
        "no_qualifying_children": (7_636_714, 2_255_068_000, "==", 0),
        "one_qualifying_child": (9_197_765, 21_441_196_000, "==", 1),
        "two_qualifying_children": (5_994_984, 22_312_989_000, "==", 2),
        "three_or_more_qualifying_children": (
            3_196_245,
            13_230_431_000,
            ">=",
            3,
        ),
    }
    for child_id, (returns, total, operator, value) in expected_values.items():
        returns_record = (
            f"irs_soi.ty2020.table_2_5.eitc_by_children.{child_id}."
            f"{child_id}.eitc_returns"
        )
        amount_record = (
            f"irs_soi.ty2020.table_2_5.eitc_by_children.{child_id}."
            f"{child_id}.eitc_total"
        )
        assert values_by_record[returns_record].value == returns
        assert values_by_record[amount_record].value == total
        assert {
            (constraint.variable, constraint.operator, constraint.value)
            for constraint in values_by_record[returns_record].constraints
        } == {
            (
                "us.tax.earned_income_credit_qualifying_children",
                operator,
                value,
            ),
        }
        assert {
            (constraint.variable, constraint.operator, constraint.value)
            for constraint in values_by_record[amount_record].constraints
        } == {
            (
                "us.tax.earned_income_credit_qualifying_children",
                operator,
                value,
            ),
        }

    assert records_by_id[
        "irs_soi.ty2020.table_2_5.eitc_by_children."
        "no_qualifying_children.no_qualifying_children.eitc_returns"
    ].source_cell_addresses == ("Z9", "Z6", "A1", "R3", "Z4")
    assert records_by_id[
        "irs_soi.ty2020.table_2_5.eitc_by_children."
        "three_or_more_qualifying_children."
        "three_or_more_qualifying_children.eitc_total"
    ].source_cell_addresses == ("BW9", "BW6", "A1", "BN3", "BV4")


def test_source_package_alias_builds_soi_table_2_5_eitc_agi_children_2022_facts():
    package = load_source_package("soi-table-2-5-eitc-agi-children-2022")
    cells = package.build_source_cells(2022)
    records = package.build_source_records(2022, cells=cells)
    facts = package.build_facts(2022, cells=cells)
    records_by_id = {record.source_record_id: record for record in records}
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert package.package_id == "soi-table-2-5-eitc-agi-children-2022"
    assert len(cells) == 4_293
    assert validate_source_cells(cells).valid
    assert len(facts) == 224
    assert validate_facts(facts).valid
    assert all(fact.source.source_file == "22in25ic.xls" for fact in facts)
    assert all(fact.source.raw_r2_uri for fact in facts)

    no_child_under_1 = (
        "irs_soi.ty2022.table_2_5.eitc_by_agi_children."
        "no_qualifying_children.under_1.eitc_returns"
    )
    one_child_10k = (
        "irs_soi.ty2022.table_2_5.eitc_by_agi_children."
        "one_qualifying_child.10k_to_11k.eitc_total"
    )
    three_plus_50k = (
        "irs_soi.ty2022.table_2_5.eitc_by_agi_children."
        "three_or_more_qualifying_children.50k_plus.eitc_total"
    )
    assert values_by_record[no_child_under_1].value == 97_411
    assert values_by_record[one_child_10k].value == 1_024_890_000
    assert values_by_record[three_plus_50k].value == 234_030_000
    assert records_by_id[no_child_under_1].source_cell_addresses == (
        "Z10",
        "Z6",
        "A10",
        "A1",
        "R3",
        "Z4",
    )
    assert records_by_id[three_plus_50k].source_cell_addresses == (
        "BW37",
        "BW6",
        "A37",
        "A1",
        "BN3",
        "BV4",
    )
    assert {
        (constraint.variable, constraint.operator, constraint.value)
        for constraint in values_by_record[no_child_under_1].constraints
    } == {
        ("us:statutes/26/62#adjusted_gross_income", "<", 1),
        ("us.tax.earned_income_credit_qualifying_children", "==", 0),
    }
    assert {
        (constraint.variable, constraint.operator, constraint.value)
        for constraint in values_by_record[three_plus_50k].constraints
    } == {
        ("us:statutes/26/62#adjusted_gross_income", ">=", 50_000),
        ("us.tax.earned_income_credit_qualifying_children", ">=", 3),
    }


def test_source_package_alias_builds_soi_table_4_3_facts():
    package = load_source_package("soi-table-4-3")
    cells = package.build_source_cells(2023)
    records = package.build_source_records(2023, cells=cells)
    facts = package.build_facts(2023, cells=cells)
    records_by_id = {record.source_record_id: record for record in records}
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert package.package_id == "soi-table-4-3"
    assert validate_source_cells(cells).valid
    assert validate_facts(facts).valid
    assert len(cells) == 2_145
    assert len(facts) == 18
    assert all(fact.source.raw_r2_uri for fact in facts)
    return_count = (
        "irs_soi.ty2023.table_4_3.all_returns_excluding_dependents.all.return_count"
    )
    itemized_deductions = (
        "irs_soi.ty2023.table_4_3.all_returns_excluding_dependents."
        "all.itemized_deductions_amount"
    )
    total_income_tax = (
        "irs_soi.ty2023.table_4_3.all_returns_excluding_dependents."
        "all.total_income_tax_amount"
    )
    assert records_by_id[total_income_tax].source_cell_addresses == (
        "BJ9",
        "BJ6",
        "A1",
    )
    assert records_by_id[itemized_deductions].source_cell_addresses == (
        "AD9",
        "AD6",
        "A1",
    )
    assert values_by_record[return_count].value == 153_076_443
    assert values_by_record[itemized_deductions].value == 690_129_229_000
    assert values_by_record[total_income_tax].value == 2_144_410_963_000
    assert values_by_record[total_income_tax].source.source_file == "23in43ts.xls"
    assert values_by_record[total_income_tax].domain == (
        "individual_income_tax_returns_excluding_dependents"
    )
    assert not values_by_record[total_income_tax].constraints


def test_source_package_alias_builds_usda_snap_fy24_national_and_state_facts():
    package = load_source_package("usda-snap-fy69-to-current")
    cells = package.build_source_cells(2024)
    records = package.build_source_records(2024, cells=cells)
    facts = package.build_facts(2024, cells=cells)
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


def test_source_package_alias_builds_bea_nipa_pension_facts():
    package = load_source_package("bea-nipa-pension-contributions")
    rows = package.build_source_rows(2022)
    cells = package.build_source_cells(2022, source_rows=rows)
    facts = package.build_facts(2022, cells=cells, source_rows=rows)
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert len(rows) == 559_069
    assert validate_source_rows(rows).valid
    assert rows[0].values == {
        "Period": 1929,
        "SeriesCode": "A001RC",
        "Value": 105_322,
    }
    assert validate_source_cells(cells).valid
    assert validate_facts(facts).valid
    assert len(cells) == 9
    assert len(facts) == 2
    assert all(fact.source_row_keys for fact in facts)
    assert all(fact.source.source_name == "bea" for fact in facts)
    assert all("fred" not in (fact.source.url or "") for fact in facts)
    assert all(fact.source.source_file == "NipaDataA.txt" for fact in facts)
    assert (
        values_by_record[
            "bea_nipa.cy2022.defined_contribution_employer_contributions."
            "w351rc.employer_contributions"
        ].value
        == 247_468_000_000
    )
    assert (
        values_by_record[
            "bea_nipa.cy2022.defined_contribution_actual_contributions."
            "y351rc.actual_employer_and_household_contributions"
        ].value
        == 815_419_000_000
    )


def test_source_package_alias_builds_bea_nipa_total_wages_facts():
    package = load_source_package("bea-nipa-total-wages-salaries")
    rows = package.build_source_rows(2024)
    cells = package.build_source_cells(2024, source_rows=rows)
    records = package.build_source_records(2024, cells=cells, source_rows=rows)
    facts = package.build_facts(2024, cells=cells, source_rows=rows)
    records_by_id = {record.source_record_id: record for record in records}
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert len(rows) == 559_069
    assert validate_source_rows(rows).valid
    assert validate_source_cells(cells).valid
    assert validate_facts(facts).valid
    assert len(cells) == 12
    assert len(facts) == 3
    assert all(fact.source_row_keys for fact in facts)
    assert all(fact.source.source_name == "bea" for fact in facts)
    assert all("fred" not in (fact.source.url or "") for fact in facts)
    assert all(fact.source.raw_r2_uri for fact in facts)

    value_2018 = "bea_nipa.cy2018.total_wages_salaries.a034rc.wages_salaries_amount"
    value_2023 = "bea_nipa.cy2023.total_wages_salaries.a034rc.wages_salaries_amount"
    value_2024 = "bea_nipa.cy2024.total_wages_salaries.a034rc.wages_salaries_amount"
    assert records_by_id[value_2018].source_cell_addresses == ("C2", "C1", "B2")
    assert records_by_id[value_2024].source_cell_addresses == ("C4", "C1", "B4")
    assert values_by_record[value_2018].value == 8_899_824_000_000
    assert values_by_record[value_2023].value == 11_732_410_000_000
    assert values_by_record[value_2024].value == 12_387_929_000_000
    assert values_by_record[value_2023].value / values_by_record[
        value_2018
    ].value == pytest.approx(1.318274383852984)
    assert values_by_record[value_2024].value / values_by_record[
        value_2018
    ].value == pytest.approx(1.391929660631491)


def test_source_package_alias_builds_federal_reserve_z1_net_worth_fact():
    package = load_source_package("federal-reserve-z1-household-net-worth")
    cells = package.build_source_cells(2024)
    records = package.build_source_records(2024, cells=cells)
    facts = package.build_facts(2024, cells=cells)
    records_by_id = {record.source_record_id: record for record in records}
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert package.package_id == "federal-reserve-z1-household-net-worth"
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


def test_source_package_alias_builds_psca_roth_availability_facts():
    package = load_source_package("psca-67th-annual-401k-survey-roth-availability")
    cells = package.build_source_cells(2023)
    records = package.build_source_records(2023, cells=cells)
    facts = package.build_facts(2023, cells=cells)
    records_by_id = {record.source_record_id: record for record in records}
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert package.package_id == ("psca-67th-annual-401k-survey-roth-availability")
    assert len(cells) == 310
    assert validate_source_cells(cells).valid
    assert len(facts) == 2
    assert validate_facts(facts).valid
    assert all(fact.source.source_name == "psca" for fact in facts)
    assert all(fact.source.raw_r2_uri for fact in facts)

    current_id = (
        "psca.py2023.annual_401k_survey.roth_after_tax_availability."
        "roth_after_tax_contributions.plan_availability_share"
    )
    prior_id = (
        "psca.py2022.annual_401k_survey.roth_after_tax_availability."
        "roth_after_tax_contributions.plan_availability_share"
    )
    assert records_by_id[current_id].source_cell_addresses == ("E37", "E1")
    assert records_by_id[prior_id].source_cell_addresses == ("E38", "E1")
    assert values_by_record[current_id].value == 0.93
    assert values_by_record[prior_id].value == 0.89
    assert values_by_record[current_id].period.value == 2023
    assert values_by_record[prior_id].period.value == 2022
    assert values_by_record[current_id].constraints[0].variable == (
        "retirement_plan.feature"
    )


def test_source_package_alias_builds_vanguard_roth_participation_fact():
    package = load_source_package("vanguard-how-america-saves-2024-roth-participation")
    cells = package.build_source_cells(2024)
    records = package.build_source_records(2024, cells=cells)
    facts = package.build_facts(2024, cells=cells)
    records_by_id = {record.source_record_id: record for record in records}
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert package.package_id == "vanguard-how-america-saves-2024-roth-participation"
    assert len(cells) == 61_308
    assert validate_source_cells(cells).valid
    assert len(facts) == 1
    assert validate_facts(facts).valid
    assert all(fact.source.source_name == "vanguard" for fact in facts)
    assert all(fact.source.raw_r2_uri for fact in facts)

    source_record_id = (
        "vanguard.cy2023.how_america_saves.roth_participation."
        "roth_contributions.participant_usage_share"
    )
    assert records_by_id[source_record_id].source_cell_addresses == (
        "E3584",
        "E1",
        "A3584",
        "B3584",
    )
    assert values_by_record[source_record_id].value == 0.17
    assert (
        values_by_record[source_record_id].filters["retirement_plan.feature"]
        == "roth_contributions"
    )
    assert values_by_record[source_record_id].measure.unit == "share"


def test_source_package_alias_builds_dft_nts_household_car_availability_facts():
    package = load_source_package("dft-nts-household-car-availability-2024")
    cells = package.build_source_cells(2024)
    records = package.build_source_records(2024, cells=cells)
    facts = package.build_facts(2024, cells=cells)
    records_by_id = {record.source_record_id: record for record in records}
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert package.package_id == "dft-nts-household-car-availability-2024"
    assert len(cells) == 660
    assert validate_source_cells(cells).valid
    assert len(facts) == 3
    assert validate_facts(facts).valid
    assert all(fact.source.source_name == "dft" for fact in facts)
    assert all(
        fact.source.source_file == "nts_2024_household_car_availability.html"
        for fact in facts
    )
    assert all(fact.source.raw_r2_uri for fact in facts)
    assert {fact.geography.id for fact in facts} == {"E92000001"}
    assert {fact.entity.name for fact in facts} == {"household"}

    no_car_id = (
        "dft_nts.cy2024.household_car_availability.no_car_or_van.household_share"
    )
    one_car_id = (
        "dft_nts.cy2024.household_car_availability.one_car_or_van.household_share"
    )
    two_plus_id = (
        "dft_nts.cy2024.household_car_availability."
        "two_or_more_cars_or_vans.household_share"
    )
    assert records_by_id[no_car_id].source_cell_addresses == ("E13", "E1")
    assert records_by_id[one_car_id].source_cell_addresses == ("E12", "E1")
    assert records_by_id[two_plus_id].source_cell_addresses == ("E10", "E1")
    assert values_by_record[no_car_id].value == 0.22
    assert values_by_record[one_car_id].value == 0.44
    assert values_by_record[two_plus_id].value == 0.34
    assert {
        (constraint.variable, constraint.operator, constraint.value)
        for constraint in values_by_record[two_plus_id].constraints
    } == {("household.car_or_van_count", ">=", 2)}


def test_source_package_alias_builds_hmrc_salary_sacrifice_relief_facts():
    package = load_source_package("hmrc-salary-sacrifice-relief-2024")
    rows = package.build_source_rows(2024)
    cells = package.build_source_cells(2024, source_rows=rows)
    records = package.build_source_records(2024, cells=cells, source_rows=rows)
    facts = package.build_facts(2024, cells=cells, source_rows=rows)
    records_by_id = {record.source_record_id: record for record in records}
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert package.package_id == "hmrc-salary-sacrifice-relief-2024"
    assert len(rows) == 82
    assert validate_source_rows(rows).valid
    assert rows[2].values["contribution_type"] == "Salary sacrificed contributions"
    assert validate_source_cells(cells).valid
    assert len(cells) == 56
    assert len(facts) == 6
    assert validate_facts(facts).valid
    assert all(fact.source_row_keys for fact in facts)
    assert all(fact.source.source_name == "hmrc" for fact in facts)
    assert all(fact.source.source_file == "Tables_6_1_and_6_2.csv" for fact in facts)
    assert all(fact.source.raw_r2_uri for fact in facts)
    assert {f"{fact.period.type}:{fact.period.value}" for fact in facts} == {
        "tax_year:2023-24"
    }
    assert all(fact.geography.id == "GBR" for fact in facts)

    total_id = (
        "hmrc_pensions.ty2023_24.salary_sacrifice_income_tax_relief_by_rate."
        "total.value_of_relief"
    )
    employee_nics_id = (
        "hmrc_pensions.ty2023_24.salary_sacrifice_nics_relief_by_class."
        "class_1_primary_employee.value_of_relief"
    )
    employer_nics_id = (
        "hmrc_pensions.ty2023_24.salary_sacrifice_nics_relief_by_class."
        "class_1_secondary_employer.value_of_relief"
    )
    assert records_by_id[total_id].source_cell_addresses == ("H2", "H1")
    assert records_by_id[employee_nics_id].source_cell_addresses == ("H6", "H1")
    assert values_by_record[total_id].value == 7_200_000_000
    assert (
        values_by_record[
            "hmrc_pensions.ty2023_24.salary_sacrifice_income_tax_relief_by_rate."
            "basic_rate.value_of_relief"
        ].value
        == 1_600_000_000
    )
    assert (
        values_by_record[
            "hmrc_pensions.ty2023_24.salary_sacrifice_income_tax_relief_by_rate."
            "higher_rate.value_of_relief"
        ].value
        == 4_400_000_000
    )
    assert (
        values_by_record[
            "hmrc_pensions.ty2023_24.salary_sacrifice_income_tax_relief_by_rate."
            "additional_rate.value_of_relief"
        ].value
        == 1_200_000_000
    )
    assert values_by_record[employee_nics_id].value == 1_200_000_000
    assert values_by_record[employer_nics_id].value == 2_900_000_000
    assert (
        "nics_relief_class",
        "==",
        "Class 1 Primary (employee)",
    ) in {
        (constraint.variable, constraint.operator, constraint.value)
        for constraint in values_by_record[employee_nics_id].constraints
    }


def test_source_package_alias_builds_hmrc_salary_sacrifice_reform_facts():
    package = load_source_package("hmrc-salary-sacrifice-reform-2025")
    cells = package.build_source_cells(2025)
    records = package.build_source_records(2025, cells=cells)
    facts = package.build_facts(2025, cells=cells)
    records_by_id = {record.source_record_id: record for record in records}
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert package.package_id == "hmrc-salary-sacrifice-reform-2025"
    assert len(cells) == 326
    assert validate_source_cells(cells).valid
    assert len(facts) == 3
    assert validate_facts(facts).valid
    assert all(fact.source.source_name == "hmrc" for fact in facts)
    assert all(
        fact.source.source_file
        == "salary_sacrifice_reform_for_pension_contributions.html"
        for fact in facts
    )
    assert all(fact.source.raw_r2_uri for fact in facts)
    assert {f"{fact.period.type}:{fact.period.value}" for fact in facts} == {
        "calendar_year:2025"
    }
    assert {fact.geography.id for fact in facts} == {"GBR"}
    assert {fact.entity.name for fact in facts} == {"person"}

    total_id = (
        "hmrc_salary_sacrifice_reform.cy2025.pension_salary_sacrifice_users."
        "all_users.employee_count"
    )
    above_id = (
        "hmrc_salary_sacrifice_reform.cy2025.pension_salary_sacrifice_users."
        "above_2000.employee_count"
    )
    below_id = (
        "hmrc_salary_sacrifice_reform.cy2025.pension_salary_sacrifice_users."
        "at_or_below_2000.employee_count"
    )
    assert records_by_id[total_id].source_cell_addresses == ("E40", "E1")
    assert records_by_id[above_id].source_cell_addresses == ("E41", "E1")
    assert records_by_id[below_id].source_cell_addresses == ("E45", "E1")
    assert values_by_record[total_id].value == 7_700_000
    assert values_by_record[above_id].value == 3_300_000
    assert values_by_record[below_id].value == 4_300_000
    assert {
        (constraint.variable, constraint.operator, constraint.value)
        for constraint in values_by_record[above_id].constraints
    } == {
        ("salary_sacrifice.uses_pension_salary_sacrifice", "==", True),
        ("salary_sacrifice.annual_pension_contribution", ">", 2000),
    }
    assert {
        (constraint.variable, constraint.operator, constraint.value)
        for constraint in values_by_record[below_id].constraints
    } == {
        ("salary_sacrifice.uses_pension_salary_sacrifice", "==", True),
        ("salary_sacrifice.annual_pension_contribution", "<=", 2000),
    }


def test_source_package_alias_builds_hmt_budget_salary_sacrifice_fact():
    package = load_source_package("hmt-budget-policy-costings-2025-salary-sacrifice")
    cells = package.build_source_cells(2025)
    records = package.build_source_records(2025, cells=cells)
    facts = package.build_facts(2025, cells=cells)
    records_by_id = {record.source_record_id: record for record in records}
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert package.package_id == "hmt-budget-policy-costings-2025-salary-sacrifice"
    assert len(cells) == 15_690
    assert validate_source_cells(cells).valid
    assert len(facts) == 1
    assert validate_facts(facts).valid

    source_record_id = (
        "hmt_budget_2025.cy2024.salary_sacrifice_pension_contributions."
        "all_salary_sacrifice_pension_contributions.contribution_amount"
    )
    fact = values_by_record[source_record_id]
    assert records_by_id[source_record_id].source_cell_addresses == (
        "E1052",
        "E1",
        "A1052",
        "B1052",
        "D1052",
    )
    assert fact.value == 32_000_000_000
    assert fact.period.type == "calendar_year"
    assert fact.period.value == 2024
    assert fact.geography.id == "GBR"
    assert fact.entity.name == "person"
    assert fact.source.source_name == "hmt"
    assert fact.source.source_file == "Budget_2025_Policy_Costings.pdf"
    assert fact.source.raw_r2_uri
    assert fact.measure.concept == (
        "uk_pensions.pension_salary_sacrifice_contribution_amount"
    )
    assert fact.measure.source_concept == (
        "hmt.budget_2025.salary_sacrifice_pension_contribution_amount"
    )
    assert fact.measure.unit == "gbp"
    assert fact.filters[
        "salary_sacrifice.pension_contribution_arrangement"
    ] == "salary_sacrifice"


def test_source_package_alias_builds_isc_census_pupil_count_fact():
    package = load_source_package("isc-census-2024-pupil-count")
    cells = package.build_source_cells(2024)
    records = package.build_source_records(2024, cells=cells)
    facts = package.build_facts(2024, cells=cells)
    records_by_id = {record.source_record_id: record for record in records}
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert package.package_id == "isc-census-2024-pupil-count"
    assert len(cells) == 77_088
    assert validate_source_cells(cells).valid
    assert len(facts) == 1
    assert validate_facts(facts).valid
    assert all(fact.source.source_name == "isc" for fact in facts)
    assert all(fact.source.source_file == "isc_census_2024.pdf" for fact in facts)
    assert all(fact.source.raw_r2_uri for fact in facts)
    assert {f"{fact.period.type}:{fact.period.value}" for fact in facts} == {
        "calendar_year:2024"
    }
    assert {fact.geography.id for fact in facts} == {"GBR"}
    assert {fact.entity.name for fact in facts} == {"person"}

    source_record_id = (
        "isc.cy2024.census.pupil_count.isc_member_school_pupils.pupil_count"
    )
    assert records_by_id[source_record_id].source_cell_addresses == (
        "E147",
        "E1",
        "A147",
        "B147",
        "D147",
    )
    assert values_by_record[source_record_id].value == 556_551
    assert values_by_record[source_record_id].filters["school.sector"] == (
        "independent"
    )
    assert values_by_record[source_record_id].measure.unit == "persons"


def test_source_package_alias_builds_hmrc_spi_income_band_facts():
    package = load_source_package("hmrc-spi-income-bands-2023")
    cells = package.build_source_cells(2023)
    records = package.build_source_records(2023, cells=cells)
    facts = package.build_facts(2023, cells=cells)
    records_by_id = {record.source_record_id: record for record in records}
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert package.package_id == "hmrc-spi-income-bands-2023"
    assert len(cells) == 18_586
    assert validate_source_cells(cells).valid
    assert len(facts) == 156
    assert validate_facts(facts).valid
    assert all(fact.source.source_name == "hmrc_spi" for fact in facts)
    assert all(
        fact.source.source_file == "Collated_Tables_3_1_to_3_17_2223.ods"
        for fact in facts
    )
    assert all(fact.source.raw_r2_uri for fact in facts)
    assert {f"{fact.period.type}:{fact.period.value}" for fact in facts} == {
        "tax_year:2022-23"
    }
    assert all(fact.geography.id == "GBR" for fact in facts)

    employment_id = (
        "hmrc_spi.ty2022_23.table_3_6.income_by_total_income_band."
        "12k_to_15k.employment_income_amount"
    )
    self_employment_top_id = (
        "hmrc_spi.ty2022_23.table_3_6.income_by_total_income_band."
        "1m_plus.self_employment_income_amount"
    )
    property_id = (
        "hmrc_spi.ty2022_23.table_3_7.income_by_total_income_band."
        "12k_to_15k.property_income_amount"
    )
    dividend_top_id = (
        "hmrc_spi.ty2022_23.table_3_7.income_by_total_income_band."
        "1m_plus.dividend_income_amount"
    )
    assert records_by_id[employment_id].source_cell_addresses == ("F6", "F5")
    assert records_by_id[property_id].source_cell_addresses == ("C6", "C5")
    assert values_by_record[employment_id].value == 17_900_000_000
    assert values_by_record[self_employment_top_id].value == 21_400_000_000
    assert values_by_record[property_id].value == 696_000_000
    assert values_by_record[dividend_top_id].value == 10_400_000_000
    assert (
        "total_income",
        "<",
        15_000,
    ) in {
        (constraint.variable, constraint.operator, constraint.value)
        for constraint in values_by_record[employment_id].constraints
    }
    assert {
        (constraint.variable, constraint.operator, constraint.value)
        for constraint in values_by_record[self_employment_top_id].constraints
    } == {("total_income", ">=", 1_000_000)}


def test_source_package_alias_builds_hmrc_spi_projection_facts():
    package = load_source_package("hmrc-spi-income-projection-2026")
    source_rows = package.build_source_rows(2026)
    cells = package.build_source_cells(2026, source_rows=source_rows)
    records = package.build_source_records(2026, cells=cells)
    facts = package.build_facts(2026, cells=cells)
    records_by_id = {record.source_record_id: record for record in records}
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert package.package_id == "hmrc-spi-income-projection-2026"
    assert len(source_rows) == 112
    assert validate_source_rows(source_rows).valid
    assert len(cells) == 221
    assert validate_source_cells(cells).valid
    assert len(facts) == 144
    assert validate_facts(facts).valid
    assert all(fact.source.source_name == "hmrc_spi" for fact in facts)
    assert all(fact.source.source_file == "incomes_projection.csv" for fact in facts)
    assert all(fact.source.raw_r2_uri for fact in facts)
    assert {f"{fact.period.type}:{fact.period.value}" for fact in facts} == {
        "calendar_year:2026"
    }
    assert all(fact.geography.id == "GBR" for fact in facts)

    employment_id = (
        "hmrc_spi.cy2026.income_projection.by_total_income_band."
        "12k_to_15k.employment_income_amount"
    )
    property_id = (
        "hmrc_spi.cy2026.income_projection.by_total_income_band."
        "12k_to_15k.property_income_amount"
    )
    dividend_id = (
        "hmrc_spi.cy2026.income_projection.by_total_income_band."
        "500k_to_1m.dividend_income_amount"
    )
    assert records_by_id[employment_id].source_cell_addresses == (
        "D2",
        "D1",
        "B2",
        "Q2",
    )
    assert records_by_id[property_id].source_cell_addresses == (
        "L2",
        "L1",
        "B2",
        "Q2",
    )
    assert values_by_record[employment_id].value == 4_003_725_725
    assert values_by_record[property_id].value == 46_028_865
    assert values_by_record[dividend_id].value == 6_422_119_621
    assert values_by_record[property_id].measure.source_concept == (
        "policyengine_uk_data.incomes_projection.property_income_amount"
    )
    assert values_by_record[property_id].measure.concept_relation == "approximate"
    assert (
        "total_income",
        "<",
        15_000,
    ) in {
        (constraint.variable, constraint.operator, constraint.value)
        for constraint in values_by_record[property_id].constraints
    }


def test_source_package_alias_builds_hmrc_spi_local_income_facts():
    package = load_source_package("hmrc-spi-local-income-2022")
    rows = package.build_source_rows(2022)
    cells = package.build_source_cells(2022, source_rows=rows)
    records = package.build_source_records(2022, cells=cells, source_rows=rows)
    facts = package.build_facts(2022, cells=cells, source_rows=rows)
    records_by_id = {record.source_record_id: record for record in records}
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert package.package_id == "hmrc-spi-local-income-2022"
    assert rows == []
    assert len(cells) == 86_635
    assert validate_source_cells(cells).valid
    assert len(facts) == 4_088
    assert validate_facts(facts).valid
    assert all(fact.source.source_name == "hmrc_spi" for fact in facts)
    assert all(
        fact.source.source_file == "Collated_Tables_3_12_to_3_15a_2122.ods"
        for fact in facts
    )
    assert all(fact.source.raw_r2_uri for fact in facts)
    assert {f"{fact.period.type}:{fact.period.value}" for fact in facts} == {
        "tax_year:2021-22"
    }
    assert {fact.geography.level for fact in facts} == {
        "local_authority",
        "parliamentary_constituency",
    }

    hartlepool_count_id = (
        "hmrc_spi.ty2021_22.table_3_14.local_authority_income."
        "e06000001.self_employment_income_taxpayer_count"
    )
    hartlepool_employment_mean_id = (
        "hmrc_spi.ty2021_22.table_3_14.local_authority_income."
        "e06000001.employment_income_mean"
    )
    aldershot_employment_count_id = (
        "hmrc_spi.ty2021_22.table_3_15.parliamentary_constituency_income."
        "e14000530.employment_income_taxpayer_count"
    )
    aldershot_self_employment_mean_id = (
        "hmrc_spi.ty2021_22.table_3_15.parliamentary_constituency_income."
        "e14000530.self_employment_income_mean"
    )

    assert records_by_id[hartlepool_count_id].source_cell_addresses == (
        "C9",
        "C5",
        "B9",
    )
    assert records_by_id[hartlepool_employment_mean_id].source_cell_addresses == (
        "G9",
        "G5",
        "B9",
    )
    assert records_by_id[aldershot_employment_count_id].source_cell_addresses == (
        "F408",
        "F5",
        "B408",
    )
    assert records_by_id[aldershot_self_employment_mean_id].source_cell_addresses == (
        "D408",
        "D5",
        "B408",
    )
    assert values_by_record[hartlepool_count_id].value == 3_000
    assert values_by_record[hartlepool_employment_mean_id].value == 29_600
    assert values_by_record[aldershot_employment_count_id].value == 46_000
    assert values_by_record[aldershot_self_employment_mean_id].value == 20_600
    assert values_by_record[hartlepool_count_id].geography.id == "E06000001"
    assert values_by_record[aldershot_employment_count_id].geography.id == ("E14000530")
    assert {
        (constraint.variable, constraint.operator, constraint.value)
        for constraint in values_by_record[hartlepool_count_id].constraints
    } == {("income_source", "==", "self_employment_income")}
    assert {
        (constraint.variable, constraint.operator, constraint.value)
        for constraint in values_by_record[aldershot_employment_count_id].constraints
    } == {("income_source", "==", "employment_income")}


def test_source_package_alias_builds_ons_savings_interest_income_fact():
    package = load_source_package("ons-savings-interest-income")
    rows = package.build_source_rows(2023)
    cells = package.build_source_cells(2023, source_rows=rows)
    records = package.build_source_records(2023, cells=cells, source_rows=rows)
    facts = package.build_facts(2023, cells=cells, source_rows=rows)
    records_by_id = {record.source_record_id: record for record in records}
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert package.package_id == "ons-savings-interest-income"
    annual_rows = [row for row in rows if row.values["frequency"] == "annual"]
    quarterly_rows = [row for row in rows if row.values["frequency"] == "quarterly"]
    assert len(rows) == 195
    assert len(annual_rows) == 39
    assert len(quarterly_rows) == 156
    assert annual_rows[-1].values["year"] == 2025
    assert annual_rows[-1].values["value"] == 95_576
    assert validate_source_rows(rows).valid
    assert len(cells) == 30
    assert validate_source_cells(cells).valid
    assert len(facts) == 1
    assert validate_facts(facts).valid
    assert all(fact.source_row_keys for fact in facts)
    assert all(fact.source.source_name == "ons" for fact in facts)
    assert all(
        fact.source.source_file == "ons_haxv_savings_interest_timeseries.json"
        for fact in facts
    )
    assert all(fact.source.raw_r2_uri for fact in facts)

    record_id = "ons_ukea.cy2023.haxv_savings_interest_income.haxv.amount"
    assert records_by_id[record_id].source_cell_addresses == ("H2", "H1")
    assert values_by_record[record_id].value == 86_040_000_000
    assert values_by_record[record_id].period.type == "calendar_year"
    assert values_by_record[record_id].period.value == 2023
    assert {
        (constraint.variable, constraint.operator, constraint.value)
        for constraint in values_by_record[record_id].constraints
    } == {
        ("frequency", "==", "annual"),
        ("ons_series_id", "==", "HAXV"),
    }

    cells_2025 = package.build_source_cells(2025, source_rows=rows)
    [fact_2025] = package.build_facts(2025, cells=cells_2025, source_rows=rows)
    assert fact_2025.source_record_id == (
        "ons_ukea.cy2025.haxv_savings_interest_income.haxv.amount"
    )
    assert fact_2025.value == 95_576_000_000


def test_source_package_alias_builds_ons_private_rent_fact():
    package = load_source_package("ons-private-rent-house-prices-march-2026")
    cells = package.build_source_cells(2026)
    records = package.build_source_records(2026, cells=cells)
    facts = package.build_facts(2026, cells=cells)
    records_by_id = {record.source_record_id: record for record in records}
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert package.package_id == "ons-private-rent-house-prices-march-2026"
    assert len(cells) == 1195
    assert validate_source_cells(cells).valid
    assert len(facts) == 1
    assert validate_facts(facts).valid
    assert all(fact.source.source_name == "ons" for fact in facts)
    assert all(
        fact.source.source_file == "ons_private_rent_house_prices_march_2026.html"
        for fact in facts
    )
    assert all(fact.source.raw_r2_uri for fact in facts)

    record_id = (
        "ons_prhi.month2026_02.uk_private_rent.private_rent.average_monthly_rent"
    )
    assert records_by_id[record_id].source_cell_addresses == ("E101", "E1")
    assert values_by_record[record_id].value == 1374
    assert values_by_record[record_id].period.type == "month"
    assert values_by_record[record_id].period.value == "2026-02"
    assert values_by_record[record_id].geography.id == "GBR"
    assert values_by_record[record_id].entity.name == "dwelling"
    assert {
        (constraint.variable, constraint.operator, constraint.value)
        for constraint in values_by_record[record_id].constraints
    } == {("housing.tenure", "==", "private_rent")}


def test_source_package_alias_builds_mhclg_ehs_social_rent_fact():
    package = load_source_package("mhclg-english-housing-survey-rented-sectors-2023-24")
    cells = package.build_source_cells(2024)
    records = package.build_source_records(2024, cells=cells)
    facts = package.build_facts(2024, cells=cells)
    records_by_id = {record.source_record_id: record for record in records}
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert package.package_id == ("mhclg-english-housing-survey-rented-sectors-2023-24")
    assert len(cells) == 6915
    assert validate_source_cells(cells).valid
    assert len(facts) == 1
    assert validate_facts(facts).valid
    assert all(fact.source.source_name == "mhclg" for fact in facts)
    assert all(
        fact.source.source_file == "english_housing_survey_2023_24_rented_sectors.html"
        for fact in facts
    )
    assert all(fact.source.raw_r2_uri for fact in facts)

    record_id = (
        "mhclg_ehs.fy2023_24.social_rent_weekly_costs.social_rent.mean_weekly_rent"
    )
    assert records_by_id[record_id].source_cell_addresses == ("E238", "E1")
    assert values_by_record[record_id].value == 118
    assert values_by_record[record_id].period.type == "fiscal_year"
    assert values_by_record[record_id].period.value == "2023-24"
    assert values_by_record[record_id].geography.id == "E92000001"
    assert values_by_record[record_id].entity.name == "dwelling"
    assert {
        (constraint.variable, constraint.operator, constraint.value)
        for constraint in values_by_record[record_id].constraints
    } == {("housing.tenure", "==", "social_rent")}


def test_source_package_alias_builds_ons_population_projection_facts():
    package = load_source_package("ons-uk-population-projections-2022")
    cells = package.build_source_cells(2022)
    records = package.build_source_records(2022, cells=cells)
    facts = package.build_facts(2022, cells=cells)
    records_by_id = {record.source_record_id: record for record in records}
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert package.package_id == "ons-uk-population-projections-2022"
    assert len(cells) == 338_735
    assert validate_source_cells(cells).valid
    assert len(facts) == 13
    assert validate_facts(facts).valid
    assert all(fact.source.source_name == "ons" for fact in facts)
    assert all(
        fact.source.source_file == "uk_population_projections_2022_based_uk.zip!"
        "uk/uk_ppp_machine_readable.xlsx"
        for fact in facts
    )
    assert all(
        fact.source.source_sha256
        == "7e05ff530230cd48cb2624879b29c410ecdb237bd78b74f4acb5cb74609df1ef"
        for fact in facts
    )
    assert all(fact.source.raw_r2_uri for fact in facts)
    assert all(fact.geography.id == "GBR" for fact in facts)
    assert (
        len(
            records_by_id[
                "ons_population_projection.cy2022.uk_population_by_age_gender."
                "all.population_count"
            ].source_cell_addresses
        )
        == 430
    )
    assert {
        "B2",
        "A215",
        "B215",
    }.issubset(
        records_by_id[
            "ons_population_projection.cy2022.uk_population_by_age_gender."
            "all.population_count"
        ].source_cell_addresses
    )
    assert (
        values_by_record[
            "ons_population_projection.cy2022.uk_population_by_age_gender."
            "all.population_count"
        ].value
        == 67_602_761
    )
    assert (
        values_by_record[
            "ons_population_projection.cy2022.uk_population_by_age_gender."
            "female_0_14.population_count"
        ].value
        == 5_665_646
    )
    male_75_90 = values_by_record[
        "ons_population_projection.cy2022.uk_population_by_age_gender."
        "male_75_90.population_count"
    ]
    assert male_75_90.value == 2_507_317
    assert {
        (constraint.variable, constraint.operator, constraint.value)
        for constraint in male_75_90.constraints
    } == {
        ("person.gender", "==", "male"),
        ("person.age", ">=", 75),
        ("person.age", "<", 91),
    }

    future_values = {
        fact.source_record_id: fact.value
        for fact in package.build_facts(2029, cells=cells)
    }
    assert (
        future_values[
            "ons_population_projection.cy2029.uk_population_by_age_gender."
            "all.population_count"
        ]
        == 71_547_662
    )


def test_source_package_alias_builds_ons_demographics_profile_facts():
    package = load_source_package("ons-demographics-profile-2026")
    source_rows = package.build_source_rows(2026)
    cells = package.build_source_cells(2026, source_rows=source_rows)
    records = package.build_source_records(2026, cells=cells)
    facts = package.build_facts(2026, cells=cells)
    records_by_id = {record.source_record_id: record for record in records}
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert package.package_id == "ons-demographics-profile-2026"
    assert len(source_rows) == 138
    assert validate_source_rows(source_rows).valid
    assert len(cells) == 1_776
    assert validate_source_cells(cells).valid
    assert len(facts) == 110
    assert validate_facts(facts).valid
    assert all(fact.source.source_name == "ons" for fact in facts)
    assert all(fact.source.source_file == "demographics.csv" for fact in facts)
    assert all(fact.source.raw_r2_uri for fact in facts)

    east_id = (
        "ons.cy2026.policyengine_uk_demographics_profile."
        "east_age_0_9.population_count"
    )
    children_id = (
        "ons.cy2026.policyengine_uk_demographics_profile."
        "scotland_children_under_16.population_count"
    )
    babies_id = (
        "ons.cy2026.policyengine_uk_demographics_profile."
        "scotland_babies_under_1.population_count"
    )
    assert records_by_id[east_id].source_cell_addresses == ("L2", "B2", "C2")
    assert records_by_id[children_id].source_cell_addresses == (
        "L110",
        "B110",
        "C110",
    )
    assert values_by_record[east_id].value == 723_000
    assert values_by_record[children_id].value == 888_000
    assert values_by_record[babies_id].value == 46_000
    assert {
        (constraint.variable, constraint.operator, constraint.value)
        for constraint in values_by_record[east_id].constraints
    } == {
        ("name", "==", "east_age_0_9"),
        ("reference", "==", "ons_age_sex_region"),
    }


def test_source_package_alias_builds_ons_regional_land_profile_facts():
    package = load_source_package("ons-regional-land-profile-2026")
    source_rows = package.build_source_rows(2026)
    cells = package.build_source_cells(2026, source_rows=source_rows)
    records = package.build_source_records(2026, cells=cells)
    facts = package.build_facts(2026, cells=cells)
    records_by_id = {record.source_record_id: record for record in records}
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert package.package_id == "ons-regional-land-profile-2026"
    assert len(source_rows) == 11
    assert validate_source_rows(source_rows).valid
    assert len(cells) == 36
    assert validate_source_cells(cells).valid
    assert len(records) == 22
    assert len(facts) == 22
    assert validate_facts(facts).valid
    assert all(fact.source.source_name == "ons" for fact in facts)
    assert all(fact.source.source_file == "regional_land_values.csv" for fact in facts)
    assert all(fact.source.raw_r2_uri for fact in facts)

    avg_price_id = (
        "ons.cy2025.policyengine_uk_regional_land_profile."
        "NORTH_EAST.avg_house_price"
    )
    dwellings_id = (
        "ons.cy2025.policyengine_uk_regional_land_profile."
        "NORTH_EAST.dwellings"
    )
    assert records_by_id[avg_price_id].source_cell_addresses == ("B2", "B1")
    assert records_by_id[dwellings_id].source_cell_addresses == ("C2", "C1")
    assert values_by_record[avg_price_id].value == 165_257
    assert values_by_record[dwellings_id].value == 1_280_700
    assert {
        (constraint.variable, constraint.operator, constraint.value)
        for constraint in values_by_record[avg_price_id].constraints
    } == {
        ("region", "==", "NORTH_EAST"),
    }


def test_source_package_alias_builds_ons_families_households_facts():
    package = load_source_package("ons-families-households-2024")
    cells = package.build_source_cells(2024)
    records = package.build_source_records(2024, cells=cells)
    facts = package.build_facts(2024, cells=cells)
    records_by_id = {record.source_record_id: record for record in records}
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert package.package_id == "ons-families-households-2024"
    assert len(cells) == 86_145
    assert validate_source_cells(cells).valid
    assert len(facts) == 10
    assert validate_facts(facts).valid
    assert all(fact.source.source_name == "ons" for fact in facts)
    assert all(
        fact.source.source_file == "familiesandhouseholdsuk2024.xlsx" for fact in facts
    )
    assert all(fact.source.raw_r2_uri for fact in facts)
    assert all(fact.geography.id == "GBR" for fact in facts)
    assert {fact.entity.name for fact in facts} == {"household"}

    couple_3_plus = (
        "ons_families_households.cy2024.households_by_type."
        "couple_3_plus_dependent_children.households"
    )
    lone_parent = (
        "ons_families_households.cy2024.households_by_type."
        "lone_parent_dependent_children.households"
    )
    assert records_by_id[couple_3_plus].source_cell_addresses == ("CH21", "CH12")
    assert records_by_id[lone_parent].source_cell_addresses == ("CH24", "CH12")
    assert values_by_record[couple_3_plus].value == 963_000
    assert values_by_record[lone_parent].value == 1_881_000
    assert {
        (constraint.variable, constraint.operator, constraint.value)
        for constraint in values_by_record[couple_3_plus].constraints
    } == {
        (
            "uk_households.household_type",
            "==",
            "couple_3_plus_dependent_children",
        )
    }


def test_source_package_alias_builds_nrs_live_birth_fact():
    package = load_source_package("nrs-vital-events-reference-tables-2024")
    cells = package.build_source_cells(2024)
    records = package.build_source_records(2024, cells=cells)
    facts = package.build_facts(2024, cells=cells)
    records_by_id = {record.source_record_id: record for record in records}
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert package.package_id == "nrs-vital-events-reference-tables-2024"
    assert len(cells) == 8_820
    assert validate_source_cells(cells).valid
    assert len(facts) == 1
    assert validate_facts(facts).valid
    assert all(fact.source.source_name == "nrs" for fact in facts)
    assert all(
        fact.source.source_file == "vital-events-reference-tables-chapter-1.xlsx"
        for fact in facts
    )
    assert all(fact.source.raw_r2_uri for fact in facts)

    record_id = (
        "nrs_vital_events.cy2024.table_1_01b.scotland_live_births."
        "scotland.live_birth_count"
    )
    assert records_by_id[record_id].source_cell_addresses == ("E60", "E6", "A1", "A6")
    fact = values_by_record[record_id]
    assert fact.value == 45_763
    assert fact.geography.id == "S92000003"
    assert fact.entity.role == "live_birth"
    assert not fact.constraints


def test_source_package_alias_builds_nrs_children_under_16_fact():
    package = load_source_package("nrs-mid-year-population-estimates-2024")
    cells = package.build_source_cells(2024)
    records = package.build_source_records(2024, cells=cells)
    facts = package.build_facts(2024, cells=cells)
    records_by_id = {record.source_record_id: record for record in records}
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert package.package_id == "nrs-mid-year-population-estimates-2024"
    assert len(cells) == 18_347
    assert validate_source_cells(cells).valid
    assert len(facts) == 1
    assert validate_facts(facts).valid
    assert all(fact.source.source_name == "nrs" for fact in facts)
    assert all(
        fact.source.source_file == "data-mid-year-population-estimates-2024.xlsx"
        for fact in facts
    )
    assert all(fact.source.raw_r2_uri for fact in facts)

    record_id = (
        "nrs_population_estimates.cy2024.table_3.scotland_age_structure."
        "scotland.children_under_16_count"
    )
    assert records_by_id[record_id].source_cell_addresses == (
        "E6",
        "E5",
        "A1",
        "B6",
        "C6",
    )
    fact = values_by_record[record_id]
    assert fact.value == 896_833
    assert fact.geography.id == "S92000003"
    assert {
        (constraint.variable, constraint.operator, constraint.value)
        for constraint in fact.constraints
    } == {
        ("person.age", ">=", 0),
        ("person.age", "<", 16),
    }


def test_source_package_alias_builds_ons_dwelling_tenure_facts():
    package = load_source_package("ons-subnational-dwellings-by-tenure-2024")
    cells = package.build_source_cells(2024)
    facts = package.build_facts(2024, cells=cells)
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert package.package_id == "ons-subnational-dwellings-by-tenure-2024"
    assert len(cells) == 10_519
    assert validate_source_cells(cells).valid
    assert len(facts) == 5
    assert validate_facts(facts).valid
    assert all(fact.source.source_name == "ons" for fact in facts)
    assert all(
        fact.source.source_file == "subnationaldwellingsbytenure2024.xlsx"
        for fact in facts
    )
    assert all(fact.source.raw_r2_uri for fact in facts)
    assert {fact.entity.name for fact in facts} == {"dwelling"}
    assert all(fact.geography.id == "E92000001" for fact in facts)

    owned = values_by_record[
        "ons_spree.cy2024.england_dwelling_stock_by_tenure.england.owned_outright"
    ]
    private_rent = values_by_record[
        "ons_spree.cy2024.england_dwelling_stock_by_tenure.england.private_rent"
    ]
    total = values_by_record[
        "ons_spree.cy2024.england_dwelling_stock_total.england.total"
    ]
    assert owned.value == 8_374_612
    assert private_rent.value == 5_299_840
    assert total.value == 25_616_116
    assert {
        (constraint.variable, constraint.operator, constraint.value)
        for constraint in private_rent.constraints
    } == {("tenure_type", "==", "RENT_PRIVATELY")}
    assert not total.constraints


def test_source_package_alias_builds_ons_nbs_land_facts():
    package = load_source_package("ons-national-balance-sheet-land-2025")
    cells = package.build_source_cells(2024)
    facts = package.build_facts(2024, cells=cells)
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert package.package_id == "ons-national-balance-sheet-land-2025"
    assert len(cells) == 44_708
    assert validate_source_cells(cells).valid
    assert len(facts) == 5
    assert validate_facts(facts).valid
    assert all(fact.source.source_name == "ons" for fact in facts)
    assert all(
        fact.source.source_file == "nbsreferencetables2025.xlsx" for fact in facts
    )
    assert all(fact.source.raw_r2_uri for fact in facts)
    assert {fact.entity.name for fact in facts} == {"institutional_sector"}
    assert all(fact.geography.id == "GBR" for fact in facts)

    total = values_by_record[
        "ons_nbs.cy2024.table_2.total_economy_land.total_economy.land_value"
    ]
    households = values_by_record[
        "ons_nbs.cy2024.table_11.households_land.households.land_value"
    ]
    private_corporations = values_by_record[
        "ons_nbs.cy2024.table_5.private_non_financial_corporations_land."
        "private_non_financial_corporations.land_value"
    ]
    assert total.value == 7_117_771_000_000
    assert households.value == 4_559_831_000_000
    assert private_corporations.value == 1_794_111_000_000
    assert {
        (constraint.variable, constraint.operator, constraint.value)
        for constraint in households.constraints
    } == {("national_accounts.institutional_sector", "==", "households")}


def test_ons_population_projection_range_guard_fails_on_shifted_endpoint():
    package = load_source_package("ons-uk-population-projections-2022")
    cells = package.build_source_cells(2022)
    spec = package.build_source_record_specs(2022)[1]
    end_age_guard = replace(
        spec.selector.guard_cells[-1],
        expected_value=15,
    )
    bad_spec = replace(
        spec,
        selector=replace(
            spec.selector,
            guard_cells=(*spec.selector.guard_cells[:-1], end_age_guard),
        ),
    )

    with pytest.raises(ValueError, match="expected end age"):
        resolve_source_record(cells, bad_spec)


def test_ons_population_projection_range_label_guard_fails_on_interior_shift():
    package = load_source_package("ons-uk-population-projections-2022")
    cells = package.build_source_cells(2022)
    spec = package.build_source_record_specs(2022)[1]
    [age_sequence_guard] = spec.selector.range_label_guards
    bad_age_sequence_guard = replace(
        age_sequence_guard,
        expected_values=(
            age_sequence_guard.expected_values[0],
            age_sequence_guard.expected_values[2],
            *age_sequence_guard.expected_values[2:],
        ),
    )
    bad_spec = replace(
        spec,
        selector=replace(
            spec.selector,
            range_label_guards=(bad_age_sequence_guard,),
        ),
    )

    with pytest.raises(ValueError, match="expected age sequence B3"):
        resolve_source_record(cells, bad_spec)


def test_ons_population_projection_range_label_guard_rejects_null():
    package = load_source_package("ons-uk-population-projections-2022")
    cells = package.build_source_cells(2022)
    spec = package.build_source_record_specs(2022)[1]
    [age_sequence_guard] = spec.selector.range_label_guards
    null_age_sequence_guard = replace(
        age_sequence_guard,
        expected_values=(
            age_sequence_guard.expected_values[0],
            None,
            *age_sequence_guard.expected_values[2:],
        ),
    )
    bad_spec = replace(
        spec,
        selector=replace(
            spec.selector,
            range_label_guards=(null_age_sequence_guard,),
        ),
    )

    with pytest.raises(ValueError, match="must not contain null"):
        resolve_source_record(cells, bad_spec)


def test_source_package_alias_builds_voa_council_tax_band_facts():
    package = load_source_package("voa-council-tax-bands-2025")
    cells = package.build_source_cells(2025)
    records = package.build_source_records(2025, cells=cells)
    facts = package.build_facts(2025, cells=cells)
    records_by_id = {record.source_record_id: record for record in records}
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert package.package_id == "voa-council-tax-bands-2025"
    assert len(cells) == 14_262
    assert validate_source_cells(cells).valid
    assert len(facts) == 2_653
    assert validate_facts(facts).valid
    assert all(fact.source.source_name == "voa" for fact in facts)
    assert all(
        fact.source.source_file == "2025_CT_SoP_Summary_Tables.xlsx" for fact in facts
    )
    assert all(fact.source.raw_r2_uri for fact in facts)
    assert {fact.entity.name for fact in facts} == {"dwelling"}
    assert {f"{fact.period.type}:{fact.period.value}" for fact in facts} == {
        "calendar_year:2025"
    }

    north_east_band_a = (
        "voa.ctsop2025.table_2.region_council_tax_bands.north_east.band_a"
    )
    wales_total = "voa.ctsop2025.table_2.region_council_tax_bands.wales.total"
    assert records_by_id[north_east_band_a].source_cell_addresses == ("E8", "E5")
    assert records_by_id[wales_total].source_cell_addresses == ("N560", "N5")
    assert values_by_record[north_east_band_a].value == 667_540
    assert values_by_record[wales_total].value == 1_484_410
    assert values_by_record[north_east_band_a].geography.id == "E12000001"
    assert values_by_record[wales_total].geography.id == "W92000004"
    assert {
        (constraint.variable, constraint.operator, constraint.value)
        for constraint in values_by_record[north_east_band_a].constraints
    } == {
        ("council_tax_band", "==", "A"),
        ("uk_region", "==", "NORTH_EAST"),
    }
    assert {
        (constraint.variable, constraint.operator, constraint.value)
        for constraint in values_by_record[wales_total].constraints
    } == {("uk_region", "==", "WALES")}


def test_source_package_alias_builds_scotgov_council_tax_band_facts():
    package = load_source_package("scotgov-council-tax-bands-2025")
    cells = package.build_source_cells(2025)
    records = package.build_source_records(2025, cells=cells)
    facts = package.build_facts(2025, cells=cells)
    records_by_id = {record.source_record_id: record for record in records}
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert package.package_id == "scotgov-council-tax-bands-2025"
    assert len(cells) == 546
    assert validate_source_cells(cells).valid
    assert len(facts) == 9
    assert validate_facts(facts).valid
    assert all(fact.source.source_name == "scottish_government" for fact in facts)
    assert all(
        fact.source.source_file == "CTAXBASE_2025_Tables_Chargeable_Dwellings.xlsx"
        for fact in facts
    )
    assert all(fact.source.raw_r2_uri for fact in facts)
    assert {fact.entity.name for fact in facts} == {"dwelling"}
    assert all(fact.geography.id == "S92000003" for fact in facts)

    band_a = "scotgov.ctaxbase2025.chargeable_dwellings_by_band.scotland.band_a"
    total = "scotgov.ctaxbase2025.chargeable_dwellings_by_band.scotland.total"
    assert records_by_id[band_a].source_cell_addresses == ("B8", "B5")
    assert records_by_id[total].source_cell_addresses == ("J8", "J5")
    assert values_by_record[band_a].value == 498_707
    assert values_by_record[total].value == 2_623_149
    assert {
        (constraint.variable, constraint.operator, constraint.value)
        for constraint in values_by_record[band_a].constraints
    } == {
        ("council_tax_band", "==", "A"),
        ("uk_region", "==", "SCOTLAND"),
    }


def test_source_package_alias_builds_scotgov_scottish_child_payment_facts():
    package = load_source_package(
        "scotgov-scottish-budget-social-security-assistance-2026"
    )
    cells = package.build_source_cells(2026)
    records = package.build_source_records(2026, cells=cells)
    facts = package.build_facts(2026, cells=cells)
    records_by_id = {record.source_record_id: record for record in records}
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert (
        package.package_id == "scotgov-scottish-budget-social-security-assistance-2026"
    )
    assert len(cells) == 645
    assert validate_source_cells(cells).valid
    assert len(facts) == 2
    assert validate_facts(facts).valid
    assert all(fact.source.source_name == "scottish_government" for fact in facts)
    assert all(
        fact.source.source_file
        == "scottish_budget_2026_2027_chapter_5_social_justice.html"
        for fact in facts
    )
    assert all(fact.source.raw_r2_uri for fact in facts)
    assert {fact.period.value for fact in facts} == {"2026-27", "2027-28"}
    assert all(fact.geography.id == "S92000003" for fact in facts)
    assert records_by_id[
        "scotgov_budget.fy2026.social_security_assistance."
        "scottish_child_payment.scottish_child_payment.spend"
    ].source_cell_addresses == ("D16", "D1")
    latest_fact = values_by_record[
        "scotgov_budget.fy2026.social_security_assistance."
        "scottish_child_payment.scottish_child_payment.spend"
    ]
    assert latest_fact.value == 484_800_000

    prior_values = {
        fact.period.value: fact.value
        for year in (2024, 2025)
        for fact in package.build_facts(year)
        if fact.source_record_id.endswith(
            "scottish_child_payment.scottish_child_payment.spend"
        )
    }
    assert prior_values == {
        "2024-25": 455_800_000,
        "2025-26": 471_000_000,
    }
    assert {
        (constraint.variable, constraint.operator, constraint.value)
        for constraint in latest_fact.constraints
    } == {
        ("uk_social_security.benefit", "==", "scottish_child_payment"),
        ("uk_public_sector.budget_portfolio", "==", "social_justice"),
        (
            "uk_public_sector.budget_level_2",
            "==",
            "social_security_assistance",
        ),
    }
    under_1_record = (
        "scotgov_budget.fy2027_28.social_security_assistance."
        "scottish_child_payment_under_1_children."
        "scottish_child_payment_under_1.recipient_child_count"
    )
    assert records_by_id[under_1_record].source_cell_addresses == (
        "E39",
        "E1",
        "B39",
    )
    assert values_by_record[under_1_record].value == 12_000
    assert values_by_record[under_1_record].period.value == "2027-28"
    assert {
        (constraint.variable, constraint.operator, constraint.value)
        for constraint in values_by_record[under_1_record].constraints
    } == {
        ("uk_social_security.benefit", "==", "scottish_child_payment"),
        ("person.age", "<", 1),
    }


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
    assert (
        values_by_record[
            "cms_aca.oep2025.state_marketplace.ca.average_monthly_aptc"
        ].value
        == 562
    )


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
            "cms_aca.effectuated_enrollment.2022.state_marketplace.ca."
            "average_monthly_aptc"
        ].value
        == 469.44
    )


def test_source_package_alias_builds_kff_marketplace_effectuated_enrollment_facts():
    package = load_source_package("kff-marketplace-effectuated-enrollment")
    rows = package.build_source_rows(2022)
    cells = package.build_source_cells(2022, source_rows=rows)
    records = package.build_source_records(2022, cells=cells, source_rows=rows)
    facts = package.build_facts(2022, cells=cells, source_rows=rows)
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
    assert len(cells) == 260
    assert len(facts) == 51
    assert validate_facts(facts).valid
    assert all(fact.source_row_keys for fact in facts)
    assert all(fact.source.source_name == "kff" for fact in facts)
    assert all(fact.source.source_file.endswith(".html") for fact in facts)
    assert all(fact.source.raw_r2_uri for fact in facts)
    assert records_by_id[
        "kff.marketplace_effectuated_enrollment.2022.state.al."
        "total_effectuated_marketplace_enrollment"
    ].source_cell_addresses == ("C2", "C1")
    assert (
        values_by_record[
            "kff.marketplace_effectuated_enrollment.2022.state.al."
            "total_effectuated_marketplace_enrollment"
        ].value
        == 202_847
    )
    assert (
        values_by_record[
            "kff.marketplace_effectuated_enrollment.2022.state.ca."
            "total_effectuated_marketplace_enrollment"
        ].value
        == 1_701_375
    )

    facts_2024 = package.build_facts(2024)
    values_2024 = {fact.source_record_id: fact for fact in facts_2024}
    assert (
        values_2024[
            "kff.marketplace_effectuated_enrollment.2024.state.al."
            "total_effectuated_marketplace_enrollment"
        ].value
        == 396_750
    )
    assert (
        values_2024[
            "kff.marketplace_effectuated_enrollment.2024.state.ca."
            "total_effectuated_marketplace_enrollment"
        ].value
        == 1_795_695
    )


def test_source_package_alias_builds_cms_medicaid_monthly_state_facts():
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
        fact.source.source_file == "pi-dataset-april-2026-release.csv" for fact in facts
    )
    assert all(fact.source.raw_r2_uri for fact in facts)
    assert {f"{fact.period.type}:{fact.period.value}" for fact in facts} == {
        "month:2025-12"
    }
    ca_total = (
        "cms_medicaid.month2025_12.state_enrollment.ca.total_medicaid_chip_enrollment"
    )
    ca_medicaid = (
        "cms_medicaid.month2025_12.state_enrollment.ca.total_medicaid_enrollment"
    )
    ca_chip = "cms_medicaid.month2025_12.state_enrollment.ca.total_chip_enrollment"
    ca_child = (
        "cms_medicaid.month2025_12.state_enrollment.ca.medicaid_chip_child_enrollment"
    )
    ca_adult = (
        "cms_medicaid.month2025_12.state_enrollment.ca.total_adult_medicaid_enrollment"
    )
    tx_total = (
        "cms_medicaid.month2025_12.state_enrollment.tx.total_medicaid_chip_enrollment"
    )
    ny_total = (
        "cms_medicaid.month2025_12.state_enrollment.ny.total_medicaid_chip_enrollment"
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


def test_source_package_alias_builds_cms_medicaid_december_2024_facts():
    package = load_source_package("cms-medicaid-chip-monthly-enrollment-december-2024")
    rows = package.build_source_rows(2024)
    cells = package.build_source_cells(2024, source_rows=rows)
    records = package.build_source_records(2024, cells=cells, source_rows=rows)
    facts = package.build_facts(2024, cells=cells, source_rows=rows)
    records_by_id = {record.source_record_id: record for record in records}
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert package.package_id == ("cms-medicaid-chip-monthly-enrollment-december-2024")
    assert len(rows) == 10_608
    assert validate_source_rows(rows).valid
    assert validate_source_cells(cells).valid
    assert len(cells) == 2_288
    assert len(facts) == 255
    assert validate_facts(facts).valid
    assert all(fact.source_row_keys for fact in facts)
    assert all(fact.source.raw_r2_uri for fact in facts)
    assert {f"{fact.period.type}:{fact.period.value}" for fact in facts} == {
        "month:2024-12"
    }

    ca_total = (
        "cms_medicaid.month2024_12.state_enrollment.ca.total_medicaid_chip_enrollment"
    )
    ca_medicaid = (
        "cms_medicaid.month2024_12.state_enrollment.ca.total_medicaid_enrollment"
    )
    al_medicaid = (
        "cms_medicaid.month2024_12.state_enrollment.al.total_medicaid_enrollment"
    )
    ak_medicaid = (
        "cms_medicaid.month2024_12.state_enrollment.ak.total_medicaid_enrollment"
    )

    assert records_by_id[ca_total].source_cell_addresses == (
        "U6",
        "U1",
        "C6",
        "E6",
        "F6",
    )
    assert values_by_record[ca_total].value == 13_487_072
    assert values_by_record[ca_medicaid].value == 12_254_163
    assert values_by_record[al_medicaid].value == 772_748
    assert values_by_record[ak_medicaid].value == 232_106
    assert values_by_record[ca_total].geography.id == "0400000US06"


def test_source_package_alias_builds_cms_medicare_state_payment_facts():
    package = load_source_package("cms-medicare-state-payment-of-premiums")
    cells = package.build_source_cells(2026)
    records = package.build_source_records(2026, cells=cells)
    facts = package.build_facts(2026, cells=cells)
    records_by_id = {record.source_record_id: record for record in records}
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert package.package_id == "cms-medicare-state-payment-of-premiums"
    assert len(cells) == 185
    assert validate_source_cells(cells).valid
    assert len(facts) == 2
    assert validate_facts(facts).valid
    assert all(fact.source.source_name == "cms_medicare" for fact in facts)
    assert all(fact.source.raw_r2_uri for fact in facts)

    part_b_id = (
        "cms_medicare.cy2026.state_paid_premiums.part_b.part_b."
        "beneficiary_count_lower_bound"
    )
    part_a_id = (
        "cms_medicare.cy2026.state_paid_premiums.part_a.part_a."
        "beneficiary_count_lower_bound"
    )
    assert records_by_id[part_b_id].source_cell_addresses == ("E10", "E1")
    assert records_by_id[part_a_id].source_cell_addresses == ("E11", "E1")
    assert values_by_record[part_b_id].value == 10_000_000
    assert values_by_record[part_a_id].value == 700_000
    assert values_by_record[part_b_id].filters["estimate.bound_type"] == ("lower_bound")
    assert values_by_record[part_a_id].constraints[0].variable == (
        "medicare.premium_part"
    )


def test_source_package_alias_builds_cms_medicare_trustees_part_b_premium_fact():
    package = load_source_package(
        "cms-medicare-trustees-report-2025-part-b-premium-income"
    )
    cells = package.build_source_cells(2025)
    records = package.build_source_records(2025, cells=cells)
    facts = package.build_facts(2025, cells=cells)
    records_by_id = {record.source_record_id: record for record in records}
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert (
        package.package_id == "cms-medicare-trustees-report-2025-part-b-premium-income"
    )
    assert len(cells) == 93_486
    assert validate_source_cells(cells).valid
    assert len(facts) == 1
    assert validate_facts(facts).valid
    assert all(fact.source.source_name == "cms_medicare" for fact in facts)
    assert all(fact.source.raw_r2_uri for fact in facts)

    source_record_id = (
        "cms_medicare.cy2024.part_b_premium_income."
        "premiums_from_enrollees.actual_amount"
    )
    assert records_by_id[source_record_id].source_cell_addresses == (
        "E3356",
        "E1",
        "A3356",
        "B3356",
        "D3356",
        "F3356",
    )
    assert values_by_record[source_record_id].value == 139_837_000_000
    assert values_by_record[source_record_id].filters["amount_basis"] == "actual"
    assert values_by_record[source_record_id].measure.unit == "usd"


def test_source_package_alias_builds_treasury_eitc_outlay_fact():
    package = load_source_package("treasury-tax-expenditures-fy2023-eitc-outlays")
    cells = package.build_source_cells(2023)
    records = package.build_source_records(2023, cells=cells)
    facts = package.build_facts(2023, cells=cells)
    records_by_id = {record.source_record_id: record for record in records}
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert package.package_id == "treasury-tax-expenditures-fy2023-eitc-outlays"
    assert len(cells) == 52_986
    assert validate_source_cells(cells).valid
    assert len(facts) == 1
    assert validate_facts(facts).valid
    assert all(fact.source.source_name == "treasury" for fact in facts)
    assert all(fact.source.raw_r2_uri for fact in facts)

    source_record_id = (
        "treasury.fy2023.tax_expenditures.eitc_outlay_effects."
        "earned_income_tax_credit.outlay_effect_amount"
    )
    assert records_by_id[source_record_id].source_cell_addresses == (
        "E3224",
        "E1",
        "A3224",
        "B3224",
        "D3224",
        "F3224",
    )
    assert values_by_record[source_record_id].value == 64_440_000_000
    assert (
        values_by_record[source_record_id].filters["tax_expenditure.provision"]
        == "earned_income_tax_credit"
    )
    assert values_by_record[source_record_id].measure.unit == "usd"


def test_source_package_alias_builds_jct_mortgage_interest_deduction_fact():
    package = load_source_package(
        "jct-tax-expenditures-2024-mortgage-interest-deduction"
    )
    cells = package.build_source_cells(2024)
    records = package.build_source_records(2024, cells=cells)
    facts = package.build_facts(2024, cells=cells)
    records_by_id = {record.source_record_id: record for record in records}
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert package.package_id == "jct-tax-expenditures-2024-mortgage-interest-deduction"
    assert len(cells) == 15_918
    assert validate_source_cells(cells).valid
    assert len(facts) == 1
    assert validate_facts(facts).valid
    assert all(fact.source.source_name == "jct" for fact in facts)
    assert all(fact.source.raw_r2_uri for fact in facts)

    source_record_id = (
        "jct.fy2024.tax_expenditures.mortgage_interest_deduction."
        "mortgage_interest_owner_occupied_residences."
        "individual_tax_expenditure_amount"
    )
    assert records_by_id[source_record_id].source_cell_addresses == (
        "E963",
        "E1",
        "A963",
        "B963",
        "D963",
        "F963",
    )
    assert values_by_record[source_record_id].value == 24_800_000_000
    assert (
        values_by_record[source_record_id].filters["tax_expenditure.provision"]
        == "mortgage_interest_owner_occupied_residences"
    )
    assert values_by_record[source_record_id].filters["taxpayer_scope"] == "individuals"
    assert values_by_record[source_record_id].measure.unit == "usd"


def test_source_package_alias_builds_cms_nhe_historical_service_fact():
    package = load_source_package("cms-nhe-historical-service-source")
    cells = package.build_source_cells(2024)
    facts = package.build_facts(2024, cells=cells)

    assert package.package_id == "cms-nhe-historical-service-source"
    assert validate_source_cells(cells).valid
    assert validate_facts(facts).valid
    assert len(cells) == 35_970
    assert len(facts) == 1
    fact = facts[0]
    assert fact.value == 931_692_000_000
    assert fact.source.source_file.endswith(".zip!NHE2024.xls")
    assert fact.source.raw_r2_uri
    assert not fact.filters
    assert not fact.constraints


def test_source_package_alias_builds_census_stc_income_tax_facts():
    package = load_source_package("census-stc-individual-income-tax")
    rows = package.build_source_rows(2024)
    cells = package.build_source_cells(2024, source_rows=rows)
    facts = package.build_facts(2024, cells=cells, source_rows=rows)
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert package.package_id == "census-stc-individual-income-tax"
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
    assert ca_fact_2023.source.source_file == "FY2023-Flat-File.txt"
    assert ca_fact_2023.source.source_table == (
        "FY2023 STC Flat File item T40 Individual Income Taxes"
    )
    assert ca_fact_2023.source.raw_r2_uri


def test_source_package_alias_builds_census_pep_national_age_facts():
    package = load_source_package("census-pep-2024-national-age-sex")
    rows = package.build_source_rows(2024)
    cells = package.build_source_cells(2024, source_rows=rows)
    facts = package.build_facts(2024, cells=cells, source_rows=rows)
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert package.package_id == "census-pep-2024-national-age-sex"
    assert len(rows) == 306
    assert validate_source_rows(rows).valid
    assert validate_source_cells(cells).valid
    assert validate_facts(facts).valid
    assert len(cells) == 824
    assert len(facts) == 19
    assert all(fact.source_row_keys for fact in facts)
    assert all(fact.source.raw_r2_uri for fact in facts)
    assert (
        values_by_record[
            "census_pep.cy2024.national_resident_population_age.all.population"
        ].value
        == 340_110_988
    )
    age_fact = values_by_record[
        "census_pep.cy2024.national_resident_population_age.0_to_4.population"
    ]
    assert age_fact.value == 18_599_314
    assert {
        (constraint.variable, constraint.operator, constraint.value)
        for constraint in age_fact.constraints
    } == {
        ("age", ">=", 0),
        ("age", "<", 5),
    }
    assert not age_fact.filters


def _rounded_under_5_target(total: int | float, raw_under_5: int | float) -> int:
    return round(total * round(raw_under_5 / total * 100, 1) / 100)


def test_source_package_alias_builds_census_pep_2023_state_age_facts():
    package = load_source_package("census-pep-2023-state-age-sex")
    rows = package.build_source_rows(2023)
    cells = package.build_source_cells(2023, source_rows=rows)
    facts = package.build_facts(2023, cells=cells, source_rows=rows)
    values_by_record = {fact.source_record_id: fact for fact in facts}

    ca_total = values_by_record[
        "census_pep.v2023.cy2023.state_resident_population.ca.all.population"
    ]
    ca_under_5 = values_by_record[
        "census_pep.v2023.cy2023.state_resident_population.ca.0_to_4.population"
    ]
    tx_total = values_by_record[
        "census_pep.v2023.cy2023.state_resident_population.tx.all.population"
    ]
    tx_under_5 = values_by_record[
        "census_pep.v2023.cy2023.state_resident_population.tx.0_to_4.population"
    ]

    assert package.package_id == "census-pep-2023-state-age-sex"
    assert len(rows) == 236_844
    assert validate_source_rows(rows).valid
    assert validate_source_cells(cells).valid
    assert validate_facts(facts).valid
    assert len(cells) == 368_438
    assert len(facts) == 102
    assert all(fact.source_row_keys for fact in facts)
    assert all(fact.source.raw_r2_uri for fact in facts)
    assert ca_total.value == 38_965_193
    assert ca_under_5.value == 2_097_790
    assert _rounded_under_5_target(ca_total.value, ca_under_5.value) == 2_104_120
    assert tx_total.value == 30_503_301
    assert tx_under_5.value == 1_936_893
    assert _rounded_under_5_target(tx_total.value, tx_under_5.value) == 1_921_708
    assert len(ca_total.source_row_keys) == 516
    assert len(ca_under_5.source_row_keys) == 30
    assert {
        (constraint.variable, constraint.operator, constraint.value)
        for constraint in ca_under_5.constraints
    } == {
        ("age", ">=", 0),
        ("age", "<", 5),
    }


def test_source_package_alias_builds_census_pep_2023_puerto_rico_age_facts():
    package = load_source_package("census-pep-2023-puerto-rico-age-sex")
    rows = package.build_source_rows(2023)
    cells = package.build_source_cells(2023, source_rows=rows)
    facts = package.build_facts(2023, cells=cells, source_rows=rows)
    values_by_record = {fact.source_record_id: fact for fact in facts}

    pr_total = values_by_record[
        "census_pep.v2023.cy2023.state_resident_population.pr.all.population"
    ]
    pr_under_5 = values_by_record[
        "census_pep.v2023.cy2023.state_resident_population.pr.0_to_4.population"
    ]

    assert package.package_id == "census-pep-2023-puerto-rico-age-sex"
    assert len(rows) == 33_541
    assert validate_source_rows(rows).valid
    assert validate_source_cells(cells).valid
    assert validate_facts(facts).valid
    assert len(cells) == 67_090
    assert len(facts) == 2
    assert all(fact.source_row_keys for fact in facts)
    assert all(fact.source.raw_r2_uri for fact in facts)
    assert pr_total.value == 3_205_691
    assert pr_under_5.value == 96_979
    assert _rounded_under_5_target(pr_total.value, pr_under_5.value) == 96_171
    assert len(pr_total.source_row_keys) == 6_708
    assert len(pr_under_5.source_row_keys) == 390
    assert {
        (constraint.variable, constraint.operator, constraint.value)
        for constraint in pr_under_5.constraints
    } == {
        ("age", ">=", 0),
        ("age", "<", 5),
    }


def test_source_package_alias_builds_census_acs_s0101_national_age_facts():
    package = load_source_package("census-acs-s0101-national-age-2024")
    rows = package.build_source_rows(2024)
    cells = package.build_source_cells(2024, source_rows=rows)
    facts = package.build_facts(2024, cells=cells, source_rows=rows)
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert package.package_id == "census-acs-s0101-national-age-2024"
    assert len(rows) == 18
    assert validate_source_rows(rows).valid
    assert validate_source_cells(cells).valid
    assert validate_facts(facts).valid
    assert len(cells) == 133
    assert len(facts) == 18
    assert all(fact.source_row_keys for fact in facts)
    assert all(fact.source.raw_r2_uri for fact in facts)
    under_5 = values_by_record[
        "census_acs.acs1_2024.s0101.national_age.age_0_to_4.population"
    ]
    age_85_plus = values_by_record[
        "census_acs.acs1_2024.s0101.national_age.age_85_plus.population"
    ]

    assert under_5.value == 18_365_047
    assert under_5.source.source_file == "acs_S0101_national_2024.json"
    assert {
        (constraint.variable, constraint.operator, constraint.value)
        for constraint in under_5.constraints
    } == {
        ("age", ">=", 0),
        ("age", "<", 5),
    }
    assert age_85_plus.value == 6_343_153
    assert len(age_85_plus.constraints) == 1


def test_source_package_alias_builds_census_acs_s0101_state_age_facts():
    package = load_source_package("census-acs-s0101-state-age-2024")
    rows = package.build_source_rows(2024)
    cells = package.build_source_cells(2024, source_rows=rows)
    facts = package.build_facts(2024, cells=cells, source_rows=rows)
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert package.package_id == "census-acs-s0101-state-age-2024"
    assert len(rows) == 936
    assert validate_source_rows(rows).valid
    assert validate_source_cells(cells).valid
    assert validate_facts(facts).valid
    assert len(cells) == 6_559
    assert len(facts) == 936
    assert {fact.geography.level for fact in facts} == {"state"}
    assert all(fact.source_row_keys for fact in facts)
    assert all(fact.source.raw_r2_uri for fact in facts)

    al_under_5 = values_by_record[
        "census_acs.acs1_2024.s0101.state_age.01.age_0_to_4.population"
    ]
    ca_age_85_plus = values_by_record[
        "census_acs.acs1_2024.s0101.state_age.06.age_85_plus.population"
    ]
    pr_age_85_plus = values_by_record[
        "census_acs.acs1_2024.s0101.state_age.72.age_85_plus.population"
    ]

    assert al_under_5.value == 285_758
    assert al_under_5.geography.id == "0400000US01"
    assert al_under_5.source.source_file == "acs_S0101_state_2024.json"
    assert ca_age_85_plus.value == 724_840
    assert ca_age_85_plus.geography.name == "California"
    assert pr_age_85_plus.value == 109_911
    assert pr_age_85_plus.geography.id == "0400000US72"


def test_source_package_alias_builds_census_acs_s0101_district_age_facts():
    package = load_source_package("census-acs-s0101-congressional-district-age-2024")
    rows = package.build_source_rows(2024)
    cells = package.build_source_cells(2024, source_rows=rows)
    facts = package.build_facts(2024, cells=cells, source_rows=rows)
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert package.package_id == "census-acs-s0101-congressional-district-age-2024"
    assert len(rows) == 7_866
    assert validate_source_rows(rows).valid
    assert validate_source_cells(cells).valid
    assert validate_facts(facts).valid
    assert len(cells) == 55_069
    assert len(facts) == 7_866
    assert {fact.geography.level for fact in facts} == {"congressional_district"}
    assert all(fact.source_row_keys for fact in facts)
    assert all(fact.source.raw_r2_uri for fact in facts)

    al01_under_5 = values_by_record[
        "census_acs.acs1_2024.s0101.congressional_district_age.0101."
        "age_0_to_4.population"
    ]
    ca52_age_85_plus = values_by_record[
        "census_acs.acs1_2024.s0101.congressional_district_age.0652."
        "age_85_plus.population"
    ]
    pr_age_85_plus = values_by_record[
        "census_acs.acs1_2024.s0101.congressional_district_age.7298."
        "age_85_plus.population"
    ]

    assert al01_under_5.value == 39_908
    assert al01_under_5.geography.id == "5001900US0101"
    assert al01_under_5.geography.name == (
        "Congressional District 1 (119th Congress), Alabama"
    )
    assert al01_under_5.source.source_file == "acs_S0101_district_2024.json"
    assert ca52_age_85_plus.value == 14_396
    assert ca52_age_85_plus.geography.name == (
        "Congressional District 52 (119th Congress), California"
    )
    assert pr_age_85_plus.value == 109_911
    assert pr_age_85_plus.geography.id == "5001900US7298"


def test_source_package_alias_builds_census_acs_s2201_district_snap_facts():
    package = load_source_package("census-acs-s2201-congressional-district-snap-2024")
    rows = package.build_source_rows(2024)
    cells = package.build_source_cells(2024, source_rows=rows)
    facts = package.build_facts(2024, cells=cells, source_rows=rows)
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert package.package_id == "census-acs-s2201-congressional-district-snap-2024"
    assert len(rows) == 1_311
    assert validate_source_rows(rows).valid
    assert validate_source_cells(cells).valid
    assert validate_facts(facts).valid
    assert len(cells) == 9_184
    assert len(facts) == 1_311
    assert {fact.geography.level for fact in facts} == {"congressional_district"}
    assert all(fact.source_row_keys for fact in facts)
    assert all(fact.source.raw_r2_uri for fact in facts)

    al01_total = values_by_record[
        "census_acs.acs1_2024.s2201.congressional_district_snap.0101."
        "all_households.household_count"
    ]
    al01_snap = values_by_record[
        "census_acs.acs1_2024.s2201.congressional_district_snap.0101."
        "receiving_food_stamps_snap.household_count"
    ]
    ca52_snap = values_by_record[
        "census_acs.acs1_2024.s2201.congressional_district_snap.0652."
        "receiving_food_stamps_snap.household_count"
    ]
    pr_snap = values_by_record[
        "census_acs.acs1_2024.s2201.congressional_district_snap.7298."
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
    } == {
        ("snap_receipt_status", "==", "receiving_food_stamps_snap"),
    }
    assert ca52_snap.value == 44_942
    assert pr_snap.value == 559_700
    assert pr_snap.geography.id == "5001900US7298"


def test_source_package_alias_builds_census_cd119_sld_facts():
    package = load_source_package("census-cd119-sld-2024")
    rows = package.build_source_rows(2024)
    cells = package.build_source_cells(2024, source_rows=rows)
    facts = package.build_facts(2024, cells=cells, source_rows=rows)
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert package.package_id == "census-cd119-sld-2024"
    assert len(rows) == 13_686
    assert validate_source_rows(rows).valid
    assert validate_source_cells(cells).valid
    assert validate_facts(facts).valid
    assert len(cells) == 205_305
    assert len(facts) == 13_686
    assert {fact.geography.level for fact in facts} == {
        "state_legislative_district_lower",
        "state_legislative_district_upper",
    }
    assert all(fact.source_row_keys for fact in facts)
    assert all(fact.source.raw_r2_uri for fact in facts)

    ca_sd_1_population = values_by_record[
        "census_decennial.cd119_2024.sld.population.sldu_06001.population"
    ]
    ca_sd_1_households = values_by_record[
        "census_decennial.cd119_2024.sld.households.sldu_06001.household_count"
    ]
    ca_ad_80_population = values_by_record[
        "census_decennial.cd119_2024.sld.population.sldl_06080.population"
    ]
    ca_ad_80_households = values_by_record[
        "census_decennial.cd119_2024.sld.households.sldl_06080.household_count"
    ]

    assert ca_sd_1_population.value == 943_108
    assert ca_sd_1_population.geography.id == "610U900US06001"
    assert ca_sd_1_population.geography.name == "State Senate District 1, California"
    assert ca_sd_1_population.measure.concept == "census_decennial.resident_population"
    assert ca_sd_1_households.value == 361_548
    assert ca_sd_1_households.measure.concept == (
        "census_decennial.occupied_housing_units"
    )
    assert ca_ad_80_population.value == 515_699
    assert ca_ad_80_population.geography.id == "620L900US06080"
    assert ca_ad_80_households.value == 154_291


def test_source_package_alias_builds_census_b01001_female_age_facts():
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
        "census_acs.acs1_2023.b01001.female_age.01.age_15_to_17.female_population"
    ]
    ca_age_40_to_44 = values_by_record[
        "census_acs.acs1_2023.b01001.female_age.06.age_40_to_44.female_population"
    ]
    pr_age_40_to_44 = values_by_record[
        "census_acs.acs1_2023.b01001.female_age.72.age_40_to_44.female_population"
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


def test_source_package_alias_builds_cdc_vsrr_live_birth_facts():
    package = load_source_package("cdc-vsrr-live-births-monthly-2024")
    rows = package.build_source_rows(2024)
    cells = package.build_source_cells(2024, source_rows=rows)
    facts = package.build_facts(2024, cells=cells, source_rows=rows)
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert package.package_id == "cdc-vsrr-live-births-monthly-2024"
    assert len(rows) == 312
    assert validate_source_rows(rows).valid
    assert validate_source_cells(cells).valid
    assert validate_facts(facts).valid
    assert len(cells) == 2_504
    assert len(facts) == 312
    assert {fact.period.type for fact in facts} == {"month"}
    assert all(fact.source_row_keys for fact in facts)
    assert all(fact.source.raw_r2_uri for fact in facts)

    al_january = values_by_record[
        "cdc_vsrr.live_births.2024-01.01.live_births.live_birth_count"
    ]
    ca_june = values_by_record[
        "cdc_vsrr.live_births.2024-06.06.live_births.live_birth_count"
    ]
    pr_june = values_by_record[
        "cdc_vsrr.live_births.2024-06.72.live_births.live_birth_count"
    ]

    assert al_january.value == 4_932
    assert al_january.period.value == "2024-01"
    assert al_january.geography.id == "0400000US01"
    assert al_january.source.source_file == "cdc_vsrr_births_2024.json"
    assert ca_june.value == 32_268
    assert ca_june.geography.name == "California"
    assert pr_june.value == 1_255
    assert pr_june.geography.id == "0400000US72"


def test_source_package_alias_builds_cdc_vsrr_2023_live_birth_facts():
    package = load_source_package("cdc-vsrr-live-births-monthly-2023")
    rows = package.build_source_rows(2023)
    cells = package.build_source_cells(2023, source_rows=rows)
    facts = package.build_facts(2023, cells=cells, source_rows=rows)
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert package.package_id == "cdc-vsrr-live-births-monthly-2023"
    assert len(rows) == 624
    assert validate_source_rows(rows).valid
    assert validate_source_cells(cells).valid
    assert validate_facts(facts).valid
    assert len(cells) == 5_000
    assert len(facts) == 624
    assert all(fact.source_row_keys for fact in facts)
    assert all(fact.source.raw_r2_uri for fact in facts)

    al_january = values_by_record[
        "cdc_vsrr.live_births.2023-01.01.live_births.live_birth_count"
    ]
    ca_december = values_by_record[
        "cdc_vsrr.live_births.2023-12.06.live_births.live_birth_count"
    ]
    pr_december = values_by_record[
        "cdc_vsrr.live_births.2023-12.72.live_births.live_birth_count"
    ]

    assert al_january.value == 5_000
    assert al_january.period.value == "2023-01"
    assert al_january.geography.id == "0400000US01"
    assert al_january.source.source_file == "cdc_vsrr_births_2023.json"
    assert ca_december.value == 33_377
    assert pr_december.value == 1_554


def test_source_package_alias_builds_hhs_acf_tanf_financial_facts():
    package = load_source_package("hhs-acf-tanf-financial-2024")
    cells = package.build_source_cells(2024)
    facts = package.build_facts(2024, cells=cells)
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


def test_source_package_alias_builds_hhs_acf_tanf_caseload_facts():
    package = load_source_package("hhs-acf-tanf-caseload-2024")
    cells = package.build_source_cells(2024)
    records = package.build_source_records(2024, cells=cells)
    facts = package.build_facts(2024, cells=cells)
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
def test_source_package_alias_builds_hhs_acf_liheap_profile_fact(
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
    household_count = (
        f"hhs_acf_liheap.fy{year}.national_profile.state_programs.households_served"
    )
    assert records[0].source_cell_addresses == addresses
    assert values_by_record[household_count].value == households
    assert values_by_record[household_count].source.source_file == source_file
    assert values_by_record[household_count].constraints


def test_source_package_alias_builds_dhs_ohss_unauthorized_population_fact():
    package = load_source_package(
        "dhs-ohss-unauthorized-immigrant-population-2018-2022"
    )
    cells = package.build_source_cells(2022)
    records = package.build_source_records(2022, cells=cells)
    facts = package.build_facts(2022, cells=cells)
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert package.package_id == (
        "dhs-ohss-unauthorized-immigrant-population-2018-2022"
    )
    assert validate_source_cells(cells).valid
    assert validate_facts(facts).valid
    assert len(cells) == 8_814
    assert len(facts) == 1
    assert all(fact.source.raw_r2_uri for fact in facts)
    unauthorized_count = (
        "dhs_ohss.unauthorized_immigrant_population.2022."
        "undocumented.rounded_summary_count"
    )
    assert records[0].source_cell_addresses == (
        "E11",
        "E1",
        "A11",
        "B11",
        "D11",
        "C12",
    )
    assert values_by_record[unauthorized_count].value == 11_000_000
    assert values_by_record[unauthorized_count].source.source_file == (
        "dhs_ohss_unauthorized_immigrant_population_2018_2022.pdf"
    )
    assert values_by_record[unauthorized_count].constraints


def test_source_package_alias_builds_cmsny_undocumented_population_fact():
    package = load_source_package("cmsny-undocumented-population-2023")
    cells = package.build_source_cells(2023)
    records = package.build_source_records(2023, cells=cells)
    facts = package.build_facts(2023, cells=cells)
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert package.package_id == "cmsny-undocumented-population-2023"
    assert validate_source_cells(cells).valid
    assert validate_facts(facts).valid
    assert len(cells) == 270
    assert len(facts) == 1
    assert all(fact.source.source_name == "cmsny" for fact in facts)
    assert all(fact.source.raw_r2_uri for fact in facts)
    undocumented_count = (
        "cmsny.undocumented_population.2023.undocumented_residents.population_count"
    )
    assert records[0].source_cell_addresses == (
        "E7",
        "E1",
        "A7",
        "B7",
        "D7",
    )
    assert values_by_record[undocumented_count].value == 12_200_000
    assert values_by_record[undocumented_count].source.source_file == (
        "cmsny_undocumented_population_increased_to_12_million_2023.html"
    )
    assert values_by_record[undocumented_count].filters["immigration_status"] == (
        "UNDOCUMENTED"
    )


def test_source_package_alias_builds_soi_ira_contribution_facts():
    traditional = load_source_package("soi-ira-traditional-contributions-2022")
    roth = load_source_package("soi-ira-roth-contributions-2022")
    traditional_facts = traditional.build_facts(2022)
    roth_facts = roth.build_facts(2022)
    traditional_values = {fact.source_record_id: fact for fact in traditional_facts}
    roth_values = {fact.source_record_id: fact for fact in roth_facts}

    assert validate_facts(traditional_facts).valid
    assert validate_facts(roth_facts).valid
    assert len(traditional_facts) == 2
    assert len(roth_facts) == 2
    assert all(fact.source.raw_r2_uri for fact in traditional_facts + roth_facts)
    assert (
        traditional_values[
            "irs_soi.ty2022.traditional_ira_contributions.all_taxpayers."
            "all_taxpayers.amount"
        ].value
        == 23_034_199_000
    )
    assert (
        roth_values[
            "irs_soi.ty2022.roth_ira_contributions.all_taxpayers.all_taxpayers.amount"
        ].value
        == 34_951_077_000
    )
    assert (
        traditional_values[
            "irs_soi.ty2022.traditional_ira_contributions.all_taxpayers."
            "all_taxpayers.taxpayer_count"
        ].value
        == 5_101_648
    )


def test_source_package_alias_builds_soi_w2_statistics_2020_facts():
    package = load_source_package("soi-w2-statistics-2020")
    cells = package.build_source_cells(2020)
    facts = package.build_facts(2020, cells=cells)
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert package.package_id == "soi-w2-statistics-2020"
    assert validate_source_cells(cells).valid
    assert validate_facts(facts).valid
    assert len(cells) == 1_650
    assert len(facts) == 5
    assert all(fact.source.raw_r2_uri for fact in facts)
    assert (
        values_by_record[
            "irs_soi.ty2020.form_w2_social_security_tips."
            "box_7_social_security_tips.amount"
        ].value
        == 26_786_522_000
    )
    assert (
        values_by_record[
            "irs_soi.ty2020.form_w2_social_security_tips."
            "box_7_social_security_tips.return_count"
        ].value
        == 6_038_613
    )
    assert (
        values_by_record[
            "irs_soi.ty2020.form_w2_401k_elective_deferrals."
            "box_12_d_401k_elective_deferrals.amount"
        ].value
        == 277_859_181_000
    )
    assert (
        values_by_record[
            "irs_soi.ty2020.form_w2_designated_roth_401k_contributions."
            "box_12_aa_designated_roth_401k_contributions.amount"
        ].value
        == 32_302_509_000
    )


def test_source_package_alias_builds_ssa_supplement_payment_facts():
    package = load_source_package("ssa-annual-statistical-supplement-2025")
    rows = package.build_source_rows(2024)
    cells = package.build_source_cells(2024, source_rows=rows)
    records = package.build_source_records(2024, cells=cells, source_rows=rows)
    facts = package.build_facts(2024, cells=cells, source_rows=rows)
    records_by_id = {record.source_record_id: record for record in records}
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert package.package_id == "ssa-annual-statistical-supplement-2025"
    assert len(rows) == 6
    assert validate_source_rows(rows).valid
    assert len(cells) == 56
    assert validate_source_cells(cells).valid
    assert len(facts) == 6
    assert validate_facts(facts).valid
    assert all(fact.source_row_keys for fact in facts)
    assert all(fact.source.source_name == "ssa" for fact in facts)
    assert all(fact.source.source_file == "ssa_oasdi_ssi_2024.csv" for fact in facts)
    assert all(fact.source.raw_r2_uri for fact in facts)
    assert all(fact.geography.id == "0100000US" for fact in facts)
    dependents_record = (
        "ssa_supplement.cy2024.oasdi_ssi_payments."
        "social_security_dependents_benefits.payment_amount"
    )
    assert records_by_id[dependents_record].source_cell_addresses == (
        "C6",
        "C1",
        "B6",
        "D6",
    )
    assert values_by_record[dependents_record].value == 51_075_000_000
    assert (
        values_by_record[
            "ssa_supplement.cy2024.oasdi_ssi_payments."
            "social_security_benefits.payment_amount"
        ].value
        == 1_471_195_000_000
    )
    assert (
        values_by_record[
            "ssa_supplement.cy2024.oasdi_ssi_payments.ssi_payments.payment_amount"
        ].value
        == 63_079_493_000
    )
    assert {
        (constraint.variable, constraint.operator, constraint.value)
        for constraint in values_by_record[dependents_record].constraints
    } == {
        (
            "us_social_security_and_ssi.program_payment_type",
            "==",
            "social_security_dependents_benefits",
        ),
    }


def test_source_package_alias_builds_ssa_population_projection_age_facts():
    package = load_source_package("ssa-population-projections-tr2024")
    rows = package.build_source_rows(2025)
    cells = package.build_source_cells(2025, source_rows=rows)
    records = package.build_source_records(2025, cells=cells, source_rows=rows)
    facts = package.build_facts(2025, cells=cells, source_rows=rows)
    records_by_id = {record.source_record_id: record for record in records}
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert package.package_id == "ssa-population-projections-tr2024"
    assert len(rows) == 16_160
    assert validate_source_rows(rows).valid
    assert rows[0].values["Year"] == 1941
    assert rows[0].values["Age"] == 0
    assert validate_source_cells(cells).valid
    assert len(cells) == 1_326
    assert len(facts) == 101
    assert validate_facts(facts).valid
    assert all(fact.source_row_keys for fact in facts)
    assert all(fact.source.source_name == "ssa" for fact in facts)
    assert all(fact.source.source_file == "SSPopJul_TR2024.csv" for fact in facts)
    assert all(fact.source.raw_r2_uri for fact in facts)
    assert all(fact.geography.id == "0100000US" for fact in facts)
    assert {f"{fact.period.type}:{fact.period.value}" for fact in facts} == {
        "calendar_year:2025"
    }

    age_0 = "ssa.tr2024.cy2025.midyear_population_age.age_0.population"
    age_100_plus = "ssa.tr2024.cy2025.midyear_population_age.age_100_plus.population"
    assert records_by_id[age_0].source_cell_addresses == ("C2", "C1", "A2")
    assert records_by_id[age_100_plus].source_cell_addresses == (
        "C102",
        "C1",
        "A102",
    )
    assert values_by_record[age_0].value == 3_857_298
    assert values_by_record[age_100_plus].value == 99_208
    assert {
        (constraint.variable, constraint.operator, constraint.value)
        for constraint in values_by_record[age_0].constraints
    } == {("age", ">=", 0), ("age", "<", 1)}
    assert {
        (constraint.variable, constraint.operator, constraint.value)
        for constraint in values_by_record[age_100_plus].constraints
    } == {("age", ">=", 100)}


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
    age_85_plus = "census.popproj2023.cy2025.national_population.age_85_plus.population"
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


def test_source_package_alias_builds_soi_historic_table_2_facts():
    package = load_source_package("soi-historic-table-2")
    rows = package.build_source_rows(2022)
    cells = package.build_source_cells(2022, source_rows=rows)
    facts = package.build_facts(2022, cells=cells, source_rows=rows)
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert package.package_id == "soi-historic-table-2"
    assert len(rows) == 594
    assert validate_source_rows(rows).valid
    assert rows[0].values["STATE"] == "US"
    assert rows[0].values["AGI_STUB"] == 0
    assert validate_source_cells(cells).valid
    assert validate_facts(facts).valid
    assert len(cells) == 1956
    assert len(facts) == 143
    assert all(fact.source_row_keys for fact in facts)
    assert (
        values_by_record[
            "irs_soi.ty2022.historic_table_2.us.all.tax_filer_individual_count"
        ].value
        == 293_617_150
    )
    assert (
        values_by_record[
            "irs_soi.ty2022.historic_table_2.us.all.premium_tax_credit_returns"
        ].value
        == 7_841_370
    )
    assert (
        values_by_record["irs_soi.ty2022.historic_table_2.us.all.eitc_amount"].value
        == 59_204_588_000
    )
    agi_bracket_fact = values_by_record[
        "irs_soi.ty2022.historic_table_2.us.1_to_10k.eitc_claims"
    ]
    assert agi_bracket_fact.value == 5_013_220
    assert {constraint.operator for constraint in agi_bracket_fact.constraints} == {
        "<",
        ">=",
    }


def test_source_package_alias_builds_soi_historic_table_2_state_agi_facts():
    package = load_source_package("soi-historic-table-2-state-agi-2022")
    rows = package.build_source_rows(2022)
    cells = package.build_source_cells(2022, source_rows=rows)
    records = package.build_source_records(2022, cells=cells, source_rows=rows)
    facts = package.build_facts(2022, cells=cells, source_rows=rows)
    records_by_id = {record.source_record_id: record for record in records}
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert package.package_id == "soi-historic-table-2-state-agi-2022"
    assert len(rows) == 594
    assert validate_source_rows(rows).valid
    assert len(cells) == 83_293
    assert validate_source_cells(cells).valid
    assert len(facts) == 918
    assert validate_facts(facts).valid
    assert all(fact.geography.level == "state" for fact in facts)
    assert all(fact.source.raw_r2_uri for fact in facts)

    al_under_1_record = (
        "irs_soi.ty2022.historic_table_2.state_agi.al.under_1.return_count"
    )
    al_under_1 = values_by_record[al_under_1_record]
    assert al_under_1.value == 32_590
    assert al_under_1.geography.id == "0400000US01"
    assert "state" not in al_under_1.filters
    assert records_by_id[al_under_1_record].source_cell_addresses == ("C2", "A2")
    assert len(al_under_1.source_row_keys) == 1
    assert {
        (constraint.operator, constraint.value) for constraint in al_under_1.constraints
    } == {("<", 1)}
    al_under_1_agi_record = (
        "irs_soi.ty2022.historic_table_2.state_agi.al.under_1."
        "adjusted_gross_income"
    )
    al_under_1_agi = values_by_record[al_under_1_agi_record]
    assert al_under_1_agi.value == -1_132_335_000
    assert al_under_1_agi.measure.concept == (
        "us:statutes/26/62#adjusted_gross_income"
    )
    assert al_under_1_agi.measure.unit == "usd"
    assert records_by_id[al_under_1_agi_record].source_cell_addresses == ("T2", "A2")

    ca_500k_plus_record = (
        "irs_soi.ty2022.historic_table_2.state_agi.ca.500k_plus.return_count"
    )
    ca_500k_plus = values_by_record[ca_500k_plus_record]
    assert ca_500k_plus.value == 426_810
    assert ca_500k_plus.geography.id == "0400000US06"
    assert "state" not in ca_500k_plus.filters
    assert records_by_id[ca_500k_plus_record].source_cell_addresses == (
        "C50",
        "C51",
        "A50",
        "A51",
        "B50",
        "B51",
    )
    assert len(ca_500k_plus.source_row_keys) == 2
    assert {
        (constraint.operator, constraint.value)
        for constraint in ca_500k_plus.constraints
    } == {(">=", 500_000)}
    ca_500k_plus_agi_record = (
        "irs_soi.ty2022.historic_table_2.state_agi.ca.500k_plus."
        "adjusted_gross_income"
    )
    ca_500k_plus_agi = values_by_record[ca_500k_plus_agi_record]
    assert ca_500k_plus_agi.value == 613_219_427_000
    assert records_by_id[ca_500k_plus_agi_record].source_cell_addresses == (
        "T50",
        "T51",
        "A50",
        "A51",
        "B50",
        "B51",
    )


def test_source_package_alias_builds_soi_historic_table_2_state_eitc_facts():
    package = load_source_package("soi-historic-table-2-state-eitc-2022")
    rows = package.build_source_rows(2022)
    cells = package.build_source_cells(2022, source_rows=rows)
    records = package.build_source_records(2022, cells=cells, source_rows=rows)
    facts = package.build_facts(2022, cells=cells, source_rows=rows)
    records_by_id = {record.source_record_id: record for record in records}
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert package.package_id == "soi-historic-table-2-state-eitc-2022"
    assert len(rows) == 594
    assert validate_source_rows(rows).valid
    assert len(cells) == 8_476
    assert validate_source_cells(cells).valid
    assert len(facts) == 102
    assert validate_facts(facts).valid
    assert all(fact.geography.level == "state" for fact in facts)
    assert all(fact.source_row_keys for fact in facts)
    assert all(fact.source.raw_r2_uri for fact in facts)

    al_claims = "irs_soi.ty2022.historic_table_2.state_eitc.al.al.eitc_claims"
    ca_amount = "irs_soi.ty2022.historic_table_2.state_eitc.ca.ca.eitc_amount"
    assert values_by_record[al_claims].value == 440_510
    assert values_by_record[al_claims].geography.id == "0400000US01"
    assert records_by_id[al_claims].source_cell_addresses == (
        "DZ2",
        "DZ1",
        "A2",
        "B2",
    )
    assert values_by_record[ca_amount].value == 5_770_703_000
    assert values_by_record[ca_amount].geography.id == "0400000US06"
    assert records_by_id[ca_amount].source_cell_addresses == (
        "EA6",
        "EA1",
        "A6",
        "B6",
    )


def test_source_package_alias_builds_soi_congressional_district_2022_facts():
    package = load_source_package("soi-congressional-district-2022")
    rows = package.build_source_rows(2022)
    cells = package.build_source_cells(2022, source_rows=rows)
    facts = package.build_facts(2022, cells=cells, source_rows=rows)
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert package.package_id == "soi-congressional-district-2022"
    assert len(rows) == 4_791
    assert validate_source_rows(rows).valid
    assert rows[0].values["STATE"] == "US"
    assert rows[0].values["CONG_DISTRICT"] == 0
    assert rows[0].values["agi_stub"] == 0
    assert len(cells) == 660
    assert validate_source_cells(cells).valid
    assert len(facts) == 9
    assert validate_facts(facts).valid
    assert all(fact.source_row_keys for fact in facts)
    assert all(fact.source.raw_r2_uri for fact in facts)
    assert (
        values_by_record[
            "irs_soi.ty2022.congressional_district_2022."
            "all_returns.us.adjusted_gross_income"
        ].value
        == 14_424_810_411_000
    )
    assert (
        values_by_record[
            "irs_soi.ty2022.congressional_district_2022."
            "all_returns.al_total.return_count"
        ].value
        == 2_104_760
    )
    assert (
        values_by_record[
            "irs_soi.ty2022.congressional_district_2022."
            "all_returns.al_01.adjusted_gross_income"
        ].value
        == 22_915_824_000
    )


def test_source_package_alias_builds_soi_state_2022_facts():
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


def test_source_package_alias_builds_obr_efo_receipts_facts():
    package = load_source_package("obr-efo-receipts")
    cells = package.build_source_cells(2025)
    records = package.build_source_records(2025, cells=cells)
    facts = package.build_facts(2025, cells=cells)
    records_by_id = {record.source_record_id: record for record in records}
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert package.package_id == "obr-efo-receipts"
    assert len(cells) == 35_913
    assert validate_source_cells(cells).valid
    assert len(facts) == 9
    assert validate_facts(facts).valid
    assert all(fact.source.source_name == "obr" for fact in facts)
    assert all(fact.source.source_file.endswith(".xlsx") for fact in facts)
    assert all(fact.source.raw_r2_uri for fact in facts)
    assert all(fact.entity.name == "government" for fact in facts)
    assert all(fact.measure.source_concept for fact in facts)
    assert records_by_id[
        "obr_efo.fy2025.receipts.income_tax_gross_of_tax_credits.all.amount"
    ].source_cell_addresses == ("D6", "D5")
    assert values_by_record[
        "obr_efo.fy2025.receipts.income_tax_gross_of_tax_credits.all.amount"
    ].value == pytest.approx(331_437_583_074.4429)
    assert values_by_record[
        "obr_efo.fy2025.receipts.value_added_tax.all.amount"
    ].value == pytest.approx(180_168_938_685.41794)


def test_source_package_alias_builds_obr_efo_expenditure_facts():
    package = load_source_package("obr-efo-expenditure")
    cells = package.build_source_cells(2025)
    records = package.build_source_records(2025, cells=cells)
    facts = package.build_facts(2025, cells=cells)
    records_by_id = {record.source_record_id: record for record in records}
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert package.package_id == "obr-efo-expenditure"
    assert len(cells) == 58_355
    assert validate_source_cells(cells).valid
    assert len(facts) == 19
    assert validate_facts(facts).valid
    assert all(fact.entity.name == "government" for fact in facts)
    assert all(fact.measure.source_concept for fact in facts)
    assert records_by_id[
        "obr_efo.fy2025.expenditure.total_net_council_tax_receipts.all.amount"
    ].source_cell_addresses == ("D19", "D5")
    assert values_by_record[
        "obr_efo.fy2025.expenditure.total_net_council_tax_receipts.all.amount"
    ].value == pytest.approx(50_925_163_826.30539)
    assert values_by_record[
        "obr_efo.fy2025.expenditure.state_pension.all.amount"
    ].value == pytest.approx(146_185_954_351.57382)
    assert (
        values_by_record[
            "obr_efo.fy2025.expenditure.bbc_licence_fee_receipts.all.amount"
        ].value
        == 3_872_000_000
    )


def test_source_package_alias_builds_slc_student_support_facts():
    package = load_source_package("slc-student-support-england-2025")
    cells = package.build_source_cells(2025)
    records = package.build_source_records(2025, cells=cells)
    facts = package.build_facts(2025, cells=cells)
    records_by_id = {record.source_record_id: record for record in records}
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert package.package_id == "slc-student-support-england-2025"
    assert len(cells) == 28_037
    assert validate_source_cells(cells).valid
    assert len(facts) == 6
    assert validate_facts(facts).valid
    assert all(fact.source.source_name == "slc" for fact in facts)
    assert all(fact.source.source_file == "slcsp052025.xlsx" for fact in facts)
    assert all(fact.source.raw_r2_uri for fact in facts)
    assert all(fact.geography.id == "E92000001" for fact in facts)
    assert records_by_id[
        "slc_student_support.cy2025.maintenance_loan_recipients.all.recipients"
    ].source_cell_addresses == ("P13", "P8")
    assert (
        values_by_record[
            "slc_student_support.cy2025.maintenance_loan_recipients.all.recipients"
        ].value
        == 1_159_761
    )
    assert values_by_record[
        "slc_student_support.cy2025.maintenance_loan_amount_paid.all.amount_paid"
    ].value == pytest.approx(8_591_659_718.080004)
    assert (
        values_by_record[
            "slc_student_support.cy2025.targeted_support_recipients."
            "adult_dependants_grant.recipients"
        ].value
        == 18_611
    )
    assert values_by_record[
        "slc_student_support.cy2025.targeted_support_amount_awarded."
        "parents_learning_allowance.amount_awarded"
    ].value == pytest.approx(181_421_659.32)
    targeted_fact = values_by_record[
        "slc_student_support.cy2025.targeted_support_recipients."
        "parents_learning_allowance.recipients"
    ]
    assert {constraint.variable for constraint in targeted_fact.constraints} == {
        "uk_student_support.product"
    }


def test_source_package_alias_builds_slc_borrower_forecast_facts():
    package = load_source_package("slc-student-loan-borrower-forecasts-england-2025")
    rows = package.build_source_rows(2025)
    cells = package.build_source_cells(2025, source_rows=rows)
    records = package.build_source_records(2025, cells=cells, source_rows=rows)
    facts = package.build_facts(2025, cells=cells, source_rows=rows)
    records_by_id = {record.source_record_id: record for record in records}
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert package.package_id == "slc-student-loan-borrower-forecasts-england-2025"
    assert len(rows) == 36
    assert validate_source_rows(rows).valid
    assert len(cells) == 55
    assert validate_source_cells(cells).valid
    assert len(facts) == 4
    assert validate_facts(facts).valid
    assert all(fact.source.source_name == "slc" for fact in facts)
    assert all(
        fact.source.source_file == "ees_student_loan_forecasts_england_table_6a.html"
        for fact in facts
    )
    assert all(fact.source.raw_r2_uri for fact in facts)
    assert all(fact.geography.id == "E92000001" for fact in facts)
    assert records_by_id[
        "slc_student_loan_forecasts.cy2025."
        "england_borrowers_liable_by_plan.plan_2.borrower_count"
    ].source_cell_addresses == ("K2", "K1")
    assert (
        values_by_record[
            "slc_student_loan_forecasts.cy2025."
            "england_borrowers_liable_by_plan.plan_2.borrower_count"
        ].value
        == 8_940_000
    )
    assert (
        values_by_record[
            "slc_student_loan_forecasts.cy2025."
            "england_borrowers_liable_by_plan.plan_5.borrower_count"
        ].value
        == 10_000
    )
    assert (
        values_by_record[
            "slc_student_loan_forecasts.cy2025."
            "england_borrowers_above_threshold_by_plan.plan_2.borrower_count"
        ].value
        == 3_985_000
    )
    plan_5_above = values_by_record[
        "slc_student_loan_forecasts.cy2025."
        "england_borrowers_above_threshold_by_plan.plan_5.borrower_count"
    ]
    assert plan_5_above.value == 0
    assert {
        (constraint.variable, constraint.operator, constraint.value)
        for constraint in plan_5_above.constraints
    } == {
        ("uk_student_loans.borrower_status", "==", "above_repayment_threshold"),
        ("uk_student_loans.repayment_plan", "==", "plan_5"),
    }

    future_facts = package.build_facts(2030, source_rows=rows)
    future_values = {fact.source_record_id: fact.value for fact in future_facts}
    assert (
        future_values[
            "slc_student_loan_forecasts.cy2030."
            "england_borrowers_liable_by_plan.plan_5.borrower_count"
        ]
        == 3_400_000
    )


def test_source_package_alias_builds_slc_repayment_england_facts():
    package = load_source_package("slc-student-loan-repayments-england-2025")
    cells = package.build_source_cells(2025)
    records = package.build_source_records(2025, cells=cells)
    facts = package.build_facts(2025, cells=cells)
    records_by_id = {record.source_record_id: record for record in records}
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert package.package_id == "slc-student-loan-repayments-england-2025"
    assert len(cells) == 38_955
    assert validate_source_cells(cells).valid
    assert len(facts) == 8
    assert validate_facts(facts).valid
    assert all(fact.source.source_name == "slc" for fact in facts)
    assert all(
        fact.source.source_file == "slcsp012025_Corrected.xlsx" for fact in facts
    )
    assert all(fact.source.raw_r2_uri for fact in facts)
    assert {f"{fact.period.type}:{fact.period.value}" for fact in facts} == {
        "fiscal_year:2024-25"
    }
    assert all(fact.geography.id == "E92000001" for fact in facts)
    assert records_by_id[
        "slc_student_loans.fy2024_25.england_he_repayments_by_plan."
        "all.total_higher_education"
    ].source_cell_addresses == ("BI27", "BI6")
    assert values_by_record[
        "slc_student_loans.fy2024_25.england_he_repayments_by_plan."
        "all.total_higher_education"
    ].value == pytest.approx(5_018_231_834.95)
    plan_2 = sum(
        values_by_record[
            "slc_student_loans.fy2024_25.england_he_repayments_by_plan."
            f"all.{measure_id}"
        ].value
        for measure_id in ("plan_2_full_time", "plan_2_part_time")
    )
    plan_5 = sum(
        values_by_record[
            "slc_student_loans.fy2024_25.england_he_repayments_by_plan."
            f"all.{measure_id}"
        ].value
        for measure_id in ("plan_5_full_time", "plan_5_part_time")
    )
    assert plan_2 == pytest.approx(2_778_253_361.64)
    assert plan_5 == pytest.approx(40_869_580.81)
    plan_5_part_time = values_by_record[
        "slc_student_loans.fy2024_25.england_he_repayments_by_plan.all.plan_5_part_time"
    ]
    assert {
        (constraint.variable, constraint.operator, constraint.value)
        for constraint in plan_5_part_time.constraints
    } == {
        ("uk_student_loans.course_mode", "==", "part_time"),
        ("uk_student_loans.repayment_plan", "==", "plan_5"),
    }


@pytest.mark.parametrize(
    (
        "source",
        "source_record_id",
        "source_file",
        "cell_count",
        "geography_id",
        "source_cell_addresses",
        "value",
    ),
    [
        (
            "slc-student-loan-repayments-scotland-2025",
            "slc_student_loans.fy2024_25.scotland_he_repayments_total."
            "all.total_higher_education",
            "slcsp042025.xlsx",
            15_172,
            "S92000003",
            ("U25", "U6"),
            203_305_148.38,
        ),
        (
            "slc-student-loan-repayments-wales-2025",
            "slc_student_loans.fy2024_25.wales_he_repayments_total."
            "all.total_higher_education",
            "slcsp022025.xlsx",
            27_193,
            "W92000004",
            ("BD28", "BD7"),
            229_112_784.43,
        ),
        (
            "slc-student-loan-repayments-northern-ireland-2025",
            "slc_student_loans.fy2024_25.northern_ireland_he_repayments_total."
            "all.total_higher_education",
            "slcsp032025.xlsx",
            25_995,
            "N92000002",
            ("U28", "U6"),
            181_691_655.25,
        ),
    ],
)
def test_source_package_alias_builds_slc_repayment_country_total_facts(
    source,
    source_record_id,
    source_file,
    cell_count,
    geography_id,
    source_cell_addresses,
    value,
):
    package = load_source_package(source)
    cells = package.build_source_cells(2025)
    records = package.build_source_records(2025, cells=cells)
    facts = package.build_facts(2025, cells=cells)

    assert len(cells) == cell_count
    assert validate_source_cells(cells).valid
    assert len(facts) == 1
    assert validate_facts(facts).valid
    assert records[0].source_record_id == source_record_id
    assert records[0].source_cell_addresses == source_cell_addresses
    assert facts[0].source_record_id == source_record_id
    assert facts[0].source.source_name == "slc"
    assert facts[0].source.source_file == source_file
    assert facts[0].source.raw_r2_uri
    assert f"{facts[0].period.type}:{facts[0].period.value}" == ("fiscal_year:2024-25")
    assert facts[0].geography.id == geography_id
    assert facts[0].value == pytest.approx(value)


def test_source_package_alias_builds_dwp_uc_two_child_limit_facts():
    package = load_source_package("dwp-uc-two-child-limit-2025")
    cells = package.build_source_cells(2026)
    records = package.build_source_records(2026, cells=cells)
    facts = package.build_facts(2026, cells=cells)
    records_by_id = {record.source_record_id: record for record in records}
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert package.package_id == "dwp-uc-two-child-limit-2025"
    assert len(cells) == 407_123
    assert validate_source_cells(cells).valid
    assert len(facts) == 42
    assert validate_facts(facts).valid
    assert all(fact.source.source_name == "dwp" for fact in facts)
    assert all(fact.source.source_file.endswith(".ods") for fact in facts)
    assert all(fact.source.raw_r2_uri for fact in facts)
    assert all(fact.geography.name == "Great Britain" for fact in facts)
    assert records_by_id[
        "dwp_uc_two_child_limit.cy2026.not_receiving_child_element_summary."
        "households.not_receiving_child_element.households"
    ].source_cell_addresses == ("B11", "B8")
    assert (
        values_by_record[
            "dwp_uc_two_child_limit.cy2026.not_receiving_child_element_summary."
            "households.not_receiving_child_element.households"
        ].value
        == 453_600
    )
    assert (
        values_by_record[
            "dwp_uc_two_child_limit.cy2026.not_receiving_child_element_summary."
            "children_within_households.not_receiving_child_element."
            "children_within_households"
        ].value
        == 1_613_980
    )
    assert (
        values_by_record[
            "dwp_uc_two_child_limit.cy2026.not_receiving_child_element_summary."
            "affected_children.not_receiving_child_element.affected_children"
        ].value
        == 580_400
    )
    assert (
        values_by_record[
            "dwp_uc_two_child_limit.cy2026.not_receiving_by_child_count."
            "children_within_households.not_receiving_child_element."
            "children_within_households_4_children"
        ].value
        == 462_520
    )
    assert (
        values_by_record[
            "dwp_uc_two_child_limit.cy2026.not_receiving_by_health_disability."
            "children_within_households.not_receiving_child_element.claimant_pip"
        ].value
        == 225_320
    )
    disabled_child_element = values_by_record[
        "dwp_uc_two_child_limit.cy2026.not_receiving_by_health_disability."
        "households.not_receiving_child_element.disabled_child_element"
    ]
    assert disabled_child_element.value == 124_560
    assert {
        constraint.variable for constraint in disabled_child_element.constraints
    } == {
        "uk_universal_credit.health_disability_entitlement",
        "uk_universal_credit.two_child_limit_status",
    }


def test_source_package_alias_builds_dwp_benefit_cap_facts():
    package = load_source_package("dwp-benefit-cap-november-2025")
    cells = package.build_source_cells(2025)
    records = package.build_source_records(2025, cells=cells)
    facts = package.build_facts(2025, cells=cells)
    records_by_id = {record.source_record_id: record for record in records}
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert package.package_id == "dwp-benefit-cap-november-2025"
    assert len(cells) == 20_764
    assert validate_source_cells(cells).valid
    assert len(facts) == 15
    assert validate_facts(facts).valid
    assert all(fact.source.source_name == "dwp" for fact in facts)
    assert all(fact.source.source_file.endswith(".ods") for fact in facts)
    assert all(fact.source.raw_r2_uri for fact in facts)
    assert {f"{fact.period.type}:{fact.period.value}" for fact in facts} == {
        "month:2025-11"
    }
    assert records_by_id[
        "dwp_benefit_cap.month2025_11."
        "point_in_time_uc_households_by_amount_capped.gb_total.total"
    ].source_cell_addresses == ("D14", "D12")
    assert (
        values_by_record[
            "dwp_benefit_cap.month2025_11."
            "point_in_time_uc_households_by_amount_capped.gb_total.total"
        ].value
        == 110_637
    )
    up_to_100 = values_by_record[
        "dwp_benefit_cap.month2025_11."
        "point_in_time_uc_households_by_amount_capped.gb_total.up_to_100"
    ]
    assert up_to_100.value == 38_402
    assert {
        (constraint.variable, constraint.operator, constraint.value)
        for constraint in up_to_100.constraints
    } == {
        ("uk_benefit_cap.monthly_reduction_band", "==", "up_to_100"),
        ("uk_benefit_cap.monthly_reduction_amount", "<=", 100),
    }
    assert (
        values_by_record[
            "dwp_benefit_cap.month2025_11."
            "point_in_time_uc_households_by_amount_capped.gb_total."
            "1300_01_and_above"
        ].value
        == 627
    )


def test_source_package_alias_builds_dwp_uc_payment_dist_facts():
    package = load_source_package("dwp-uc-national-payment-dist-2025")
    cells = package.build_source_cells(2025)
    records = package.build_source_records(2025, cells=cells)
    facts = package.build_facts(2025, cells=cells)
    records_by_id = {record.source_record_id: record for record in records}
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert package.package_id == "dwp-uc-national-payment-dist-2025"
    assert len(cells) == 551
    assert validate_source_cells(cells).valid
    assert len(facts) == 104
    assert validate_facts(facts).valid
    assert all(fact.source.source_name == "dwp" for fact in facts)
    assert all(
        fact.source.source_file == "uc_national_payment_dist.xlsx" for fact in facts
    )
    assert all(fact.source.raw_r2_uri for fact in facts)
    assert {f"{fact.period.type}:{fact.period.value}" for fact in facts} == {
        "month:2025-05"
    }
    assert all(fact.geography.id == "GBR" for fact in facts)
    assert records_by_id[
        "dwp_uc.month2025_05."
        "households_by_monthly_award_band_and_family_type."
        "0_01_to_100.single_no_children"
    ].source_cell_addresses == ("D11", "D8")
    assert (
        values_by_record[
            "dwp_uc.month2025_05."
            "households_by_monthly_award_band_and_family_type."
            "0_01_to_100.single_no_children"
        ].value
        == 102_312
    )
    over_band = values_by_record[
        "dwp_uc.month2025_05.households_by_monthly_award_band_and_family_type."
        "2500_01_or_over.couple_with_children"
    ]
    assert over_band.value == 61_727
    assert {
        (constraint.variable, constraint.operator, constraint.value)
        for constraint in over_band.constraints
    } == {
        ("uk_universal_credit.family_type", "==", "couple_with_children"),
        ("uk_universal_credit.monthly_award_amount", ">", 2500),
        (
            "uk_universal_credit.monthly_award_band",
            "==",
            "2500_01_or_over",
        ),
    }


def test_source_package_alias_builds_dfc_ni_uc_claimant_facts():
    package = load_source_package("dfc-ni-uc-statistics-may-2025")
    cells = package.build_source_cells(2025)
    records = package.build_source_records(2025, cells=cells)
    facts = package.build_facts(2025, cells=cells)
    records_by_id = {record.source_record_id: record for record in records}
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert package.package_id == "dfc-ni-uc-statistics-may-2025"
    assert len(cells) == 23_169
    assert validate_source_cells(cells).valid
    assert len(facts) == 29
    assert validate_facts(facts).valid
    assert all(fact.source.source_name == "dfc_ni" for fact in facts)
    assert all(
        fact.source.source_file == "dfc-ni-uc-stats-supp-tables-may-2025.ods"
        for fact in facts
    )
    assert all(fact.source.raw_r2_uri for fact in facts)
    assert {f"{fact.period.type}:{fact.period.value}" for fact in facts} == {
        "month:2025-05"
    }
    assert {fact.entity.name for fact in facts} == {"person"}
    assert {fact.geography.level for fact in facts} == {
        "local_authority",
        "parliamentary_constituency",
    }

    belfast_east_id = (
        "dfc_ni_uc.month2025_05.n05000001_claimants.universal_credit.claimant_count"
    )
    belfast_south_id = (
        "dfc_ni_uc.month2025_05.n05000003_claimants.universal_credit.claimant_count"
    )
    west_tyrone_id = (
        "dfc_ni_uc.month2025_05.n05000018_claimants.universal_credit.claimant_count"
    )
    ards_and_north_down_id = (
        "dfc_ni_uc.month2025_05.n09000011_claimants.universal_credit.claimant_count"
    )
    belfast_lgd_id = (
        "dfc_ni_uc.month2025_05.n09000003_claimants.universal_credit.claimant_count"
    )
    assert records_by_id[belfast_east_id].source_cell_addresses == ("B95", "B3")
    assert records_by_id[belfast_south_id].source_cell_addresses == ("D95", "D3")
    assert records_by_id[west_tyrone_id].source_cell_addresses == ("S95", "S3")
    assert records_by_id[ards_and_north_down_id].source_cell_addresses == (
        "D95",
        "D3",
    )
    assert records_by_id[belfast_lgd_id].source_cell_addresses == ("E95", "E3")
    assert values_by_record[belfast_east_id].value == 11_850
    assert values_by_record[belfast_south_id].value == 9_420
    assert values_by_record[west_tyrone_id].value == 12_140
    assert values_by_record[ards_and_north_down_id].value == 15_320
    assert values_by_record[belfast_lgd_id].value == 53_450
    assert values_by_record[belfast_east_id].geography.id == "N05000001"
    assert values_by_record[west_tyrone_id].geography.id == "N05000018"
    assert values_by_record[ards_and_north_down_id].geography.id == "N09000011"
    assert values_by_record[belfast_lgd_id].geography.id == "N09000003"
    assert {
        (constraint.variable, constraint.operator, constraint.value)
        for constraint in values_by_record[belfast_east_id].constraints
    } == {("benefit.program", "==", "universal_credit")}


def test_source_package_alias_builds_ons_nomis_local_authority_age_facts():
    package = load_source_package("ons-nomis-local-authority-population-2024")
    rows = package.build_source_rows(2024)
    cells = package.build_source_cells(2024, source_rows=rows)
    records = package.build_source_records(2024, cells=cells, source_rows=rows)
    facts = package.build_facts(2024, cells=cells, source_rows=rows)
    records_by_id = {record.source_record_id: record for record in records}
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert package.package_id == "ons-nomis-local-authority-population-2024"
    assert len(rows) == 5_776
    assert validate_source_rows(rows).valid
    assert len(cells) == 196_418
    assert validate_source_cells(cells).valid
    assert len(facts) == 2_888
    assert validate_facts(facts).valid
    assert all(fact.source.source_name == "ons" for fact in facts)
    assert all(
        fact.source.source_file == "nomis_nm_2002_local_authority_age_bands_2024.csv"
        for fact in facts
    )
    assert all(fact.source.raw_r2_uri for fact in facts)
    assert {f"{fact.period.type}:{fact.period.value}" for fact in facts} == {
        "calendar_year:2024"
    }
    assert {fact.entity.name for fact in facts} == {"person"}
    assert {fact.geography.level for fact in facts} == {"local_authority"}

    hartlepool_0_10_id = (
        "ons_nomis_local_authority_population.cy2024.age_0_10."
        "e06000001_age_0_10.population_count"
    )
    ards_and_north_down_0_10_id = (
        "ons_nomis_local_authority_population.cy2024.age_0_10."
        "n09000011_age_0_10.population_count"
    )
    buckinghamshire_70_80_id = (
        "ons_nomis_local_authority_population.cy2024.age_70_80."
        "e06000060_age_70_80.population_count"
    )

    assert records_by_id[hartlepool_0_10_id].source_cell_addresses == (
        "AA2",
        "AA3",
        "AA1",
        "I3",
        "O2",
        "O3",
        "S2",
        "S3",
    )
    assert records_by_id[ards_and_north_down_0_10_id].source_cell_addresses == (
        "AA5762",
        "AA5763",
        "AA1",
        "I5763",
        "O5762",
        "O5763",
        "S5762",
        "S5763",
    )
    assert records_by_id[buckinghamshire_70_80_id].source_cell_addresses == (
        "AA3488",
        "AA3489",
        "AA1",
        "I3489",
        "O3488",
        "O3489",
        "S3488",
        "S3489",
    )
    assert values_by_record[hartlepool_0_10_id].value == 10_970
    assert values_by_record[ards_and_north_down_0_10_id].value == 16_885
    assert values_by_record[buckinghamshire_70_80_id].value == 48_824
    assert values_by_record[hartlepool_0_10_id].geography.id == "E06000001"
    assert values_by_record[ards_and_north_down_0_10_id].geography.id == "N09000011"
    assert values_by_record[buckinghamshire_70_80_id].geography.id == "E06000060"
    assert {
        (constraint.variable, constraint.operator, constraint.value)
        for constraint in values_by_record[hartlepool_0_10_id].constraints
    } == {("person.age", ">=", 0), ("person.age", "<", 10)}
    assert {
        (constraint.variable, constraint.operator, constraint.value)
        for constraint in values_by_record[buckinghamshire_70_80_id].constraints
    } == {("person.age", ">=", 70), ("person.age", "<", 80)}


def test_source_package_alias_builds_ons_small_area_income_local_authority_facts():
    package = load_source_package("ons-small-area-income-local-authority-2020")
    rows = package.build_source_rows(2020)
    cells = package.build_source_cells(2020, source_rows=rows)
    records = package.build_source_records(2020, cells=cells, source_rows=rows)
    facts = package.build_facts(2020, cells=cells, source_rows=rows)
    records_by_id = {record.source_record_id: record for record in records}
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert package.package_id == "ons-small-area-income-local-authority-2020"
    assert rows == []
    assert len(cells) == 288_635
    assert validate_source_cells(cells).valid
    assert len(facts) == 1_044
    assert validate_facts(facts).valid
    assert all(fact.source.source_name == "ons" for fact in facts)
    assert all(
        fact.source.source_file == "saiefy1920finalqaddownload280923.xlsx"
        for fact in facts
    )
    assert all(fact.source.raw_r2_uri for fact in facts)
    assert {f"{fact.period.type}:{fact.period.value}" for fact in facts} == {
        "fiscal_year:2019-20"
    }
    assert {fact.entity.name for fact in facts} == {"household"}
    assert {fact.geography.level for fact in facts} == {"local_authority"}

    hartlepool_total_income_id = (
        "ons_small_area_income.fye2020.local_authority.total_annual_income."
        "e06000001.total_annual_income"
    )
    hartlepool_bhc_income_id = (
        "ons_small_area_income.fye2020.local_authority.net_income_bhc."
        "e06000001.net_income_bhc"
    )
    hartlepool_ahc_income_id = (
        "ons_small_area_income.fye2020.local_authority.net_income_ahc."
        "e06000001.net_income_ahc"
    )

    expected_hartlepool_addresses = (
        "G87",
        "G88",
        "G89",
        "G90",
        "G91",
        "G92",
        "G93",
        "G94",
        "G95",
        "G96",
        "G97",
        "G98",
        "G5",
        "D87",
        "C98",
        "D98",
    )
    assert (
        records_by_id[hartlepool_total_income_id].source_cell_addresses
        == expected_hartlepool_addresses
    )
    assert (
        records_by_id[hartlepool_bhc_income_id].source_cell_addresses
        == expected_hartlepool_addresses
    )
    assert (
        records_by_id[hartlepool_ahc_income_id].source_cell_addresses
        == expected_hartlepool_addresses
    )
    assert values_by_record[hartlepool_total_income_id].value == pytest.approx(
        33_741.666666666664
    )
    assert values_by_record[hartlepool_bhc_income_id].value == pytest.approx(
        26_341.666666666664
    )
    assert values_by_record[hartlepool_ahc_income_id].value == pytest.approx(
        23_158.333333333332
    )
    assert values_by_record[hartlepool_total_income_id].geography.id == "E06000001"
    assert (
        values_by_record[hartlepool_total_income_id].measure.concept
        == "uk_income.total_annual_household_income.mean"
    )
    assert (
        values_by_record[hartlepool_bhc_income_id].measure.concept
        == "uk_income.net_income_before_housing_costs.mean"
    )
    assert (
        values_by_record[hartlepool_ahc_income_id].measure.concept
        == "uk_income.net_income_after_housing_costs.mean"
    )


def test_source_package_alias_builds_dwp_benefit_statistics_facts():
    package = load_source_package("dwp-benefit-statistics-february-2026")
    cells = package.build_source_cells(2025)
    records = package.build_source_records(2025, cells=cells)
    facts = package.build_facts(2025, cells=cells)
    records_by_id = {record.source_record_id: record for record in records}
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert package.package_id == "dwp-benefit-statistics-february-2026"
    assert len(cells) == 1_481
    assert validate_source_cells(cells).valid
    assert len(facts) == 12
    assert validate_facts(facts).valid
    assert all(fact.source.source_name == "dwp" for fact in facts)
    assert all(fact.source.source_file.endswith(".html") for fact in facts)
    assert all(fact.source.raw_r2_uri for fact in facts)
    assert {f"{fact.period.type}:{fact.period.value}" for fact in facts} == {
        "month:2025-08"
    }
    assert records_by_id[
        "dwp_benefit_statistics.month2025_08.headline_claimants."
        "employment_and_support_allowance.claimants"
    ].source_cell_addresses == ("B10", "B1")
    assert records_by_id[
        "dwp_benefit_statistics.month2025_08.esa_claimants_by_claim_type."
        "contributions_based.claimants"
    ].source_cell_addresses == ("E172", "E1")
    assert (
        values_by_record[
            "dwp_benefit_statistics.month2025_08.headline_claimants."
            "personal_independence_payment.claimants"
        ].value
        == 3_842_000
    )
    assert (
        values_by_record[
            "dwp_benefit_statistics.month2025_08.headline_claimants."
            "employment_and_support_allowance.claimants"
        ].value
        == 999_000
    )
    assert (
        values_by_record[
            "dwp_benefit_statistics.month2025_08.headline_claimants."
            "jobseekers_allowance.claimants"
        ].value
        == 71_000
    )
    income_related_esa = values_by_record[
        "dwp_benefit_statistics.month2025_08.esa_claimants_by_claim_type."
        "income_related.claimants"
    ]
    assert income_related_esa.value == 180_000
    assert {
        (constraint.variable, constraint.operator, constraint.value)
        for constraint in income_related_esa.constraints
    } == {
        (
            "uk_social_security.benefit",
            "==",
            "employment_and_support_allowance",
        ),
        ("uk_social_security.esa_claim_type", "==", "income_related"),
    }


def test_source_package_alias_builds_dwp_pip_daily_living_foi_facts():
    package = load_source_package("dwp-pip-daily-living-foi-2025")
    cells = package.build_source_cells(2025)
    records = package.build_source_records(2025, cells=cells)
    facts = package.build_facts(2025, cells=cells)
    records_by_id = {record.source_record_id: record for record in records}
    values_by_record = {fact.source_record_id: fact for fact in facts}

    assert package.package_id == "dwp-pip-daily-living-foi-2025"
    assert len(cells) == 44
    assert validate_source_cells(cells).valid
    assert len(facts) == 2
    assert validate_facts(facts).valid
    assert all(fact.source.source_name == "dwp" for fact in facts)
    assert all(fact.source.source_file.endswith(".html") for fact in facts)
    assert all(fact.source.raw_r2_uri for fact in facts)
    assert {f"{fact.period.type}:{fact.period.value}" for fact in facts} == {
        "month:2025-01"
    }
    assert {fact.geography.level for fact in facts} == {"statistical_scope"}
    assert records_by_id[
        "dwp_pip.month2025_01.daily_living_claimants_by_award_rate.enhanced.claimants"
    ].source_cell_addresses == ("B2", "B1")
    assert (
        values_by_record[
            "dwp_pip.month2025_01.daily_living_claimants_by_award_rate."
            "enhanced.claimants"
        ].value
        == 1_608_000
    )
    standard = values_by_record[
        "dwp_pip.month2025_01.daily_living_claimants_by_award_rate.standard.claimants"
    ]
    assert standard.value == 1_283_000
    assert {
        (constraint.variable, constraint.operator, constraint.value)
        for constraint in standard.constraints
    } == {
        (
            "uk_personal_independence_payment.claimant_age_group",
            "==",
            "working_age",
        ),
        (
            "uk_personal_independence_payment.component",
            "==",
            "daily_living",
        ),
        (
            "uk_personal_independence_payment.daily_living_award_status",
            "==",
            "standard",
        ),
        (
            "uk_personal_independence_payment.policy_ownership_scope",
            "==",
            "england_wales_abroad",
        ),
        (
            "uk_personal_independence_payment.rules",
            "==",
            "normal_rules",
        ),
    }


def test_obr_efo_receipts_selector_guards_fiscal_year_header():
    package = load_source_package("obr-efo-receipts")
    cells = package.build_source_cells(2025)
    spec = package.build_source_record_specs(2025)[0]
    bad_spec = replace(
        spec,
        selector=replace(spec.selector, expected_column_header="2024-25"),
    )

    with pytest.raises(ValueError, match="expected column header"):
        resolve_source_record(cells, bad_spec)


def test_build_suite_accepts_declarative_package_directory(tmp_path):
    package_path = REPO_ROOT / "packages" / "irs_soi" / "table_1_1"

    report = build_source_suite(package_path, tmp_path / "suite", year=2023)

    assert report.valid
    assert report.source == "soi-table-1-1"
    assert report.to_dict()["counts"]["source_record_count"] == 80


def test_validate_source_package_reports_counts():
    report = validate_source_package("soi-table-1-1", year=2023)

    assert report.valid
    assert report.counts == {
        "measure_count": 4,
        "record_set_count": 1,
        "row_count": 20,
        "source_record_count": 80,
        "source_region_count": 1,
    }


def test_validate_source_package_reports_historic_table_2_counts():
    report = validate_source_package("soi-historic-table-2", year=2022)

    assert report.valid
    assert report.counts == {
        "measure_count": 13,
        "record_set_count": 1,
        "row_count": 11,
        "source_record_count": 143,
        "source_region_count": 1,
    }


def test_validate_source_package_reports_cms_aca_oep_counts():
    report = validate_source_package("cms-aca-oep-state-level", year=2024)

    assert report.valid
    assert report.counts == {
        "measure_count": 3,
        "record_set_count": 1,
        "row_count": 51,
        "source_record_count": 153,
        "source_region_count": 1,
    }


def test_validate_source_package_reports_cms_aca_oep_2022_counts():
    report = validate_source_package("cms-aca-oep-state-level-2022", year=2022)

    assert report.valid
    assert report.counts == {
        "measure_count": 3,
        "record_set_count": 2,
        "row_count": 101,
        "source_record_count": 151,
        "source_region_count": 2,
    }


def test_validate_source_package_reports_cms_aca_oep_2025_counts():
    report = validate_source_package("cms-aca-oep-state-level-2025", year=2025)

    assert report.valid
    assert report.counts == {
        "measure_count": 3,
        "record_set_count": 1,
        "row_count": 51,
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
        "measure_count": 8,
        "record_set_count": 1,
        "row_count": 51,
        "source_record_count": 408,
        "source_region_count": 1,
    }


def test_validate_source_package_reports_kff_marketplace_enrollment_counts():
    report = validate_source_package(
        "kff-marketplace-effectuated-enrollment",
        year=2024,
    )

    assert report.valid
    assert report.counts == {
        "measure_count": 1,
        "record_set_count": 1,
        "row_count": 51,
        "source_record_count": 51,
        "source_region_count": 1,
    }


@pytest.mark.parametrize(
    ("source", "expected_counts"),
    [
        (
            "cms-aca-oep-state-level-2025",
            {
                "measure_count": 3,
                "record_set_count": 1,
                "row_count": 51,
                "source_record_count": 153,
                "source_region_count": 1,
            },
        ),
        (
            "kff-marketplace-effectuated-enrollment",
            {
                "measure_count": 1,
                "record_set_count": 1,
                "row_count": 51,
                "source_record_count": 51,
                "source_region_count": 1,
            },
        ),
        (
            "cms-aca-oep-state-level-2022",
            {
                "measure_count": 3,
                "record_set_count": 2,
                "row_count": 101,
                "source_record_count": 151,
                "source_region_count": 2,
            },
        ),
        (
            "cms-aca-effectuated-enrollment-2022",
            {
                "measure_count": 8,
                "record_set_count": 1,
                "row_count": 51,
                "source_record_count": 408,
                "source_region_count": 1,
            },
        ),
        (
            "cms-nhe-historical-service-source",
            {
                "measure_count": 1,
                "record_set_count": 1,
                "row_count": 1,
                "source_record_count": 1,
                "source_region_count": 1,
            },
        ),
        (
            "census-stc-individual-income-tax",
            {
                "measure_count": 46,
                "record_set_count": 46,
                "row_count": 46,
                "source_record_count": 46,
                "source_region_count": 46,
            },
        ),
        (
            "census-pep-2024-national-age-sex",
            {
                "measure_count": 1,
                "record_set_count": 1,
                "row_count": 19,
                "source_record_count": 19,
                "source_region_count": 1,
            },
        ),
        (
            "census-pep-2023-state-age-sex",
            {
                "measure_count": 51,
                "record_set_count": 51,
                "row_count": 102,
                "source_record_count": 102,
                "source_region_count": 51,
            },
        ),
        (
            "census-pep-2023-puerto-rico-age-sex",
            {
                "measure_count": 1,
                "record_set_count": 1,
                "row_count": 2,
                "source_record_count": 2,
                "source_region_count": 1,
            },
        ),
        (
            "census-acs-s0101-national-age-2024",
            {
                "measure_count": 1,
                "record_set_count": 1,
                "row_count": 18,
                "source_record_count": 18,
                "source_region_count": 1,
            },
        ),
        (
            "census-acs-s0101-state-age-2024",
            {
                "measure_count": 52,
                "record_set_count": 52,
                "row_count": 936,
                "source_record_count": 936,
                "source_region_count": 52,
            },
        ),
        (
            "census-acs-s0101-congressional-district-age-2024",
            {
                "measure_count": 437,
                "record_set_count": 437,
                "row_count": 7_866,
                "source_record_count": 7_866,
                "source_region_count": 437,
            },
        ),
        (
            "census-acs-s2201-congressional-district-snap-2024",
            {
                "measure_count": 437,
                "record_set_count": 437,
                "row_count": 1_311,
                "source_record_count": 1_311,
                "source_region_count": 437,
            },
        ),
        (
            "census-b01001-female-age-2023",
            {
                "measure_count": 52,
                "record_set_count": 52,
                "row_count": 468,
                "source_record_count": 468,
                "source_region_count": 52,
            },
        ),
        (
            "cdc-vsrr-live-births-monthly-2024",
            {
                "measure_count": 312,
                "record_set_count": 312,
                "row_count": 312,
                "source_record_count": 312,
                "source_region_count": 312,
            },
        ),
        (
            "cdc-vsrr-live-births-monthly-2023",
            {
                "measure_count": 624,
                "record_set_count": 624,
                "row_count": 624,
                "source_record_count": 624,
                "source_region_count": 624,
            },
        ),
        (
            "ons-families-households-2024",
            {
                "measure_count": 1,
                "record_set_count": 1,
                "row_count": 10,
                "source_record_count": 10,
                "source_region_count": 1,
            },
        ),
        (
            "hhs-acf-tanf-financial-2024",
            {
                "measure_count": 52,
                "record_set_count": 52,
                "row_count": 52,
                "source_record_count": 52,
                "source_region_count": 52,
            },
        ),
        (
            "hhs-acf-tanf-caseload-2024",
            {
                "measure_count": 8,
                "record_set_count": 3,
                "row_count": 53,
                "source_record_count": 58,
                "source_region_count": 3,
            },
        ),
        (
            "hhs-acf-liheap-fy2023-national-profile",
            {
                "measure_count": 1,
                "record_set_count": 1,
                "row_count": 1,
                "source_record_count": 1,
                "source_region_count": 1,
            },
        ),
        (
            "hhs-acf-liheap-fy2024-national-profile",
            {
                "measure_count": 1,
                "record_set_count": 1,
                "row_count": 1,
                "source_record_count": 1,
                "source_region_count": 1,
            },
        ),
        (
            "cms-medicare-trustees-report-2025-part-b-premium-income",
            {
                "measure_count": 1,
                "record_set_count": 1,
                "row_count": 1,
                "source_record_count": 1,
                "source_region_count": 1,
            },
        ),
        (
            "treasury-tax-expenditures-fy2023-eitc-outlays",
            {
                "measure_count": 1,
                "record_set_count": 1,
                "row_count": 1,
                "source_record_count": 1,
                "source_region_count": 1,
            },
        ),
        (
            "jct-tax-expenditures-2024-mortgage-interest-deduction",
            {
                "measure_count": 1,
                "record_set_count": 1,
                "row_count": 1,
                "source_record_count": 1,
                "source_region_count": 1,
            },
        ),
        (
            "soi-table-1-2",
            {
                "measure_count": 7,
                "record_set_count": 1,
                "row_count": 1,
                "source_record_count": 7,
                "source_region_count": 1,
            },
        ),
        (
            "soi-table-2-1",
            {
                "measure_count": 17,
                "record_set_count": 1,
                "row_count": 1,
                "source_record_count": 17,
                "source_region_count": 1,
            },
        ),
        (
            "soi-table-2-5",
            {
                "measure_count": 8,
                "record_set_count": 1,
                "row_count": 1,
                "source_record_count": 8,
                "source_region_count": 1,
            },
        ),
        (
            "soi-table-2-5-eitc-children-2020",
            {
                "measure_count": 8,
                "record_set_count": 4,
                "row_count": 4,
                "source_record_count": 8,
                "source_region_count": 4,
            },
        ),
        (
            "soi-table-2-5-eitc-agi-children-2022",
            {
                "measure_count": 8,
                "record_set_count": 4,
                "row_count": 112,
                "source_record_count": 224,
                "source_region_count": 4,
            },
        ),
        (
            "soi-table-4-3",
            {
                "measure_count": 18,
                "record_set_count": 1,
                "row_count": 1,
                "source_record_count": 18,
                "source_region_count": 1,
            },
        ),
        (
            "usda-snap-fy69-to-current",
            {
                "measure_count": 32,
                "record_set_count": 24,
                "row_count": 162,
                "source_record_count": 216,
                "source_region_count": 24,
            },
        ),
        (
            "cms-medicaid-chip-monthly-enrollment-dataset",
            {
                "measure_count": 5,
                "record_set_count": 1,
                "row_count": 51,
                "source_record_count": 255,
                "source_region_count": 1,
            },
        ),
        (
            "cms-medicaid-chip-monthly-enrollment-december-2024",
            {
                "measure_count": 5,
                "record_set_count": 1,
                "row_count": 51,
                "source_record_count": 255,
                "source_region_count": 1,
            },
        ),
        (
            "ssa-population-projections-tr2024",
            {
                "measure_count": 1,
                "record_set_count": 1,
                "row_count": 101,
                "source_record_count": 101,
                "source_region_count": 1,
            },
        ),
        (
            "census-population-projections-2023",
            {
                "measure_count": 86,
                "record_set_count": 86,
                "row_count": 86,
                "source_record_count": 86,
                "source_region_count": 86,
            },
        ),
        (
            "soi-historic-table-2-state-agi-2022",
            {
                "measure_count": 102,
                "record_set_count": 51,
                "row_count": 459,
                "source_record_count": 918,
                "source_region_count": 51,
            },
        ),
        (
            "soi-historic-table-2-state-eitc-2022",
            {
                "measure_count": 102,
                "record_set_count": 51,
                "row_count": 51,
                "source_record_count": 102,
                "source_region_count": 51,
            },
        ),
        (
            "cms-medicare-state-payment-of-premiums",
            {
                "measure_count": 2,
                "record_set_count": 2,
                "row_count": 2,
                "source_record_count": 2,
                "source_region_count": 2,
            },
        ),
        (
            "soi-ira-traditional-contributions-2022",
            {
                "measure_count": 2,
                "record_set_count": 1,
                "row_count": 1,
                "source_record_count": 2,
                "source_region_count": 1,
            },
        ),
        (
            "soi-ira-roth-contributions-2022",
            {
                "measure_count": 2,
                "record_set_count": 1,
                "row_count": 1,
                "source_record_count": 2,
                "source_region_count": 1,
            },
        ),
        (
            "soi-w2-statistics-2020",
            {
                "measure_count": 5,
                "record_set_count": 3,
                "row_count": 3,
                "source_record_count": 5,
                "source_region_count": 3,
            },
        ),
        (
            "federal-reserve-z1-household-net-worth",
            {
                "measure_count": 1,
                "record_set_count": 1,
                "row_count": 1,
                "source_record_count": 1,
                "source_region_count": 1,
            },
        ),
        (
            "bea-nipa-total-wages-salaries",
            {
                "measure_count": 3,
                "record_set_count": 3,
                "row_count": 3,
                "source_record_count": 3,
                "source_region_count": 3,
            },
        ),
        (
            "bea-nipa-personal-income-components",
            {
                "measure_count": 18,
                "record_set_count": 18,
                "row_count": 18,
                "source_record_count": 18,
                "source_region_count": 18,
            },
        ),
        (
            "bea-nipa-personal-income-disposition",
            {
                "measure_count": 6,
                "record_set_count": 6,
                "row_count": 6,
                "source_record_count": 6,
                "source_region_count": 6,
            },
        ),
        (
            "bea-regional-state-personal-income-components-2024",
            {
                "measure_count": 6,
                "record_set_count": 6,
                "row_count": 312,
                "source_record_count": 312,
                "source_region_count": 6,
            },
        ),
        (
            "dhs-ohss-unauthorized-immigrant-population-2018-2022",
            {
                "measure_count": 1,
                "record_set_count": 1,
                "row_count": 1,
                "source_record_count": 1,
                "source_region_count": 1,
            },
        ),
        (
            "cmsny-undocumented-population-2023",
            {
                "measure_count": 1,
                "record_set_count": 1,
                "row_count": 1,
                "source_record_count": 1,
                "source_region_count": 1,
            },
        ),
        (
            "psca-67th-annual-401k-survey-roth-availability",
            {
                "measure_count": 2,
                "record_set_count": 2,
                "row_count": 2,
                "source_record_count": 2,
                "source_region_count": 2,
            },
        ),
        (
            "vanguard-how-america-saves-2024-roth-participation",
            {
                "measure_count": 1,
                "record_set_count": 1,
                "row_count": 1,
                "source_record_count": 1,
                "source_region_count": 1,
            },
        ),
        (
            "dft-nts-household-car-availability-2024",
            {
                "measure_count": 1,
                "record_set_count": 1,
                "row_count": 3,
                "source_record_count": 3,
                "source_region_count": 1,
            },
        ),
    ],
)
def test_validate_source_package_reports_new_us_source_counts(
    source,
    expected_counts,
):
    if source == "soi-w2-statistics-2020":
        year = 2020
    elif source in {
        "cdc-vsrr-live-births-monthly-2023",
        "census-b01001-female-age-2023",
        "census-pep-2023-state-age-sex",
        "census-pep-2023-puerto-rico-age-sex",
    }:
        year = 2023
    elif source in {
        "soi-table-1-2",
        "soi-table-2-1",
        "soi-table-2-5",
        "soi-table-4-3",
        "usda-snap-fy69-to-current",
        "cms-medicaid-chip-monthly-enrollment-dataset",
        "cms-medicaid-chip-monthly-enrollment-december-2024",
        "cms-medicare-state-payment-of-premiums",
    }:
        if source == "usda-snap-fy69-to-current":
            year = 2024
        elif source == "cms-medicaid-chip-monthly-enrollment-dataset":
            year = 2026
        elif source == "cms-medicaid-chip-monthly-enrollment-december-2024":
            year = 2024
        elif source == "cms-medicare-state-payment-of-premiums":
            year = 2026
        else:
            year = 2023
    elif source == "dhs-ohss-unauthorized-immigrant-population-2018-2022":
        year = 2022
    elif source == "cmsny-undocumented-population-2023":
        year = 2023
    elif source == "psca-67th-annual-401k-survey-roth-availability":
        year = 2023
    elif source == "vanguard-how-america-saves-2024-roth-participation":
        year = 2024
    elif source == "hhs-acf-liheap-fy2023-national-profile":
        year = 2023
    elif source == "cms-medicare-trustees-report-2025-part-b-premium-income":
        year = 2025
    elif source == "treasury-tax-expenditures-fy2023-eitc-outlays":
        year = 2023
    elif source == "jct-tax-expenditures-2024-mortgage-interest-deduction":
        year = 2024
    elif source == "cms-aca-oep-state-level-2025":
        year = 2025
    elif source == "soi-table-2-5-eitc-children-2020":
        year = 2020
    elif source in {
        "census-population-projections-2023",
        "ssa-population-projections-tr2024",
    }:
        year = 2025
    elif source.startswith("soi-ira") or source in {
        "soi-historic-table-2-state-agi-2022",
        "soi-historic-table-2-state-eitc-2022",
        "soi-table-2-5-eitc-agi-children-2022",
        "cms-aca-oep-state-level-2022",
        "cms-aca-effectuated-enrollment-2022",
    }:
        year = 2022
    else:
        year = 2024
    report = validate_source_package(source, year=year)

    assert report.valid
    assert report.counts == expected_counts


@pytest.mark.parametrize("year", [2025, 2026])
def test_validate_source_package_reports_obr_efo_receipts_counts(year):
    report = validate_source_package("obr-efo-receipts", year=year)

    assert report.valid
    assert report.counts == {
        "measure_count": 9,
        "record_set_count": 9,
        "row_count": 9,
        "source_record_count": 9,
        "source_region_count": 9,
    }


@pytest.mark.parametrize("year", [2025, 2026])
def test_validate_source_package_reports_obr_efo_expenditure_counts(year):
    report = validate_source_package("obr-efo-expenditure", year=year)

    assert report.valid
    assert report.counts == {
        "measure_count": 19,
        "record_set_count": 19,
        "row_count": 19,
        "source_record_count": 19,
        "source_region_count": 19,
    }


def test_validate_source_package_reports_slc_student_support_counts():
    report = validate_source_package("slc-student-support-england-2025", year=2025)

    assert report.valid
    assert report.counts == {
        "measure_count": 4,
        "record_set_count": 4,
        "row_count": 6,
        "source_record_count": 6,
        "source_region_count": 4,
    }


def test_validate_source_package_reports_slc_borrower_forecast_counts():
    report = validate_source_package(
        "slc-student-loan-borrower-forecasts-england-2025",
        year=2025,
    )

    assert report.valid
    assert report.counts == {
        "measure_count": 2,
        "record_set_count": 2,
        "row_count": 4,
        "source_record_count": 4,
        "source_region_count": 2,
    }


def test_validate_source_package_reports_slc_repayment_england_counts():
    report = validate_source_package(
        "slc-student-loan-repayments-england-2025",
        year=2025,
    )

    assert report.valid
    assert report.counts == {
        "measure_count": 8,
        "record_set_count": 1,
        "row_count": 1,
        "source_record_count": 8,
        "source_region_count": 1,
    }


@pytest.mark.parametrize(
    "source",
    [
        "slc-student-loan-repayments-scotland-2025",
        "slc-student-loan-repayments-wales-2025",
        "slc-student-loan-repayments-northern-ireland-2025",
    ],
)
def test_validate_source_package_reports_slc_repayment_country_counts(source):
    report = validate_source_package(source, year=2025)

    assert report.valid
    assert report.counts == {
        "measure_count": 1,
        "record_set_count": 1,
        "row_count": 1,
        "source_record_count": 1,
        "source_region_count": 1,
    }


def test_validate_source_package_reports_hmrc_salary_sacrifice_relief_counts():
    report = validate_source_package("hmrc-salary-sacrifice-relief-2024", year=2024)

    assert report.valid
    assert report.counts == {
        "measure_count": 2,
        "record_set_count": 2,
        "row_count": 6,
        "source_record_count": 6,
        "source_region_count": 2,
    }


def test_validate_source_package_reports_hmrc_salary_sacrifice_reform_counts():
    report = validate_source_package("hmrc-salary-sacrifice-reform-2025", year=2025)

    assert report.valid
    assert report.counts == {
        "measure_count": 1,
        "record_set_count": 1,
        "row_count": 3,
        "source_record_count": 3,
        "source_region_count": 1,
    }


def test_validate_source_package_reports_hmt_budget_salary_sacrifice_counts():
    report = validate_source_package(
        "hmt-budget-policy-costings-2025-salary-sacrifice",
        year=2025,
    )

    assert report.valid
    assert report.counts == {
        "measure_count": 1,
        "record_set_count": 1,
        "row_count": 1,
        "source_record_count": 1,
        "source_region_count": 1,
    }


def test_validate_source_package_reports_isc_census_pupil_count_counts():
    report = validate_source_package("isc-census-2024-pupil-count", year=2024)

    assert report.valid
    assert report.counts == {
        "measure_count": 1,
        "record_set_count": 1,
        "row_count": 1,
        "source_record_count": 1,
        "source_region_count": 1,
    }


def test_validate_source_package_reports_hmrc_spi_income_band_counts():
    report = validate_source_package("hmrc-spi-income-bands-2023", year=2023)

    assert report.valid
    assert report.counts == {
        "measure_count": 12,
        "record_set_count": 2,
        "row_count": 26,
        "source_record_count": 156,
        "source_region_count": 2,
    }


def test_validate_source_package_reports_hmrc_spi_projection_counts():
    report = validate_source_package("hmrc-spi-income-projection-2026", year=2026)

    assert report.valid
    assert report.counts == {
        "measure_count": 12,
        "record_set_count": 1,
        "row_count": 12,
        "source_record_count": 144,
        "source_region_count": 1,
    }


def test_validate_source_package_reports_hmrc_spi_local_income_counts():
    report = validate_source_package("hmrc-spi-local-income-2022", year=2022)

    assert report.valid
    assert report.counts == {
        "measure_count": 8,
        "record_set_count": 2,
        "row_count": 1022,
        "source_record_count": 4088,
        "source_region_count": 2,
    }


def test_validate_source_package_reports_ons_savings_interest_counts():
    report = validate_source_package("ons-savings-interest-income", year=2023)

    assert report.valid
    assert report.counts == {
        "measure_count": 1,
        "record_set_count": 1,
        "row_count": 1,
        "source_record_count": 1,
        "source_region_count": 1,
    }


def test_validate_source_package_reports_ons_private_rent_counts():
    report = validate_source_package(
        "ons-private-rent-house-prices-march-2026",
        year=2026,
    )

    assert report.valid
    assert report.counts == {
        "measure_count": 1,
        "record_set_count": 1,
        "row_count": 1,
        "source_record_count": 1,
        "source_region_count": 1,
    }


def test_validate_source_package_reports_mhclg_ehs_social_rent_counts():
    report = validate_source_package(
        "mhclg-english-housing-survey-rented-sectors-2023-24",
        year=2024,
    )

    assert report.valid
    assert report.counts == {
        "measure_count": 1,
        "record_set_count": 1,
        "row_count": 1,
        "source_record_count": 1,
        "source_region_count": 1,
    }


def test_validate_source_package_reports_ons_population_projection_counts():
    report = validate_source_package("ons-uk-population-projections-2022", year=2022)

    assert report.valid
    assert report.counts == {
        "measure_count": 1,
        "record_set_count": 1,
        "row_count": 13,
        "source_record_count": 13,
        "source_region_count": 1,
    }


def test_validate_source_package_reports_ons_demographics_profile_counts():
    report = validate_source_package("ons-demographics-profile-2026", year=2026)

    assert report.valid
    assert report.counts == {
        "measure_count": 1,
        "record_set_count": 1,
        "row_count": 110,
        "source_record_count": 110,
        "source_region_count": 1,
    }


def test_validate_source_package_reports_ons_regional_land_profile_counts():
    report = validate_source_package("ons-regional-land-profile-2026", year=2026)

    assert report.valid
    assert report.counts == {
        "measure_count": 2,
        "record_set_count": 1,
        "row_count": 11,
        "source_record_count": 22,
        "source_region_count": 1,
    }


def test_validate_source_package_reports_nrs_live_birth_counts():
    report = validate_source_package(
        "nrs-vital-events-reference-tables-2024",
        year=2024,
    )

    assert report.valid
    assert report.counts == {
        "measure_count": 1,
        "record_set_count": 1,
        "row_count": 1,
        "source_record_count": 1,
        "source_region_count": 1,
    }


def test_validate_source_package_reports_nrs_children_under_16_counts():
    report = validate_source_package(
        "nrs-mid-year-population-estimates-2024",
        year=2024,
    )

    assert report.valid
    assert report.counts == {
        "measure_count": 1,
        "record_set_count": 1,
        "row_count": 1,
        "source_record_count": 1,
        "source_region_count": 1,
    }


def test_validate_source_package_reports_ons_dwelling_tenure_counts():
    report = validate_source_package(
        "ons-subnational-dwellings-by-tenure-2024",
        year=2024,
    )

    assert report.valid
    assert report.counts == {
        "measure_count": 5,
        "record_set_count": 2,
        "row_count": 2,
        "source_record_count": 5,
        "source_region_count": 2,
    }


def test_validate_source_package_reports_ons_nbs_land_counts():
    report = validate_source_package(
        "ons-national-balance-sheet-land-2025",
        year=2024,
    )

    assert report.valid
    assert report.counts == {
        "measure_count": 5,
        "record_set_count": 5,
        "row_count": 5,
        "source_record_count": 5,
        "source_region_count": 5,
    }


def test_validate_source_package_reports_voa_council_tax_band_counts():
    report = validate_source_package("voa-council-tax-bands-2025", year=2025)

    assert report.valid
    assert report.counts == {
        "measure_count": 18,
        "record_set_count": 10,
        "row_count": 2573,
        "source_record_count": 2653,
        "source_region_count": 10,
    }


def test_validate_source_package_reports_scotgov_council_tax_band_counts():
    report = validate_source_package("scotgov-council-tax-bands-2025", year=2025)

    assert report.valid
    assert report.counts == {
        "measure_count": 9,
        "record_set_count": 1,
        "row_count": 1,
        "source_record_count": 9,
        "source_region_count": 1,
    }


def test_validate_source_package_reports_scotgov_scottish_child_payment_counts():
    report = validate_source_package(
        "scotgov-scottish-budget-social-security-assistance-2026",
        year=2026,
    )

    assert report.valid
    assert report.counts == {
        "measure_count": 2,
        "record_set_count": 2,
        "row_count": 2,
        "source_record_count": 2,
        "source_region_count": 2,
    }


def test_validate_source_package_reports_dwp_uc_two_child_limit_counts():
    report = validate_source_package("dwp-uc-two-child-limit-2025", year=2026)

    assert report.valid
    assert report.counts == {
        "measure_count": 42,
        "record_set_count": 9,
        "row_count": 9,
        "source_record_count": 42,
        "source_region_count": 9,
    }


def test_validate_source_package_reports_dwp_benefit_cap_counts():
    report = validate_source_package("dwp-benefit-cap-november-2025", year=2025)

    assert report.valid
    assert report.counts == {
        "measure_count": 15,
        "record_set_count": 1,
        "row_count": 1,
        "source_record_count": 15,
        "source_region_count": 1,
    }


def test_validate_source_package_reports_dwp_uc_payment_dist_counts():
    report = validate_source_package("dwp-uc-national-payment-dist-2025", year=2025)

    assert report.valid
    assert report.counts == {
        "measure_count": 4,
        "record_set_count": 1,
        "row_count": 26,
        "source_record_count": 104,
        "source_region_count": 1,
    }


def test_validate_source_package_reports_dfc_ni_uc_claimant_counts():
    report = validate_source_package("dfc-ni-uc-statistics-may-2025", year=2025)

    assert report.valid
    assert report.counts == {
        "measure_count": 29,
        "record_set_count": 29,
        "row_count": 29,
        "source_record_count": 29,
        "source_region_count": 29,
    }


def test_validate_source_package_reports_ons_nomis_local_authority_age_counts():
    report = validate_source_package(
        "ons-nomis-local-authority-population-2024",
        year=2024,
    )

    assert report.valid
    assert report.counts == {
        "measure_count": 8,
        "record_set_count": 8,
        "row_count": 2888,
        "source_record_count": 2888,
        "source_region_count": 8,
    }


def test_validate_source_package_reports_ons_small_area_income_local_authority_counts():
    report = validate_source_package(
        "ons-small-area-income-local-authority-2020",
        year=2020,
    )

    assert report.valid
    assert report.counts == {
        "measure_count": 3,
        "record_set_count": 3,
        "row_count": 1044,
        "source_record_count": 1044,
        "source_region_count": 3,
    }


def test_validate_source_package_reports_dwp_benefit_statistics_counts():
    report = validate_source_package(
        "dwp-benefit-statistics-february-2026",
        year=2025,
    )

    assert report.valid
    assert report.counts == {
        "measure_count": 2,
        "record_set_count": 2,
        "row_count": 12,
        "source_record_count": 12,
        "source_region_count": 2,
    }


def test_validate_source_package_reports_dwp_pip_daily_living_foi_counts():
    report = validate_source_package("dwp-pip-daily-living-foi-2025", year=2025)

    assert report.valid
    assert report.counts == {
        "measure_count": 1,
        "record_set_count": 1,
        "row_count": 2,
        "source_record_count": 2,
        "source_region_count": 1,
    }


def test_validate_source_package_catches_authoring_errors(tmp_path):
    source_path = REPO_ROOT / "packages" / "irs_soi" / "table_1_1"
    payload = yaml.safe_load((source_path / "source_package.yaml").read_text())
    record_set = payload["record_sets"][0]
    record_set["rows"][2]["value_id"] = record_set["rows"][1]["value_id"]
    record_set["rows"][3]["constraints"] = []
    record_set["measures"][1]["column"] = "B10"
    record_set["measures"][1].pop("concept_evidence_notes")
    record_set["measures"][1].pop("concept_evidence_url")

    package_dir = tmp_path / "bad-package"
    package_dir.mkdir()
    (package_dir / "source_package.yaml").write_text(yaml.safe_dump(payload))

    report = validate_source_package(package_dir, year=2023)
    error_codes = {error.code for error in report.errors}

    assert not report.valid
    assert {
        "duplicate_row_id",
        "duplicate_source_record_id",
        "malformed_measure_column",
        "missing_bound_constraint",
        "missing_concept_evidence",
        "missing_row_constraints",
    } <= error_codes


def test_validate_source_package_reports_invalid_row_guard(tmp_path):
    source_path = REPO_ROOT / "packages" / "irs_soi" / "table_1_1"
    payload = yaml.safe_load((source_path / "source_package.yaml").read_text())
    payload["record_sets"][0]["rows"][0]["guard_cells"] = [
        {
            "column": "A",
            "expected_value": "Selected row",
            "row": "end",
        }
    ]

    package_dir = tmp_path / "bad-row-guard-package"
    package_dir.mkdir()
    (package_dir / "source_package.yaml").write_text(yaml.safe_dump(payload))

    report = validate_source_package(package_dir, year=2023)

    assert not report.valid
    assert any(
        error.code == "source_record_compile_failed"
        and "End row guard requires row_end_number" in error.message
        for error in report.errors
    )


def test_validate_source_package_reports_malformed_row_guard_column(tmp_path):
    source_path = REPO_ROOT / "packages" / "irs_soi" / "table_1_1"
    payload = yaml.safe_load((source_path / "source_package.yaml").read_text())
    payload["record_sets"][0]["rows"][0]["guard_cells"] = [
        {
            "column": "B ",
            "expected_value": "All returns",
        }
    ]

    package_dir = tmp_path / "bad-row-guard-column-package"
    package_dir.mkdir()
    (package_dir / "source_package.yaml").write_text(yaml.safe_dump(payload))

    report = validate_source_package(package_dir, year=2023)

    assert not report.valid
    assert any(
        error.code == "record_set_compile_failed"
        and "Malformed row_guard column" in error.message
        for error in report.errors
    )


def test_validate_source_package_reports_invalid_numeric_row_guard(tmp_path):
    source_path = REPO_ROOT / "packages" / "irs_soi" / "table_1_1"
    payload = yaml.safe_load((source_path / "source_package.yaml").read_text())
    payload["record_sets"][0]["rows"][0]["guard_cells"] = [
        {
            "column": "A",
            "expected_value": "All returns",
            "row": 0,
        }
    ]

    package_dir = tmp_path / "bad-numeric-row-guard-package"
    package_dir.mkdir()
    (package_dir / "source_package.yaml").write_text(yaml.safe_dump(payload))

    report = validate_source_package(package_dir, year=2023)

    assert not report.valid
    assert any(
        error.code == "source_record_compile_failed"
        and "Row guard row must be at least 1" in error.message
        for error in report.errors
    )


def test_validate_source_package_reports_boolean_row_guard(tmp_path):
    source_path = REPO_ROOT / "packages" / "irs_soi" / "table_1_1"
    payload = yaml.safe_load((source_path / "source_package.yaml").read_text())
    payload["record_sets"][0]["rows"][0]["guard_cells"] = [
        {
            "column": "A",
            "expected_value": "All returns",
            "row": True,
        }
    ]

    package_dir = tmp_path / "boolean-row-guard-package"
    package_dir.mkdir()
    (package_dir / "source_package.yaml").write_text(yaml.safe_dump(payload))

    report = validate_source_package(package_dir, year=2023)

    assert not report.valid
    assert any(
        error.code == "source_record_compile_failed"
        and "Row guard row must not be boolean" in error.message
        for error in report.errors
    )


def test_validate_source_package_reports_malformed_range_label_guard(tmp_path):
    source_path = REPO_ROOT / "packages" / "irs_soi" / "table_1_1"
    payload = yaml.safe_load((source_path / "source_package.yaml").read_text())
    row = payload["record_sets"][0]["rows"][0]
    row["row_end_number"] = row["row_number"] + 1
    row["range_label_guards"] = [
        {
            "column": "1",
            "expected_values": ["All returns", "$1 under $5,000"],
        }
    ]

    package_dir = tmp_path / "bad-range-label-column-package"
    package_dir.mkdir()
    (package_dir / "source_package.yaml").write_text(yaml.safe_dump(payload))

    report = validate_source_package(package_dir, year=2023)

    assert not report.valid
    assert any(
        error.code == "record_set_compile_failed"
        and "Malformed range_label_guard column" in error.message
        for error in report.errors
    )


def test_validate_source_package_reports_range_label_guard_length(tmp_path):
    source_path = REPO_ROOT / "packages" / "irs_soi" / "table_1_1"
    payload = yaml.safe_load((source_path / "source_package.yaml").read_text())
    row = payload["record_sets"][0]["rows"][0]
    row["row_end_number"] = row["row_number"] + 1
    row["range_label_guards"] = [
        {
            "column": "A",
            "expected_values": ["All returns"],
        }
    ]

    package_dir = tmp_path / "bad-range-label-length-package"
    package_dir.mkdir()
    (package_dir / "source_package.yaml").write_text(yaml.safe_dump(payload))

    report = validate_source_package(package_dir, year=2023)

    assert not report.valid
    assert any(
        error.code == "source_record_compile_failed"
        and "Range label guard" in error.message
        for error in report.errors
    )


def test_validate_source_package_reports_ambiguous_range_label_values(tmp_path):
    source_path = REPO_ROOT / "packages" / "irs_soi" / "table_1_1"
    payload = yaml.safe_load((source_path / "source_package.yaml").read_text())
    row = payload["record_sets"][0]["rows"][0]
    row["row_end_number"] = row["row_number"] + 1
    row["range_label_guards"] = [
        {
            "column": "A",
            "expected_values": {
                "integer_range": {
                    "start": 1,
                    "end": 2,
                },
                "parts": [["All returns", "$1 under $5,000"]],
            },
        }
    ]

    package_dir = tmp_path / "ambiguous-range-label-values-package"
    package_dir.mkdir()
    (package_dir / "source_package.yaml").write_text(yaml.safe_dump(payload))

    report = validate_source_package(package_dir, year=2023)

    assert not report.valid
    assert any(
        error.code == "record_set_compile_failed"
        and "exactly one compact form" in error.message
        for error in report.errors
    )


def test_validate_source_package_reports_null_range_label_value(tmp_path):
    source_path = REPO_ROOT / "packages" / "irs_soi" / "table_1_1"
    payload = yaml.safe_load((source_path / "source_package.yaml").read_text())
    row = payload["record_sets"][0]["rows"][0]
    row["row_end_number"] = row["row_number"] + 1
    row["range_label_guards"] = [
        {
            "column": "A",
            "expected_values": ["All returns", None],
        }
    ]

    package_dir = tmp_path / "null-range-label-value-package"
    package_dir.mkdir()
    (package_dir / "source_package.yaml").write_text(yaml.safe_dump(payload))

    report = validate_source_package(package_dir, year=2023)

    assert not report.valid
    assert any(
        error.code == "record_set_compile_failed"
        and "must not contain null" in error.message
        for error in report.errors
    )


def test_scaffold_source_package_writes_todo_template(tmp_path):
    report = scaffold_source_package(
        tmp_path / "package",
        source_id="irs_soi",
        package_id="soi-table-1-2",
        source_table="Publication 1304 Table 1.2",
        resource_directory="data/irs_soi/table_1_2",
    )
    source_package = Path(report.source_package_path)
    content = source_package.read_text()

    assert source_package.exists()
    assert "package_id: soi-table-1-2" in content
    assert "source_name: irs_soi" in content
    assert "TODO" in content


def test_source_package_cli_commands_emit_json(tmp_path, capsys):
    exit_code = harness_main(
        [
            "validate-package",
            "packages/irs_soi/table_1_4",
            "--year",
            "2023",
        ]
    )
    validate_payload = yaml.safe_load(capsys.readouterr().out)

    assert exit_code == 0
    assert validate_payload["valid"]
    assert validate_payload["counts"]["source_record_count"] == 260

    exit_code = harness_main(
        [
            "scaffold-package",
            "--source-id",
            "irs_soi",
            "--package-id",
            "soi-table-test",
            "--out",
            str(tmp_path / "scaffolded"),
        ]
    )
    scaffold_payload = yaml.safe_load(capsys.readouterr().out)

    assert exit_code == 0
    assert scaffold_payload["package_id"] == "soi-table-test"
    assert (tmp_path / "scaffolded" / "source_package.yaml").exists()
