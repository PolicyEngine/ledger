#!/usr/bin/env python3
"""Cut the next witnessed thesis-ledger release for the working tree.

The cutter accepts a pending append after an already witnessed HEAD: it first
verifies the existing release chain without requiring that HEAD equal the
working-tree ledger, then proves that the old HEAD is the exact byte prefix of
the current ledger.  A networked cut stages and fully verifies both RFC 3161
responses before any release file is created.
"""

from __future__ import annotations

import argparse
import http.client
import math
import os
import pathlib
import re
import stat
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from typing import Any

from canonical_json import canonical_bytes
from verify_release_chain import (
    DEFAULT_CLOCK_SKEW_SECONDS,
    LEDGER_RELATIVE,
    MANIFEST_RELATIVE,
    PREFIX_RELATIVE,
    ROOT,
    SCHEMA_VERSION,
    ChainVerification,
    ReleaseChainError,
    jsonl_line_offsets,
    load_manifest,
    manifest_filename,
    receipt_paths_for_manifest,
    sha256_bytes,
    validate_manifest_schema,
    verify_release_chain,
)

MAX_TOKEN_BYTES = 1024 * 1024
DEFAULT_TIMEOUT_SECONDS = 45.0
TSA_ENDPOINTS = {
    "freetsa": "https://freetsa.org/tsr",
    # DigiCert's documented RFC 3161 endpoint is plain HTTP (their TLS
    # endpoint does not answer timestamp queries); the token itself is a
    # self-authenticating signature, verified against pinned anchors.
    "digicert": "http://timestamp.digicert.com",
}
Requester = Callable[[str, bytes, float], bytes]


class ReleaseCutError(RuntimeError):
    """The next release could not be constructed or safely written."""


