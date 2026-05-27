# PUF Integration Strategy

## Overview

The IRS Public Use File (PUF) provides actual tax return data with much better coverage of high-income taxpayers than CPS. This document outlines integration strategies.

## Current Limitations with CPS

| Issue | Impact |
|-------|--------|
| Income top-coding | Underestimates high-earner taxes |
| Survey vs actual | Self-reported income differs from tax returns |
| Missing tax variables | Must impute AGI, deductions, credits |
| High-income undersampling | Can't calibrate 1M+ bracket |

## PUF Access Options

### Option 1: Tax-Calculator PUF (PSL)

The Policy Simulation Library maintains an extrapolated PUF:
- Based on 2011 IRS PUF with statistical aging
- ~200k weighted records
- Includes most Schedule A, B, C, D, E items
- **Access**: Requires IRS PUF license agreement

```python
# Integration approach
from taxcalc import Records
records = Records()  # Loads PUF if available
df = records.dataframe(["AGI", "c00100", "e00200", ...])
```

### Option 2: PolicyEngine Enhanced CPS

PolicyEngine statistically matches CPS with PUF characteristics:
- Open source, no license required
- Imputes tax variables onto CPS
- Calibrated to IRS SOI totals
- **Status**: Already using via `policyengine_us.Microsimulation()`

```python
from policyengine_us import Microsimulation
sim = Microsimulation()
agi = sim.calculate("adjusted_gross_income", 2024)
```

### Option 3: Synthetic PUF from IRS SOI

Build synthetic microdata matching IRS SOI tables:
- Use published IRS SOI tabulations
- Generate synthetic records via iterative proportional fitting
- Match joint distributions of income, deductions, credits
- **Advantage**: No license required, fully reproducible

## Recommended Approach

### Phase 1: Enhanced CPS (Current)
- ✅ Load CPS ASEC from Census
- ✅ Build tax units with aggregated variables
- ✅ Calibrate to IRS SOI totals
- ⚠️ Limited high-income accuracy

### Phase 2: Synthetic High-Income Tail
Add Pareto extrapolation for incomes above CPS top-code:

```python
def add_synthetic_high_income(df, pareto_alpha=1.5):
    """
    Extend income distribution with Pareto tail.

    Uses IRS SOI 1M+ totals to calibrate tail.
    """
    # IRS SOI 2021: 758,471 returns with AGI >= $1M
    # Total AGI in that bracket: $3.86T
    # Mean AGI: $5.09M

    n_synthetic = 758_471 - df[df['agi'] >= 1_000_000]['weight'].sum()

    # Generate Pareto-distributed incomes
    min_income = 1_000_000
    synthetic_incomes = pareto.rvs(pareto_alpha, scale=min_income, size=n_synthetic)

    # Create synthetic records
    ...
```

### Phase 3: Full PUF Integration
If IRS PUF license obtained:

```python
class PolicyEnginePUF:
    """Load and process IRS PUF."""

    def __init__(self, puf_path: str):
        self.raw = pd.read_csv(puf_path)
        self.records = self._build_tax_units()

    def _build_tax_units(self):
        """Map PUF variables to PolicyEngine schema."""
        return pd.DataFrame({
            'weight': self.raw['S006'] / 100,  # PUF weights are x100
            'adjusted_gross_income': self.raw['E00100'],
            'wage_income': self.raw['E00200'],
            'interest_income': self.raw['E00300'],
            'dividend_income': self.raw['E00600'],
            'business_income': self.raw['E00900'],
            'capital_gains': self.raw['E01000'],
            # ... map all relevant fields
        })
```

## Data Quality Comparison

| Metric | CPS | CPS+Calibration | Enhanced CPS | PUF |
|--------|-----|-----------------|--------------|-----|
| Total Returns | ⚠️ +24% | ✅ <1% | ✅ <1% | ✅ exact |
| Total AGI | ⚠️ +3% | ⚠️ -9% | ✅ <2% | ✅ exact |
| 1M+ Returns | ❌ -8% | ❌ +164% | ✅ ~5% | ✅ exact |
| Credit Totals | ⚠️ varies | ⚠️ varies | ✅ ~5% | ✅ exact |

## Implementation Roadmap

1. **Now**: CPS + calibration to IRS SOI (implemented)
2. **Next**: Pareto tail for high incomes
3. **Next**: Validate against JCT/CBO baselines
4. **Future**: PUF integration if licensed

## Resources

- [IRS SOI Tax Stats](https://www.irs.gov/statistics/soi-tax-stats)
- [Tax-Calculator PUF Documentation](https://pslmodels.github.io/Tax-Calculator/)
- [PolicyEngine US Data](https://github.com/PolicyEngine/policyengine-us)
- [CBO Tax Simulation](https://www.cbo.gov/publication/55413)
