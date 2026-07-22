#!/usr/bin/env python3
# Thin shim over receipt==0.2.0 (hash-pinned in uv.lock). Any receipt upgrade
# requires a fresh byte-equivalence proof at this repo's then-current pin BEFORE
# the bump.
"""Offline verification for the witnessed thesis-ledger release chain."""

from __future__ import annotations

import argparse
import pathlib
import sys
from datetime import datetime
from typing import Any

import receipt.release_chain as _receipt

try:
    from receipt_pins import LEDGER_SPEC
except ModuleNotFoundError as exc:
    if exc.name != "receipt_pins":
        raise
    # The test suite copies the legacy three-script surface into temporary
    # repositories. The editable consumer tree remains the sole pin owner.
    from scripts.receipt_pins import LEDGER_SPEC


ROOT = pathlib.Path(__file__).resolve().parents[1]
MANIFEST_RELATIVE = LEDGER_SPEC.manifest_relative
LEDGER_RELATIVE = LEDGER_SPEC.state_relative
PREFIX_RELATIVE = LEDGER_SPEC.prefix_relative
STATE_PATH = LEDGER_SPEC.state_path
SCHEMA_VERSION = LEDGER_SPEC.schema_version
ANCHORS = LEDGER_SPEC.anchors
PRODUCER_PUBLIC_KEY_FILENAME = LEDGER_SPEC.producer_public_key_filename
PRODUCER_SPKI_SHA256 = LEDGER_SPEC.producer_spki_sha256

CRYPTOGRAPHY_AVAILABLE = _receipt.CRYPTOGRAPHY_AVAILABLE
DEFAULT_CLOCK_SKEW_SECONDS = _receipt.DEFAULT_CLOCK_SKEW_SECONDS
MAX_FUTURE_SECONDS = _receipt.MAX_FUTURE_SECONDS
MAX_RELEASE_INDEX = _receipt.MAX_RELEASE_INDEX
MANIFEST_RE = _receipt.MANIFEST_RE
PRODUCER_SIGNATURE_BYTES = _receipt.PRODUCER_SIGNATURE_BYTES
PRODUCER_SIGNATURE_RE = _receipt.PRODUCER_SIGNATURE_RE
RECEIPT_RE = _receipt._receipt_re(LEDGER_SPEC)
SHA256_RE = _receipt.SHA256_RE
STRICT_UTC_RE = _receipt.STRICT_UTC_RE
TIME_STAMP_RE = _receipt.TIME_STAMP_RE

AnchorSpec = _receipt.AnchorSpec
ChainSpec = _receipt.ChainSpec
ChainVerification = _receipt.ChainVerification
GitEntry = _receipt.GitEntry
ReleaseChainError = _receipt.ReleaseChainError
ReleaseRecord = _receipt.ReleaseRecord

git_blob_bytes = _receipt.git_blob_bytes
git_file_entry = _receipt.git_file_entry
git_tree_entries = _receipt.git_tree_entries
jsonl_line_offsets = _receipt.jsonl_line_offsets
manifest_filename = _receipt.manifest_filename
parse_created_at = _receipt.parse_created_at
producer_signature_path_for_manifest = _receipt.producer_signature_path_for_manifest
resolve_base_commit = _receipt.resolve_base_commit
sha256_bytes = _receipt.sha256_bytes


def validate_manifest_schema(manifest: Any) -> dict[str, Any]:
    return _receipt.validate_manifest_schema(manifest, LEDGER_SPEC)


def load_manifest(path: pathlib.Path) -> tuple[dict[str, Any], bytes, str]:
    return _receipt.load_manifest(path, LEDGER_SPEC)


def receipt_paths_for_manifest(path: pathlib.Path) -> dict[str, pathlib.Path]:
    return _receipt.receipt_paths_for_manifest(path, LEDGER_SPEC)


def verify_producer_signature_bytes(
    manifest: bytes,
    signature: bytes,
    *,
    anchor_dir: pathlib.Path,
    enforce_production_pin: bool,
    label: str,
) -> None:
    return _receipt.verify_producer_signature_bytes(
        manifest,
        signature,
        spec=LEDGER_SPEC,
        anchor_dir=anchor_dir,
        enforce_production_pin=enforce_production_pin,
        label=label,
    )


def verify_producer_signature(
    manifest: bytes,
    signature_path: pathlib.Path,
    *,
    anchor_dir: pathlib.Path,
    enforce_production_pin: bool,
) -> None:
    return _receipt.verify_producer_signature(
        manifest,
        signature_path,
        spec=LEDGER_SPEC,
        anchor_dir=anchor_dir,
        enforce_production_pin=enforce_production_pin,
    )


def verify_receipt(
    manifest_digest: str,
    receipt: pathlib.Path,
    tsa: str,
    *,
    anchor_dir: pathlib.Path,
    enforce_production_pins: bool,
    now: datetime | None = None,
) -> datetime:
    return _receipt.verify_receipt(
        manifest_digest,
        receipt,
        tsa,
        spec=LEDGER_SPEC,
        anchor_dir=anchor_dir,
        enforce_production_pins=enforce_production_pins,
        now=now,
    )


def verify_release_receipts(
    manifest: dict[str, Any],
    manifest_digest: str,
    receipt_paths: dict[str, pathlib.Path],
    *,
    anchor_dir: pathlib.Path,
    enforce_production_pins: bool,
    clock_skew_seconds: int,
    previous_times: dict[str, datetime] | None = None,
    now: datetime | None = None,
) -> dict[str, datetime]:
    return _receipt.verify_release_receipts(
        manifest,
        manifest_digest,
        receipt_paths,
        spec=LEDGER_SPEC,
        anchor_dir=anchor_dir,
        enforce_production_pins=enforce_production_pins,
        clock_skew_seconds=clock_skew_seconds,
        previous_times=previous_times,
        now=now,
    )


