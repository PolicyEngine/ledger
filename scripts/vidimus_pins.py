"""Consumer-owned trust and append-gate configuration for vidimus."""

from __future__ import annotations

import pathlib

from vidimus.append_gate import AppendGateSpec
from vidimus.release_chain import AnchorSpec, ChainSpec


LEDGER_SPEC = ChainSpec(
    manifest_relative=pathlib.PurePosixPath("releases/manifests"),
    state_relative=pathlib.PurePosixPath("ledger/official_observations.jsonl"),
    prefix_relative=pathlib.PurePosixPath("ledger/immutable_prefix.json"),
    anchor_relative=pathlib.PurePosixPath("releases/anchors"),
    release_root_relative=pathlib.PurePosixPath("releases"),
    schema_version="thesis_ledger_release_v1",
    producer_public_key_filename="producer-ed25519.pub",
    producer_spki_sha256=(
        "4a90eff40455ce0d853d4bab1608efbdae1efaf8c06054ead6e396c5b0c4846e"
    ),
    anchors={
        "freetsa": AnchorSpec(
            filename="freetsa-root-2016.pem",
            pem_sha256=(
                "2151b61137ffa86bf664691ba67e7da0b19f98c758e3d228d5d8ebf27e044438"
            ),
            policy_oid="1.2.3.4.1",
            signer_certificate_sha256=(
                "32e841a95cc1164101ffde41298ef2fc75c1c4372ef095e88a6bbd47dfb191fc"
            ),
            signer_spki_sha256=(
                "fa02bd555e3e483d62b4e70be6218692068d2b0b0a7525db58dcbf2901cdb072"
            ),
        ),
        "digicert": AnchorSpec(
            filename="digicert-trusted-root-g4.pem",
            pem_sha256=(
                "ce7d6b44f5d510391be98c8d76b18709400a30cd87659bfebe1c6f97ff5181ee"
            ),
            policy_oid="2.16.840.1.114412.7.1",
            signer_certificate_sha256=(
                "4aa03fa22cd75c84c55c938f828e676b9caecab33fe36d269aa334f146110a33"
            ),
            signer_spki_sha256=(
                "7abda95ed7301ac94bded350babc319903d0b4f16c4e7e39346dba5f9e992b72"
            ),
        ),
    },
)


APPEND_GATE_SPEC = AppendGateSpec(
    chain=LEDGER_SPEC,
    prefix_schema_version="thesis_facts_immutable_prefix_v1",
    release_manifest_prefix="releases/manifests/",
    genesis_support_files=frozenset(
        {
            "releases/README.md",
            *(
                f"releases/anchors/{anchor.filename}"
                for anchor in LEDGER_SPEC.anchors.values()
            ),
            (f"releases/anchors/{LEDGER_SPEC.producer_public_key_filename}"),
        }
    ),
    gate_surface=frozenset(
        {
            "scripts/check_thesis_facts_append.py",
            "scripts/verify_release_chain.py",
            "scripts/canonical_json.py",
            "scripts/cut_release_manifest.py",
            ".github/workflows/thesis-facts-append.yml",
            "releases/anchors/**",
        }
    ),
    data_surface=frozenset(
        {
            "ledger/**",
            "releases/manifests/**",
        }
    ),
    assertion_content_keys=(
        "source_record_id",
        "value",
        "observed_at",
        "period",
        "geography",
        "entity",
        "aggregation",
        "filters",
        "domain",
    ),
)
