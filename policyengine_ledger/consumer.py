"""Consumer artifacts and period-contract resolution for Ledger profiles.

This module is the supported way for downstream builds (Populace, Thesis,
future rule engines) to consume Ledger facts: a versioned on-disk artifact
plus a resolution API that selects profile targets from consumer-contract
fact rows.

Resolution enforces the period contract. A fact's value refers to the fact's
own reference period; consuming it at any other period silently is the
failure mode that produced PolicyEngine/populace#212 (SOI tax-year levels
applied un-aged to a later build year). Resolving at a different period
therefore hard-fails unless the consumer passes an explicit, named
:class:`PeriodAlignmentDeclaration`. Ledger records the declaration in the
resolved rows; it never computes the aligned value. Aging, uprating, and
reconciliation stay in the consumer.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from importlib.resources import files as _resource_files
from pathlib import Path
from typing import Any

from ledger.core import ALLOWED_ASSERTIONS, DEFAULT_ASSERTION
from policyengine_ledger.target_profiles import (
    TargetProfile,
    TargetProfileTarget,
    load_target_profile,
    target_profile_from_mapping,
)
from policyengine_ledger.target_profiles.model import (
    FORBIDDEN_RUNTIME_KEYS,
    FORBIDDEN_VALUE_KEYS,
)

CONSUMER_ARTIFACT_SCHEMA_VERSION = "policyengine_ledger.consumer_artifact.v1"
RESOLVED_TARGET_SCHEMA_VERSION = "policyengine_ledger.resolved_target.v1"
SUPPORTED_BASE_PERIOD_POLICIES = {"latest_not_after_build_base_period"}

_SELECTOR_KEYS = {
    "source_name",
    "source_table",
    "source_measure_id",
    "source_concept",
    "concept",
    "record_set_id",
    "record_set_spec_id",
    "groupby_dimension",
    "domain",
    "entity",
    "assertion",
}


@dataclass(frozen=True)
class PeriodAlignmentDeclaration:
    """A consumer's explicit declaration of how it will align a fact period.

    The declaration names the consumer-side transformation (for example a
    versioned growth-factor aging model) that will be applied to the fact
    value outside Ledger. It carries no values: parameters reference factor
    series or model configuration, never target amounts.
    """

    model_id: str
    model_version: str
    parameters: Mapping[str, str | int | float | bool] = field(default_factory=dict)
    notes: str | None = None

    def __post_init__(self) -> None:
        if not self.model_id or not str(self.model_id).strip():
            raise ValueError("Period alignment declarations need a model_id.")
        if not self.model_version or not str(self.model_version).strip():
            raise ValueError("Period alignment declarations need a model_version.")
        forbidden = FORBIDDEN_VALUE_KEYS | FORBIDDEN_RUNTIME_KEYS
        present = sorted(key for key in forbidden if key in self.parameters)
        if present:
            raise ValueError(
                f"Period alignment parameters must not declare {present}; "
                "declarations reference models and factor series, never "
                "target values or runtime hooks."
            )
        for key, value in self.parameters.items():
            if isinstance(value, list | dict | tuple | set):
                raise ValueError(
                    f"Period alignment parameter {key!r} has a non-scalar value."
                )

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable declaration."""
        payload: dict[str, Any] = {
            "model_id": self.model_id,
            "model_version": self.model_version,
        }
        if self.parameters:
            payload["parameters"] = dict(sorted(self.parameters.items()))
        if self.notes:
            payload["notes"] = self.notes
        return payload


@dataclass(frozen=True)
class PeriodContractViolation:
    """One target resolved at a period its facts do not cover."""

    profile_id: str
    target_id: str
    fact_period: dict[str, Any]
    requested_period: dict[str, Any]
    message: str

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable violation."""
        return asdict(self)


class PeriodContractError(ValueError):
    """Raised when facts would be consumed at the wrong period silently."""

    def __init__(self, violations: Sequence[PeriodContractViolation]) -> None:
        self.violations = tuple(violations)
        details = "; ".join(
            f"{violation.target_id}: fact period "
            f"{violation.fact_period['type']}:{violation.fact_period['value']} "
            f"!= requested "
            f"{violation.requested_period['type']}:"
            f"{violation.requested_period['value']}"
            for violation in self.violations
        )
        super().__init__(
            "Period contract violation: facts cannot be consumed at a period "
            "other than their reference period without an explicit "
            "PeriodAlignmentDeclaration. Pass alignments={target_id: "
            "PeriodAlignmentDeclaration(model_id=..., model_version=...)} "
            f"for: {details}"
        )


@dataclass(frozen=True)
class ResolutionIssue:
    """One non-period resolution problem."""

    code: str
    message: str
    profile_id: str
    target_id: str | None = None
    severity: str = "error"

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable issue."""
        return asdict(self)