def _validate_timeout(value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ReleaseCutError("timeout_seconds must be a finite positive number")
    result = float(value)
    if not math.isfinite(result) or result <= 0:
        raise ReleaseCutError("timeout_seconds must be a finite positive number")
    return result


def request_timestamp(endpoint: str, query: bytes, timeout_seconds: float) -> bytes:
    """POST one DER RFC 3161 query and return a size-bounded response."""

    if endpoint not in TSA_ENDPOINTS.values():
        raise ReleaseCutError(f"refusing unapproved TSA endpoint: {endpoint!r}")
    if type(query) is not bytes or not query:
        raise ReleaseCutError("RFC 3161 query must be non-empty bytes")
    timeout = _validate_timeout(timeout_seconds)
    request = urllib.request.Request(
        endpoint,
        data=query,
        headers={
            "Content-Type": "application/timestamp-query",
            "User-Agent": "Thesis-Ledger-Release-Witness/1",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        token = response.read(MAX_TOKEN_BYTES + 1)
    if not token:
        raise ReleaseCutError(f"TSA returned an empty response: {endpoint}")
    if len(token) > MAX_TOKEN_BYTES:
        raise ReleaseCutError(
            f"TSA response exceeds the one-megabyte limit: {endpoint}"
        )
    return token


def _run_git(root: pathlib.Path, arguments: list[str], label: str) -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), *arguments],
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise ReleaseCutError(
            f"git is required to auto-detect producer {label}"
        ) from exc
    if completed.returncode != 0:
        diagnostic = (completed.stderr or completed.stdout).strip()
        raise ReleaseCutError(
            f"cannot auto-detect producer {label}: {diagnostic or 'git command failed'}"
        )
    output = completed.stdout.strip()
    if not output or "\n" in output or "\r" in output:
        raise ReleaseCutError(f"cannot auto-detect a unique non-empty producer {label}")
    return output


def _validate_provenance(value: str, label: str) -> str:
    if type(value) is not str or not value or value != value.strip():
        raise ReleaseCutError(
            f"producer {label} must be a non-empty string without outer whitespace"
        )
    if len(value) > 1024 or any(
        ord(char) < 0x20 or ord(char) == 0x7F for char in value
    ):
        raise ReleaseCutError(
            f"producer {label} contains control characters or is too long"
        )
    return value


_SCP_REMOTE_RE = re.compile(r"(?:[^/@:]+@)?(?P<host>[^/:]+):(?P<path>[^?#]+)\Z")


def _normalize_remote(remote: str) -> str:
    """Return credential-free repository provenance from a Git remote URL."""

    remote = _validate_provenance(remote, "remote URL")
    host: str
    path: str
    if "://" in remote:
        parsed = urllib.parse.urlsplit(remote)
        if parsed.scheme not in {"https", "ssh", "git"}:
            raise ReleaseCutError(
                "cannot safely normalize the origin URL; pass --repo explicitly"
            )
        if parsed.query or parsed.fragment or not parsed.hostname:
            raise ReleaseCutError(
                "cannot safely normalize the origin URL; pass --repo explicitly"
            )
        host = parsed.hostname
        try:
            port = parsed.port
        except ValueError as exc:
            raise ReleaseCutError(
                "cannot safely normalize the origin URL; pass --repo explicitly"
            ) from exc
        if port is not None:
            host = f"{host}:{port}"
        path = parsed.path
    else:
        match = _SCP_REMOTE_RE.fullmatch(remote)
        if match is None:
            raise ReleaseCutError(
                "origin is not a network repository URL; pass --repo explicitly"
            )
        host = match.group("host")
        path = match.group("path")

    pieces = path.strip("/").split("/")
    if pieces and pieces[-1].endswith(".git"):
        pieces[-1] = pieces[-1][:-4]
    if not pieces or any(piece in {"", ".", ".."} for piece in pieces):
        raise ReleaseCutError(
            "cannot safely normalize the origin URL; pass --repo explicitly"
        )
    if host.lower() in {"github.com", "www.github.com"}:
        if len(pieces) != 2:
            raise ReleaseCutError(
                "GitHub origin is not an owner/repository URL; pass --repo explicitly"
            )
        return _validate_provenance("/".join(pieces), "repo")
    return _validate_provenance(f"{host}/{'/'.join(pieces)}", "repo")


def _git_root(root: pathlib.Path) -> None:
    detected = pathlib.Path(
        _run_git(root, ["rev-parse", "--show-toplevel"], "Git worktree")
    ).resolve()
    if detected != root:
        raise ReleaseCutError(
            f"--root must be the Git worktree root ({detected}), not {root}"
        )


def detect_producer(
    root: pathlib.Path,
    *,
    repo: str | None,
    branch: str | None,
) -> dict[str, str]:
    """Resolve producer claims without invoking a shell or recording credentials."""

    if repo is not None:
        selected_repo = _validate_provenance(repo, "repo")
    else:
        _git_root(root)
        selected_repo = _normalize_remote(
            _run_git(root, ["remote", "get-url", "origin"], "repo")
        )

    if branch is not None:
        selected_branch = _validate_provenance(branch, "branch")
    else:
        _git_root(root)
        selected_branch = _validate_provenance(
            _run_git(
                root,
                ["symbolic-ref", "--quiet", "--short", "HEAD"],
                "branch (detached HEAD; pass --branch explicitly)",
            ),
            "branch",
        )
    return {"repo": selected_repo, "branch": selected_branch}


def _regular_bytes(path: pathlib.Path, label: str) -> bytes:
    try:
        flags = os.O_RDONLY
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(path, flags)
    except FileNotFoundError as exc:
        raise ReleaseCutError(f"required {label} is missing: {path}") from exc
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise ReleaseCutError(f"required {label} is not a regular file: {path}")
        with os.fdopen(descriptor, "rb") as stream:
            descriptor = -1
            return stream.read()
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _created_at_utc(now: datetime | None) -> str:
    current = now or datetime.now(timezone.utc)
    if (
        not isinstance(current, datetime)
        or current.tzinfo is None
        or current.utcoffset() is None
    ):
        raise ReleaseCutError("now must be a timezone-aware datetime")
    try:
        current_utc = current.astimezone(timezone.utc)
    except (OverflowError, ValueError) as exc:
        raise ReleaseCutError("now cannot be represented as UTC") from exc
    return current_utc.isoformat(timespec="seconds").replace("+00:00", "Z")


def _build_manifest(
    ledger: bytes,
    immutable_prefix: bytes,
    existing: ChainVerification,
    producer: dict[str, str],
    *,
    now: datetime | None,
) -> tuple[dict[str, Any], bytes]:
    offsets = jsonl_line_offsets(ledger, LEDGER_RELATIVE.as_posix())
    line_count = len(offsets) - 1
    head = existing.head
    if head is None:
        release_index = 0
        previous_hash = None
        append = None
    else:
        previous_count = head.manifest["state"]["lineCount"]
        if previous_count > line_count:
            raise ReleaseCutError(
                f"working-tree ledger has {line_count} rows, fewer than witnessed "
                f"HEAD's {previous_count} rows"
            )
        witnessed_prefix = ledger[: offsets[previous_count]]
        witnessed_digest = sha256_bytes(witnessed_prefix)
        if witnessed_digest != head.manifest["state"]["jsonlSha256"]:
            raise ReleaseCutError(
                "working-tree ledger does not begin with the exact byte state "
                "committed by the witnessed HEAD"
            )
        immutable_digest = sha256_bytes(immutable_prefix)
        if immutable_digest != head.manifest["state"]["immutablePrefixSha256"]:
            raise ReleaseCutError(
                "ledger/immutable_prefix.json differs from the witnessed HEAD"
            )
        if line_count == previous_count:
            raise ReleaseCutError(
                "working-tree ledger has no pending rows after the witnessed HEAD"
            )
        release_index = head.release_index + 1
        previous_hash = head.sha256
        suffix = ledger[offsets[previous_count] :]
        append = {
            "previousLineCount": previous_count,
            "appendedRowCount": line_count - previous_count,
            "appendedBytesSha256": sha256_bytes(suffix),
        }

    manifest: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "releaseIndex": release_index,
        "previousManifestSha256": previous_hash,
        "state": {
            "path": LEDGER_RELATIVE.as_posix(),
            "jsonlSha256": sha256_bytes(ledger),
            "lineCount": line_count,
            "immutablePrefixSha256": sha256_bytes(immutable_prefix),
        },
        "append": append,
        "createdAtUtc": _created_at_utc(now),
        "producer": producer,
    }
    validate_manifest_schema(manifest)
    return manifest, canonical_bytes(manifest) + b"\n"


