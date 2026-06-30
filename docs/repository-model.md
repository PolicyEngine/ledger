# Ledger Repository Model

Ledger is global at the schema layer. Jurisdiction packages are modular source
packages that build source-backed Ledger records for one jurisdiction or source
family.

## Names

```text
GitHub repositories after the rename:
  PolicyEngine/ledger
  PolicyEngine/ledger-us
  PolicyEngine/ledger-uk

Python distributions:
  policyengine-ledger
  policyengine-ledger-us
  policyengine-ledger-uk

Python imports:
  policyengine_ledger
  policyengine_ledger_us
  policyengine_ledger_uk
```

The `policyengine-` prefix belongs in published distribution names, where
generic names collide. Public imports use the explicit `policyengine_ledger`
namespace to avoid colliding with unrelated `ledger` packages.

## Ownership

`ledger` owns the stable contract:

- source artifact metadata
- parsed source cells
- source record specs
- aggregate facts
- aggregate constraints
- source-to-canonical concept alignments
- stable keys
- validation
- relational DB schema
- fixture/build harness

Jurisdiction packages own source implementations:

- source manifests
- artifact retrieval specs
- source-specific parsers
- selector specs
- source-record specs
- fixture builds for that jurisdiction

They must emit the shared Ledger schema. They should not define a different fact,
constraint, lineage, validation, or DB model.

## Current State

The current in-repo US loaders are a prototype so the core contract can move
quickly while SOI fixtures exercise the schema. Once the contract stabilizes,
the US loaders should move to `policyengine-ledger-us`, with the core repository
retaining only a small test fixture and the shared harness.
