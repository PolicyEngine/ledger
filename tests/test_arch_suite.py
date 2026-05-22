"""Tests for the Arch source-package build suite."""

from __future__ import annotations

import json
import sqlite3
import textwrap

from arch.concepts import ConceptAlignmentReport
from arch.core import (
    Aggregation,
    AggregateConstraint,
    AggregateFact,
    EntityDimension,
    GeographyDimension,
    Measure,
    PeriodDimension,
    SourceProvenance,
    SourceRecordLayout,
    validate_facts,
)
from arch.harness import main as harness_main
from arch.sources.cells import (
    SourceArtifactMetadata,
    SourceCell,
    build_source_cell_key,
    validate_source_cells,
)
from arch.sources.rows import SourceRow, build_source_row_key, validate_source_rows
from arch.suite import (
    SourceRecordSuiteReport,
    SourceRegionSuiteReport,
    build_agent_acceptance_report,
    build_source_cells,
    build_source_record_specs,
    build_source_regions,
    build_source_suite,
    validate_source_record_specs,
    validate_source_regions,
)


def test_build_source_suite_writes_artifacts_and_reports(tmp_path):
    output_dir = tmp_path / "suite"

    report = build_source_suite("soi-table-1-1", output_dir, year=2023)
    summary = json.loads((output_dir / "reports" / "build_summary.json").read_text())

    assert report.valid
    assert summary["valid"]
    assert summary["counts"] == {
        "artifact_count": 1,
        "agent_acceptance_error_count": 0,
        "concept_alignment_count": 1,
        "constraint_count": 144,
        "consumer_fact_count": 80,
        "fact_count": 80,
        "lineage_coverage": 1.0,
        "source_cell_count": 1932,
        "source_record_count": 80,
        "source_region_count": 1,
        "source_row_count": 0,
    }
    assert (output_dir / "source_cells.jsonl").exists()
    assert (output_dir / "source_regions.jsonl").exists()
    assert (output_dir / "facts.jsonl").exists()
    assert (output_dir / "consumer_facts.jsonl").exists()
    assert (output_dir / "arch.db").exists()
    assert (output_dir / "datapackage.json").exists()
    assert (output_dir / "ro-crate-metadata.json").exists()
    assert (output_dir / "reports" / "source_regions.json").exists()
    assert (output_dir / "reports" / "selectors.json").exists()
    assert (output_dir / "reports" / "source_records.json").exists()
    assert (output_dir / "reports" / "consumer_facts.json").exists()
    assert (output_dir / "reports" / "agent_acceptance.json").exists()
    consumer_facts = [
        json.loads(line)
        for line in (output_dir / "consumer_facts.jsonl").read_text().splitlines()
    ]
    datapackage = json.loads((output_dir / "datapackage.json").read_text())
    acceptance = json.loads(
        (output_dir / "reports" / "agent_acceptance.json").read_text()
    )

    assert len(consumer_facts) == 80
    assert consumer_facts[0]["aggregate_fact_key"].startswith(
        "arch.aggregate_fact.v2:"
    )
    assert consumer_facts[0]["semantic_fact_key"].startswith(
        "arch.semantic_fact.v2:"
    )
    assert datapackage["profile"] == "data-package"
    assert {resource["path"] for resource in datapackage["resources"]} >= {
        "source_cells.jsonl",
        "source_regions.jsonl",
        "facts.jsonl",
        "consumer_facts.jsonl",
        "arch.db",
        "reports/build_summary.json",
        "reports/source_regions.json",
        "reports/selectors.json",
        "reports/consumer_facts.json",
        "reports/agent_acceptance.json",
    }
    assert acceptance["valid"]
    assert acceptance["checks"] == {
        "concept_alignments_have_evidence": True,
        "concept_alignments_resolve": True,
        "expected_constraints_present": True,
        "facts_have_provenance": True,
        "facts_have_source_cell_lineage": True,
        "facts_have_source_row_lineage": True,
        "full_source_document_parsed": True,
        "raw_artifacts_have_r2": True,
        "required_concept_alignments_validated": True,
        "row_lineage_semantics_evidenced": True,
        "selected_row_only_parser_not_used": True,
        "stage_reports_valid": True,
    }
    assert [warning["code"] for warning in acceptance["warnings"]] == [
        "concept_alignment_validation_skipped"
    ]

    with sqlite3.connect(output_dir / "arch.db") as connection:
        facts_count = connection.execute(
            "SELECT COUNT(*) FROM aggregate_facts"
        ).fetchone()[0]

    assert facts_count == 80


