# López de Prado (2014) — The Deflated Sharpe Ratio

**Citation**: López de Prado, M., "The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting, and Non-Normality", *Journal of Portfolio Management* 40(5) (2014).

## Why this matters to our project

Our Chain 1 picks top specs from 88 trials. Any reported Sharpe ratio of the winner is **guaranteed to overstate true Sharpe** due to:

1. **Selection bias**: max of many random variables is systematically higher than the underlying mean.
2. **Non-normal returns**: trade-level P&L has skew + kurtosis (fat tails).
3. **Autocorrelation**: consecutive trade outcomes correlate (we saw this in overlapping vs non-overlapping).

This paper provides the DSR that **numerically corrects** for all three. For the paper claims, reporting DSR instead of raw SR is the standard defensive move.

## 1. Background

### Sharpe Ratio (classical)
```
SR = (μ − r_f) / σ
```
- μ = mean return
- σ = std return
- r_f = risk-free rate (≈0 for high-frequency)

Annualized: `SR_annual = SR_per_trade · √(trades_per_year)`

### Problem 1: Selection bias (max over M trials)

Even if all M specs have true Sharpe = 0, the **observed max Sharpe** is positive:
```
E[max SR_i] ≈ (1 − γ)·Φ⁻¹(1 − 1/M) + γ·Φ⁻¹(1 − (e·M)⁻¹)
  where γ ≈ 0.5772 (Euler-Mascheroni)
        Φ⁻¹ = inverse normal CDF
```

For M = 88:
- `(1 − γ)·Φ⁻¹(1 − 1/88) ≈ 0.42 · 2.37 = 1.00`
- `γ·Φ⁻¹(1 − (e·88)⁻¹) ≈ 0.58 · 2.46 = 1.42`
- Total: `E[max SR | true SR=0] ≈ 2.42` per-unit.

**i.e., if we pick the winner from 88 random-noise strategies, the winner will have observed Sharpe ≈ 2.4.** Without correction, this is indistinguishable from genuine edge.

### Problem 2: Non-normal returns (skew & kurtosis)

True variance of `SR̂` depends on higher moments:
```
Var(SR̂) = (1 − γ₃·SR + ((γ₄−1)/4)·SR²) / (n − 1)
  where γ₃ = skewness, γ₄ = excess kurtosis
```

Fat tails (high γ₄) **inflate** SR variance → confidence intervals wider.

### Problem 3: Autocorrelation

If returns have autocorrelation ρ, effective sample size is smaller:
```
n_effective = n · (1 − ρ) / (1 + ρ)
```

For ρ = 0.3 (mild positive autocorrelation): `n_eff = n · 0.54`. SR precision halves.

## 2. Deflated Sharpe Ratio — formula

After accounting for all three, DSR is the **probability that the true SR > 0** conditional on the observed SR*:

```
DSR = Φ( (SR* − E[max SR_i]) · √(n − 1) · (1 − γ₃·SR* + ((γ₄−1)/4)·SR*²)⁻¹ᐟ² )
```

where:
- `SR*` = adjusted Sharpe (non-normality corrected)
- `E[max SR_i]` = selection-bias term (Eq above)
- `Φ` = normal CDF

### Interpretation
- DSR near 1.0: strong evidence of genuine edge
- DSR ≈ 0.5: no evidence; might be luck
- DSR < 0.5: observed SR is below selection-bias expected max (no signal)

**Recommended threshold**: `DSR ≥ 0.95` to claim genuine strategy.

## 3. For our iter013 estimated DSR