@dataclass(frozen=True)
class ResolvedTarget:
    """One profile target row resolved against a Ledger fact row.

    ``value`` is always the published fact value at ``fact_period``. When
    ``basis`` is ``declared_alignment`` the consumer has declared it will
    transform the value to ``requested_period`` with ``alignment``; Ledger
    passes the declaration through untouched.
    """

    profile_id: str
    target_id: str
    basis: str
    value: Any
    value_type: str
    unit: str | None
    assertion: str
    fact_period: dict[str, Any]
    requested_period: dict[str, Any]
    aggregate_fact_key: str
    semantic_fact_key: str
    geography: dict[str, Any]
    entity: dict[str, Any]
    dimensions: dict[str, Any]
    universe_constraints: dict[str, Any]
    source: dict[str, Any]
    lineage: dict[str, Any]
    alignment: dict[str, Any] | None = None
    label: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable resolved row."""
        payload = {
            "schema_version": RESOLVED_TARGET_SCHEMA_VERSION,
            **asdict(self),
        }
        if payload.get("alignment") is None:
            payload.pop("alignment", None)
        if payload.get("label") is None:
            payload.pop("label", None)
        return payload


@dataclass(frozen=True)
class ResolutionReport:
    """Resolved targets plus contract diagnostics for one profile."""

    profile_id: str
    requested_period: dict[str, Any]
    resolved: tuple[ResolvedTarget, ...]
    violations: tuple[PeriodContractViolation, ...] = ()
    issues: tuple[ResolutionIssue, ...] = ()

    @property
    def valid(self) -> bool:
        """Whether resolution produced no violations or blocking issues."""
        return not self.violations and not any(
            issue.severity == "error" for issue in self.issues
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable report."""
        return {
            "profile_id": self.profile_id,
            "requested_period": self.requested_period,
            "valid": self.valid,
            "resolved": [row.to_dict() for row in self.resolved],
            "violations": [violation.to_dict() for violation in self.violations],
            "issues": [issue.to_dict() for issue in self.issues],
        }


