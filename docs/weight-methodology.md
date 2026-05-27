# Weight Methodology

## Overview

PolicyEngine calibrates microdata weights to match administrative targets using gradient descent on squared relative error. This approach:

1. **No prior dependence**: Weights are determined purely by targets, not by arbitrary demographic calibration choices
2. **Soft constraints**: Handles conflicting or infeasible targets gracefully
3. **Hierarchical consistency**: Lower-level targets are rescaled to sum to higher levels
4. **Local area support**: Calibrates to national, state, and sub-state geographies

## Calibration Approach

### Loss Function

We minimize mean squared relative error across all targets:

```python
loss = mean(((Σᵢ wᵢ * Aⱼᵢ - targetⱼ) / (targetⱼ + 1))²)
```

Where:
- `wᵢ` = weight for record i
- `Aⱼᵢ` = indicator/value for record i contributing to target j
- `targetⱼ` = administrative target value

### Optimizer

- **Method**: Adam or L-BFGS-B on log-weights
- **Log-space**: Ensures weights stay positive, allows large adjustments
- **Initialization**: From CPS ASEC weights (affects convergence speed, not final result)

```python
log_weights = torch.tensor(np.log(initial_weights), requires_grad=True)
optimizer = torch.optim.Adam([log_weights], lr=0.3)

for epoch in range(epochs):
    weights = torch.exp(log_weights)
    estimates = weights @ indicator_matrix
    loss = ((estimates - targets) / (targets + 1)).pow(2).mean()
    loss.backward()
    optimizer.step()
```

### Why Not Entropy Calibration?

Entropy calibration (KL divergence minimization) treats original weights as a meaningful prior. But:

1. ASEC weights target demographics (age × sex × race × state) - arbitrary for tax policy
2. We calibrate to tax-relevant targets directly
3. The "prior" adds no value if we have comprehensive tax targets

Gradient descent on squared error is simpler and more direct.

## Target Hierarchy and Consistency

### Geographic Levels

| Level | Source | Example Targets |
|-------|--------|-----------------|
| National | IRS SOI Publication 1304 | Returns by AGI bracket, total AGI |
| State | IRS SOI Historic Table 2 | State × AGI bracket returns |
| County | IRS SOI County Data | County total returns, AGI |
| ZIP | IRS SOI ZIP Code Data | ZIP total returns, AGI |

### Hierarchical Rescaling

Lower-level targets must sum to higher-level targets. If they don't (due to rounding, sampling), we rescale:

```python
def rescale_for_consistency(national, state, district):
    """Ensure hierarchical consistency: districts → states → national."""

    for variable in variables:
        for bracket in agi_brackets:
            # Get national total
            us_total = national.query(f"variable == '{variable}' and bracket == '{bracket}'")['value'].iloc[0]

            # Get state sum
            state_mask = (state['variable'] == variable) & (state['bracket'] == bracket)
            state_sum = state.loc[state_mask, 'value'].sum()

            # Rescale states if needed
            if not np.isclose(state_sum, us_total, rtol=1e-3):
                state.loc[state_mask, 'value'] *= us_total / state_sum

            # Same for districts within each state
            for fips in state['state_fips'].unique():
                s_total = state.query(f"state_fips == '{fips}' and variable == '{variable}'")['value'].iloc[0]
                d_mask = (district['state_fips'] == fips) & (district['variable'] == variable)
                d_sum = district.loc[d_mask, 'value'].sum()

                if not np.isclose(d_sum, s_total, rtol=1e-3):
                    district.loc[d_mask, 'value'] *= s_total / d_sum

    return national, state, district
```

### Target Grouping

Targets are grouped by geographic level and variable type. Each group contributes equally to total loss, preventing national targets from dominating:

```python
# Groups ordered: National → State → County/ZIP
# Within each level, group by variable type
groups = [
    ("national", "returns_by_agi"),      # 1 target per bracket
    ("national", "agi_by_bracket"),      # 1 target per bracket
    ("state", "returns_by_agi"),         # 51 × brackets targets
    ("state", "agi_by_bracket"),         # 51 × brackets targets
    ("county", "total_returns"),         # ~3000 targets
    ...
]

# Normalize within groups so each group has equal weight
for group in groups:
    group_loss = mean(group_squared_errors)
    total_loss += group_loss / n_groups
```

## Local Area Calibration

### Challenge: CPS Geographic Granularity

CPS provides:
- **State**: Explicit in data
- **PUMA**: Public Use Microdata Area (~100k people)
- **Metro status**: Metropolitan vs non-metropolitan

CPS does NOT provide:
- County (except for large counties that are their own PUMA)
- ZIP code
- Congressional district

### Solution: Geographic Assignment + Reweighting

**Step 1: Assign sub-state geography**

Use PUMA-to-geography crosswalks:
- PUMA → County (Census MABLE/Geocorr)
- PUMA → Congressional District (Census relationship files)
- PUMA → ZIP (probabilistic based on population overlap)

```python
def assign_county(puma, state_fips):
    """Assign county based on PUMA-county overlap probabilities."""
    overlaps = puma_county_crosswalk.query(f"puma == '{puma}' and state == '{state_fips}'")
    # Probabilistically assign based on population share
    return np.random.choice(overlaps['county'], p=overlaps['pop_share'])
```

**Step 2: Calibrate with geographic targets**

Include county/ZIP targets in the calibration:

```python
targets = [
    # National targets
    Target("US", "returns_50k_to_75k", 19_494_660),
    # State targets
    Target("CA", "returns_50k_to_75k", 2_100_000),
    Target("TX", "returns_50k_to_75k", 1_800_000),
    ...
    # County targets
    Target("06037", "total_returns", 3_200_000),  # LA County
    Target("06073", "total_returns", 1_100_000),  # San Diego County
    ...
]
```

