"""Offline release-chain and append-gate tests.

The committed fixture keys are deliberately public test credentials.  Every
test copies the fixture tree before minting because OpenSSL advances each TSA's
serial file.  No production TSA or network service is contacted.
"""

from __future__ import annotations

import copy
import hashlib
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
TSA_FIXTURE = ROOT / "tests" / "fixtures" / "release_tsa"
SCRIPT_NAMES = (
    "canonical_json.py",
    "check_thesis_facts_append.py",
    "verify_release_chain.py",
)

sys.path.insert(0, str(ROOT / "scripts"))

from canonical_json import canonical_bytes  # noqa: E402
from check_thesis_facts_append import (  # noqa: E402
    expected_assertion_version_id,
)
from cut_release_manifest import (  # noqa: E402
    TSA_ENDPOINTS,
    ReleaseCutError,
    cut_release_manifest,
)
from verify_release_chain import (  # noqa: E402
    ReleaseChainError,
    load_manifest,
    manifest_filename,
    validate_manifest_schema,
)


@dataclass(frozen=True)
class ReleaseEnvironment:
    repo: Path
    tsa: Path

    @property
    def anchors(self) -> Path:
        return self.tsa / "anchors"


def _run(
    command: list[str],
    *,
    cwd: Path,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        check=check,
        capture_output=True,
        text=True,
    )


def _git(repo: Path, *arguments: str) -> str:
    return _run(["git", *arguments], cwd=repo).stdout.strip()


def _initialize_repo(repo: Path) -> str:
    (repo / "ledger").mkdir(parents=True)
    (repo / "scripts").mkdir()
    for name in ("official_observations.jsonl", "immutable_prefix.json"):
        shutil.copy2(ROOT / "ledger" / name, repo / "ledger" / name)
    for name in SCRIPT_NAMES:
        shutil.copy2(ROOT / "scripts" / name, repo / "scripts" / name)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.name", "Release Chain Test")
    _git(repo, "config", "user.email", "release-chain@example.invalid")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "pre-genesis base")
    return _git(repo, "rev-parse", "HEAD")


def _copy_environment(
    source: ReleaseEnvironment, destination: Path
) -> ReleaseEnvironment:
    repo = destination / "repo"
    tsa = destination / "release_tsa"
    shutil.copytree(source.repo, repo)
    shutil.copytree(source.tsa, tsa)
    return ReleaseEnvironment(repo=repo, tsa=tsa)


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _line_count(payload: bytes) -> int:
    assert payload.endswith(b"\n")
    return len(payload.splitlines())


def _created_at() -> str:
    # Give OpenSSL a one-second margin so the receipt cannot precede the
    # producer timestamp solely because the two clocks straddle a second.
    value = datetime.now(timezone.utc) - timedelta(seconds=1)
    return value.isoformat(timespec="seconds").replace("+00:00", "Z")


def _release_manifest(
    repo: Path,
    *,
    index: int,
    previous_manifest: bytes | None = None,
    previous_ledger: bytes | None = None,
) -> dict[str, Any]:
    ledger = (repo / "ledger" / "official_observations.jsonl").read_bytes()
    prefix = (repo / "ledger" / "immutable_prefix.json").read_bytes()
    if index == 0:
        assert previous_manifest is None
        assert previous_ledger is None
        append = None
        previous_digest = None
    else:
        assert previous_manifest is not None
        assert previous_ledger is not None
        assert ledger.startswith(previous_ledger)
        suffix = ledger[len(previous_ledger) :]
        append = {
            "previousLineCount": _line_count(previous_ledger),
            "appendedRowCount": _line_count(ledger) - _line_count(previous_ledger),
            "appendedBytesSha256": _sha256(suffix),
        }
        previous_digest = _sha256(previous_manifest)
    return {
        "schemaVersion": "thesis_ledger_release_v1",
        "releaseIndex": index,
        "previousManifestSha256": previous_digest,
        "state": {
            "path": "ledger/official_observations.jsonl",
            "jsonlSha256": _sha256(ledger),
            "lineCount": _line_count(ledger),
            "immutablePrefixSha256": _sha256(prefix),
        },
        "append": append,
        "createdAtUtc": _created_at(),
        "producer": {
            "repo": "PolicyEngine/ledger",
            "branch": "release-chain-test",
        },
    }