def test_build_source_suite_supports_soi_table_1_4(tmp_path):
    output_dir = tmp_path / "suite"

    report = build_source_suite("soi-table-1-4", output_dir, year=2023)
    summary = json.loads((output_dir / "reports" / "build_summary.json").read_text())

    assert report.valid
    assert summary["counts"] == {
        "artifact_count": 1,
        "agent_acceptance_error_count": 0,
        "concept_alignment_count": 1,
        "constraint_count": 432,
        "consumer_fact_count": 240,
        "fact_count": 240,
        "lineage_coverage": 1.0,
        "source_cell_count": 8109,
        "source_record_count": 240,
        "source_region_count": 1,
        "source_row_count": 0,
    }
    assert summary["reports"]["source_regions"]["covered_cell_count"] == 1780
    assert summary["reports"]["agent_acceptance"]["valid"]
    assert summary["reports"]["agent_acceptance"]["warnings"][0]["code"] == (
        "concept_alignment_validation_skipped"
    )
    assert (output_dir / "source_regions.jsonl").exists()
    assert (output_dir / "arch.db").exists()


def test_build_source_suite_supports_bea_full_source_rows(tmp_path):
    output_dir = tmp_path / "suite"

    report = build_source_suite(
        "bea-nipa-pension-contributions",
        output_dir,
        year=2022,
    )
    summary = json.loads((output_dir / "reports" / "build_summary.json").read_text())

    assert report.valid
    assert summary["counts"]["source_row_count"] == 559_069
    assert summary["counts"]["source_cell_count"] == 9
    assert summary["counts"]["fact_count"] == 2
    assert summary["counts"]["consumer_fact_count"] == 2
    assert summary["reports"]["source_rows"]["valid"]
    assert summary["reports"]["database"]["source_columns_count"] == 3
    assert summary["reports"]["database"]["source_row_values_count"] == 1_677_207
    assert summary["reports"]["agent_acceptance"]["checks"][
        "facts_have_source_row_lineage"
    ]
    assert (output_dir / "source_rows.jsonl").exists()
    assert (output_dir / "arch.db").exists()

    with sqlite3.connect(output_dir / "arch.db") as connection:
        connection.row_factory = sqlite3.Row
        source_rows_count = connection.execute(
            "SELECT COUNT(*) FROM source_rows"
        ).fetchone()[0]
        source_columns_count = connection.execute(
            "SELECT COUNT(*) FROM source_columns"
        ).fetchone()[0]
        source_row_values_count = connection.execute(
            "SELECT COUNT(*) FROM source_row_values"
        ).fetchone()[0]
        fact_source_rows_count = connection.execute(
            "SELECT COUNT(*) FROM fact_source_rows"
        ).fetchone()[0]
        fact_row_values = connection.execute(
            """
            SELECT
                source_row_values.raw_column_name,
                source_row_values.normalized_column_name,
                source_row_values.value_text,
                source_row_values.value_numeric
            FROM aggregate_facts
            JOIN fact_source_rows
              ON fact_source_rows.fact_key = aggregate_facts.fact_key
            JOIN source_row_values
              ON source_row_values.source_row_key = fact_source_rows.source_row_key
            WHERE aggregate_facts.source_record_id = ?
            ORDER BY source_row_values.column_number
            """,
            (
                "bea_nipa.cy2022.defined_contribution_employer_contributions."
                "w351rc.employer_contributions",
            ),
        ).fetchall()

    assert source_rows_count == 559_069
    assert source_columns_count == 3
    assert source_row_values_count == 1_677_207
    assert fact_source_rows_count == 2
    assert [tuple(row) for row in fact_row_values] == [
        ("SeriesCode", "series_code", "W351RC", None),
        ("Period", "period", "2022", 2022.0),
        ("Value", "value", "247468", 247468.0),
    ]
    assert summary["reports"]["agent_acceptance"]["checks"][
        "row_lineage_semantics_evidenced"
    ]


