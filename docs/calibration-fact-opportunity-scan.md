# Calibration Fact Opportunity Scan

Status: backlog note for future Arch and Microplex planning

## Purpose

After Microplex can consume Arch-backed facts for its current targets, run a
separate scan for new source facts that would improve calibration quality.

This is not part of the first migration slice. The first slice should preserve
current Microplex behavior. This scan is about what Microplex could usefully
calibrate to once Arch has a broader source registry.

## Boundary

Arch should collect and validate publisher facts. Microplex should decide
whether to activate them as targets, how to reconcile overlapping sources, and
how to age or transform them for a model year.

Do not add a fact to Arch just because a simulator variable exists. Add it when
there is a primary source aggregate with clear provenance, dimensions, and
lineage.

## Candidate Fact Families

Prioritize administrative or official aggregate sources before survey-based
facts.

- **Tax filing aggregates:** SOI return counts, income components, deductions,
  credits, liability, filing status, income bands, and state tables.
- **Wage and employment aggregates:** W-2 wage totals, wage distributions,
  employer/payroll aggregates, and official labor compensation series.
- **Program participation counts:** SNAP, SSI, Social Security, TANF, Medicaid,
  ACA marketplace, Medicare, UI, housing assistance, and child care subsidies.
- **Benefit amounts:** aggregate benefits paid, average benefit amounts, and
  program-by-geography totals.
- **Population denominators:** Census PEP, intercensal population, age/sex
  distributions, household counts, and geography crosswalk denominators.
- **National accounts controls:** BEA income, transfers, pensions, consumption,
  and other macro totals that can constrain aggregate simulated flows.
- **Distributional controls:** brackets or bins by income, age, geography,
  filing status, family type, benefit eligibility group, or program status.
- **Policy-specific statutory concepts:** facts that align directly to Axiom
  legal concepts such as adjusted gross income, child tax credit, earned income,
  taxable income, and benefit unit definitions.

## Prioritization Rubric

Score each candidate before adding it to an agent ingestion queue:

- **Primary source:** official publisher source, not FRED or another secondary
  mirror.
- **Microplex value:** likely to reduce calibration error or improve an
  important distribution.
- **Coverage:** national, state, or local coverage that maps to current
  Microplex geographies.
- **Granularity:** dimensions and bins align with model entities and known
  constraints.
- **Lineage feasibility:** source tables can be parsed with stable source
  record/cell lineage.
- **Concept clarity:** source concept can align to Arch/Axiom vocabulary without
  ambiguous transformations.
- **Freshness and revision behavior:** source releases have predictable
  vintages, corrections, and revision history.
- **Non-survey preference:** administrative or official program data ranks
  ahead of survey-derived estimates unless the survey fills a unique gap.

## Output Of A Scan

Each scan should produce a table with:

- source family;
- publisher;
- source artifact or release;
- candidate Arch facts;
- dimensions and constraints available;
- likely Microplex target use;
- current Microplex target gap addressed;
- lineage feasibility;
- priority;
- recommended source-package work item.

## Suggested First Questions

1. Which current Microplex calibration residuals are largest or most important?
2. Which existing source families already in Arch can add facts cheaply?
3. Which candidate facts improve distributions, not just national totals?
4. Which facts can be represented as direct source facts versus Microplex
   derived targets?
5. Which facts have legal/statutory concept keys that should align with Axiom?

## Near-Term Sequence

1. Finish the current-target migration for SOI.
2. Inventory current Microplex targets and residual/gap categories.
3. Score candidate new fact families using this rubric.
4. Add source-package work items for the highest-value primary sources.
5. Let Microplex decide active target adoption after Arch facts pass lineage and
   validation gates.

