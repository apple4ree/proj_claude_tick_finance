# Almgren & Chriss (2001) — Optimal Execution of Portfolio Transactions

**Citation**: Almgren, R., & Chriss, N., "Optimal execution of portfolio transactions", *Journal of Risk* 3, 5–39 (2001).

## Why this matters to our project

Chain 2 must decide **when to exit** an open position — PT target, SL cap, time stop. Currently Chain 2 / Chain 1.5 choose these via empirical Optuna search. Almgren-Chriss provides **theoretical** optimal execution horizon under a trade-off between:

1. **Impact cost** (transacting too fast moves price against us)
2. **Risk cost** (transacting too slowly exposes us to volatility)

The framework gives a closed-form optimal execution trajectory and — critically for us — an optimal *time scale* T* that can **calibrate our Chain 2's `time_stop_ticks` default**.

## 1. Model setup

We want to liquidate X shares over horizon T. Divide into N trades at times `t_k = k·T/N`. Let `n_k` be trade size at step k, so `Σ n_k = X`.

### Cost model
Two components:

**Temporary impact** (reverts after trade):
```
h(v_k) = ε + η·v_k           where v_k = n_k / (T/N)
```
`ε` = half-spread (fixed), `η` = linear impact coefficient.

**Permanent impact** (doesn't revert):
```
g(v_k) = γ·v_k
```

### Price process
```
S_{t_k} = S_{t_{k-1}} + σ·√(T/N)·ξ_k − τ·g(n_k/τ)
```
where `τ = T/N`, `ξ_k ~ N(0,1)`.

### Effective cost
Expected trading cost `E[C]` + variance term `V[C]`. The trader minimizes:
```
U(x) = E[C] + λ·V[C]
  where λ = risk aversion
```

## 2. Closed-form optimal trajectory

After optimization over `{n_k}`:

```
x_k* = sinh(κ·(T − t_k)) / sinh(κ·T) · X
  where κ = √(λ·σ²/η̃)  (curvature)
        η̃ = η − γ·τ/2  (adjusted impact coefficient)
```

### Three regimes by risk aversion λ

- **λ → 0** (risk-neutral): κ → 0, optimal strategy = **VWAP over full horizon**. Slowest.
- **λ → ∞** (risk-averse): κ → ∞, **execute everything immediately**. Impact cost ignored.
- **λ > 0** (realistic): **exponential decay**. Most execution early, tapering.

## 3. Optimal horizon T*

For a **fixed target cost budget** C_target:
```
T* = √(η / (λ·σ²))
```

**Interpretation**: 
- Volatile market (high σ) → execute faster (shorter T*)
- Deep market (low η) → can execute slower
- Risk-averse (high λ) → execute faster

## 4. For our Chain 2 engine

### 4.1 Calibration of time_stop_ticks

Currently Chain 2 default `time_stop_ticks = 50` (chosen empirically). Almgren-Chriss gives a principled alternative:

```python
# In cost_model.py or execution_runner.py:
def ac_optimal_horizon(
    eta_bps_per_share: float,  # impact coefficient (from empirical fits)
    lambda_risk_aversion: float,  # user parameter (e.g., 1e-6)
    sigma_bps_per_tick: float,   # mid-price volatility in bps per tick
) -> int:
    """Almgren-Chriss optimal execution horizon in ticks."""
    import math
    T_star = math.sqrt(eta_bps_per_share / (lambda_risk_aversion * sigma_bps_per_tick**2))
    return int(max(1, min(500, round(T_star))))
```

### 4.2 Why this matters for PT/SL

Our iter013 spec holds for up to 50 ticks, hits PT at various points. Under AC:
- If market is calm (σ small), we can hold longer → wider PT accepted.
- If market is volatile, cut holding short → tighter time_stop.

Our current `extra_regime_gate = (rvol < 30)` is crude AC-style adaptation.

### 4.3 Connection to our `horizon_curve`

Chain 1's `horizon_curve` shows expectancy peaks at certain H and decays. AC says: **don't hold beyond T* because risk cost dominates**. Our empirical h=5/10/20 peak vs h=200 decline is AC in action.

## 5. Implementation priorities

### Near-term (Chain 2.1)
- Compute σ (mid_bps / sqrt(ticks)) from our backtest runs → typical values per symbol/date
- Assume λ (e.g., 1e-5 for "institutional retail") as a parameter in ExecutionSpec
- η calibration: from our empirical fills, fit linear `price_impact = η × fill_size`

### Longer-term
- Implement `time_stop_ticks = ac_optimal_horizon(η, λ, σ)` as default
- Chain 1.5 can tune this or use it as baseline

## 6. Limitations of AC for our use case

- **Our problem**: predict direction + exit. AC is about **liquidating** a pre-sized position optimally.
- **AC assumes position size X is given**; we have X=1 fixed. So the "optimization of trade size trajectory" is degenerate.
- **What AC gives us**: a sense of how long to hold = T*.

For **market-making** paradigm (Chain 2.3+), AC is more directly applicable — size changes during execution due to inventory drift.

## 7. Related work

- Bertsimas, D., & Lo, A. W. (1998). "Optimal control of execution costs." *Journal of Financial Markets*. Original VWAP-optimal framework pre-AC.
- Obizhaeva, A. A., & Wang, J. (2013). "Optimal trading strategy and supply/demand dynamics." Better for limit-book dynamics.
- Cartea, Jaimungal, Penalva (2015). *Algorithmic and High-Frequency Trading* — Ch.6 reviews AC and extensions with HJB equations.
- López de Prado (2018). AFML Ch.19 applies AC to portfolio execution with ML-derived forecasts.

## Known caveats

- Linear impact is an approximation. Real markets show `impact ∝ √size` (Bouchaud 2004) — see `bouchaud_2004_price_impact.md`.
- AC ignores queue position; for LIMIT orders our effective speed depends on queue, not just posting rate.
- λ is a user-chosen parameter; AC doesn't prescribe it. Downside of all utility-maximization approaches.