def test_build_source_suite_supports_soi_historic_table_2_rows(tmp_path):
    output_dir = tmp_path / "suite"

    report = build_source_suite(
        "soi-historic-table-2",
        output_dir,
        year=2022,
    )
    summary = json.loads((output_dir / "reports" / "build_summary.json").read_text())

    assert report.valid
    assert summary["counts"] == {
        "artifact_count": 1,
        "agent_acceptance_error_count": 0,
        "concept_alignment_count": 1,
        "constraint_count": 234,
        "consumer_fact_count": 143,
        "fact_count": 143,
        "lineage_coverage": 1.0,
        "source_cell_count": 1956,
        "source_record_count": 143,
        "source_region_count": 1,
        "source_row_count": 594,
    }
    assert summary["reports"]["database"]["source_columns_count"] == 163
    assert summary["reports"]["database"]["source_row_values_count"] == 96_822
    assert summary["reports"]["agent_acceptance"]["checks"][
        "row_lineage_semantics_evidenced"
    ]
    assert summary["reports"]["agent_acceptance"]["valid"]


def test_agent_acceptance_rejects_row_constraints_without_source_evidence():
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
        raw_r2_bucket="arch-raw",
        raw_r2_key="raw/bea/test.csv",
        raw_r2_uri="r2://arch-raw/raw/bea/test.csv",
    )
    row = SourceRow(
        artifact=artifact,
        sheet_name="NipaDataA",
        row_number=2,
        values={"Period": 2022, "SeriesCode": "W351RC", "Value": 1},
    )
    row_key = build_source_row_key(row)
    cell = SourceCell(
        artifact=artifact,
        sheet_name="NipaDataA",
        row_number=2,
        column_number=3,
        address="C2",
        cell_type="number",
        raw_value=1,
        display_value="1",
        source_row_key=row_key,
    )
    fact = AggregateFact(
        value=1,
        period=PeriodDimension(type="calendar_year", value=2022),
        geography=GeographyDimension(
            level="country",
            id="0100000US",
            vintage="current",
            name="United States",
        ),
        entity=EntityDimension(name="pension_plan"),
        measure=Measure(
            concept="bea_nipa.defined_contribution_employer_contributions",
            unit="usd",
        ),
        aggregation=Aggregation(method="sum"),
        source=SourceProvenance(
            source_name="bea",
            source_table="test",
            source_file="test.csv",
            url="https://example.test/test.csv",
            vintage="test",
            extracted_at="2026-05-06",
            extraction_method="test",
        ),
        filters={"bea_nipa.series_code": "W351RC"},
        source_record_id="bea.test.w351rc",
        source_cell_keys=(build_source_cell_key(cell),),
        source_row_keys=(row_key,),
        constraints=(
            AggregateConstraint(
                variable="bea_nipa.table_id",
                operator="==",
                value="T61100D",
            ),
        ),
        layout=SourceRecordLayout(
            groupby_dimension="bea_nipa.series_code",
            groupby_value_id="w351rc",
            table_record_kind="detail",
        ),
    )

    report = build_agent_acceptance_report(
        [fact],
        [row],
        [cell],
        source_rows=validate_source_rows([row]),
        source_cells=validate_source_cells([cell]),
        source_regions=SourceRegionSuiteReport(
            region_count=0,
            covered_cell_count=0,
            errors=(),
        ),
        source_records=SourceRecordSuiteReport(
            spec_count=1,
            resolved_count=1,
            lineaged_count=1,
            errors=(),
        ),
        fact_report=validate_facts([fact]),
        concept_alignments=ConceptAlignmentReport(
            alignment_count=0,
            checked_count=0,
            alignments=(),
            errors=(),
        ),
    )

    assert not report.valid
    assert "row_constraint_not_evidenced" in {
        error.code for error in report.errors
    }


