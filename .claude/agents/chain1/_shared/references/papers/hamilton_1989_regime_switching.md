# Hamilton (1989) — A New Approach to the Economic Analysis of Nonstationary Time Series and the Business Cycle

**Citation**: Hamilton, J. D., "A New Approach to the Economic Analysis of Nonstationary Time Series and the Business Cycle", *Econometrica* 57(2), 357–384 (1989).

## Why this matters to our project

Hamilton 1989 introduced **Markov regime-switching models** to econometrics — the canonical statistical framework for "the data-generating process changes between unobservable states." This is the **theoretical basis for HMM-based regime classification** in our framework.

For us:
- Currently, "regime" = simple threshold like `rolling_realized_vol < 30` — a deterministic, observable filter.
- Hamilton's framework says: there are **latent regimes** with different parameters, and we should use **probabilistic state inference** (filtered/smoothed probabilities) instead of hard thresholds.
- Concretely: Chain 1.5's `extra_regime_gate` could become a probability-weighted soft gate.

## 1. Setup

Time series `y_t` follows different processes depending on unobservable regime `S_t ∈ {1, 2, ..., K}`:

```
y_t | S_t = i  ~  N(μ_i, σ²_i)    (or AR process)
```

With Markov transition between regimes:
```
P(S_t = j | S_{t-1} = i) = p_ij
  Σ_j p_ij = 1
```

### Likelihood (filtering)

Forward recursion: at each t, compute `P(S_t = i | y_{1..t}, θ)`:
```
P(S_t = i | y_{1..t}) = (P(S_t=i | y_{1..t-1}) · f(y_t | S_t=i)) / Σ_j ...
```

Combine with state evolution:
```
P(S_t = i | y_{1..t-1}) = Σ_j p_ji · P(S_{t-1} = j | y_{1..t-1})
```

→ EM algorithm (or quasi-MLE) for parameter estimation `θ = {μ_i, σ_i, p_ij}`.

## 2. Key results

### Smoothed inference
Backward recursion gives `P(S_t = i | y_{1..T})` — uses ALL data including future:
```
P(S_t = i | y_{1..T}) ∝ P(S_t = i | y_{1..t}) · P(y_{t+1..T} | S_t = i)
```

For us: filtered (real-time) inference is what's usable in trading; smoothed is for backtest analysis.

### Regime persistence
Diagonal of transition matrix gives expected duration in each regime:
```
E[duration in regime i] = 1 / (1 - p_ii)
```

For us: if `p_low_vol_low_vol = 0.99`, expected dwell time is 100 ticks (10s) — useful for setting `max_hold_ticks` in Chain 1.5.

### Extension: regime-dependent AR
```
y_t = μ_{S_t} + φ_{S_t} · y_{t-1} + ε_t,  ε_t ~ N(0, σ²_{S_t})
```
Each regime has its own dynamics.

## 3. Implementation for our project

### Phase A — Standalone HMM as regime detector
```python
# chain1/regime_detector.py (new)
from hmmlearn.hmm import GaussianHMM

def fit_2state_vol_regime(returns: np.ndarray, n_iter=50):
    """Fit 2-state HMM on log-returns of mid_px.
    
    Returns:
      filtered_probs: P(S_t = "high_vol" | y_{1..t}) per tick
      transition: 2x2 transition matrix
      means, vars: regime parameters
    """
    model = GaussianHMM(n_components=2, covariance_type="full",
                         n_iter=n_iter, init_params="stmc", random_state=42)
    model.fit(returns.reshape(-1, 1))
    # Order regimes: lower-variance = "calm", higher = "volatile"
    if model.covars_[0][0,0] > model.covars_[1][0,0]:
        # Swap so regime 0 = calm
        ...
    return {
        "filtered_probs_volatile": model.predict_proba(returns.reshape(-1,1))[:, 1],
        "transition": model.transmat_,
        "regime_means": model.means_,
        "regime_vars": [model.covars_[i][0,0] for i in range(2)],
    }
```

### Phase B — As Chain 1 primitive
```python
def regime_volatility_prob(snap_buffer, fitted_hmm) -> float:
    """Returns filtered P(S_t = high_vol regime | recent returns).
    
    Range: [0, 1]. 0 = pure calm regime, 1 = pure volatile regime.
    """
    # Apply pre-fitted HMM to recent returns from snap_buffer
    ...
```

Then signal can use:
```
formula = "obi_1 > 0.5 AND regime_volatility_prob(50) < 0.3"
```
→ enter long when OBI imbalanced AND HMM says we're in calm regime (probability < 30%).

### Phase C — Regime-conditional spec parameters
Different specs for different regimes:
```
spec_calm:    obi_1 > 0.4 AND regime_prob < 0.2  →  H=20  (longer hold OK)
spec_volatile: obi_1 > 0.7 AND regime_prob > 0.7 →  H=5  (shorter hold)
```
Chain 1.5 could route between these based on real-time regime probability.