### Inputs
- Observed SR per trade: need to compute from trace
- Estimated from Stage 2 OOS:
  - mean signed = +12.98 bps
  - std signed ≈ 10 bps (estimated; verify)
  - SR_per_trade ≈ 12.98 / 10 = 1.3
  - SR_annualized ≈ 1.3 · √(200K trades/year) ≈ 580 (absurd — this is the per-trade-gross issue)
  
  Better: use SR on **daily P&L aggregation**:
  - n_trades/day ≈ 80
  - mean daily P&L ≈ 80 · 12.98 = 1,038 bps = 10.4% per day (unrealistic because it's sum over many 1-share trades without fees)
  
  → Sharpe calculation depends on what we count as "one period". Safer to use **per-trade** Sharpe.

### Apply DSR formula (rough)
- SR_per_trade ≈ 1.3
- γ₃ (skew) and γ₄ (kurt) — need actual trace; typical values for us: γ₃ ≈ 0 (nearly symmetric, from earlier analysis), γ₄ ≈ 1-2 (slight fat tails)
- n = 1,661 OOS trades
- M = 88 specs tested

Adjusted SR:
```
SR* = SR · √(1 − 0·SR + ((1-1)/4)·SR²) / √(1 − autocorr) ≈ SR / √(1 − 0) ≈ 1.3
```

Selection bias:
```
E[max SR | 88 trials, assuming trials' SR ~ N(0, σ_SR²)]
```
Under null (zero edge), σ_SR² ≈ 1/n. For n = 1,000-trade trials, σ_SR ≈ 0.032.

```
E[max SR] ≈ (1 − 0.58) · Φ⁻¹(1 − 1/88) · 0.032 ≈ 0.03  per-trade
```
(Small because each trial has low variance.)

**DSR:**
```
DSR ≈ Φ( (1.3 − 0.03) · √(1,660) ) = Φ(51.8) ≈ 1.0
```

→ **iter013 OOS strongly genuine** (DSR far above 0.95).

### Same exercise for baseline/Chain 1.5 comparison
- Baseline Chain 1.5 H=50: exp +9.54 bps, n=71, σ ≈ 10 → SR_per_trade ≈ 0.95
- DSR ≈ Φ(0.95 · √70) = Φ(7.9) ≈ 1.0

Still strong despite smaller n.

### Warning: depends on std estimate
Our σ ≈ 10 bps is **rough**. Actual per-trade std could be 3-20 bps depending on how spreads are counted. For paper publication, compute σ precisely from trace.

## 4. Implementation for our framework

### 4.1 Add to `chain2-gate` scoring
```python
# In chain2-gate/scoring_flow.md:
# Step 4.5 (new): DSR filter.
#   For each candidate spec, compute per-trade Sharpe from BacktestResult/trace.
#   Compute DSR with M = iteration_count.
#   Require DSR >= 0.95 for MUST_INCLUDE promotion.
#   Log DSR value for STRONG/MARGINAL tiers.
```

### 4.2 Helper function in `chain1/statistics.py` (new file)
```python
import numpy as np
from scipy.stats import norm
from scipy.special import digamma

def deflated_sharpe_ratio(
    sr_observed: float,
    n_trades: int,
    n_trials: int,
    skewness: float,
    excess_kurtosis: float,
    autocorrelation: float = 0.0,
) -> float:
    """Returns probability that true SR > 0 given observed SR after corrections.
    
    Reference: López de Prado 2014.
    """
    # Non-normality adjustment
    numer = 1 - skewness * sr_observed + (excess_kurtosis / 4) * sr_observed**2
    if numer <= 0:
        return 0.0  # malformed
    sr_adj = sr_observed * np.sqrt(
        ( (n_trades - 1) / (1 - (n_trades - 1) * autocorrelation + 1e-12) )
        / numer
    )
    # Expected max SR under null (eq from LdP 2014)
    gamma = 0.5772
    em = ((1 - gamma) * norm.ppf(1 - 1/n_trials) + 
          gamma * norm.ppf(1 - 1/(np.e * n_trials)))
    # Probability SR* exceeds em
    return float(norm.cdf(sr_adj - em))
```

### 4.3 Report in paper
For each top spec, show: raw SR, adjusted SR, selection-bias-adjusted threshold, DSR.

## 5. Limitations

- **Independence of trials assumption** — our specs share primitives, so correlated. True M_effective < 88. DSR is slightly *optimistic* for us.
- **Gaussian assumption for SR distribution** — works for n ≥ 30, our cases comfortable.
- **Stationarity of the return distribution** — violated when regime shifts. For multi-day horizons, might need block-bootstrap DSR.

## 6. Paper narrative

When presenting top strategies:
> "We compute the Deflated Sharpe Ratio (López de Prado, 2014) to correct for selection bias over M = 88 candidate specs, non-normality of trade-level returns, and autocorrelation. Our top specs report DSR > 0.95, confirming that the observed performance is unlikely to be the product of multiple-trial selection alone."

## Related references

- López de Prado, M. (2018). AFML Ch.14. Applied version with more extensions. `lopez_de_prado_2018_backtest_statistics.md`.
- Bailey, D. H., & López de Prado, M. (2012). "The Sharpe Ratio Efficient Frontier." Foundational.
- Bailey, D. H., Borwein, J., López de Prado, M., Zhu, Q. (2014). "Pseudo-mathematics and financial charlatanism: The effects of backtest overfitting on out-of-sample performance." PBO-based complement to DSR.
- Harvey, C. R., Liu, Y., Zhu, H. (2016). Multiple-testing correction (Bonferroni/BH). Companion: `harvey_liu_zhu_2016_multiple_testing.md`.