def test_agent_acceptance_accepts_age_constraints_from_source_cell_header():
    artifact = SourceArtifactMetadata(
        source_name="census_population_projections",
        source_table="test",
        source_file="test.csv",
        url="https://example.test/test.csv",
        vintage="test",
        sha256="abc123",
        size_bytes=10,
        extracted_at="2026-05-11",
        extraction_method="test",
        raw_r2_bucket="arch-raw",
        raw_r2_key="raw/census/test.csv",
        raw_r2_uri="r2://arch-raw/raw/census/test.csv",
    )
    row = SourceRow(
        artifact=artifact,
        sheet_name="test",
        row_number=2,
        values={"YEAR": 2025, "POP_0": 1},
    )
    row_key = build_source_row_key(row)
    header_cell = SourceCell(
        artifact=artifact,
        sheet_name="test",
        row_number=1,
        column_number=6,
        address="F1",
        cell_type="text",
        raw_value="POP_0",
        display_value="POP_0",
    )
    value_cell = SourceCell(
        artifact=artifact,
        sheet_name="test",
        row_number=2,
        column_number=6,
        address="F2",
        cell_type="number",
        raw_value=1,
        display_value="1",
        source_row_key=row_key,
    )
    fact = AggregateFact(
        value=1,
        period=PeriodDimension(type="calendar_year", value=2025),
        geography=GeographyDimension(
            level="country",
            id="0100000US",
            vintage="current",
            name="United States",
        ),
        entity=EntityDimension(name="person"),
        measure=Measure(
            concept="census.population_projection",
            unit="count",
        ),
        aggregation=Aggregation(method="count"),
        source=SourceProvenance(
            source_name="census_population_projections",
            source_table="test",
            source_file="test.csv",
            url="https://example.test/test.csv",
            vintage="test",
            extracted_at="2026-05-11",
            extraction_method="test",
        ),
        source_record_id="census.test.age_0.population",
        source_cell_keys=(
            build_source_cell_key(value_cell),
            build_source_cell_key(header_cell),
        ),
        source_row_keys=(row_key,),
        constraints=(
            AggregateConstraint(
                variable="age",
                operator=">=",
                value=0,
            ),
            AggregateConstraint(
                variable="age",
                operator="<",
                value=1,
            ),
        ),
        layout=SourceRecordLayout(
            groupby_dimension="age",
            groupby_value_id="age_0",
            table_record_kind="detail",
        ),
    )
    cells = [header_cell, value_cell]

    report = build_agent_acceptance_report(
        [fact],
        [row],
        cells,
        source_rows=validate_source_rows([row]),
        source_cells=validate_source_cells(cells),
        source_regions=SourceRegionSuiteReport(
            region_count=0,
            covered_cell_count=0,
            errors=(),
        ),
        source_records=SourceRecordSuiteReport(
            spec_count=1,
            resolved_count=1,
            lineaged_count=1,
            errors=(),
        ),
        fact_report=validate_facts([fact]),
        concept_alignments=ConceptAlignmentReport(
            alignment_count=0,
            checked_count=0,
            alignments=(),
            errors=(),
        ),
    )

    assert report.valid
    assert report.checks["row_lineage_semantics_evidenced"]
    assert "row_constraint_not_evidenced" not in {
        error.code for error in report.errors
    }


