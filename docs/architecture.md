# Ledger Data Architecture

## Overview

Ledger is PolicyEngine's source-data foundation for social simulation. It captures
source publications, preserves provenance, and represents published values as
structured, queryable facts. Populace consumes Ledger facts to produce final
calibrated simulation inputs.

This document describes the source-publication pipeline from government
statistics releases to source-backed facts and target profiles. Ledger is global at the schema,
validation, and build-harness layer. Jurisdiction source packages such as
`ledger-us` and `ledger-uk` emit records into that shared contract.

## Repository Boundaries

| Layer | Owns | Does not own |
|-------|------|--------------|
| Ledger | Source artifacts, provenance, aggregate facts, constraints, target profiles | Raw microdata storage, source reconciliation, aging, imputation, active target selection |
| Populace Targets | Source selection, reconciliation, aging, imputation, active target sets | Source artifact storage and provenance |
| Populace | Entity model, weights, calibration interfaces, calibrated output | Source ETL and source provenance |
| Jurisdiction source packages | Source-specific parsers and specs that emit Ledger records | Forked fact or constraint schemas |
| Jurisdiction simulation packages | Model-specific adapters, variable mappings, target recipes | Source facts |
| PolicyEngine | Policy-facing workflows and analysis tools | Source ETL or calibrated dataset generation |

## Storage Layers

### Object Storage

Source files are immutable and versioned.

```text
sources/
  irs/soi/2023/table_1_2.xlsx          # IRS SOI individual returns
  census/acs/2023/table_b01001.csv     # ACS published table
  bls/cpi/2024/monthly.csv             # CPI monthly series
  usda/snap/2023/qc_data.xlsx          # SNAP QC data
```

### Supabase Schemas

| Schema | Purpose | Example Tables |
|--------|---------|----------------|
| `ledger` | Source metadata and lineage | sources, files, content, fetch_log |
| `indices` | Source time series | series, values (CPI, wage growth) |
| `targets` | Target inputs | strata, constraints, targets |
| `populace` | Final calibrated data | households, persons, tax_units |

## Python Namespaces

New code should use the `policyengine_ledger` namespace:

```python
from policyengine_ledger.sources import SourceFile, SourceReference, query_sources
from policyengine_ledger.facts import SourceFact
from policyengine_ledger.targets import Target, query_targets
from policyengine_ledger.normalization import convert_units
```

The `db` package contains the current SQLModel persistence and loader
implementation behind the public `policyengine_ledger` namespace.

Jurisdiction source packages should use short import namespaces and published
distribution names with a PolicyEngine prefix:

```text
repo: PolicyEngine/ledger-us
distribution: policyengine-ledger-us
import: policyengine_ledger_us
```

They should depend on `policyengine-ledger` and emit shared `ledger` objects
rather than redefining source rows/cells, source-row values, aggregate facts,
aggregate constraints, stable keys, or DB tables.

## Data Flow

```text
source publications
(files, manifests,
 parsed-as-published cells)
      |
      v
policyengine_ledger.sources
(source lineage references)
      |
      v
policyengine_ledger.facts
(structured source claims)
      |
      |
      v
policyengine_ledger.normalization
(units, scales, IDs, source-published arithmetic)
      |
      v
policyengine_ledger.aggregate_facts
(published aggregate facts)
      |
      v
policyengine_ledger.target_profiles
      |
      v
        Populace Targets
   (selected, reconciled,
    aged active target sets)
                  |
                  v
             populace.*
          (final calibrated
              datasets)
```

## Source Facts And Populace Targets

Source ETL should separate Ledger aggregate facts from Populace target composition:

1. Load or parse source publications into source lineage and published cells.
2. Materialize source-backed facts in Ledger.
3. Apply representation-only normalization such as unit scale conversion or
   source-published total/share arithmetic.
4. Keep the fact queryable with source and derivation metadata.
5. Let Populace select, reconcile, age, and activate calibration target sets.

Ledger source facts can align source-published concepts to canonical vocabulary
terms. When a legal concept is available from Axiom, Ledger should use the Axiom
term as the canonical concept key and keep the publisher's column/series concept
as `source_concept`. For example, SOI adjusted gross income is represented as:

```text
canonical concept: us:statutes/26/62#adjusted_gross_income
source concept:    irs_soi.adjusted_gross_income
relation:          exact
authority:         ledger-us
```

This alignment is evidence-bearing metadata, not a Ledger dependency on Axiom
runtime behavior. Nonlegal empirical inputs can use shared Ledger/common concepts
and later align to Axiom or Populace where appropriate.

The `policyengine_ledger.normalization` package owns low-assumption representation helpers:

```python
from policyengine_ledger.facts import SourceFact
from policyengine_ledger.normalization import convert_units

snap_households = SourceFact(
    name="snap_households",
    value=22_323,
    period=2023,
    unit="thousands",
    source="usda_snap",
    jurisdiction="us",
)

normalized_fact = convert_units(snap_households, 1000, "count")
```