def resolve_profile_targets(
    profile: TargetProfile,
    rows: Sequence[Mapping[str, Any]],
    requested_period: Mapping[str, Any],
    *,
    alignments: (
        Mapping[str, PeriodAlignmentDeclaration] | PeriodAlignmentDeclaration | None
    ) = None,
    geography_level: str = "country",
    strict: bool = True,
) -> ResolutionReport:
    """Resolve profile targets from consumer-contract fact rows.

    ``alignments`` maps ``target_id`` (or ``"*"`` for all targets) to the
    consumer's :class:`PeriodAlignmentDeclaration`. ``strict`` raises
    :class:`PeriodContractError` on period violations and ``ValueError`` on
    blocking coverage issues instead of returning an invalid report.
    """
    requested = _normalize_period(requested_period)
    alignment_map = _normalize_alignments(alignments)
    if profile.base_period_policy not in SUPPORTED_BASE_PERIOD_POLICIES:
        raise ValueError(
            f"Unsupported base_period_policy {profile.base_period_policy!r}; "
            f"supported: {sorted(SUPPORTED_BASE_PERIOD_POLICIES)}."
        )

    resolved: list[ResolvedTarget] = []
    violations: list[PeriodContractViolation] = []
    issues: list[ResolutionIssue] = []

    for target in profile.targets_for_geography(geography_level):
        candidates, selector_issues = _select_rows(
            profile.profile_id,
            target,
            rows,
            geography_level=geography_level,
        )
        issues.extend(selector_issues)
        if not candidates:
            issues.append(
                ResolutionIssue(
                    code="no_matching_facts",
                    message=(
                        f"Target {target.target_id!r} matched no consumer fact "
                        "rows; the profile selector and fact coverage disagree."
                    ),
                    profile_id=profile.profile_id,
                    target_id=target.target_id,
                )
            )
            continue

        chosen_period, period_issue = _choose_period(
            profile.profile_id,
            target,
            candidates,
            requested,
        )
        if period_issue is not None:
            issues.append(period_issue)
            continue

        alignment = alignment_map.get(target.target_id, alignment_map.get("*"))
        period_matches = chosen_period == requested
        if period_matches:
            basis = "fact"
            if target.target_id in alignment_map:
                issues.append(
                    ResolutionIssue(
                        code="unused_alignment",
                        message=(
                            f"Target {target.target_id!r} resolves at its fact "
                            "period; the declared alignment was not needed."
                        ),
                        profile_id=profile.profile_id,
                        target_id=target.target_id,
                        severity="warning",
                    )
                )
            alignment = None
        elif alignment is None:
            violations.append(
                PeriodContractViolation(
                    profile_id=profile.profile_id,
                    target_id=target.target_id,
                    fact_period=chosen_period,
                    requested_period=requested,
                    message=(
                        "Fact period differs from the requested period and no "
                        "period alignment was declared."
                    ),
                )
            )
            continue
        else:
            basis = "declared_alignment"

        for row in candidates:
            if dict(row["period"]) != chosen_period:
                continue
            resolved.append(
                _resolved_target(
                    profile.profile_id,
                    target,
                    row,
                    basis=basis,
                    requested_period=requested,
                    alignment=alignment,
                )
            )

    report = ResolutionReport(
        profile_id=profile.profile_id,
        requested_period=requested,
        resolved=tuple(resolved),
        violations=tuple(violations),
        issues=tuple(issues),
    )
    if strict:
        if report.violations:
            raise PeriodContractError(report.violations)
        blocking = [issue for issue in report.issues if issue.severity == "error"]
        if blocking:
            raise ValueError(
                "Profile resolution failed: "
                + "; ".join(issue.message for issue in blocking)
            )
    return report


def _resolved_target(
    profile_id: str,
    target: TargetProfileTarget,
    row: Mapping[str, Any],
    *,
    basis: str,
    requested_period: dict[str, Any],
    alignment: PeriodAlignmentDeclaration | None,
) -> ResolvedTarget:
    observed_measure = row.get("observed_measure", {})
    return ResolvedTarget(
        profile_id=profile_id,
        target_id=target.target_id,
        basis=basis,
        value=row["value"],
        value_type=row["value_type"],
        unit=observed_measure.get("unit"),
        assertion=row["assertion"],
        fact_period=dict(row["period"]),
        requested_period=requested_period,
        aggregate_fact_key=row["aggregate_fact_key"],
        semantic_fact_key=row["semantic_fact_key"],
        geography=dict(row.get("geography", {})),
        entity=dict(row.get("entity", {})),
        dimensions=dict(row.get("dimensions", {})),
        universe_constraints=dict(row.get("universe_constraints", {})),
        source=dict(row.get("source", {})),
        lineage=dict(row.get("lineage", {})),
        alignment=alignment.to_dict() if alignment is not None else None,
        label=row.get("label"),
    )


def _select_rows(
    profile_id: str,
    target: TargetProfileTarget,
    rows: Sequence[Mapping[str, Any]],
    *,
    geography_level: str,
) -> tuple[list[Mapping[str, Any]], list[ResolutionIssue]]:
    issues: list[ResolutionIssue] = []
    selector = dict(target.ledger_selector)
    unknown = sorted(set(selector) - _SELECTOR_KEYS)
    if unknown:
        issues.append(
            ResolutionIssue(
                code="unknown_selector_key",
                message=(
                    f"Target {target.target_id!r} selector has unknown keys "
                    f"{unknown}; supported keys: {sorted(_SELECTOR_KEYS)}."
                ),
                profile_id=profile_id,
                target_id=target.target_id,
            )
        )
        return [], issues
    matched = [
        row
        for row in rows
        if row.get("geography", {}).get("level") == geography_level
        and all(
            _selector_value(row, key) == value for key, value in selector.items()
        )
    ]
    return matched, issues


