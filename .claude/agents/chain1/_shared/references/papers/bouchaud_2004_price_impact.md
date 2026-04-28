# Bouchaud, Gefen, Potters, & Wyart (2004) — Fluctuations and Response in Financial Markets

**Citation**: Bouchaud, J.-P., Gefen, Y., Potters, M., & Wyart, M., "Fluctuations and response in financial markets: the subtle nature of 'random' price changes", *Quantitative Finance* 4(2), 176–190 (2004).

## Why this matters to our project

Kyle's λ says price impact is **linear** in order flow: `Δp = λ · V`. Bouchaud et al. empirically refute this. Real price impact scales as **square-root**:
```
Δp ∝ √V
```

For our Chain 2 `slippage_cost_bps` computation:
- We currently assume 1-share orders → slippage = 0 (fits in top-of-book)
- For any realistic deployment with >100 share orders, slippage becomes significant
- Square-root impact means **cost grows sublinearly** with size → careful sizing can beat linear intuitions

## 1. Empirical regularities

From analysis of NYSE, Paris Bourse equities:

### Market-order impact
```
I(Q) = Y · √Q · sign(Q) · σ
  where Y ≈ 0.5-1.5 (stock-dependent)
        σ = daily volatility
        Q = normalized order size (fraction of daily volume)
```

**Sign**: buy orders push price up, sell orders push down.
**Magnitude**: doubling Q increases impact by √2 ≈ 1.41×, not 2×.

### Limit-order book response
Upon a market order arrival, the book **partially refills** but not instantly:
- Immediate response: spread widens (adverse selection)
- 1-10 seconds later: new limit orders arrive, spread tightens
- 1-10 minutes later: impact partially reverts, **permanent component ≈ 50-70% of peak**

## 2. Mathematical framework

### Response function R(τ)
Define:
```
R(τ) = <ε_t · (p_{t+τ} − p_t)>  (averaged over many events)
```
where `ε_t` is the sign of the trade at time t.

Empirical finding: `R(τ)` rises rapidly, then slowly saturates or partially decays:
```
R(τ) ~ log(τ) for small τ (fast rise)
R(τ) → constant for large τ (permanent)
```

### Price diffusion paradox
Individual trades are **positively autocorrelated** (sign clustering: buys followed by buys).

If impact were simply linear and permanent, prices would **blow up** via compounding of self-correlated trades.

Resolution: **mean-reverting component** in order flow balances out → prices are nearly random walk.

## 3. For our Chain 2 slippage model

### Current (Phase 2.0): slippage = 0
```python
cost_breakdown.slippage_cost_bps = 0.0  # assumes lot size fits top-of-book
```

### Better model (Phase 2.1+, needed for >100 shares)
```python
def bouchaud_slippage(
    order_shares: float,
    daily_volume_shares: float,
    daily_volatility_bps: float,
    Y: float = 1.0,
) -> float:
    """Bouchaud square-root impact: bps."""
    import math
    Q = order_shares / daily_volume_shares
    return Y * math.sqrt(Q) * daily_volatility_bps
```

**For KRX 005930** (daily vol ~1M shares, σ_daily ~50 bps):
- 10 shares: Q = 1e-5, slippage ≈ 0.16 bps (negligible)
- 100 shares: Q = 1e-4, slippage ≈ 0.5 bps
- 10,000 shares: Q = 0.01, slippage ≈ 5 bps — **meaningful**!

→ For sizing beyond retail (Chain 2.4+), this matters.

## 4. Connection to other references

### vs Kyle (1985)
- Kyle: `Δp = λ · V` (linear)
- Bouchaud: `Δp = Y · σ · √Q` (square-root)
- Reconciliation: **Kyle is locally valid, Bouchaud is globally**. At tiny Q linearity holds; at typical daily Q square-root dominates.

### vs Almgren-Chriss (2001)
AC uses linear impact `η · v`. For correctness, should use Bouchaud's square-root:
```
Optimal horizon T* under square-root impact = (η / (λσ²))^{2/3}
```
(Different exponent from linear case).

Most HFT execution algorithms use **TWAP (time-weighted average price)** or **POV (percentage of volume)** which are robust to exact impact model.

## 5. Why our current project doesn't need this urgently

- We trade 1 share → slippage negligible
- Chain 2 engine assumes single-unit fill
- Our `spread_cost_bps` already captures the half-spread which dominates single-unit costs

### When this becomes critical
- **Chain 2.4+ with variable sizing**: e.g., `sizing_rule = "kelly_scaled"` may request 100-1000 shares
- **Market-making paradigm** with inventory buildup >100 shares
- **Backtest validation with realistic capital** (e.g., 100M KRW / 180K price = 555 shares per trade)

## 6. Implementation plan

### Near-term
Add to `chain2/cost_model.py`:
```python
BOUCHAUD_Y_DEFAULT = 1.0  # calibrate per symbol
DAILY_VOLUME_SHARES = {  # from empirical data
    "005930": 15_000_000,
    "000660": 5_000_000,
    # ...
}
DAILY_VOLATILITY_BPS = {
    "005930": 100,   # ~1% daily typical
    "000660": 120,
    # ...
}

def estimate_slippage(symbol: str, lot_size: int) -> float:
    """Bouchaud square-root slippage estimate."""
    vol = DAILY_VOLUME_SHARES.get(symbol, 1_000_000)
    vola = DAILY_VOLATILITY_BPS.get(symbol, 100.0)
    q_frac = lot_size / vol
    return BOUCHAUD_Y_DEFAULT * (q_frac ** 0.5) * vola
```

### Calibration (Phase 2.5+)
Fit Y per symbol from our execution traces:
- Pair: (observed mid move post-fill, fill size)
- Regress: `impact ≈ Y · sqrt(size / daily_vol) · sigma_daily`
- Get Y empirical, use in subsequent backtests.

## 7. Limitations

- **Daily volume / volatility calibration** requires external data. Currently not in our feed.
- **Y is time-varying** (intraday, across regimes). Static Y is a simplification.
- **Cross-impact** across symbols not captured (for multi-symbol portfolios).
- **Non-stationarity**: crisis periods have much higher Y.

## 8. Paper narrative

When citing in our deployment section:
> "Consistent with Bouchaud et al. (2004), we assume square-root market impact for large orders. Our current backtest uses 1-share orders, making slippage negligible; for deployment at retail scale (up to 1000 shares per trade for KRX large caps), estimated slippage remains <5 bps and does not materially change the fee analysis."

## Related references

- Gatheral, J. (2010). "No-dynamic-arbitrage and market impact." *Quantitative Finance* 10(7). Unifies Kyle and Bouchaud under arbitrage constraints.
- Hasbrouck, J. (2007). "Empirical Market Microstructure." Textbook, Chapter 10 surveys impact models.
- Tóth, B., et al. (2011). "Anomalous price impact and the critical nature of liquidity in financial markets." Square-root law robustness.
- Almgren, R., Thum, C., Hauptmann, E., Li, H. (2005). "Direct estimation of equity market impact." Empirical calibration.
