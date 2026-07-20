#!/usr/bin/env python3
# Thin shim over vidimus==0.1.2 (hash-pinned in uv.lock). Any vidimus upgrade
# requires a fresh byte-equivalence proof at this repo's then-current pin BEFORE
# the bump.
"""Gate every change to the thesis-facts observation ledger."""

from __future__ import annotations

import argparse
import pathlib
import sys
from typing import Any

import vidimus.append_gate as _vidimus
from vidimus.release_chain import MANIFEST_RE, ReleaseChainError

try:
    from vidimus_pins import APPEND_GATE_SPEC, LEDGER_SPEC
except ModuleNotFoundError as exc:
    if exc.name != "vidimus_pins":
        raise
    # The test suite copies the legacy three-script surface into temporary
    # repositories. The editable consumer tree remains the sole pin owner.
    from scripts.vidimus_pins import APPEND_GATE_SPEC, LEDGER_SPEC


CODE_ROOT = pathlib.Path(__file__).resolve().parents[1]
ROOT = CODE_ROOT
LEDGER_PATH = ROOT / LEDGER_SPEC.state_relative
PREFIX_PATH = ROOT / LEDGER_SPEC.prefix_relative
RELEASE_MANIFEST_PREFIX = APPEND_GATE_SPEC.release_manifest_prefix
GENESIS_SUPPORT_FILES = APPEND_GATE_SPEC.genesis_support_files
GATE_SURFACE = APPEND_GATE_SPEC.gate_surface
DATA_SURFACE = APPEND_GATE_SPEC.data_surface
ASSERTION_CONTENT_KEYS = APPEND_GATE_SPEC.assertion_content_keys

AppendError = _vidimus.AppendError
AppendGateSpec = _vidimus.AppendGateSpec
reject_non_append_bytes = _vidimus.reject_non_append_bytes


def _set_root(root: pathlib.Path) -> None:
    """Select candidate paths while leaving the trusted code root unchanged."""

    global ROOT, LEDGER_PATH, PREFIX_PATH
    ROOT = root.resolve()
    LEDGER_PATH = ROOT / LEDGER_SPEC.state_relative
    PREFIX_PATH = ROOT / LEDGER_SPEC.prefix_relative


def _candidate() -> Any:
    return _vidimus._set_root(ROOT, APPEND_GATE_SPEC)


def check_surface_separation(base_ref: str) -> tuple[set[str], set[str]]:
    return _vidimus.check_surface_separation(base_ref, _candidate())


def expected_assertion_version_id(row: dict[str, Any]) -> str:
    return _vidimus.expected_assertion_version_id(row, APPEND_GATE_SPEC)


def effective_current_rows(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return _vidimus.effective_current_rows(rows, APPEND_GATE_SPEC)


def check_prefix(lines: list[str]) -> dict[str, Any]:
    return _vidimus.check_prefix(lines, _candidate())


def check_rows(lines: list[str], prefix_count: int) -> None:
    return _vidimus.check_rows(lines, prefix_count, APPEND_GATE_SPEC)


def check_append_only(base_ref: str, lines: list[str]) -> int:
    return _vidimus.check_append_only(base_ref, lines, _candidate())


def check_prefix_anchored_to_base(
    base_ref: str, candidate_prefix: dict[str, Any]
) -> int:
    return _vidimus.check_prefix_anchored_to_base(
        base_ref,
        candidate_prefix,
        _candidate(),
    )


def check_release_proposal(
    base_ref: str,
    *,
    anchor_dir: pathlib.Path | None = None,
    enforce_production_pins: bool | None = None,
) -> int | None:
    return _vidimus.check_release_proposal(
        base_ref,
        candidate=_candidate(),
        anchor_dir=anchor_dir,
        enforce_production_pins=enforce_production_pins,
    )


def check_release_chain_without_base(
    *,
    anchor_dir: pathlib.Path | None = None,
    enforce_production_pins: bool | None = None,
) -> int | None:
    return _vidimus.check_release_chain_without_base(
        candidate=_candidate(),
        anchor_dir=anchor_dir,
        enforce_production_pins=enforce_production_pins,
    )


def verify_append_gate(
    root: pathlib.Path = ROOT,
    *,
    base_ref: str | None = None,
    trusted_code_root: pathlib.Path = CODE_ROOT,
    release_anchor_dir: pathlib.Path | None = None,
) -> str:
    return _vidimus.verify_append_gate(
        root,
        spec=APPEND_GATE_SPEC,
        base_ref=base_ref,
        trusted_code_root=trusted_code_root,
        release_anchor_dir=release_anchor_dir,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        type=pathlib.Path,
        default=CODE_ROOT,
        help="candidate worktree root (defaults to the checker's repository)",
    )
    parser.add_argument(
        "--base-ref",
        help="enforce an append-only diff against this git ref",
    )
    parser.add_argument(
        "--release-anchor-dir",
        type=pathlib.Path,
        help=argparse.SUPPRESS,
    )
    args = parser.parse_args()
    try:
        summary = verify_append_gate(
            args.root.resolve(),
            base_ref=args.base_ref,
            trusted_code_root=CODE_ROOT.resolve(),
            release_anchor_dir=args.release_anchor_dir,
        )
    except AppendError as exc:
        print(f"thesis-facts append check failed: {exc}", file=sys.stderr)
        return 1
    print(summary)
    return 0


__all__ = [
    "APPEND_GATE_SPEC",
    "ASSERTION_CONTENT_KEYS",
    "AppendError",
    "AppendGateSpec",
    "CODE_ROOT",
    "DATA_SURFACE",
    "GATE_SURFACE",
    "GENESIS_SUPPORT_FILES",
    "LEDGER_PATH",
    "MANIFEST_RE",
    "PREFIX_PATH",
    "RELEASE_MANIFEST_PREFIX",
    "ROOT",
    "ReleaseChainError",
    "check_append_only",
    "check_prefix",
    "check_prefix_anchored_to_base",
    "check_release_chain_without_base",
    "check_release_proposal",
    "check_rows",
    "check_surface_separation",
    "effective_current_rows",
    "expected_assertion_version_id",
    "main",
    "reject_non_append_bytes",
    "verify_append_gate",
]


if __name__ == "__main__":
    raise SystemExit(main())