def test_build_suite_cli_emits_json_summary(tmp_path, capsys):
    output_dir = tmp_path / "suite"

    exit_code = harness_main(
        [
            "build-suite",
            "soi-table-1-1",
            "--year",
            "2023",
            "--out",
            str(output_dir),
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["valid"]
    assert payload["outputs"]["source_regions"] == str(
        output_dir / "source_regions.jsonl"
    )
    assert payload["outputs"]["database"] == str(output_dir / "arch.db")
    assert payload["outputs"]["consumer_facts"] == str(
        output_dir / "consumer_facts.jsonl"
    )
    assert payload["outputs"]["datapackage"] == str(output_dir / "datapackage.json")
    assert payload["reports"]["consumer_facts"]["fact_count"] == 80
    assert payload["reports"]["source_regions"]["covered_cell_count"] == 340
    assert payload["reports"]["source_records"]["lineage_coverage"] == 1.0
    assert payload["reports"]["agent_acceptance"]["valid"]
    assert payload["reports"]["agent_acceptance"]["warnings"][0]["code"] == (
        "concept_alignment_validation_skipped"
    )


def test_build_source_suite_accepts_required_axiom_validation(tmp_path):
    output_dir = tmp_path / "suite"
    axiom_cli = _write_fake_axiom_cli(
        tmp_path,
        valid_concepts={"us:statutes/26/62#adjusted_gross_income"},
    )

    report = build_source_suite(
        "soi-table-1-1",
        output_dir,
        year=2023,
        axiom_command=[str(axiom_cli)],
        axiom_roots=[tmp_path / "rules-us"],
        require_axiom_validation=True,
    )
    summary = json.loads((output_dir / "reports" / "build_summary.json").read_text())

    assert report.valid
    assert summary["reports"]["concept_alignments"]["checked_count"] == 1
    assert summary["reports"]["agent_acceptance"]["warnings"] == []
    assert summary["reports"]["agent_acceptance"]["checks"][
        "required_concept_alignments_validated"
    ]


def test_build_source_suite_can_require_axiom_validation(tmp_path):
    output_dir = tmp_path / "suite"

    report = build_source_suite(
        "soi-table-1-4",
        output_dir,
        year=2023,
        require_axiom_validation=True,
    )
    summary = json.loads((output_dir / "reports" / "build_summary.json").read_text())

    assert not report.valid
    assert not summary["valid"]
    assert summary["reports"]["agent_acceptance"]["errors"][0]["code"] == (
        "concept_alignment_validation_skipped"
    )
    assert not summary["reports"]["agent_acceptance"]["checks"][
        "required_concept_alignments_validated"
    ]


def test_build_suite_refuses_nonempty_output_dir_without_replace(tmp_path):
    output_dir = tmp_path / "suite"
    output_dir.mkdir()
    (output_dir / "existing.txt").write_text("keep", encoding="utf-8")

    try:
        build_source_suite("soi-table-1-1", output_dir, year=2023)
    except FileExistsError as exc:
        assert "not empty" in str(exc)
    else:
        raise AssertionError("Expected nonempty output directory to be rejected")

    assert (output_dir / "existing.txt").read_text(encoding="utf-8") == "keep"


def test_source_record_suite_reports_selector_errors():
    specs = build_source_record_specs("soi-table-1-1", year=2023)

    report = validate_source_record_specs(specs[:1], cells=[])

    assert not report.valid
    assert report.spec_count == 1
    assert report.resolved_count == 0
    assert report.errors[0].code == "source_record_resolution_failed"


def test_source_region_suite_reports_covered_cells():
    cells = build_source_cells("soi-table-1-1", year=2023)
    regions = build_source_regions("soi-table-1-1", year=2023)

    report = validate_source_regions(regions, cells)

    assert report.valid
    assert report.region_count == 1
    assert report.covered_cell_count == 340


def _write_fake_axiom_cli(tmp_path, *, valid_concepts: set[str]):
    axiom_cli = tmp_path / "axiom"
    axiom_cli.write_text(
        textwrap.dedent(
            f"""\
            #!/usr/bin/env python3
            import json
            import sys

            concept_id = sys.argv[sys.argv.index("validate") + 1]
            valid_concepts = {sorted(valid_concepts)!r}
            if concept_id in valid_concepts:
                print(json.dumps({{
                    "concept_id": concept_id,
                    "concept": {{"concept_id": concept_id}},
                    "errors": [],
                    "valid": True,
                }}))
                raise SystemExit(0)
            print(json.dumps({{
                "concept_id": concept_id,
                "errors": [
                    {{
                        "code": "concept_not_found",
                        "message": f"Concept {{concept_id}} is not available.",
                    }}
                ],
                "valid": False,
            }}))
            raise SystemExit(1)
            """
        )
    )
    axiom_cli.chmod(0o755)
    return axiom_cli
