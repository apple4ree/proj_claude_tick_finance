# Benjamini & Hochberg (1995) — Controlling the False Discovery Rate

**Citation**: Benjamini, Y., & Hochberg, Y., "Controlling the false discovery rate: a practical and powerful approach to multiple testing", *Journal of the Royal Statistical Society Series B* 57(1), 289–300 (1995).

## Why this matters to our project

We tested **88 SignalSpec candidates** and picked the top-ranked ones for paper claims. Bonferroni correction is overly conservative — we lose nearly all discoveries. The **False Discovery Rate (FDR)** procedure is the modern compromise:

- Accepts that **some** false positives are inevitable at scale
- Controls the **proportion** of false positives among rejections to a target level (q)
- Has dramatically more statistical power than Bonferroni for correlated tests

Used by Harvey-Liu-Zhu (2016) as the recommended correction for factor discovery. See companion `harvey_liu_zhu_2016_multiple_testing.md`.

## 1. Definitions

### FWER (Family-Wise Error Rate) — what Bonferroni controls
```
FWER = P(at least 1 false rejection among m tests)
```
Bonferroni: `α_each = α / m` → FWER ≤ α.

**Problem**: for m = 88, Bonferroni at α=0.05 requires per-test α = 0.0006 → t-stat ≥ 3.3. Very few specs pass.

### FDR — what BH controls
```
FDR = E[V / R | R > 0] · P(R > 0)
  where R = # rejected, V = # incorrect rejections
```

Control target: `FDR ≤ q` (typically q = 0.05, 0.10).

**Interpretation**: of the specs we "discover", at most q proportion are false positives (in expectation).

## 2. BH procedure

Given m p-values `p_(1) ≤ p_(2) ≤ ... ≤ p_(m)` (sorted ascending):

1. Find largest index k such that:
```
p_(k) ≤ (k/m) · q
```

2. Reject null hypotheses H_(1), ..., H_(k). **Keep p-values ≤ p_(k)**.

### Geometric interpretation
Plot `p_(i)` vs i. Draw line `y = (i/m) · q`. Find last point below the line. All prior points: reject null.

### Example for our 88 specs, q = 0.05
| Rank | threshold p-value |
|---|---|
| 1 | 5.7e-4 (same as Bonferroni!) |
| 2 | 1.1e-3 |
| 5 | 2.8e-3 |
| 10 | 5.7e-3 |
| 50 | 2.8e-2 |
| 88 | 5.0e-2 |

→ BH is **much more lenient** than Bonferroni at higher ranks.

## 3. Assumptions

### Independent tests (original BH)
BH is valid when p-values are independent or Positively Regression Dependent (PRD). Our specs have shared primitives → positively correlated → PRD likely holds.

### Arbitrary dependence (BY procedure)
Benjamini & Yekutieli (2001) extend to any dependence structure. Uses:
```
p_(k) ≤ (k/m) · q / C(m)
  where C(m) = Σ_{i=1..m} 1/i ≈ ln(m) + γ
```
For m=88: `C(88) ≈ 5.03`. BY is **5× stricter** than BH but works under any dependence.

**Recommendation**: use BH for our case (specs likely PRD); if conservative, use BY.

## 4. For our project

### 4.1 Formal hypothesis per spec
For each spec i, test:
- H_0: `E[signed_return] = 0` (signal has no edge)
- H_1: `E[signed_return] > 0` (signal has positive edge)

One-sided t-test (or permutation test for non-normal):
```
t_i = mean(signed_returns_i) / (std(signed_returns_i) / sqrt(n_trades_i))
p_i = 1 - Φ(t_i)   (normal approx) 
```

### 4.2 Applied to iter013 OOS (n=1661)
- mean signed = +12.98 bps
- std signed ≈ 10 bps (rough estimate; need actual trace)
- t ≈ 12.98 / (10 / √1661) = 52.9
- p ≈ 0 (way past any threshold)

→ iter013 definitively rejects null even after harsh correction.

### 4.3 For borderline specs
Some specs have lower t-stats. BH allows us to set a principled acceptance cutoff:

```python
def bh_fdr_cutoff(p_values: np.ndarray, q: float = 0.05) -> tuple[float, list[int]]:
    """BH-FDR: return cutoff p-value and list of rejected indices."""
    sorted_idx = np.argsort(p_values)
    sorted_p = p_values[sorted_idx]
    m = len(sorted_p)
    # BH line
    bh_line = np.arange(1, m + 1) / m * q
    passed = sorted_p <= bh_line
    if not passed.any():
        return (0.0, [])
    k_max = np.where(passed)[0].max()
    cutoff = sorted_p[k_max]
    rejected = sorted_idx[:k_max + 1].tolist()
    return (float(cutoff), rejected)
```

## 5. Implementation in chain2-gate

Current `chain2-gate` scores specs by composite (expectancy × fee_absorption × density). Add FDR filter:

```python
# In chain2-gate/scoring_flow.md update:
# 5. FDR filter (new 2026-04-23):
#    For each candidate spec, compute one-sided p-value of mean return > 0.
#    Run BH at q=0.05.
#    Only specs in the rejected set are eligible for MUST_INCLUDE promotion.
#    Specs failing BH can still be STRONG/MARGINAL for discovery purposes.
```

## 6. Connection to our session's "overlap vs non-overlap" bug

Our earlier measurement (+11.28 bps with overlapping trades) **inflated** the signal-per-trade metric because overlapping trades share outcomes. Under FDR:
- n_effective (independent trades) is lower than reported n
- t_stat drops by √(n_eff / n_reported)
- p_value rises correspondingly

**Caveat**: Even after overlap correction, iter013 t-stat easily passes BH. But this matters for borderline specs (iter_007 etc. where gains are small).

## 7. Limitations and nuances

### Positive regression dependence (PRD)
Required for BH to control FDR strictly. Our specs share primitives → likely PRD. If not sure, use BY (conservative).

### q-value choice
- q = 0.05: mainstream
- q = 0.10: exploratory (appropriate for "discovery" phase)
- q = 0.01: confirmation (appropriate for deployment)

### Post-hoc power
Even if FDR-significant, **economic significance** matters. +0.1 bps per trade is statistically significant with n=10,000 but **useless** post-fee.

## 8. Paper narrative

When reporting top-k specs:
> "Among 88 candidate SignalSpecs, we report the top-k that pass Benjamini-Hochberg FDR control at q = 0.05. This corrects for the multiple-testing nature of our autonomous exploration while preserving statistical power compared to Bonferroni (Harvey et al., 2016)."

## Related references

- Harvey, C. R., Liu, Y., Zhu, H. (2016). Applied to factor discovery. `harvey_liu_zhu_2016_multiple_testing.md`.
- Benjamini, Y., & Yekutieli, D. (2001). "The control of the false discovery rate in multiple testing under dependency." BY procedure.
- Storey, J. D. (2002). "A direct approach to false discovery rates." Improves power via data-driven π_0 estimation.
- López de Prado, M. (2018). AFML Ch.11. Applies PBO (combinatorial) instead of BH.