**Step 3: Validate geographic distributions**

After calibration, verify:
- State totals match IRS SOI state data
- County totals match IRS SOI county data
- Geographic distributions are plausible

### Alternative: Geo-Stacking

For very granular geography (ZIP codes), create multiple copies of each household assigned to different geographies:

```python
def geo_stack(household, target_geographies):
    """Create copies of household for each possible geography."""
    stacked = []
    for geo in target_geographies:
        if household_could_be_in(household, geo):
            copy = household.copy()
            copy['geography'] = geo
            copy['weight'] = household['weight'] / len(target_geographies)
            stacked.append(copy)
    return stacked
```

The calibration then adjusts weights to match targets at each geography level.

## Target Sources

### IRS Statistics of Income

| Source | Geographic Level | Variables | Years |
|--------|------------------|-----------|-------|
| Publication 1304 | National | Full income/tax detail | 1990-2023 |
| Historic Table 2 | State × AGI bracket | Returns, AGI, tax | 1996-2022 |
| County Data | County | Returns, exemptions, AGI | 1989-2022 |
| ZIP Code Data | ZIP | Returns, exemptions, AGI | 1998-2022 |
| EITC Statistics | State | EITC recipients, amounts | 1999-2022 |

### Census / ACS

| Source | Geographic Level | Variables |
|--------|------------------|-----------|
| ACS 1-year | State, large counties | Population, income |
| ACS 5-year | All counties, tracts | Population, income |
| Decennial Census | Block | Population counts |

### Program Administrative Data

| Source | Geographic Level | Variables |
|--------|------------------|-----------|
| SNAP QC | State | Households, benefits |
| SSA OASDI | State, county | Beneficiaries, payments |
| Medicaid | State | Enrollment |

## Implementation

### File Structure

```
calibration/
├── __init__.py
├── targets/
│   ├── irs_soi.py          # Load IRS SOI targets
│   ├── census_acs.py       # Load ACS targets
│   └── consistency.py      # Rescale for hierarchical consistency
├── optimizer/
│   ├── gradient.py         # Gradient descent calibration
│   └── loss.py             # Loss function and grouping
├── geography/
│   ├── crosswalks.py       # PUMA → County/ZIP mappings
│   └── assignment.py       # Assign sub-state geography
└── validation/
    └── diagnostics.py      # Post-calibration validation
```

### Usage

```python
from calibration import calibrate_microdata

# Load microdata with geographic assignments
microdata = load_cps_with_geography(year=2024)

# Load and validate targets
targets = load_all_targets(
    sources=["irs_soi", "census_acs"],
    geographies=["national", "state", "county"],
    year=2024
)
targets = rescale_for_consistency(targets)

# Calibrate
calibrated = calibrate_microdata(
    microdata=microdata,
    targets=targets,
    epochs=500,
    lr=0.3,
)

# Validate
report = validate_calibration(calibrated, targets)
```

## CPS ASEC Original Weights (Reference)

While we don't use ASEC weights as a prior, understanding their construction is useful:

### ASEC Population Controls (~188 constraints)

| Control Set | Categories | Dimension |
|-------------|------------|-----------|
| State totals | 51 | Civilian noninstitutional pop 16+ by state |
| Hispanic age-sex | 14 + 5 | Hispanic (14 cells) + non-Hispanic (5 cells) |
| Race age-sex | 66 + 42 + 10 | White (66) + Black (42) + Other (10) age-sex cells |

These demographic controls are orthogonal to our tax-relevant targets. ASEC weights serve only as initialization for the optimizer (faster convergence), not as a constraint.

## Variable Mapping Reference

### Tax Variables (Primary Calibration)

| Variable | Source | Used For |
|----------|--------|----------|
| `adjusted_gross_income` | CPS income sum | AGI bracket assignment |
| `filing_status` | Derived from marital status | Filing unit construction |
| `n_dependents` | CPS family structure | Credit eligibility |
| `wage_income` | `WSAL_VAL` | Income components |
| `self_employment_income` | `SEMP_VAL` | SE tax, QBI |
| `interest_income` | `INT_VAL` | Investment income |
| `dividend_income` | `DIV_VAL` | Investment income |
| `social_security_income` | `SS_VAL` | Taxable SS calculation |

### Geographic Variables

| Variable | Source | Used For |
|----------|--------|----------|
| `state_fips` | `GESTFIPS` | State-level calibration |
| `puma` | `PUMA` | Sub-state assignment |
| `county_fips` | Derived from PUMA | County calibration |
| `metro_status` | `GTMETSTA` | Urban/rural distinction |

### Weight Variables

| Variable | Description |
|----------|-------------|
| `weight` | Final calibrated weight (use for all analysis) |
| `original_weight` | ASEC weight (initialization only) |
| `weight_adjustment` | Ratio: `weight / original_weight` |

## Validation Metrics

After calibration, we report:

| Metric | Target | Description |
|--------|--------|-------------|
| Max relative error | < 5% | Largest deviation from any target |
| Mean relative error | < 1% | Average deviation across targets |
| Weight range | 0.1x - 10x | Bounds on weight adjustments |
| Coverage | > 90% | Fraction of IRS filers represented |
| Geographic balance | Per state | State weight sums match IRS |

## Known Limitations

1. **Non-filers**: CPS includes non-filers; IRS only has filers. Coverage gap ~10%.
2. **Income underreporting**: CPS self-reported income < IRS administrative income.
3. **High-income undersampling**: CPS top-codes income; few $1M+ observations.
4. **Sub-state geography**: PUMA → County/ZIP assignment is probabilistic.
5. **Temporal mismatch**: CPS March supplement vs. tax year timing.