def _build_timestamp_query(manifest: bytes, timeout_seconds: float) -> bytes:
    with tempfile.TemporaryDirectory(prefix="thesis-release-query-") as name:
        temporary = pathlib.Path(name)
        manifest_path = temporary / "manifest.json"
        query_path = temporary / "request.tsq"
        manifest_path.write_bytes(manifest)
        try:
            completed = subprocess.run(
                [
                    "openssl",
                    "ts",
                    "-query",
                    "-config",
                    "/dev/null",
                    "-data",
                    str(manifest_path),
                    "-sha256",
                    "-cert",
                    "-out",
                    str(query_path),
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                env={**os.environ, "LC_ALL": "C", "OPENSSL_CONF": "/dev/null"},
            )
        except FileNotFoundError as exc:
            raise ReleaseCutError(
                "openssl is required to construct the RFC 3161 query"
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise ReleaseCutError(
                "OpenSSL timestamp-query construction timed out"
            ) from exc
        if completed.returncode != 0:
            diagnostic = (completed.stderr or completed.stdout).strip()
            raise ReleaseCutError(
                "OpenSSL timestamp-query construction failed: "
                f"{diagnostic[-1000:] or 'no diagnostic'}"
            )
        query = _regular_bytes(query_path, "RFC 3161 query")
    if not query or len(query) > MAX_TOKEN_BYTES:
        raise ReleaseCutError("OpenSSL produced an invalid-sized RFC 3161 query")
    return query


def _request_receipts(
    query: bytes,
    *,
    requester: Requester,
    timeout_seconds: float,
) -> dict[str, bytes]:
    receipts: dict[str, bytes] = {}
    for tsa, endpoint in TSA_ENDPOINTS.items():
        try:
            token = requester(endpoint, query, timeout_seconds)
        except (
            http.client.HTTPException,
            OSError,
            ReleaseCutError,
            urllib.error.URLError,
        ) as exc:
            raise ReleaseCutError(f"{tsa} timestamp request failed: {exc}") from exc
        except Exception as exc:
            raise ReleaseCutError(f"{tsa} timestamp request failed: {exc}") from exc
        if type(token) is not bytes or not token:
            raise ReleaseCutError(f"{tsa} TSA must return non-empty bytes")
        if len(token) > MAX_TOKEN_BYTES:
            raise ReleaseCutError(f"{tsa} TSA response exceeds the one-megabyte limit")
        receipts[tsa] = token
    return receipts


def _write_staged_tree(
    stage: pathlib.Path,
    existing: ChainVerification,
    ledger: bytes,
    immutable_prefix: bytes,
    filename: str,
    manifest: bytes,
    receipts: Mapping[str, bytes],
) -> None:
    ledger_path = stage / LEDGER_RELATIVE
    prefix_path = stage / PREFIX_RELATIVE
    manifest_dir = stage / MANIFEST_RELATIVE
    ledger_path.parent.mkdir(parents=True)
    manifest_dir.mkdir(parents=True)
    ledger_path.write_bytes(ledger)
    prefix_path.write_bytes(immutable_prefix)
    for record in existing.releases:
        (manifest_dir / record.path.name).write_bytes(record.raw)
        for tsa, receipt_path in record.receipt_paths.items():
            (manifest_dir / receipt_path.name).write_bytes(
                _regular_bytes(receipt_path, f"existing {tsa} receipt")
            )
    candidate = manifest_dir / filename
    candidate.write_bytes(manifest)
    for tsa, token in receipts.items():
        receipt_paths_for_manifest(candidate)[tsa].write_bytes(token)


def _verify_staged_release(
    existing: ChainVerification,
    ledger: bytes,
    immutable_prefix: bytes,
    filename: str,
    manifest: bytes,
    receipts: Mapping[str, bytes],
    *,
    anchor_dir: pathlib.Path,
    enforce_production_pins: bool,
    clock_skew_seconds: int,
) -> None:
    with tempfile.TemporaryDirectory(prefix="thesis-release-stage-") as name:
        stage = pathlib.Path(name)
        _write_staged_tree(
            stage,
            existing,
            ledger,
            immutable_prefix,
            filename,
            manifest,
            receipts,
        )
        verify_release_chain(
            stage,
            anchor_dir=anchor_dir,
            require_chain=True,
            verify_state=True,
            enforce_production_pins=enforce_production_pins,
            clock_skew_seconds=clock_skew_seconds,
        )


def _check_output_ancestors(root: pathlib.Path) -> None:
    for directory in (root / "releases", root / MANIFEST_RELATIVE):
        try:
            metadata = directory.lstat()
        except FileNotFoundError:
            continue
        if not stat.S_ISDIR(metadata.st_mode):
            raise ReleaseCutError(
                f"release output parent is not a real directory: {directory}"
            )


def _check_targets_absent(paths: list[pathlib.Path]) -> None:
    for path in paths:
        if os.path.lexists(path):
            raise ReleaseCutError(f"refusing to overwrite release file: {path}")


def _prepare_output_directory(
    root: pathlib.Path,
) -> tuple[pathlib.Path, list[pathlib.Path]]:
    created: list[pathlib.Path] = []
    try:
        for directory in (root / "releases", root / MANIFEST_RELATIVE):
            try:
                os.mkdir(directory, 0o755)
                created.append(directory)
            except FileExistsError:
                try:
                    metadata = directory.lstat()
                except FileNotFoundError as exc:
                    raise ReleaseCutError(
                        f"release output directory changed concurrently: {directory}"
                    ) from exc
                if not stat.S_ISDIR(metadata.st_mode):
                    raise ReleaseCutError(
                        f"release output parent is not a real directory: {directory}"
                    )
    except Exception:
        _remove_empty_directories(created)
        raise
    return root / MANIFEST_RELATIVE, created


def _remove_empty_directories(directories: list[pathlib.Path]) -> None:
    for directory in reversed(directories):
        try:
            directory.rmdir()
        except OSError:
            pass


def _exclusive_batch_write(
    root: pathlib.Path,
    payloads: Mapping[pathlib.Path, bytes],
    *,
    verify_written: Callable[[], None],
) -> None:
    if not payloads:
        raise ReleaseCutError("no release files were provided for writing")
    parents = {path.parent for path in payloads}
    if parents != {root / MANIFEST_RELATIVE}:
        raise ReleaseCutError("release outputs escaped releases/manifests")
    _check_output_ancestors(root)
    _check_targets_absent(list(payloads))
    directory, created_directories = _prepare_output_directory(root)
    directory_flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        directory_flags |= os.O_DIRECTORY
    if hasattr(os, "O_NOFOLLOW"):
        directory_flags |= os.O_NOFOLLOW
    directory_fd: int | None = None
    created_names: list[str] = []
    succeeded = False
    try:
        directory_fd = os.open(directory, directory_flags)
        for path, payload in payloads.items():
            try:
                os.stat(path.name, dir_fd=directory_fd, follow_symlinks=False)
            except FileNotFoundError:
                pass
            else:
                raise ReleaseCutError(f"refusing to overwrite release file: {path}")
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            descriptor = os.open(path.name, flags, 0o644, dir_fd=directory_fd)
            created_names.append(path.name)
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
        os.fsync(directory_fd)
        verify_written()
        succeeded = True
    except BaseException as exc:
        cleanup_failures: list[str] = []
        if directory_fd is not None:
            for name in reversed(created_names):
                try:
                    os.unlink(name, dir_fd=directory_fd)
                except FileNotFoundError:
                    pass
                except OSError:
                    cleanup_failures.append(name)
            try:
                os.fsync(directory_fd)
            except OSError:
                pass
        if cleanup_failures:
            raise ReleaseCutError(
                "release write failed and rollback could not remove: "
                f"{cleanup_failures}; original error: {exc}"
            ) from exc
        raise
    finally:
        if directory_fd is not None:
            os.close(directory_fd)
        if not succeeded:
            _remove_empty_directories(created_directories)


def _snapshot_existing_files(
    verification: ChainVerification,
) -> dict[pathlib.Path, bytes]:
    snapshot: dict[pathlib.Path, bytes] = {}
    for record in verification.releases:
        snapshot[record.path] = record.raw
        for tsa, path in record.receipt_paths.items():
            snapshot[path] = _regular_bytes(path, f"existing {tsa} receipt")
    return snapshot


def _assert_unchanged(
    ledger_path: pathlib.Path,
    prefix_path: pathlib.Path,
    ledger: bytes,
    immutable_prefix: bytes,
    history: Mapping[pathlib.Path, bytes],
) -> None:
    if _regular_bytes(ledger_path, "ledger JSONL") != ledger:
        raise ReleaseCutError("ledger changed while the release was being cut")
    if _regular_bytes(prefix_path, "immutable-prefix manifest") != immutable_prefix:
        raise ReleaseCutError(
            "immutable-prefix manifest changed while the release was being cut"
        )
    for path, expected in history.items():
        if _regular_bytes(path, "existing release file") != expected:
            raise ReleaseCutError(
                f"existing release file changed while cutting the release: {path}"
            )


def cut_release_manifest(
    root: pathlib.Path = ROOT,
    *,
    repo: str | None = None,
    branch: str | None = None,
    no_tsa: bool = False,
    anchor_dir: pathlib.Path | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    clock_skew_seconds: int = DEFAULT_CLOCK_SKEW_SECONDS,
    requester: Requester | None = None,
    now: datetime | None = None,
) -> pathlib.Path:
    """Build and safely write the next release, returning its manifest path."""

    if type(no_tsa) is not bool:
        raise ReleaseCutError("no_tsa must be a boolean")
    if type(clock_skew_seconds) is not int or clock_skew_seconds < 0:
        raise ReleaseCutError("clock_skew_seconds must be a non-negative integer")
    timeout = _validate_timeout(timeout_seconds)
    try:
        selected_root = pathlib.Path(root).resolve(strict=True)
    except FileNotFoundError as exc:
        raise ReleaseCutError(f"repository root does not exist: {root}") from exc
    if not selected_root.is_dir():
        raise ReleaseCutError(f"repository root is not a directory: {selected_root}")
    selected_anchors = (
        pathlib.Path(anchor_dir).resolve()
        if anchor_dir is not None
        else selected_root / "releases" / "anchors"
    )
    enforce_production_pins = anchor_dir is None

    existing = verify_release_chain(
        selected_root,
        anchor_dir=selected_anchors,
        require_chain=False,
        verify_state=True,
        allow_pending_append=True,
        enforce_production_pins=enforce_production_pins,
        clock_skew_seconds=clock_skew_seconds,
    )
    ledger_path = selected_root / LEDGER_RELATIVE
    prefix_path = selected_root / PREFIX_RELATIVE
    ledger = _regular_bytes(ledger_path, "ledger JSONL")
    immutable_prefix = _regular_bytes(prefix_path, "immutable-prefix manifest")
    producer = detect_producer(
        selected_root,
        repo=repo,
        branch=branch,
    )
    _manifest, raw = _build_manifest(
        ledger,
        immutable_prefix,
        existing,
        producer,
        now=now,
    )
    filename = manifest_filename(_manifest["releaseIndex"], raw)
    manifest_path = selected_root / MANIFEST_RELATIVE / filename
    receipt_paths = receipt_paths_for_manifest(manifest_path)
    all_targets = [manifest_path, *receipt_paths.values()]
    _check_output_ancestors(selected_root)
    _check_targets_absent(all_targets)
    history = _snapshot_existing_files(existing)

    if no_tsa:

        def verify_manifest_only() -> None:
            loaded, loaded_raw, _digest = load_manifest(manifest_path)
            if loaded != _manifest or loaded_raw != raw:
                raise ReleaseCutError("written manifest differs from constructed bytes")
            _assert_unchanged(
                ledger_path,
                prefix_path,
                ledger,
                immutable_prefix,
                history,
            )

        _assert_unchanged(
            ledger_path,
            prefix_path,
            ledger,
            immutable_prefix,
            history,
        )
        _exclusive_batch_write(
            selected_root,
            {manifest_path: raw},
            verify_written=verify_manifest_only,
        )
        return manifest_path

    query = _build_timestamp_query(raw, timeout)
    receipts = _request_receipts(
        query,
        requester=request_timestamp if requester is None else requester,
        timeout_seconds=timeout,
    )
    _verify_staged_release(
        existing,
        ledger,
        immutable_prefix,
        filename,
        raw,
        receipts,
        anchor_dir=selected_anchors,
        enforce_production_pins=enforce_production_pins,
        clock_skew_seconds=clock_skew_seconds,
    )
    payloads = {
        manifest_path: raw,
        **{receipt_paths[tsa]: token for tsa, token in receipts.items()},
    }

    def verify_committed_release() -> None:
        _assert_unchanged(
            ledger_path,
            prefix_path,
            ledger,
            immutable_prefix,
            history,
        )
        verify_release_chain(
            selected_root,
            anchor_dir=selected_anchors,
            require_chain=True,
            verify_state=True,
            enforce_production_pins=enforce_production_pins,
            clock_skew_seconds=clock_skew_seconds,
        )

    _exclusive_batch_write(
        selected_root,
        payloads,
        verify_written=verify_committed_release,
    )
    return manifest_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="cut the next witnessed thesis-ledger release manifest"
    )
    parser.add_argument(
        "--root",
        type=pathlib.Path,
        default=ROOT,
        help="repository root (default: this script's repository)",
    )
    parser.add_argument(
        "--anchor-dir",
        type=pathlib.Path,
        help="override TSA anchors (intended for offline tests)",
    )
    parser.add_argument("--repo", help="override producer.repo provenance")
    parser.add_argument("--branch", help="override producer.branch provenance")
    parser.add_argument(
        "--no-tsa",
        action="store_true",
        help="write only the manifest; do not request or write receipts",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=DEFAULT_TIMEOUT_SECONDS,
    )
    parser.add_argument(
        "--clock-skew-seconds",
        type=int,
        default=DEFAULT_CLOCK_SKEW_SECONDS,
    )
    args = parser.parse_args()
    try:
        manifest_path = cut_release_manifest(
            args.root,
            repo=args.repo,
            branch=args.branch,
            no_tsa=args.no_tsa,
            anchor_dir=args.anchor_dir,
            timeout_seconds=args.timeout_seconds,
            clock_skew_seconds=args.clock_skew_seconds,
        )
    except (OSError, ReleaseChainError, ReleaseCutError, ValueError) as exc:
        print(f"release cut failed: {exc}", file=sys.stderr)
        return 1
    if args.no_tsa:
        print(f"release manifest written without TSA receipts: {manifest_path}")
    else:
        print(f"witnessed release written: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
