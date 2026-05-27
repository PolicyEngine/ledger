# Arch Repository Model

Arch is global at the schema layer. Jurisdiction packages are modular source
packages that build source-backed Arch records for one jurisdiction or source
family.

## Names

```text
GitHub repositories:
  PolicyEngine/arch-data
  PolicyEngine/arch-us
  PolicyEngine/arch-uk

Python distributions:
  policyengine-arch-data
  policyengine-arch-us
  policyengine-arch-uk

Python imports:
  arch
  arch_us
  arch_uk
```

The `policyengine-` prefix belongs in published distribution names, where
generic names collide. Repository names and import namespaces should stay short.

## Ownership

`arch` owns the stable contract:

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

They must emit the shared Arch schema. They should not define a different fact,
constraint, lineage, validation, or DB model.

## Current State

`arch.jurisdictions.us` is an in-repo prototype so the core contract can move
quickly while SOI fixtures exercise the schema. Once the contract stabilizes,
the US loaders should move to `arch-us`, with `arch` retaining only a small
test fixture and the shared harness.
