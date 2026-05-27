"""Bundle-level Arch build artifacts for downstream consumers."""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Sequence

from arch.source_package import SOURCE_PACKAGE_ALIASES, validate_source_package
from arch.suite import BuildSuiteReport, build_source_suite

BUNDLE_SCHEMA_VERSION = "arch.bundle.v1"
BUNDLE_COVERAGE_SCHEMA_VERSION = "arch.bundle_coverage.v1"
BUNDLE_SOURCES_SCHEMA_VERSION = "arch.bundle_sources.v1"
DEFAULT_BUNDLE_SOURCES = tuple(sorted(SOURCE_PACKAGE_ALIASES))


@dataclass(frozen=True)
class BuildBundleIssue:
    """One bundle-level build issue."""

    code: str
    message: str
    source: str | None = None
    key: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable issue."""
        return {
            key: value
            for key, value in asdict(self).items()
            if value is not None
        }


@dataclass(frozen=True)
class SkippedSourceReport:
    """A source package omitted from a default bundle for this year."""

    source: str
    reason: str
    validation: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable report."""
        return asdict(self)


@dataclass(frozen=True)
class BundleSourceReport:
    """Summary for one source-package suite inside a bundle."""

    source: str
    suite_source: str
    output_dir: str
    valid: bool
    counts: dict[str, Any]
    outputs: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable report."""
        return asdict(self)


@dataclass(frozen=True)
class BuildBundleReport:
    """End-to-end report for a merged Arch consumer bundle."""

    schema_version: str
    year: int
    output_dir: str
    outputs: dict[str, str]
    source_packages: tuple[BundleSourceReport, ...]
    skipped_sources: tuple[SkippedSourceReport, ...]
    coverage: dict[str, Any]
    errors: tuple[BuildBundleIssue, ...]
    warnings: tuple[BuildBundleIssue, ...] = ()

    @property
    def valid(self) -> bool:
        """Whether the bundle passed source-suite and duplicate checks."""
        return not self.errors and all(
            source.valid for source in self.source_packages
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable report."""
        duplicates = self.coverage["duplicates"]
        return {
            "schema_version": self.schema_version,
            "valid": self.valid,
            "year": self.year,
            "output_dir": self.output_dir,
            "outputs": self.outputs,
            "counts": {
                "source_package_count": len(self.source_packages),
                "skipped_source_count": len(self.skipped_sources),
                "fact_count": self.coverage["fact_count"],
                "source_count": len(self.coverage["counts"]["by_source"]),
                "period_count": len(self.coverage["counts"]["by_period"]),
                "geography_count": len(self.coverage["counts"]["by_geography"]),
                "entity_count": len(self.coverage["counts"]["by_entity"]),
                "aggregate_duplicate_key_count": len(
                    duplicates["aggregate_fact_keys"]
                ),
                "semantic_duplicate_key_count": len(
                    duplicates["semantic_fact_keys"]
                ),
                "error_count": len(self.errors),
                "warning_count": len(self.warnings),
            },
            "source_packages": [
                source.to_dict() for source in self.source_packages
            ],
            "skipped_sources": [
                skipped.to_dict() for skipped in self.skipped_sources
            ],
            "coverage": self.coverage,
            "errors": [issue.to_dict() for issue in self.errors],
            "warnings": [issue.to_dict() for issue in self.warnings],
        }


