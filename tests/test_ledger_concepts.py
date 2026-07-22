"""Tests for Ledger concept-alignment validation."""

from __future__ import annotations

import json
import textwrap

from ledger.concepts import (
    collect_concept_alignments,
    validate_concept_alignments,
)
from ledger.core import (
    Aggregation,
    EntityDimension,
    GeographyDimension,
    Measure,
    PeriodDimension,
    SourceProvenance,
    AggregateFact,
)
from ledger.harness import main as harness_main
from ledger.store import save_facts_jsonl

AXIOM_CREDIT_CONCEPT = "us:statutes/26/45A/a#indian_employment_credit"
MISSING_CTC_CONCEPT = "us:statutes/26/24#child_tax_credit"
SOURCE_CREDIT_CONCEPT = "irs_soi.indian_employment_credit"


def _credit_fact(**overrides):
    fact = AggregateFact(
        value=123_000_000,
        period=PeriodDimension(type="tax_year", value=2023),
        geography=GeographyDimension(
            level="country",
            id="0100000US",
            vintage="2020_census",
            name="United States",
        ),
        entity=EntityDimension(name="return", role="filing_unit"),
        measure=Measure(
            concept=AXIOM_CREDIT_CONCEPT,
            unit="usd",
            source_concept=SOURCE_CREDIT_CONCEPT,
            concept_relation="exact",
            concept_authority="ledger-us",
            concept_evidence_notes=(
                "Synthetic fixture asserting a source credit column exactly "
                "adopts an encoded Axiom tax-credit concept."
            ),
            legal_vintage="tax_year_2023",
        ),
        aggregation=Aggregation(method="sum"),
        provenance_class="administrative",
        filters={"filing_status": "all"},
        source=SourceProvenance(
            source_name="irs_soi",
            source_table="Synthetic credit table",
            source_file="synthetic-credit.jsonl",
            url="https://example.org/synthetic-credit",
            vintage="tax_year_2023",
            extracted_at="2026-05-04",
            extraction_method="test fixture",
            method_notes="Synthetic concept-alignment fixture.",
        ),
        source_record_id="irs_soi.ty2023.synthetic.indian_employment_credit",
        label="United States 2023 tax year sum Indian employment credit",
    )
    return AggregateFact(**{**fact.__dict__, **overrides})


def test_collect_concept_alignments_deduplicates_assertions():
    fact = _credit_fact()
    duplicate_assertion = _credit_fact(value=456_000_000)

    alignments = collect_concept_alignments([fact, duplicate_assertion])

    assert len(alignments) == 1
    assert alignments[0].canonical_concept == AXIOM_CREDIT_CONCEPT
    assert alignments[0].source_concept == SOURCE_CREDIT_CONCEPT


def test_validate_concept_alignments_warns_without_axiom_cli():
    report = validate_concept_alignments([_credit_fact()])

    assert report.valid
    assert report.alignment_count == 1
    assert report.checked_count == 0
    assert [warning.code for warning in report.warnings] == ["axiom_cli_not_configured"]


def test_exact_alignment_requires_evidence():
    fact = _credit_fact(
        measure=Measure(
            concept=AXIOM_CREDIT_CONCEPT,
            unit="usd",
            source_concept=SOURCE_CREDIT_CONCEPT,
            concept_relation="exact",
        )
    )

    report = validate_concept_alignments([fact])

    assert not report.valid
    assert [error.code for error in report.errors] == ["missing_concept_evidence"]


def test_validate_concept_alignments_checks_encoded_axiom_concept(tmp_path):
    axiom_cli = _write_fake_axiom_cli(tmp_path)

    report = validate_concept_alignments(
        [_credit_fact()],
        axiom_command=[str(axiom_cli)],
        axiom_roots=[tmp_path / "rules-us"],
    )

    assert report.valid
    assert report.alignment_count == 1
    assert report.checked_count == 1
    assert report.errors == ()


def test_validate_concept_alignments_reports_missing_axiom_concept(tmp_path):
    axiom_cli = _write_fake_axiom_cli(tmp_path)
    fact = _credit_fact(
        measure=Measure(
            concept=MISSING_CTC_CONCEPT,
            unit="usd",
            source_concept="irs_soi.child_tax_credit",
            concept_relation="exact",
            concept_authority="ledger-us",
            concept_evidence_notes="Synthetic CTC assertion before §24 exists.",
            legal_vintage="tax_year_2023",
        )
    )

    report = validate_concept_alignments(
        [fact],
        axiom_command=[str(axiom_cli)],
        axiom_roots=[tmp_path / "rules-us"],
    )

    assert not report.valid
    assert report.checked_count == 1
    assert [error.code for error in report.errors] == ["axiom_concept_invalid"]


def test_validate_concept_alignment_cli_emits_json(tmp_path, capsys):
    axiom_cli = _write_fake_axiom_cli(tmp_path)
    fact_path = tmp_path / "facts.jsonl"
    save_facts_jsonl([_credit_fact()], fact_path)

    exit_code = harness_main(
        [
            "validate-concept-alignments",
            "--input",
            str(fact_path),
            "--axiom-cli",
            str(axiom_cli),
            "--axiom-root",
            str(tmp_path / "rules-us"),
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["valid"]
    assert payload["alignment_count"] == 1
    assert payload["checked_count"] == 1
    assert payload["errors"] == []


def _write_fake_axiom_cli(tmp_path):
    axiom_cli = tmp_path / "axiom"
    axiom_cli.write_text(
        textwrap.dedent(
            f"""\
            #!/usr/bin/env python3
            import json
            import sys

            concept_id = sys.argv[sys.argv.index("validate") + 1]
            if concept_id == {AXIOM_CREDIT_CONCEPT!r}:
                print(json.dumps({{
                    "concept_id": concept_id,
                    "concept": {{
                        "concept_id": concept_id,
                        "status": "encoded",
                    }},
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