def _selector_value(row: Mapping[str, Any], key: str) -> Any:
    source = row.get("source", {})
    observed_measure = row.get("observed_measure", {})
    layout = row.get("layout", {})
    if key == "source_name":
        return source.get("source_name")
    if key == "source_table":
        return source.get("source_table")
    if key == "source_measure_id":
        return observed_measure.get("source_measure_id")
    if key == "source_concept":
        return observed_measure.get("source_concept")
    if key == "concept":
        alignment = row.get("concept_alignment", {})
        return alignment.get("canonical_concept") or observed_measure.get(
            "source_concept"
        )
    if key == "record_set_id":
        return layout.get("record_set_id")
    if key == "record_set_spec_id":
        return layout.get("record_set_spec_id")
    if key == "groupby_dimension":
        return layout.get("groupby_dimension")
    if key == "domain":
        return row.get("universe_constraints", {}).get("domain")
    if key == "entity":
        return row.get("entity", {}).get("name")
    if key == "assertion":
        return row.get("assertion")
    raise KeyError(key)


def _choose_period(
    profile_id: str,
    target: TargetProfileTarget,
    candidates: Sequence[Mapping[str, Any]],
    requested: dict[str, Any],
) -> tuple[dict[str, Any], None] | tuple[None, ResolutionIssue]:
    periods = {
        (row["period"]["type"], row["period"]["value"]) for row in candidates
    }
    if (requested["type"], requested["value"]) in periods:
        return requested, None

    same_type = {
        value for period_type, value in periods if period_type == requested["type"]
    }
    eligible = [
        value for value in same_type if _not_after(value, requested["value"])
    ]
    if eligible:
        return {"type": requested["type"], "value": _latest(eligible)}, None

    period_types = sorted({period_type for period_type, _ in periods})
    if len(period_types) == 1:
        values = {value for _, value in periods}
        return {"type": period_types[0], "value": _latest(values)}, None

    return None, ResolutionIssue(
        code="ambiguous_period_type",
        message=(
            f"Target {target.target_id!r} matched facts across period types "
            f"{period_types} with no exact match for "
            f"{requested['type']}:{requested['value']}; narrow the selector."
        ),
        profile_id=profile_id,
        target_id=target.target_id,
    )


def _not_after(candidate: Any, requested: Any) -> bool:
    if isinstance(candidate, int) and isinstance(requested, int):
        return candidate <= requested
    return str(candidate) <= str(requested)


def _latest(values) -> Any:
    values = list(values)
    if all(isinstance(value, int) for value in values):
        return max(values)
    return max(values, key=str)


