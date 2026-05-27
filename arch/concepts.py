"""Concept-alignment validation for Arch facts."""

from __future__ import annotations

import json
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Sequence

from arch.core import AggregateFact, build_fact_key


@dataclass(frozen=True)
class ConceptAlignment:
    """One source-to-canonical concept alignment asserted by Arch."""

    canonical_concept: str
    source_concept: str
    relation: str
    fact_key: str
    source_record_id: str | None
    authority: str | None
    evidence_url: str | None
    evidence_notes: str | None
    legal_vintage: str | None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable alignment."""
        data = asdict(self)
        return {key: value for key, value in data.items() if value is not None}


@dataclass(frozen=True)
class ConceptAlignmentIssue:
    """One concept-alignment validation issue."""

    code: str
    message: str
    canonical_concept: str | None = None
    source_concept: str | None = None
    fact_key: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable issue."""
        data = asdict(self)
        return {key: value for key, value in data.items() if value is not None}


@dataclass(frozen=True)
class ConceptAlignmentReport:
    """Validation report for source-to-canonical concept alignments."""

    alignment_count: int
    checked_count: int
    alignments: tuple[ConceptAlignment, ...]
    errors: tuple[ConceptAlignmentIssue, ...]
    warnings: tuple[ConceptAlignmentIssue, ...] = ()

    @property
    def valid(self) -> bool:
        """Whether no validation errors were found."""
        return not self.errors

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable report."""
        return {
            "valid": self.valid,
            "alignment_count": self.alignment_count,
            "checked_count": self.checked_count,
            "alignments": [alignment.to_dict() for alignment in self.alignments],
            "errors": [issue.to_dict() for issue in self.errors],
            "warnings": [issue.to_dict() for issue in self.warnings],
        }


def collect_concept_alignments(
    facts: list[AggregateFact],
) -> tuple[ConceptAlignment, ...]:
    """Collect unique source-to-canonical concept alignments from facts."""
    alignments: dict[tuple[str, str, str, str | None], ConceptAlignment] = {}
    for fact in facts:
        measure = fact.measure
        if not measure.source_concept or not measure.concept_relation:
            continue
        key = (
            measure.source_concept,
            measure.concept,
            measure.concept_relation,
            measure.legal_vintage,
        )
        alignments.setdefault(
            key,
            ConceptAlignment(
                canonical_concept=measure.concept,
                source_concept=measure.source_concept,
                relation=measure.concept_relation,
                fact_key=build_fact_key(fact),
                source_record_id=fact.source_record_id,
                authority=measure.concept_authority,
                evidence_url=measure.concept_evidence_url,
                evidence_notes=measure.concept_evidence_notes,
                legal_vintage=measure.legal_vintage,
            ),
        )
    return tuple(alignments.values())


def validate_concept_alignments(
    facts: list[AggregateFact],
    *,
    axiom_command: Sequence[str] | None = None,
    axiom_roots: Sequence[str | Path] = (),
) -> ConceptAlignmentReport:
    """Validate Arch concept alignments against optional Axiom CLI metadata."""
    alignments = collect_concept_alignments(facts)
    errors = list(_alignment_metadata_errors(alignments))
    warnings: list[ConceptAlignmentIssue] = []
    checked_count = 0

    if not alignments:
        return ConceptAlignmentReport(
            alignment_count=0,
            checked_count=0,
            alignments=(),
            errors=tuple(errors),
            warnings=(),
        )

    if axiom_command is None:
        warnings.append(
            ConceptAlignmentIssue(
                code="axiom_cli_not_configured",
                message="Axiom CLI validation skipped because no command was provided.",
            )
        )
        return ConceptAlignmentReport(
            alignment_count=len(alignments),
            checked_count=checked_count,
            alignments=alignments,
            errors=tuple(errors),
            warnings=tuple(warnings),
        )

    for alignment in alignments:
        result = _run_axiom_validate(
            axiom_command,
            alignment.canonical_concept,
            axiom_roots=axiom_roots,
        )
        if result is None:
            warnings.append(
                ConceptAlignmentIssue(
                    code="axiom_cli_unavailable",
                    message="Axiom CLI validation skipped because command failed to run.",
                    canonical_concept=alignment.canonical_concept,
                    source_concept=alignment.source_concept,
                    fact_key=alignment.fact_key,
                )
            )
            break
        checked_count += 1
        if not result.get("valid"):
            message = _axiom_error_message(result)
            errors.append(
                ConceptAlignmentIssue(
                    code="axiom_concept_invalid",
                    message=message,
                    canonical_concept=alignment.canonical_concept,
                    source_concept=alignment.source_concept,
                    fact_key=alignment.fact_key,
                )
            )

    return ConceptAlignmentReport(
        alignment_count=len(alignments),
        checked_count=checked_count,
        alignments=alignments,
        errors=tuple(errors),
        warnings=tuple(warnings),
    )


def _alignment_metadata_errors(
    alignments: tuple[ConceptAlignment, ...],
) -> tuple[ConceptAlignmentIssue, ...]:
    errors = []
    for alignment in alignments:
        if alignment.relation == "exact" and not (
            alignment.evidence_url or alignment.evidence_notes
        ):
            errors.append(
                ConceptAlignmentIssue(
                    code="missing_concept_evidence",
                    message="Exact source-to-canonical concept alignments need evidence.",
                    canonical_concept=alignment.canonical_concept,
                    source_concept=alignment.source_concept,
                    fact_key=alignment.fact_key,
                )
            )
    return tuple(errors)


def _run_axiom_validate(
    axiom_command: Sequence[str],
    concept_id: str,
    *,
    axiom_roots: Sequence[str | Path],
) -> dict[str, Any] | None:
    command = [
        *axiom_command,
        "concepts",
        "validate",
        concept_id,
        "--json",
    ]
    for root in axiom_roots:
        command.extend(["--root", str(root)])
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return None
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return {
            "valid": False,
            "errors": [
                {
                    "code": "invalid_axiom_cli_output",
                    "message": completed.stderr.strip()
                    or "Axiom CLI did not emit JSON.",
                }
            ],
        }
    if isinstance(payload, dict):
        return payload
    return {
        "valid": False,
        "errors": [
            {
                "code": "invalid_axiom_cli_output",
                "message": "Axiom CLI emitted non-object JSON.",
            }
        ],
    }


def _axiom_error_message(result: dict[str, Any]) -> str:
    errors = result.get("errors")
    if isinstance(errors, list) and errors:
        first = errors[0]
        if isinstance(first, dict) and first.get("message"):
            return str(first["message"])
    return "Axiom CLI reported invalid concept."