def build_bundle(
    output_dir: str | Path,
    *,
    year: int = 2023,
    sources: Sequence[str | Path] | None = None,
    axiom_command: Sequence[str] | None = None,
    axiom_roots: Sequence[str | Path] = (),
    require_axiom_validation: bool = False,
    replace: bool = False,
) -> BuildBundleReport:
    """Build source-package suites and merge their consumer-contract facts."""
    output_path = Path(output_dir)
    _prepare_output_dir(output_path, replace=replace)
    reports_path = output_path / "reports"
    sources_path = output_path / "sources"
    reports_path.mkdir(parents=True, exist_ok=True)
    sources_path.mkdir(parents=True, exist_ok=True)

    explicit_sources = sources is not None
    requested_sources = tuple(str(source) for source in (sources or DEFAULT_BUNDLE_SOURCES))
    build_sources, skipped_sources = _resolve_bundle_sources(
        requested_sources,
        year=year,
        explicit=explicit_sources,
    )

    errors: list[BuildBundleIssue] = []
    warnings: list[BuildBundleIssue] = []
    source_reports: list[BundleSourceReport] = []
    consumer_rows: list[dict[str, Any]] = []

    for source in build_sources:
        suite_dir = sources_path / _safe_source_dir_name(source)
        try:
            suite_report = build_source_suite(
                source,
                suite_dir,
                year=year,
                axiom_command=axiom_command,
                axiom_roots=axiom_roots,
                require_axiom_validation=require_axiom_validation,
                replace=True,
            )
        except Exception as exc:
            errors.append(
                BuildBundleIssue(
                    code="source_suite_build_failed",
                    message=str(exc),
                    source=source,
                )
            )
            continue

        if not suite_report.valid:
            errors.append(
                BuildBundleIssue(
                    code="source_suite_invalid",
                    message="Nested source-package suite did not pass validation.",
                    source=source,
                )
            )
        rows = _load_jsonl(Path(suite_report.outputs["consumer_facts"]))
        consumer_rows.extend(rows)
        source_reports.append(_bundle_source_report(source, suite_report))

    aggregate_duplicates = _duplicate_key_reports(
        consumer_rows,
        "aggregate_fact_key",
    )
    semantic_duplicates = _duplicate_key_reports(
        consumer_rows,
        "semantic_fact_key",
    )
    for duplicate in aggregate_duplicates:
        errors.append(
            BuildBundleIssue(
                code="duplicate_aggregate_fact_key",
                message="Aggregate fact keys must be unique within a bundle.",
                key=duplicate["key"],
            )
        )
    if semantic_duplicates:
        warnings.append(
            BuildBundleIssue(
                code="duplicate_semantic_fact_key",
                message=(
                    "One or more semantic facts appear in multiple rows; "
                    "downstream consumers should reconcile or select sources."
                ),
            )
        )

    consumer_facts_path = output_path / "consumer_facts.jsonl"
    source_packages_path = output_path / "source_packages.json"
    coverage_path = output_path / "coverage.json"
    report_path = reports_path / "build_bundle.json"

    _write_jsonl(consumer_facts_path, consumer_rows)
    coverage = build_bundle_coverage(
        consumer_rows,
        aggregate_duplicates=aggregate_duplicates,
        semantic_duplicates=semantic_duplicates,
    )
    _write_report(coverage_path, coverage)
    _write_report(
        source_packages_path,
        {
            "schema_version": BUNDLE_SOURCES_SCHEMA_VERSION,
            "year": year,
            "source_package_count": len(source_reports),
            "skipped_source_count": len(skipped_sources),
            "source_packages": [
                source_report.to_dict() for source_report in source_reports
            ],
            "skipped_sources": [
                skipped_source.to_dict() for skipped_source in skipped_sources
            ],
        },
    )
    report = BuildBundleReport(
        schema_version=BUNDLE_SCHEMA_VERSION,
        year=year,
        output_dir=str(output_path),
        outputs={
            "consumer_facts": str(consumer_facts_path),
            "source_packages": str(source_packages_path),
            "coverage": str(coverage_path),
            "reports": str(reports_path),
            "build_bundle": str(report_path),
            "sources": str(sources_path),
        },
        source_packages=tuple(source_reports),
        skipped_sources=tuple(skipped_sources),
        coverage=coverage,
        errors=tuple(errors),
        warnings=tuple(warnings),
    )
    _write_report(report_path, report.to_dict())
    return report