def _mint_receipt(
    payload: Path,
    receipt: Path,
    *,
    tsa: Path,
    signer: str,
) -> None:
    request = tsa / f"{signer}-request.tsq"
    _run(
        [
            "openssl",
            "ts",
            "-query",
            "-data",
            str(payload),
            "-sha256",
            "-cert",
            "-out",
            str(request),
        ],
        cwd=tsa,
    )
    _run(
        [
            "openssl",
            "ts",
            "-reply",
            "-config",
            "openssl-ts.cnf",
            "-queryfile",
            str(request),
            "-out",
            str(receipt),
        ],
        cwd=tsa / signer,
    )


def _write_release(
    environment: ReleaseEnvironment,
    manifest: dict[str, Any],
    *,
    signers: dict[str, str] | None = None,
    signed_payloads: dict[str, Path] | None = None,
) -> Path:
    raw = canonical_bytes(manifest) + b"\n"
    directory = environment.repo / "releases" / "manifests"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / manifest_filename(manifest["releaseIndex"], raw)
    path.write_bytes(raw)
    for slot in ("freetsa", "digicert"):
        receipt = path.with_name(f"{path.stem}.{slot}.tsr")
        payload = (signed_payloads or {}).get(slot, path)
        signer = (signers or {}).get(slot, slot)
        _mint_receipt(payload, receipt, tsa=environment.tsa, signer=signer)
    return path