def verify_release_chain(
    root: pathlib.Path = ROOT,
    *,
    anchor_dir: pathlib.Path | None = None,
    require_chain: bool = True,
    verify_state: bool = True,
    allow_pending_append: bool = False,
    enforce_production_pins: bool | None = None,
    clock_skew_seconds: int = DEFAULT_CLOCK_SKEW_SECONDS,
    now: datetime | None = None,
) -> ChainVerification:
    return _receipt.verify_release_chain(
        root,
        spec=LEDGER_SPEC,
        anchor_dir=anchor_dir,
        require_chain=require_chain,
        verify_state=verify_state,
        allow_pending_append=allow_pending_append,
        enforce_production_pins=enforce_production_pins,
        clock_skew_seconds=clock_skew_seconds,
        now=now,
    )


def verify_release_history_immutable(
    root: pathlib.Path, base_ref: str
) -> tuple[str, set[str], dict[str, GitEntry]]:
    return _receipt.verify_release_history_immutable(root, base_ref, LEDGER_SPEC)


def materialize_base_tree(
    root: pathlib.Path,
    commit: str,
    destination: pathlib.Path,
    release_entries: dict[str, GitEntry],
) -> None:
    return _receipt.materialize_base_tree(
        root,
        commit,
        destination,
        release_entries,
        LEDGER_SPEC,
    )


def verify_base_release_chain(
    root: pathlib.Path,
    commit: str,
    release_entries: dict[str, GitEntry],
    *,
    anchor_dir: pathlib.Path | None = None,
    enforce_production_pins: bool = True,
    clock_skew_seconds: int = DEFAULT_CLOCK_SKEW_SECONDS,
) -> ChainVerification:
    return _receipt.verify_base_release_chain(
        root,
        commit,
        release_entries,
        spec=LEDGER_SPEC,
        anchor_dir=anchor_dir,
        enforce_production_pins=enforce_production_pins,
        clock_skew_seconds=clock_skew_seconds,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="verify the offline thesis-ledger release journal"
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="require a genesis-to-HEAD chain and exact working-tree state",
    )
    parser.add_argument(
        "--base-ref",
        help="also reject any changed/deleted existing releases file vs this ref",
    )
    parser.add_argument(
        "--root",
        type=pathlib.Path,
        default=ROOT,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--anchor-dir",
        type=pathlib.Path,
        help="override releases/anchors (intended for offline test fixtures)",
    )
    parser.add_argument(
        "--clock-skew-seconds",
        type=int,
        default=DEFAULT_CLOCK_SKEW_SECONDS,
    )
    args = parser.parse_args()

    root = args.root.resolve()
    anchor_dir = args.anchor_dir.resolve() if args.anchor_dir else None
    enforce_pins = anchor_dir is None
    try:
        if args.base_ref:
            verify_release_history_immutable(root, args.base_ref)
        verification = verify_release_chain(
            root,
            anchor_dir=anchor_dir,
            require_chain=args.full or bool(args.base_ref),
            verify_state=True,
            enforce_production_pins=enforce_pins,
            clock_skew_seconds=args.clock_skew_seconds,
        )
    except (OSError, ReleaseChainError) as exc:
        print(f"release chain verification failed: {exc}", file=sys.stderr)
        return 1
    if not verification.releases:
        print("release chain absent (legacy pre-genesis state)")
        return 0
    head = verification.releases[-1]
    receipt_summary = ", ".join(
        f"{tsa}={_receipt._format_time(value)}"
        for tsa, value in sorted(head.receipt_times.items())
    )
    print(
        f"release chain OK: {len(verification.releases)} releases, "
        f"HEAD={head.path.name}, {receipt_summary}"
    )
    return 0


__all__ = [
    "ANCHORS",
    "AnchorSpec",
    "ChainSpec",
    "ChainVerification",
    "CRYPTOGRAPHY_AVAILABLE",
    "DEFAULT_CLOCK_SKEW_SECONDS",
    "GitEntry",
    "LEDGER_RELATIVE",
    "MANIFEST_RE",
    "MANIFEST_RELATIVE",
    "PREFIX_RELATIVE",
    "PRODUCER_PUBLIC_KEY_FILENAME",
    "PRODUCER_SIGNATURE_BYTES",
    "PRODUCER_SIGNATURE_RE",
    "PRODUCER_SPKI_SHA256",
    "RECEIPT_RE",
    "ROOT",
    "ReleaseChainError",
    "ReleaseRecord",
    "SCHEMA_VERSION",
    "STATE_PATH",
    "git_blob_bytes",
    "git_file_entry",
    "git_tree_entries",
    "jsonl_line_offsets",
    "load_manifest",
    "main",
    "manifest_filename",
    "materialize_base_tree",
    "parse_created_at",
    "producer_signature_path_for_manifest",
    "receipt_paths_for_manifest",
    "resolve_base_commit",
    "sha256_bytes",
    "validate_manifest_schema",
    "verify_base_release_chain",
    "verify_producer_signature",
    "verify_producer_signature_bytes",
    "verify_receipt",
    "verify_release_chain",
    "verify_release_history_immutable",
    "verify_release_receipts",
]


if __name__ == "__main__":
    raise SystemExit(main())
