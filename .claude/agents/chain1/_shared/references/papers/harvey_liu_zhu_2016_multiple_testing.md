# Harvey, Liu & Zhu (2016) — "…and the Cross-Section of Expected Returns"

**Citation**: Harvey, C. R., Liu, Y., & Zhu, H., "…and the Cross-Section of Expected Returns", *Review of Financial Studies* 29(1), 5–68 (2016).

## Why this matters to our project

We tested **88 SignalSpec candidates** and report that our best spec has OOS expectancy +12.98 bps. The paper's key message: with **multiple testing**, the naïve t-statistic threshold of 2.0 (α=0.05) is **woefully inadequate**. They argue that the equity risk premium literature has likely inflated the evidence for hundreds of "factors" precisely because of uncontrolled multiple testing.

For us: **88 specs → FDR ≈ 0.05 correction requires t-stat much higher than 2**. Without this correction, our top spec's OOS performance could be a statistical artifact.

## 1. The multiple-testing problem (setup)

Given M independent hypothesis tests at significance α:
```
P(at least one false positive) = 1 − (1 − α)^M
```

For M = 88, α = 0.05:
```
P(false positive) = 1 − 0.95^88 ≈ 0.989 ≈ 99%
```

→ Almost certain to find at least one "significant" spec purely by chance.

## 2. Three multiple-testing procedures

### 2.1 Bonferroni (strictest, conservative)
```
α_corrected = α / M
t_threshold = Z^{-1}(1 − α/(2M))
```

For M=88, α=0.05: `α_corrected = 0.000568`, `t_threshold ≈ 3.26`.

**Pro**: Always valid. **Con**: Over-corrects when tests are correlated.

### 2.2 Holm-Bonferroni (step-down)
Sort M p-values ascending. Reject H_i if `p_i ≤ α / (M − i + 1)` for the first i where this fails, else stop.

More power than Bonferroni, still strong FWER control.

### 2.3 Benjamini-Hochberg (FDR; most useful)
Sort M p-values ascending. Find largest k such that:
```
p_(k) ≤ (k/M) · q
```
Reject H_1, ..., H_k.

**Controls false discovery rate at level q** (default q=0.05).

**For our 88 specs**: If top spec p-value is 0.003, FDR threshold is `(1/88) × 0.05 = 0.00057` — reject (genuine). If p=0.01, reject line is `(2/88) × 0.05 = 0.00114` — borderline. More lenient than Bonferroni.

## 3. Harvey-Liu-Zhu's empirical finding

They survey 316 factor studies. Their recommendation:
- **For new factors**: t-stat threshold **≥ 3.0** to claim genuine
- **For existing factors**: t-stat **≥ 2.0** acceptable if already published

Implicit message: **published expectations of 5% α bounds are overly optimistic.**

## 4. For our framework

### Current state
- `chain2-gate` scoring function does not apply multiple-testing correction
- Top-N selection is raw (expectancy × fee_absorption × density)
- OOS reproduction is counted as validation but not formally tested

### Recommended additions
Add to `chain2-gate`:

```python
def bh_fdr_threshold(p_values: np.ndarray, q: float = 0.05) -> float:
    """Benjamini-Hochberg FDR threshold at level q."""
    sorted_p = np.sort(p_values)
    m = len(sorted_p)
    bh_line = np.arange(1, m+1) / m * q
    passed = sorted_p <= bh_line
    if not passed.any():
        return 0.0
    # Largest k where p_k passes
    k = np.where(passed)[0].max()
    return float(sorted_p[k])
```

Then:
```python
# In chain2-gate, per spec compute one-sided p-value of WR > 0.5:
from scipy.stats import binomtest
p_i = binomtest(n_wins, n_trades, p=0.5, alternative='greater').pvalue
# Accept as "MUST_INCLUDE" only if p_i ≤ bh_fdr_threshold([all 88 p-values], q=0.05)
```

## 5. Estimated impact on our claims

Rough calculation for iter013_ask_conc_low_vol_h50 OOS:
- n_trades = 1,661
- WR = 0.948 (hypothesized vs. null 0.5)
- Test stat (normal approx): `z = (0.948 − 0.5) / √(0.5·0.5/1661) = 36.5`
- One-sided p ≈ 0 (way below any threshold)

For Trial 0 (baseline) Chain 1.5 H=50 exp = +9.54 bps:
- Treating mean as test statistic: `t = exp / (σ_exp / √N)` — requires σ per trade
- Assumed σ ≈ 10 bps, N=71: `t = 9.54/(10/√71) = 8.04` → very strong.

**Our top specs likely pass FDR-corrected threshold.** But need to **formally compute** for paper defensibility.

## 6. Related work

- Bonferroni, C. E. (1935). Original correction.
- Benjamini, Y., & Hochberg, Y. (1995). FDR procedure — see companion `benjamini_hochberg_1995_fdr.md`.
- Romano, J. P., & Wolf, M. (2005). "Stepwise Multiple Testing as Formalized Data Snooping." Bootstrap-based correction for highly correlated tests (our specs are correlated → this might be more accurate than BH).
- López de Prado (2018). Related: Deflated Sharpe Ratio as multiple-testing correction for Sharpe specifically.

## Known caveats

- All above assume p-values are from valid hypothesis tests. Our "expectancy" is not a formal t-test; need to derive p-value from trade-level distribution.
- Correlations between specs (shared primitives, iterative design) → M_effective < 88. Harvey-Liu-Zhu's 316 factors are also correlated. They suggest using block bootstrap.
- FDR q=0.05 is itself arbitrary. Paper contexts vary from q=0.01 (very strict) to q=0.10 (exploratory).
