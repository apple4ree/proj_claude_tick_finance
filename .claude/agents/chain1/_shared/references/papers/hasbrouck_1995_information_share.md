# Hasbrouck (1995) — One Security, Many Markets: Determining the Contributions to Price Discovery

**Citation**: Hasbrouck, J., "One Security, Many Markets: Determining the Contributions to Price Discovery", *Journal of Finance* 50(4), 1175–1199 (1995).

## Why this matters to our project

Hasbrouck 1991 (already in our refs as `hasbrouck_1991_information_content.md`) gave the **single-security** VAR. Hasbrouck 1995 extends the same machinery to **multiple markets/securities trading the same underlying value** and provides the **Information Share (IS) decomposition**.

For our project: this is the **direct theoretical basis** for our planned `cross_symbol_obi_lag` and similar lead-lag primitives. When 005930 (Samsung) and 000660 (SK Hynix) move together (sector commonality), we want to detect which one "leads" — Hasbrouck 1995 IS gives a quantitative answer.

## 1. Setup

Suppose `n` price series `{p_1(t), ..., p_n(t)}` track the same fundamental value (e.g., NYSE vs NASDAQ for the same stock; or two correlated assets in our case).

### Common factor representation
Under cointegration:
```
p_i(t) = α_i + β · m(t) + ε_i(t)
```
- `m(t)` = unobservable efficient (random-walk) price
- `ε_i(t)` = transient deviation specific to market i

### VECM (Vector Error Correction Model)
```
Δp(t) = α · z(t-1) + Σ Γ_k · Δp(t-k) + u(t)
  where z(t) = β'·p(t) is the cointegration vector
        u(t) is innovations vector
```

## 2. Information Share (IS) — main result

Common-factor variance decomposition:
```
σ²_w = ψ' · Ω · ψ
  where ψ is the long-run impact vector (from VMA)
        Ω is the innovation covariance matrix
```

Information Share of market i:
```
IS_i = (ψ_i² · Ω_ii + Σ_{j≠i} ψ_i · ψ_j · Ω_ij) / σ²_w
```

Or simplified (uncorrelated case):
```
IS_i = (ψ_i · σ_i)² / Σ_j (ψ_j · σ_j)²
```

**Interpretation**: IS_i ∈ [0, 1] = fraction of common-factor (efficient-price) variance attributable to innovations originating in market i.
- IS_i = 0.7 → market i is **leader** (price discovery happens here)
- IS_i = 0.3 → market i is **follower**

## 3. Bounds (Cholesky ordering ambiguity)

Because `Ω` is not diagonal, IS depends on Cholesky ordering. Hasbrouck reports **upper and lower bounds**:
```
IS_i_upper = (ψ' · M_upper)_i
IS_i_lower = (ψ' · M_lower)_i
  where M is Cholesky decomposition under different orderings
```

**For us**: when reporting, present both bounds; if both above 0.5, market is unambiguous leader.

## 4. Empirical findings (Hasbrouck 1995)

Hasbrouck applied to 30 NYSE-listed Dow stocks vs regional exchanges.
- NYSE accounts for **80-90% of price discovery** (high IS).
- Regional exchanges contribute < 5% each (mostly liquidity service).

For our KRX project — analogous question: **between Samsung and SK Hynix (both KOSPI), who leads?**
- Hypothesis: market-cap leader (Samsung) leads (IS ≈ 0.7)
- Sector ETFs/futures may also influence both
- Unique to KRX: 호가단위 (gradational tick size) creates asymmetric latency — bigger stocks have larger ticks, response is "lumpier"

## 5. Apply to our framework

### Primitive design (Phase A2)

```python
def cross_symbol_obi_lag(
    snap_self,         # follower symbol's snapshot
    snap_leader,       # leader symbol's snapshot at lag time
    lag_ticks: int,
    primitive: str,    # which leader primitive to use
):
    """Information transfer from leader to follower.

    Returns the leader's primitive value `lag_ticks` ago, available as input
    to follower's signal formula.
    """
```

### Validation (post-implementation)

After collecting traces with cross-symbol primitives:
1. Fit VECM on (Samsung mid, Hynix mid) over IS dates
2. Compute IS_Samsung and IS_Hynix per Hasbrouck 1995
3. If IS_Samsung > 0.6 → cross-symbol primitive should use Samsung as leader
4. If IS_Samsung ≈ IS_Hynix ≈ 0.5 → bidirectional primitive needed

### Lead-lag horizon

Hasbrouck's IS is asymptotic (long-run). Short-run impulse responses give the **lag time scale**:
```python
def cross_market_irf(returns_leader, returns_follower, max_lag=20):
    """Impulse response: leader shock -> follower response over lags."""
    # Fit VAR(p), get IRF
    # Return lag_to_peak (typical 1-5 ticks for highly correlated stocks)
```

For our KRX 005930 → 000660 expectation:
- **Lag-to-peak**: 1-3 ticks (100-300ms) per Korean financial literature
- **Half-life of impulse**: 5-10 ticks (0.5-1 second)
- → Primitive should use `lag_ticks ∈ {1, 2, 3, 5}` as candidate values

## 6. Limitations

- **Cointegration assumption**: requires stable long-run relationship. Sector regime shifts can break this (e.g., 코리아 디스카운트 변화 후 섹터 동적 다름).
- **Stationarity**: VECM requires Δp stationary. Our 100ms returns are clearly stationary, but daily-level cointegration check needed before deploying.
- **Cholesky ordering**: as noted; report bounds.
- **Static IS**: IS itself may shift across regimes. Time-varying IS (Yan-Zivot 2010) handles this but more complex.
- **Multi-asset extension >2 securities**: IS computation scales; we'd want to limit to 3-5 leaders max for tractability.

## 7. Connection to other refs

- **Hasbrouck 1991** (already in refs): single-security VAR. 1995 is the multi-security extension.
- **Kyle 1985** (already in refs): adverse-selection theoretical framework. IS gives the empirical companion.
- **de Jong (2002)**: alternative price discovery measure (Gonzalo-Granger common factor weight). Some prefer it; both should agree in well-behaved cases.

## 8. Implementation priority

For our framework:
- ⭐⭐⭐ **A2 cross-symbol primitive** can be implemented directly using the IRF approach (faster than full VECM; same insight)
- ⭐ Full IS computation as **paper-grade validation** — only needed for paper submission, not iteration loop
- Post-implementation: run IS once over full IS+OOS dates, report Samsung-Hynix IS in paper — defensible quantitative claim

## 9. Paper narrative

When citing for the cross-symbol primitive section:
> "Following Hasbrouck (1995), we measure the price-discovery contribution of one symbol to another's mid-price formation via the Information Share (IS) decomposition of a cointegrated VECM. For Samsung and SK Hynix on KRX, IS_Samsung = X.XX±Y.YY across IS dates, justifying our use of Samsung's order-book imbalance as a leading indicator for SK Hynix mid-price prediction."

## Related references

- Hasbrouck, J. (1991). Single-security version (companion file).
- de Jong, F. (2002). "Measures of Contributions to Price Discovery: A Comparison." *Journal of Financial Markets*. Alternative metric.
- Gonzalo, J., & Granger, C. (1995). "Estimation of common long-memory components in cointegrated systems." *JBES*. Underlying common-factor framework.
- Yan, B., & Zivot, E. (2010). "A structural analysis of price discovery measures." Time-varying IS.
- Hasbrouck (2007). *Empirical Market Microstructure*. Textbook treatment, Ch.8.