def build_bundle_coverage(
    rows: list[dict[str, Any]],
    *,
    aggregate_duplicates: list[dict[str, Any]] | None = None,
    semantic_duplicates: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build source/concept/geography coverage diagnostics for consumer rows."""
    aggregate_duplicates = (
        aggregate_duplicates
        if aggregate_duplicates is not None
        else _duplicate_key_reports(rows, "aggregate_fact_key")
    )
    semantic_duplicates = (
        semantic_duplicates
        if semantic_duplicates is not None
        else _duplicate_key_reports(rows, "semantic_fact_key")
    )
    return {
        "schema_version": BUNDLE_COVERAGE_SCHEMA_VERSION,
        "fact_count": len(rows),
        "counts": {
            "by_source": _counts_by(rows, _source_name),
            "by_source_table": _counts_by(rows, _source_table_key),
            "by_period": _counts_by(rows, _period_key),
            "by_geography": _counts_by(rows, _geography_key),
            "by_entity": _counts_by(rows, _entity_key),
            "by_observed_measure": _counts_by(rows, _observed_measure_key),
            "by_observed_concept": _counts_by(rows, _observed_concept_key),
            "by_canonical_concept": _counts_by(rows, _canonical_concept_key),
        },
        "unique_counts": {
            "aggregate_fact_key": _unique_count(rows, "aggregate_fact_key"),
            "semantic_fact_key": _unique_count(rows, "semantic_fact_key"),
            "source_release_key": _unique_count(rows, "source_release_key"),
            "source_series_key": _unique_count(rows, "source_series_key"),
            "observed_measure_key": _unique_count(rows, "observed_measure_key"),
            "dimension_set_key": _unique_count(rows, "dimension_set_key"),
            "universe_constraint_set_key": _unique_count(
                rows,
                "universe_constraint_set_key",
            ),
        },
        "duplicates": {
            "aggregate_fact_keys": aggregate_duplicates,
            "semantic_fact_keys": semantic_duplicates,
        },
    }


def _resolve_bundle_sources(
    requested_sources: tuple[str, ...],
    *,
    year: int,
    explicit: bool,
) -> tuple[list[str], list[SkippedSourceReport]]:
    build_sources: list[str] = []
    skipped_sources: list[SkippedSourceReport] = []
    for source in requested_sources:
        report = validate_source_package(source, year=year)
        if report.valid or explicit or not _source_unavailable_for_year(report, year):
            build_sources.append(source)
            continue
        skipped_sources.append(
            SkippedSourceReport(
                source=source,
                reason="source package is not available for requested year",
                validation=report.to_dict(),
            )
        )
    return build_sources, skipped_sources


def _source_unavailable_for_year(report: Any, year: int) -> bool:
    unavailable_messages = {repr(str(year)), f"No source artifact for year {year}"}
    unavailable_codes = {
        "record_set_compile_failed",
        "source_artifact_unavailable",
    }
    return bool(report.errors) and all(
        error.code in unavailable_codes and error.message in unavailable_messages
        for error in report.errors
    )


def _bundle_source_report(
    source: str,
    suite_report: BuildSuiteReport,
) -> BundleSourceReport:
    payload = suite_report.to_dict()
    return BundleSourceReport(
        source=source,
        suite_source=suite_report.source,
        output_dir=suite_report.output_dir,
        valid=suite_report.valid,
        counts=payload["counts"],
        outputs=suite_report.outputs,
    )


def _duplicate_key_reports(
    rows: list[dict[str, Any]],
    key: str,
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(row[key], []).append(row)
    return [
        {
            "key": key_value,
            "count": len(key_rows),
            "sources": sorted({_source_table_key(row) for row in key_rows}),
            "legacy_fact_keys": sorted(
                {
                    legacy_key
                    for row in key_rows
                    if (legacy_key := row.get("legacy_fact_key"))
                }
            ),
        }
        for key_value, key_rows in sorted(grouped.items())
        if len(key_rows) > 1
    ]


def _counts_by(
    rows: list[dict[str, Any]],
    key_fn: Callable[[dict[str, Any]], str | None],
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        key = key_fn(row)
        if key is None:
            continue
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def _unique_count(rows: list[dict[str, Any]], key: str) -> int:
    return len({row[key] for row in rows if key in row})


def _source_name(row: dict[str, Any]) -> str | None:
    return row.get("source", {}).get("source_name")


def _source_table_key(row: dict[str, Any]) -> str | None:
    source = row.get("source", {})
    source_name = source.get("source_name")
    source_table = source.get("source_table")
    if not source_name or not source_table:
        return source_name or source_table
    return f"{source_name}:{source_table}"


def _period_key(row: dict[str, Any]) -> str | None:
    period = row.get("period", {})
    period_type = period.get("type")
    period_value = period.get("value")
    if period_type is None or period_value is None:
        return None
    return f"{period_type}:{period_value}"


def _geography_key(row: dict[str, Any]) -> str | None:
    geography = row.get("geography", {})
    level = geography.get("level")
    geography_id = geography.get("id")
    if level is None or geography_id is None:
        return None
    return f"{level}:{geography_id}"


def _entity_key(row: dict[str, Any]) -> str | None:
    return row.get("entity", {}).get("name")


def _observed_measure_key(row: dict[str, Any]) -> str | None:
    measure = row.get("observed_measure", {})
    source_name = measure.get("source_name")
    source_measure_id = measure.get("source_measure_id")
    if not source_name or not source_measure_id:
        return source_measure_id or source_name
    return f"{source_name}:{source_measure_id}"


def _observed_concept_key(row: dict[str, Any]) -> str | None:
    return row.get("observed_measure", {}).get("source_concept")


def _canonical_concept_key(row: dict[str, Any]) -> str | None:
    return row.get("concept_alignment", {}).get("canonical_concept")


def _safe_source_dir_name(source: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "-", source).strip("-")
    return safe or "source"


def _prepare_output_dir(output_path: Path, *, replace: bool) -> None:
    if output_path.exists() and any(output_path.iterdir()):
        if not replace:
            raise FileExistsError(
                f"Build bundle output directory is not empty: {output_path}"
            )
        if output_path.resolve() in {Path("/").resolve(), Path.home().resolve()}:
            raise ValueError(
                f"Refusing to replace unsafe output directory: {output_path}"
            )
        shutil.rmtree(output_path)
    output_path.mkdir(parents=True, exist_ok=True)


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, sort_keys=True))
            file.write("\n")


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