def _normalize_period(period: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(period, Mapping):
        raise ValueError("requested_period must be a mapping with type and value.")
    period_type = period.get("type")
    value = period.get("value")
    if not isinstance(period_type, str) or not period_type:
        raise ValueError("requested_period needs a non-empty period type.")
    if value is None or (isinstance(value, str) and not value.strip()):
        raise ValueError("requested_period needs a period value.")
    return {"type": period_type, "value": value}


def _normalize_alignments(
    alignments: (
        Mapping[str, PeriodAlignmentDeclaration] | PeriodAlignmentDeclaration | None
    ),
) -> dict[str, PeriodAlignmentDeclaration]:
    if alignments is None:
        return {}
    if isinstance(alignments, PeriodAlignmentDeclaration):
        return {"*": alignments}
    normalized: dict[str, PeriodAlignmentDeclaration] = {}
    for target_id, declaration in alignments.items():
        if not isinstance(declaration, PeriodAlignmentDeclaration):
            raise ValueError(
                "alignments values must be PeriodAlignmentDeclaration objects."
            )
        normalized[str(target_id)] = declaration
    return normalized


@dataclass(frozen=True)
class ConsumerArtifact:
    """A loaded Ledger consumer artifact."""

    path: Path
    manifest: dict[str, Any]
    rows: tuple[dict[str, Any], ...]
    profiles: Mapping[str, TargetProfile]

    def resolve(
        self,
        profile_id: str,
        requested_period: Mapping[str, Any],
        *,
        alignments: (
            Mapping[str, PeriodAlignmentDeclaration]
            | PeriodAlignmentDeclaration
            | None
        ) = None,
        geography_level: str = "country",
        strict: bool = True,
    ) -> ResolutionReport:
        """Resolve one embedded profile against the artifact's fact rows."""
        try:
            profile = self.profiles[profile_id]
        except KeyError:
            raise KeyError(
                f"Artifact has no profile {profile_id!r}; available: "
                f"{sorted(self.profiles)}."
            ) from None
        return resolve_profile_targets(
            profile,
            self.rows,
            requested_period,
            alignments=alignments,
            geography_level=geography_level,
            strict=strict,
        )


@dataclass(frozen=True)
class ConsumerArtifactBuildReport:
    """Build summary for one consumer artifact."""

    schema_version: str
    output_dir: str
    fact_row_count: int
    profile_ids: tuple[str, ...]
    coverage: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable report."""
        return {
            "schema_version": self.schema_version,
            "output_dir": self.output_dir,
            "fact_row_count": self.fact_row_count,
            "profile_ids": list(self.profile_ids),
            "coverage": self.coverage,
        }


def build_consumer_artifact(
    output_dir: str | Path,
    *,
    facts_path: str | Path,
    profile_ids: Sequence[str] = (),
    profile_paths: Sequence[str | Path] = (),
    replace: bool = False,
) -> ConsumerArtifactBuildReport:
    """Build a versioned consumer artifact from consumer facts and profiles.

    ``facts_path`` is a ``consumer_facts.jsonl`` file or a bundle directory
    containing one. The artifact is reproducible: no timestamps, canonical
    JSON, and manifest hashes for the fact rows and every profile.
    """
    output_path = Path(output_dir)
    if output_path.exists():
        if not replace:
            raise FileExistsError(
                f"Output directory exists: {output_path}. Pass replace=True."
            )
        shutil.rmtree(output_path)
    output_path.mkdir(parents=True)

    rows = _load_consumer_rows(_resolve_facts_path(facts_path))
    profiles = _load_profiles(profile_ids, profile_paths)

    facts_out = output_path / "consumer_facts.jsonl"
    with facts_out.open("w") as file:
        for row in rows:
            file.write(json.dumps(row, sort_keys=True))
            file.write("\n")

    profiles_dir = output_path / "profiles"
    profiles_dir.mkdir()
    profile_meta: dict[str, Any] = {}
    for profile_id, payload in profiles.items():
        profile_json = json.dumps(payload, sort_keys=True, indent=2)
        (profiles_dir / f"{profile_id}.json").write_text(profile_json + "\n")
        profile_meta[profile_id] = {
            "sha256": hashlib.sha256(profile_json.encode("utf-8")).hexdigest(),
            "target_count": len(payload["targets"]),
        }

    coverage = _artifact_coverage(rows, profiles)
    _write_json(output_path / "coverage.json", coverage)

    manifest = {
        "schema_version": CONSUMER_ARTIFACT_SCHEMA_VERSION,
        "consumer_fact_schema_versions": sorted(
            {row.get("schema_version") for row in rows}
        ),
        "fact_row_count": len(rows),
        "facts_sha256": _sha256_file(facts_out),
        "profiles": profile_meta,
    }
    _write_json(output_path / "manifest.json", manifest)

    return ConsumerArtifactBuildReport(
        schema_version=CONSUMER_ARTIFACT_SCHEMA_VERSION,
        output_dir=str(output_path),
        fact_row_count=len(rows),
        profile_ids=tuple(sorted(profiles)),
        coverage=coverage,
    )


def load_consumer_artifact(path: str | Path) -> ConsumerArtifact:
    """Load a consumer artifact directory and verify its manifest hashes."""
    artifact_path = Path(path)
    manifest = json.loads((artifact_path / "manifest.json").read_text())
    if manifest.get("schema_version") != CONSUMER_ARTIFACT_SCHEMA_VERSION:
        raise ValueError(
            "Unsupported consumer artifact schema_version: "
            f"{manifest.get('schema_version')!r}."
        )
    facts_file = artifact_path / "consumer_facts.jsonl"
    actual_sha256 = _sha256_file(facts_file)
    if actual_sha256 != manifest["facts_sha256"]:
        raise ValueError(
            f"Consumer artifact fact rows do not match the manifest hash: "
            f"{actual_sha256} != {manifest['facts_sha256']}."
        )
    rows = _load_consumer_rows(facts_file)
    profiles: dict[str, TargetProfile] = {}
    for profile_id in manifest.get("profiles", {}):
        payload = json.loads(
            (artifact_path / "profiles" / f"{profile_id}.json").read_text()
        )
        profiles[profile_id] = target_profile_from_mapping(payload)
    return ConsumerArtifact(
        path=artifact_path,
        manifest=manifest,
        rows=tuple(rows),
        profiles=profiles,
    )


def _resolve_facts_path(facts_path: str | Path) -> Path:
    path = Path(facts_path)
    if path.is_dir():
        candidate = path / "consumer_facts.jsonl"
        if not candidate.exists():
            raise FileNotFoundError(
                f"No consumer_facts.jsonl in bundle directory {path}."
            )
        return candidate
    if not path.exists():
        raise FileNotFoundError(f"No consumer facts file at {path}.")
    return path


def _load_consumer_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open() as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            assertion = row.setdefault("assertion", DEFAULT_ASSERTION)
            if assertion not in ALLOWED_ASSERTIONS:
                raise ValueError(
                    f"Row {line_number} of {path} has unsupported assertion "
                    f"{assertion!r}."
                )
            rows.append(row)
    return rows


def _load_profiles(
    profile_ids: Sequence[str],
    profile_paths: Sequence[str | Path],
) -> dict[str, dict[str, Any]]:
    if not profile_ids and not profile_paths:
        raise ValueError(
            "Consumer artifacts need at least one target profile "
            "(profile_ids or profile_paths)."
        )
    payloads: dict[str, dict[str, Any]] = {}
    for profile_id in profile_ids:
        profile = load_target_profile(profile_id)
        payload = json.loads(
            _resource_files("policyengine_ledger.target_profiles")
            .joinpath(f"{profile_id}.json")
            .read_text()
        )
        payloads[profile.profile_id] = payload
    for profile_path in profile_paths:
        payload = json.loads(Path(profile_path).read_text())
        profile = target_profile_from_mapping(payload)
        if profile.profile_id in payloads:
            raise ValueError(f"Duplicate profile_id {profile.profile_id!r}.")
        payloads[profile.profile_id] = payload
    return payloads


def _artifact_coverage(
    rows: Sequence[Mapping[str, Any]],
    profiles: Mapping[str, dict[str, Any]],
) -> dict[str, Any]:
    coverage: dict[str, Any] = {}
    for profile_id, payload in profiles.items():
        profile = target_profile_from_mapping(payload)
        targets: dict[str, Any] = {}
        for target in profile.targets:
            per_level: dict[str, Any] = {}
            for level in target.geography_levels:
                matched, issues = _select_rows(
                    profile_id,
                    target,
                    rows,
                    geography_level=level,
                )
                if issues:
                    per_level[level] = {
                        "matched_row_count": 0,
                        "issues": [issue.to_dict() for issue in issues],
                    }
                    continue
                periods = sorted(
                    {
                        f"{row['period']['type']}:{row['period']['value']}"
                        for row in matched
                    }
                )
                assertions = sorted({row["assertion"] for row in matched})
                per_level[level] = {
                    "matched_row_count": len(matched),
                    "fact_periods": periods,
                    "assertions": assertions,
                }
            targets[target.target_id] = per_level
        coverage[profile_id] = targets
    return coverage


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


__all__ = [
    "CONSUMER_ARTIFACT_SCHEMA_VERSION",
    "RESOLVED_TARGET_SCHEMA_VERSION",
    "ConsumerArtifact",
    "ConsumerArtifactBuildReport",
    "PeriodAlignmentDeclaration",
    "PeriodContractError",
    "PeriodContractViolation",
    "ResolutionIssue",
    "ResolutionReport",
    "ResolvedTarget",
    "build_consumer_artifact",
    "load_consumer_artifact",
    "resolve_profile_targets",
]