Projection facts from official sources such as CBO, OBR, and ONS can be loaded
as source facts directly. PolicyEngine-owned inflation, aging, projection, or
cross-source reconciliation assumptions belong in Populace Targets, not Ledger.

### Downstream Adapter Aliases

Ledger variables should describe source-backed facts, not downstream simulator
variables. If a Populace or PolicyEngine target cell names the same empirical
quantity differently, the alias belongs in the downstream adapter.

For example, IRS SOI publishes nonnegative income tax liability aggregates.
Ledger should preserve that as an SOI liability fact, while a Populace adapter
may use it to satisfy a model target named `income_tax_positive`. Ledger should
not create a duplicate source fact solely to match the model variable name.

This rule also applies in reverse: if a Populace target cell is really a
survey input, imputed model feature, or source-selection decision rather than a
publisher aggregate, the cell should stay out of Ledger until a primary source
fact and its provenance are identified.

## Downstream Target Composition

### 1. Target Inputs (from `targets.*` schema)

Target inputs define source-backed aggregates that Populace may use:

```sql
-- targets.strata: Population subgroups
INSERT INTO targets.strata (name, jurisdiction, constraints)
VALUES ('CA adults 18-64', 'us', '[{"variable": "age", "operator": ">=", "value": "18"}, ...]');

-- targets.targets: Source-backed aggregate values
INSERT INTO targets.targets (stratum_id, variable, value, period)
VALUES (1, 'eitc_recipients', 2500000, 2023);
```

### 2. Variable Mapping

Ledger fact concepts are source-linked or canonical vocabulary IDs. They should not
depend on a simulator implementation. Populace jurisdiction packages map those
target IDs to model variables and entities.

### 3. Target Composition

Populace Targets owns composition from source-backed inputs to active target
sets:

```python
target_set = populace.targets.compose(
    inputs=ledger_targets,
    target_year=2024,
    reconciliation="scale_states_to_national",
    aging="apply_published_growth_factor",
)
```

Every source choice, reconciliation rule, aging method, and activation rule is
declared and versioned in Populace, not Ledger.

### 4. Hierarchical Constraint Building

Since all weights are at the household level, person-level targets must be
aggregated:

```python
# What we want: count of people aged 18-64 in California
# What we compute: for each household, count matching persons

build_hierarchical_constraint_matrix(
    hh_df=households,      # 18,825 rows
    person_df=persons,     # 48,292 rows
    targets=targets,       # Populace active target set
)

# Returns: Constraint objects with indicators at household level
# indicator[i] = count of matching persons in household i
```

The key insight: since all persons in a household share the household weight:

```text
sum over HH(hh_weight * count_matching_in_hh) = total_matching_persons
```

### 5. IPF Calibration

Iterative Proportional Fitting adjusts household weights to match all targets:

```python
for iteration in range(max_iter):
    for constraint in constraints:
        current = sum(hh_weight * constraint.indicator)
        ratio = constraint.target_value / current
        hh_weight *= clip(ratio, 0.9, 1.1)

    hh_weight = clip(hh_weight, min_weight, max_weight)
```

### 6. Output (`populace.*` schema)

```sql
-- populace.households: Calibrated household weights
SELECT household_id, state_fips, weight, ...
FROM populace.households;
-- 18,825 rows

-- populace.persons: Linked to households
SELECT person_id, household_id, age, employment_income, ...
FROM populace.persons;
-- 48,292 rows
```

## Entity Hierarchy

```text
Household (weight lives here)
├── Tax Unit 1
│   ├── Person A (head)
│   └── Person B (spouse)
└── Tax Unit 2
    └── Person C (dependent filing separately)
```

- Weights are always at household level.
- Person-level targets aggregate count/sum per household.
- Tax-unit-level targets aggregate count/sum per household.
- Household-level targets use a direct indicator.

## Schema Details

### ledger.* (Source Lineage)

```sql
ledger.sources        -- institution, dataset, url, update_frequency
ledger.files          -- r2_key, checksum, source_id, fetched_at
ledger.content        -- parsed-as-published text/tables
ledger.fetch_log      -- change detection, version history
```

### indices.* (Source Time Series)

```sql
indices.series      -- series_id, name, source, frequency
indices.values      -- series_id, date, value
```

Populace recipes can reference these source series when they choose an
indexing rule:

```yaml
indexing_rule eitc_inflation:
  series: indices/bls_chained_cpi_u
  base_year: 2015
  rounding: 10
```

### targets.* (Target Inputs)

```sql
targets.strata           -- population subgroups with constraints
targets.constraints      -- variable, operator, value per stratum
targets.targets          -- stratum_id, variable, value, period, source
```

Targets in Ledger are source-backed inputs. Active, aged, reconciled calibration
target sets belong to Populace Targets.

### populace.* (Final Output)

```sql
populace.households     -- calibrated household records with weights
populace.persons        -- person records linked to households
populace.tax_units      -- tax unit records (future)
```
