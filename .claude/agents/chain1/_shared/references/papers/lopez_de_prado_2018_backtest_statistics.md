# López de Prado (2018) — Advances in Financial ML, Ch.11-14: Backtest Statistics

**Citation**: López de Prado, M., *Advances in Financial Machine Learning*, Wiley (2018). Esp. Ch.11 (The Dangers of Backtesting), Ch.14 (Backtest Statistics), Ch.16 (Machine Learning Asset Allocation).

## Why this matters to our project

We ran **88 SignalSpecs across 22 iterations and picked the top-10**. A naive Sharpe or expectancy of the winner is **guaranteed** to be inflated by selection bias. Before any claim like "iter013 achieves OOS +12.98 bps", we must correct for multiple-trial selection.

This reference gives three defensive tools:

1. **Deflated Sharpe Ratio (DSR)** — adjusts Sharpe down for trial count, autocorrelation, non-normality.
2. **Probability of Backtest Overfitting (PBO)** — combinatorial procedure to estimate how likely our in-sample winner is actually below-median out-of-sample.
3. **Combinatorial Purged Cross-Validation (CPCV)** — robust OOS evaluation preventing temporal leakage.

## 1. Deflated Sharpe Ratio (DSR)

### Setup
Suppose we compute Sharpe ratio `SR` from a backtest with `N` trades, trial count `M` (number of specs tested), autocorrelation `ρ`, skewness `γ₃`, excess kurtosis `γ₄`.

### Adjusted Sharpe (SR*)
Non-normality adjustment first:
```
SR* = SR · √( (1 − γ₃·SR + ((γ₄−1)/4)·SR²) / (1 − (N−1)·ρ) )
```

### DSR (subtracts selection-bias "luck")
```
DSR = Φ( (SR* − E[max_{i=1..M} SR_i]) · √(N−1) / √(1 − γ₃·SR + ((γ₄−1)/4)·SR²) )
```

where `E[max SR_i]` for M i.i.d. trials is approximated by:
```
E[max SR] = (1−γ)·Z^{-1}(1 − 1/M) + γ·Z^{-1}(1 − (e·M)^{-1})
    γ ≈ 0.5772  (Euler-Mascheroni constant)
    Z^{-1} = inverse standard-normal CDF
```

**Interpretation**: DSR is a probability in [0,1]. Values near 1 mean the signal is likely genuine; values below 0.95 are suspect.

### For our project
- N ≈ 1,661 OOS trades (iter013, Stage 2)
- M = 88 specs tried
- Sharpe-equivalent: exp 12.98 / σ (need to compute σ from trace)
- **Should compute DSR for top-5 specs** — claim in paper only those with DSR ≥ 0.95.

## 2. Probability of Backtest Overfitting (PBO)

### Procedure (CSCV — Combinatorially Symmetric CV)
1. Partition time series into S disjoint chunks (default S=16)
2. All subsets of size S/2 form "training" splits; complement is "test"
3. For each split:
   - Compute performance (e.g., Sharpe) of each of N strategies on train
   - Record the rank of "best on train" strategy on test
4. PBO = fraction of splits where best-on-train has below-median test rank.

### Interpretation
- PBO ≤ 0.05 → backtest selection is trustworthy
- PBO ≈ 0.50 → winner-on-train is pure coincidence, useless for deployment
- PBO > 0.95 → strategy universe has no real edge

### For our project
- Our 18 OOS dates can be partitioned S=6, 4-train-2-test splits
- Would give PBO estimate for our Chain 1 selection process
- **If PBO > 0.10, framework autonomous exploration claim weakens**

## 3. Combinatorial Purged Cross-Validation (CPCV)

### Problem with standard k-fold CV in finance
Labels overlap in time (overlapping trade windows) → training leakage. Our Chain 1 IS dates 20260317/23/26 and OOS 20260318~ are close enough to suffer this.

### CPCV procedure
1. Split observations into N groups chronologically
2. For each combination of k groups held out (as test), train on N-k
3. **Purge**: remove training observations that overlap with test window (same horizon H)
4. **Embargo**: also remove observations immediately after test to prevent causal leakage
5. Record test performance for each combination

### For our project
- Our current IS/OOS split is **single partition** — no CV
- Should add CPCV: e.g., N=8 chunks across 20260305~20260422, held-out-2-test combinations
- Makes OOS robustness claims statistically defensible

## 4. Key warnings (Ch.11)

López de Prado's 7 backtest sins directly relevant to us:

| # | Sin | Our risk |
|---|---|---|
| 1 | Selection bias | ⚠️ High — 88 specs, picked top-10 |
| 2 | Survivorship bias | Low (single KRX universe) |
| 3 | Look-ahead bias | Low (backtest_runner has lookahead check) |
| 4 | Outlier bias | Medium (not yet computed) |
| 5 | Shorting bias | Dealt with (long_only=True in Chain 2) |
| 6 | Bid-ask spread bias | Low (Chain 2 measures spread) |
| 7 | Transaction cost bias | ⚠️ Medium — 23 bps fee now included |

## Implementation note for framework

**Recommended additions to our pipeline**:

```python
# New module: chain1/statistics.py
def deflated_sharpe(sr, n, m_trials, skew, kurt, ac=0.0):
    """Eq. 14.6 from AFML."""
    # ... see formulas above

def pbo_score(strategy_performances: np.ndarray, n_splits: int = 16) -> float:
    """Eq. 11.8 from AFML."""
    # ... combinatorial rank analysis
```

These should be used by `chain2-gate` when promoting specs to production-eligible.

## Known caveats

- DSR assumes i.i.d. trials. Our specs are correlated (shared primitives, iterative design) → M_effective < M. True DSR maybe more optimistic than ours.
- PBO's equal-weight assumption breaks if specs have different trade frequencies.
- CPCV respects temporal order but not regime changes (market regime shift within period → still biased).

## References (secondary)

- López de Prado, M. (2014), "The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting, and Non-Normality", *Journal of Portfolio Management* 40(5). (Original DSR derivation — see companion file `lopez_de_prado_2014_deflated_sharpe.md`.)
- Bailey, D. H., & López de Prado, M. (2012), "The Sharpe Ratio Efficient Frontier". Foundational for non-normal Sharpe.