def _append_valid_row(repo: Path, identity: str) -> tuple[bytes, bytes]:
    ledger_path = repo / "ledger" / "official_observations.jsonl"
    before = ledger_path.read_bytes()
    row = copy.deepcopy(json.loads(before.splitlines()[-1]))
    row["source_record_id"] = identity
    row["label"] = f"Release-chain fixture row {identity}"
    row["value"] += 1
    row["assertionVersion"] = {"id": "", "supersedes": None}
    row["assertionVersion"]["id"] = expected_assertion_version_id(row)
    suffix = (
        json.dumps(
            row,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        + b"\n"
    )
    ledger_path.write_bytes(before + suffix)
    return before, suffix


def _genesis(environment: ReleaseEnvironment) -> Path:
    return _write_release(
        environment,
        _release_manifest(environment.repo, index=0),
    )


def _append_release(environment: ReleaseEnvironment, identity: str) -> Path:
    manifest_directory = environment.repo / "releases" / "manifests"
    genesis = next(manifest_directory.glob("0000-*.json"))
    previous_manifest = genesis.read_bytes()
    previous_ledger, _ = _append_valid_row(environment.repo, identity)
    manifest = _release_manifest(
        environment.repo,
        index=1,
        previous_manifest=previous_manifest,
        previous_ledger=previous_ledger,
    )
    return _write_release(environment, manifest)


def _run_gate(
    environment: ReleaseEnvironment,
    base_ref: str,
) -> subprocess.CompletedProcess[str]:
    return _run(
        [
            sys.executable,
            str(environment.repo / "scripts" / "check_thesis_facts_append.py"),
            "--base-ref",
            base_ref,
            "--release-anchor-dir",
            str(environment.anchors),
        ],
        cwd=environment.repo,
        check=False,
    )


def _run_verifier(environment: ReleaseEnvironment) -> subprocess.CompletedProcess[str]:
    return _run(
        [
            sys.executable,
            str(environment.repo / "scripts" / "verify_release_chain.py"),
            "--root",
            str(environment.repo),
            "--anchor-dir",
            str(environment.anchors),
            "--full",
        ],
        cwd=environment.repo,
        check=False,
    )


def _local_timestamp_requester(
    environment: ReleaseEnvironment,
    *,
    signer_overrides: dict[str, str] | None = None,
):
    endpoint_slots = {endpoint: slot for slot, endpoint in TSA_ENDPOINTS.items()}

    def request(endpoint: str, query: bytes, _timeout_seconds: float) -> bytes:
        slot = endpoint_slots[endpoint]
        signer = (signer_overrides or {}).get(slot, slot)
        request_path = environment.tsa / f"cutter-{slot}-request.tsq"
        response_path = environment.tsa / f"cutter-{slot}-response.tsr"
        request_path.write_bytes(query)
        _run(
            [
                "openssl",
                "ts",
                "-reply",
                "-config",
                "openssl-ts.cnf",
                "-queryfile",
                str(request_path),
                "-out",
                str(response_path),
            ],
            cwd=environment.tsa / signer,
        )
        return response_path.read_bytes()

    return request


@pytest.fixture(scope="session")
def pregenesis_template(tmp_path_factory: pytest.TempPathFactory) -> ReleaseEnvironment:
    root = tmp_path_factory.mktemp("release-pregenesis")
    repo = root / "repo"
    repo.mkdir()
    tsa = root / "release_tsa"
    shutil.copytree(TSA_FIXTURE, tsa)
    _initialize_repo(repo)
    return ReleaseEnvironment(repo=repo, tsa=tsa)


@pytest.fixture(scope="session")
def chain_template(
    tmp_path_factory: pytest.TempPathFactory,
    pregenesis_template: ReleaseEnvironment,
) -> ReleaseEnvironment:
    environment = _copy_environment(
        pregenesis_template,
        tmp_path_factory.mktemp("release-genesis"),
    )
    _genesis(environment)
    _git(environment.repo, "add", ".")
    _git(environment.repo, "commit", "-qm", "witness genesis")
    return environment


@pytest.fixture(scope="session")
def full_chain_template(
    tmp_path_factory: pytest.TempPathFactory,
    chain_template: ReleaseEnvironment,
) -> ReleaseEnvironment:
    environment = _copy_environment(
        chain_template,
        tmp_path_factory.mktemp("release-full-chain"),
    )
    _append_release(environment, "release.fixture.full-chain")
    _git(environment.repo, "add", ".")
    _git(environment.repo, "commit", "-qm", "witness append")
    return environment


@pytest.fixture
def pregenesis_environment(
    tmp_path: Path,
    pregenesis_template: ReleaseEnvironment,
) -> ReleaseEnvironment:
    return _copy_environment(pregenesis_template, tmp_path)


@pytest.fixture
def chain_environment(
    tmp_path: Path,
    chain_template: ReleaseEnvironment,
) -> ReleaseEnvironment:
    return _copy_environment(chain_template, tmp_path)


@pytest.fixture
def full_chain_environment(
    tmp_path: Path,
    full_chain_template: ReleaseEnvironment,
) -> ReleaseEnvironment:
    return _copy_environment(full_chain_template, tmp_path)


def test_legacy_no_chain_append_is_accepted(
    pregenesis_environment: ReleaseEnvironment,
):
    base = _git(pregenesis_environment.repo, "rev-parse", "HEAD")
    _append_valid_row(
        pregenesis_environment.repo,
        "release.fixture.legacy-pre-genesis",
    )

    completed = _run_gate(pregenesis_environment, base)

    assert completed.returncode == 0, completed.stderr
    assert "release" not in completed.stdout


def test_genesis_proposal_is_accepted(
    pregenesis_environment: ReleaseEnvironment,
):
    base = _git(pregenesis_environment.repo, "rev-parse", "HEAD")
    _genesis(pregenesis_environment)

    completed = _run_gate(pregenesis_environment, base)

    assert completed.returncode == 0, completed.stderr
    assert "release 0" in completed.stdout


def test_correct_next_append_and_exact_suffix_are_accepted(
    chain_environment: ReleaseEnvironment,
):
    base = _git(chain_environment.repo, "rev-parse", "HEAD")
    _append_release(chain_environment, "release.fixture.correct-next")

    completed = _run_gate(chain_environment, base)

    assert completed.returncode == 0, completed.stderr
    assert "+1 appended vs base, release 1" in completed.stdout


def test_chain_base_rejects_append_without_manifest(
    chain_environment: ReleaseEnvironment,
):
    base = _git(chain_environment.repo, "rev-parse", "HEAD")
    _append_valid_row(chain_environment.repo, "release.fixture.missing-manifest")

    completed = _run_gate(chain_environment, base)

    assert completed.returncode == 1
    assert "add exactly one manifest" in completed.stderr


def _candidate_manifest(
    environment: ReleaseEnvironment,
    identity: str,
) -> dict[str, Any]:
    genesis = next((environment.repo / "releases" / "manifests").glob("0000-*.json"))
    previous_ledger, _ = _append_valid_row(environment.repo, identity)
    return _release_manifest(
        environment.repo,
        index=1,
        previous_manifest=genesis.read_bytes(),
        previous_ledger=previous_ledger,
    )


def test_chain_base_rejects_wrong_next_index(
    chain_environment: ReleaseEnvironment,
):
    base = _git(chain_environment.repo, "rev-parse", "HEAD")
    manifest = _candidate_manifest(chain_environment, "release.fixture.wrong-index")
    manifest["releaseIndex"] = 2
    _write_release(chain_environment, manifest)

    completed = _run_gate(chain_environment, base)

    assert completed.returncode == 1
    assert "proposal index must be 1, not 2" in completed.stderr


def test_chain_base_rejects_wrong_previous_hash(
    chain_environment: ReleaseEnvironment,
):
    base = _git(chain_environment.repo, "rev-parse", "HEAD")
    manifest = _candidate_manifest(
        chain_environment,
        "release.fixture.wrong-previous",
    )
    manifest["previousManifestSha256"] = "0" * 64
    _write_release(chain_environment, manifest)

    completed = _run_gate(chain_environment, base)

    assert completed.returncode == 1
    assert "previousManifestSha256" in completed.stderr


def test_chain_base_rejects_state_mismatch(
    chain_environment: ReleaseEnvironment,
):
    base = _git(chain_environment.repo, "rev-parse", "HEAD")
    manifest = _candidate_manifest(
        chain_environment,
        "release.fixture.state-mismatch",
    )
    manifest["state"]["jsonlSha256"] = "0" * 64
    _write_release(chain_environment, manifest)

    completed = _run_gate(chain_environment, base)

    assert completed.returncode == 1
    assert "state.jsonlSha256" in completed.stderr


@pytest.mark.parametrize(
    ("field", "replacement", "diagnostic"),
    [
        ("previousLineCount", 0, "previousLineCount"),
        ("appendedRowCount", 2, "appendedRowCount"),
        ("appendedBytesSha256", "0" * 64, "exact byte suffix"),
    ],
)
def test_chain_base_rejects_append_block_mismatch(
    chain_environment: ReleaseEnvironment,
    field: str,
    replacement: int | str,
    diagnostic: str,
):
    base = _git(chain_environment.repo, "rev-parse", "HEAD")
    manifest = _candidate_manifest(
        chain_environment,
        f"release.fixture.append-mismatch.{field}",
    )
    manifest["append"][field] = replacement
    _write_release(chain_environment, manifest)

    completed = _run_gate(chain_environment, base)

    assert completed.returncode == 1
    assert diagnostic in completed.stderr


def test_chain_base_rejects_edited_historical_manifest(
    chain_environment: ReleaseEnvironment,
):
    base = _git(chain_environment.repo, "rev-parse", "HEAD")
    genesis = next(
        (chain_environment.repo / "releases" / "manifests").glob("0000-*.json")
    )
    genesis.write_bytes(genesis.read_bytes() + b" ")

    completed = _run_gate(chain_environment, base)

    assert completed.returncode == 1
    assert "existing release file bytes changed" in completed.stderr


def test_chain_base_rejects_deleted_historical_receipt(
    chain_environment: ReleaseEnvironment,
):
    base = _git(chain_environment.repo, "rev-parse", "HEAD")
    receipt = next(
        (chain_environment.repo / "releases" / "manifests").glob("0000-*.freetsa.tsr")
    )
    receipt.unlink()

    completed = _run_gate(chain_environment, base)

    assert completed.returncode == 1
    assert "existing release file was deleted" in completed.stderr


def test_chain_base_rejects_receipt_over_different_bytes(
    chain_environment: ReleaseEnvironment,
):
    base = _git(chain_environment.repo, "rev-parse", "HEAD")
    manifest = _candidate_manifest(
        chain_environment,
        "release.fixture.different-imprint",
    )
    other = chain_environment.tsa / "different-manifest.json"
    other.write_bytes(b'{"different":true}\n')
    _write_release(
        chain_environment,
        manifest,
        signed_payloads={"freetsa": other},
    )

    completed = _run_gate(chain_environment, base)

    assert completed.returncode == 1
    assert "RFC 3161 verification failed" in completed.stderr


def test_chain_base_rejects_untrusted_receipt(
    chain_environment: ReleaseEnvironment,
):
    base = _git(chain_environment.repo, "rev-parse", "HEAD")
    manifest = _candidate_manifest(
        chain_environment,
        "release.fixture.untrusted-receipt",
    )
    _write_release(
        chain_environment,
        manifest,
        signers={"freetsa": "untrusted"},
    )

    completed = _run_gate(chain_environment, base)

    assert completed.returncode == 1
    assert "RFC 3161 verification failed" in completed.stderr


def test_verifier_cli_full_chain_passes(
    full_chain_environment: ReleaseEnvironment,
):
    completed = _run_verifier(full_chain_environment)

    assert completed.returncode == 0, completed.stderr
    assert "release chain OK: 2 releases" in completed.stdout


def test_cutter_no_tsa_writes_only_canonical_genesis(
    pregenesis_environment: ReleaseEnvironment,
):
    path = cut_release_manifest(
        pregenesis_environment.repo,
        repo="PolicyEngine/ledger",
        branch="release-chain-test",
        no_tsa=True,
        anchor_dir=pregenesis_environment.anchors,
    )

    manifest, raw, digest = load_manifest(path)

    assert manifest["releaseIndex"] == 0
    assert manifest["append"] is None
    assert path.name == manifest_filename(0, raw)
    assert digest == _sha256(raw)
    assert not path.with_name(f"{path.stem}.freetsa.tsr").exists()
    assert not path.with_name(f"{path.stem}.digicert.tsr").exists()


def test_cutter_builds_and_verifies_exact_next_append(
    chain_environment: ReleaseEnvironment,
):
    _previous, suffix = _append_valid_row(
        chain_environment.repo,
        "release.fixture.cutter-next",
    )

    path = cut_release_manifest(
        chain_environment.repo,
        repo="PolicyEngine/ledger",
        branch="release-chain-test",
        anchor_dir=chain_environment.anchors,
        requester=_local_timestamp_requester(chain_environment),
    )

    manifest, _raw, _digest = load_manifest(path)
    completed = _run_verifier(chain_environment)
    assert completed.returncode == 0, completed.stderr
    assert manifest["releaseIndex"] == 1
    assert manifest["append"]["appendedRowCount"] == 1
    assert manifest["append"]["appendedBytesSha256"] == _sha256(suffix)


def test_cutter_rejects_wrong_second_tsa_without_partial_files(
    pregenesis_environment: ReleaseEnvironment,
):
    with pytest.raises((ReleaseChainError, ReleaseCutError)):
        cut_release_manifest(
            pregenesis_environment.repo,
            repo="PolicyEngine/ledger",
            branch="release-chain-test",
            anchor_dir=pregenesis_environment.anchors,
            requester=_local_timestamp_requester(
                pregenesis_environment,
                signer_overrides={"digicert": "freetsa"},
            ),
        )

    manifest_directory = (
        pregenesis_environment.repo / "releases" / "manifests"
    )
    assert not manifest_directory.exists() or not any(manifest_directory.iterdir())


@pytest.mark.parametrize(
    "tamper",
    [
        "historical-manifest",
        "deleted-receipt",
        "different-imprint",
        "untrusted-receipt",
        "swapped-receipt-slots",
        "wrong-previous",
        "state-mismatch",
        "append-suffix-mismatch",
    ],
)
def test_verifier_cli_catches_manifest_and_receipt_tampering(
    full_chain_environment: ReleaseEnvironment,
    tamper: str,
):
    directory = full_chain_environment.repo / "releases" / "manifests"
    genesis = next(directory.glob("0000-*.json"))
    head = next(directory.glob("0001-*.json"))
    if tamper == "historical-manifest":
        genesis.write_bytes(genesis.read_bytes() + b" ")
    elif tamper == "deleted-receipt":
        head.with_name(f"{head.stem}.digicert.tsr").unlink()
    elif tamper == "different-imprint":
        other = full_chain_environment.tsa / "different.json"
        other.write_bytes(b'{"different":true}\n')
        _mint_receipt(
            other,
            head.with_name(f"{head.stem}.freetsa.tsr"),
            tsa=full_chain_environment.tsa,
            signer="freetsa",
        )
    elif tamper == "untrusted-receipt":
        _mint_receipt(
            head,
            head.with_name(f"{head.stem}.freetsa.tsr"),
            tsa=full_chain_environment.tsa,
            signer="untrusted",
        )
    elif tamper == "swapped-receipt-slots":
        freetsa = head.with_name(f"{head.stem}.freetsa.tsr")
        digicert = head.with_name(f"{head.stem}.digicert.tsr")
        freetsa_bytes = freetsa.read_bytes()
        freetsa.write_bytes(digicert.read_bytes())
        digicert.write_bytes(freetsa_bytes)
    else:
        manifest = json.loads(head.read_text(encoding="utf-8"))
        for path in (
            head,
            head.with_name(f"{head.stem}.freetsa.tsr"),
            head.with_name(f"{head.stem}.digicert.tsr"),
        ):
            path.unlink()
        if tamper == "wrong-previous":
            manifest["previousManifestSha256"] = "0" * 64
        elif tamper == "state-mismatch":
            manifest["state"]["jsonlSha256"] = "0" * 64
        else:
            manifest["append"]["appendedBytesSha256"] = "0" * 64
        _write_release(full_chain_environment, manifest)

    completed = _run_verifier(full_chain_environment)

    assert completed.returncode == 1
    assert "release chain verification failed" in completed.stderr


def test_receipt_slots_are_cryptographically_isolated(
    full_chain_environment: ReleaseEnvironment,
):
    directory = full_chain_environment.repo / "releases" / "manifests"
    head = next(directory.glob("0001-*.json"))
    freetsa = head.with_name(f"{head.stem}.freetsa.tsr")
    digicert = head.with_name(f"{head.stem}.digicert.tsr")
    freetsa_bytes = freetsa.read_bytes()
    freetsa.write_bytes(digicert.read_bytes())
    digicert.write_bytes(freetsa_bytes)

    completed = _run_verifier(full_chain_environment)

    assert completed.returncode == 1
    assert "RFC 3161 verification failed" in completed.stderr


def _schema_manifest(index: int = 1) -> dict[str, Any]:
    manifest = {
        "schemaVersion": "thesis_ledger_release_v1",
        "releaseIndex": index,
        "previousManifestSha256": "1" * 64 if index else None,
        "state": {
            "path": "ledger/official_observations.jsonl",
            "jsonlSha256": "2" * 64,
            "lineCount": 2,
            "immutablePrefixSha256": "3" * 64,
        },
        "append": {
            "previousLineCount": 1,
            "appendedRowCount": 1,
            "appendedBytesSha256": "4" * 64,
        },
        "createdAtUtc": "2026-07-11T00:00:00Z",
        "producer": {"repo": "PolicyEngine/ledger", "branch": "test"},
    }
    if index == 0:
        manifest["append"] = None
    return manifest


@pytest.mark.parametrize(
    ("location", "field"),
    [
        ("manifest", "unexpected"),
        ("state", "unexpected"),
        ("append", "unexpected"),
        ("producer", "unexpected"),
    ],
)
def test_manifest_schema_is_closed_world(location: str, field: str):
    manifest = _schema_manifest()
    target = manifest if location == "manifest" else manifest[location]
    target[field] = "candidate-controlled extension"

    with pytest.raises(ReleaseChainError, match="closed-world"):
        validate_manifest_schema(manifest)


@pytest.mark.parametrize(
    ("location", "field"),
    [
        ("manifest", "releaseIndex"),
        ("state", "lineCount"),
        ("append", "previousLineCount"),
        ("append", "appendedRowCount"),
    ],
)
def test_manifest_counts_reject_boolean_values(location: str, field: str):
    manifest = _schema_manifest()
    target = manifest if location == "manifest" else manifest[location]
    target[field] = True

    with pytest.raises(ReleaseChainError, match="not a boolean"):
        validate_manifest_schema(manifest)


@pytest.mark.parametrize(
    "render",
    [
        lambda manifest: canonical_bytes(manifest),
        lambda manifest: json.dumps(manifest, indent=2).encode("utf-8") + b"\n",
        lambda manifest: canonical_bytes(manifest) + b"\n\n",
    ],
)
def test_manifest_file_requires_exact_canonical_bytes(
    tmp_path: Path,
    render,
):
    path = tmp_path / "manifest.json"
    path.write_bytes(render(_schema_manifest()))

    with pytest.raises(ReleaseChainError, match="not canonical JSON"):
        load_manifest(path)


def test_manifest_file_accepts_canonical_bytes_plus_one_newline(tmp_path: Path):
    manifest = _schema_manifest()
    raw = canonical_bytes(manifest) + b"\n"
    path = tmp_path / "manifest.json"
    path.write_bytes(raw)

    loaded, loaded_raw, digest = load_manifest(path)

    assert loaded == manifest
    assert loaded_raw == raw
    assert digest == _sha256(raw)