## 4. Empirical regularities (from Hamilton 1989 + extensions)

Hamilton's original application: US GNP regime-switching (recessions vs expansions). Subsequent applications to financial time series:

- **Engle-Granger cointegration with regime switching**: regime governs whether two series are cointegrated.
- **Ang-Bekaert (2002)**: term structure of interest rates has 2-3 regimes.
- **Pelletier (2006)**: stock return correlation matrices switch between high-corr (crisis) and low-corr (normal).
- **Bauwens-Otranto (2016)**: GARCH model regimes — vol-low vs vol-high vs vol-explosive.

For HF data:
- **Ghysels-Idier-Manganelli-Vergote (2017)**: tick-level regime detection via Markov-switching.
- Mixed evidence: 2-3 regimes commonly found, but stability of HMM parameters across days is fragile.

## 5. Use case for our framework

### Most direct use: replace `rolling_realized_vol < 30` with HMM filter

**Current** (deterministic):
```python
gate = rolling_realized_vol(mid_px, 100) < 30
```

**HMM-based** (probabilistic):
```python
gate = regime_volatility_prob(50) < 0.3   # probability calm < 30%
```

Advantages:
- **Smoother transitions**: no abrupt on/off at threshold
- **Symbol-invariant**: instead of magic number 30 for 005930, the HMM auto-calibrates
- **Persistence-aware**: if HMM says "high prob calm AND was calm 30 ticks ago", more confident

Disadvantages:
- **Requires fitted HMM per symbol** (training overhead)
- **Stability across days**: regime parameters may drift
- **Computational cost**: real-time forward filter per tick

### Quantitative expected gain

Regime gate improvements from this:
- Direct empirical comparison (fixed 30 vs HMM gate): difficult to predict ahead of time
- Conservative: marginal +0.5-1 bps expectancy (cleaner regime detection)
- Optimistic: +1-2 bps if our current vol gate is suboptimal threshold

## 6. Implementation considerations

### Library: `hmmlearn`
```bash
pip install hmmlearn
```
- Mature, well-tested, GaussianHMM directly usable
- Does not handle multi-day non-stationarity automatically (need to refit)

### Symbol-specific calibration
- Fit per-symbol HMM on training dates
- Save fitted params to `data/regime_models/<symbol>_hmm.pkl`
- Load at backtest start

### Live deployment
- Forward filter per incoming tick: `model.predict_proba(...)` — fast (~µs per tick)
- Refit weekly to handle slow regime drift

## 7. Caveats

- **Regime ≠ Truth**: HMM is a model. Real "regimes" are continuous + multi-dimensional, but 2-3 discrete states often work pragmatically.
- **EM local optima**: HMM training can find suboptimal solutions. Multiple random seeds + best-likelihood selection.
- **Identification**: regime labels are arbitrary (which one is "calm"?). Fix by ordering by variance.
- **Overfitting risk**: too many states (K=5+) → HMM memorizes noise. Use BIC/AIC to choose K.

## 8. Connection to other refs

- **Bouchaud 2004** (already in refs): non-linear price impact varies by regime — HMM can detect impact regime.
- **Almgren-Chriss 2001** (already in refs): optimal T* depends on σ — HMM gives σ_regime directly.
- **VPIN (Easley-LdP-O'Hara 2012)** (companion in refs): VPIN-based regime is a 1-dim alternative to HMM. Both are valid; HMM is more flexible.
- **López de Prado 2018** (already in refs): AFML Ch.16 has CVaR + regime application.

## 9. Implementation priority for us

- ⭐⭐ Add HMM as **standalone regime detector**, save filtered probs as a primitive — Phase A2 of feature expansion
- ⭐ Replace existing `rolling_realized_vol < X` filters with HMM — paper-defensible improvement
- ⭐ Use HMM to **partition iter results**: spec performance per regime (calm vs volatile) — interesting paper result

## 10. Paper narrative

When citing for the regime-aware execution section:
> "We employ Markov regime-switching models (Hamilton, 1989) to identify latent volatility regimes in KRX large-cap stocks. The fitted 2-state HMM produces filtered probabilities P(S_t = volatile | y_{1..t}) which we use as a probabilistic regime gate, replacing the deterministic threshold-based filter of Chain 1's earlier iterations."

## Related references

- Hamilton, J. D. (1994). *Time Series Analysis*, Princeton, Ch.22 — book-length treatment.
- Ang, A., & Bekaert, G. (2002). Application to interest rates.
- Engel, C., & Hamilton, J. D. (1990). Application to exchange rates.
- Pelletier, D. (2006). Multivariate regime-switching for correlation matrices.
- Bauwens, L., & Otranto, R. (2016). GARCH + regime.
- Ghysels-Idier-Manganelli-Vergote (2017). HF-microstructure HMM.
- Hartzmark-Shue (2018). Behavioral regime detection.
