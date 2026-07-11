# Witnessed ledger releases

In the gated append flow, each proposed state of
`ledger/official_observations.jsonl` is committed by a canonical release manifest
and witnessed by two RFC 3161 timestamp authorities. The manifests form an
append-only hash chain. The receipts let a verifier show that the exact manifest
bytes existed no later than each receipt's `genTime`.

## Files

For a stem `<index>-<hash16>`, where `index` is the zero-padded four-digit
release index and `hash16` is the first 16 lowercase hexadecimal characters of
the manifest file's SHA-256 digest, a release consists of exactly these files:

- `releases/manifests/<stem>.json`
- `releases/manifests/<stem>.freetsa.tsr`
- `releases/manifests/<stem>.digicert.tsr`

For example, the receipt for manifest `0007-0123456789abcdef.json` is named
`0007-0123456789abcdef.freetsa.tsr`, not
`0007-0123456789abcdef.json.freetsa.tsr`. Receipts are DER-encoded RFC 3161
responses whose SHA-256 message imprint covers the manifest file's exact bytes.
Those bytes are canonical JSON produced by `scripts/canonical_json.py`, followed
by one newline.

The pinned TSA verification chains are committed as PEM files under
`releases/anchors/`. Verification does not contact either TSA or any other
network service.

## Manifest schema

Every manifest uses the closed-world `thesis_ledger_release_v1` schema. Unknown
keys are invalid at every level, and counts are JSON integers (booleans are not
accepted as integers). The required root members are:

- `schemaVersion`: the literal `"thesis_ledger_release_v1"`.
- `releaseIndex`: a contiguous integer beginning at zero.
- `previousManifestSha256`: `null` for genesis; otherwise the full lowercase
  SHA-256 digest of the previous manifest file's exact bytes.
- `state`: an object containing only:
  - `path`: the literal `"ledger/official_observations.jsonl"`.
  - `jsonlSha256`: the lowercase SHA-256 digest of the ledger bytes represented
    by this release.
  - `lineCount`: the number of JSONL rows represented by this release.
  - `immutablePrefixSha256`: the lowercase SHA-256 digest of the exact bytes of
    `ledger/immutable_prefix.json`.
- `append`: `null` for genesis; otherwise an object containing only:
  - `previousLineCount`: the preceding manifest's `state.lineCount`.
  - `appendedRowCount`: the number of newly appended JSONL rows.
  - `appendedBytesSha256`: the lowercase SHA-256 digest of the exact byte suffix
    added after the preceding state.
- `createdAtUtc`: a strict UTC timestamp ending in `Z`.
- `producer`: an object containing only the free-form provenance strings `repo`
  and `branch`. These strings are recorded claims, not trusted authorization.

Genesis has index zero, a null previous hash, and a null append block. Every
later release increments the index by one, hashes the preceding manifest file,
increases the line count, and binds both the row-count delta and the exact byte
suffix in its append block. Both receipts must verify against their separately
pinned anchor chain and cover that release's exact manifest bytes.

## Offline verification

Clone the repository at the state you want to inspect and run:

```console
python3 scripts/verify_release_chain.py --full
```

The verifier needs only Python, OpenSSL, the committed manifests and receipts,
the committed TSA anchors, and the ledger files. It checks canonical bytes,
filenames, contiguous indices, previous-manifest links, state and append
commitments, both timestamp receipts, and timestamp ordering. Any mismatch exits
nonzero with an error identifying the failed invariant.

Retain a trusted checkpoint outside this repository, at minimum the full SHA-256
digest of a previously accepted head manifest, and compare it with later clones.
Internal verification proves that a clone is self-consistent; by itself it cannot
distinguish the original history from a complete, freshly witnessed replacement
fork. RFC 3161 timestamp authorities attest timestamps for submitted digests but
do not publish a uniqueness-enforcing append-only ledger for this repository.

## Security properties and limits

Under the configured proposal gate, every ledger append arrives with the next
manifest and both receipts. This binds the proposed ledger state, immutable
prefix, previous release, row-count change, and exact appended byte suffix into a
witnessed chain. Rewriting a checkpointed manifest or producing an unwitnessed or
internally inconsistent state is therefore detectable by any verifier holding
that checkpoint.

An RFC 3161 `genTime` establishes that the manifest existed no later than that
time. It does **not** timestamp GitHub's merge or prove when the organization
accepted the proposal. In the intended pull-request flow the receipts are created
before the gate can pass and therefore before merge; their times do not upper-bound
the later acceptance time.

This mechanism provides tamper evidence, not multi-party authorization or admin
non-repudiation. Governance remains within one GitHub organization:

- It does not require approval by an independent institution or a second party.
- An unwitnessed or inconsistent admin direct push turns verification and CI red,
  but repository controls cannot prevent every admin bypass.
- An admin direct push that includes a valid next manifest and both valid receipts
  is neither prevented nor distinguishable by offline cryptographic verification
  from an append merged through the intended pull-request path.
- The verifier, workflows, and anchors live in the repository they verify. Running
  the verifier from a clone assumes those security files were not weakened in the
  same rewrite; independent verification should pin or audit them separately as
  well as retaining a manifest checkpoint.
- The manifest chain hashes manifests, not receipt files. A receipt can be
  replaced by a newer valid receipt over the same manifest without changing later
  manifest hashes unless its exact bytes or digest were retained externally.
- The production anchors are fixed. There is no in-schema anchor-rotation
  protocol, so a TSA chain change requires an explicit verifier/schema migration
  that continues to preserve verification of the old chain.
- Four-digit indices cap this filename format at release 9999; the current schema
  does not define a rollover.

These limitations are why a retained external checkpoint is essential and why
the current design should not be described as cross-institution governance.
