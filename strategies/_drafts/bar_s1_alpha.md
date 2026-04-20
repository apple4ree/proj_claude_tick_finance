---
stage: alpha
name: bar_s1_sol_vol_momentum
created: 2026-04-17
target_symbol: SOLUSDT
target_horizon: daily
paradigm: trend_follow
---

# Alpha Design: bar_s1_sol_vol_momentum

## Hypothesis

SOL daily price exhibits persistent momentum when confirmed by above-average volume and non-expanding realized volatility; exiting to cash during vol-expansion regimes avoids the -30%+ drawdown episodes that drag buy-hold Sharpe, generating positive timing skill vs always-long.

## Market Context

- Domain: Binance spot, daily OHLCV bars
- IS: 2023-01-01 to 2024-12-31 (bull run with embedded -30% corrections)
- OOS: 2025 generalization check
- Regime: long-only with cash parking (no short); rebalance daily at close
- Rationale for SOL over BTC/ETH: SOL Sharpe ~2.1 buy-hold but with extreme intra-period drawdowns (-50% episodes); timing those drawdowns adds more absolute edge than timing ETH (lower vol) or BTC (smoother trend)

## Entry Condition

Enter long (or stay long) when ALL three conditions hold on the prior day's close:

1. **Momentum gate**: `close[-1] / close[-21] - 1 > 0`
   — 20-day return is positive (price above its level 20 bars ago)

2. **Volume confirmation**: `volume[-1] > 1.5 * mean(volume[-21:-1])`
   — yesterday's volume exceeded 1.5x the 20-day trailing mean, confirming participation/conviction behind the move

3. **Volatility regime filter**: `std(log_returns[-10:]) < std(log_returns[-30:])`
   — 10-day realized vol is below 30-day realized vol (vol is NOT expanding/breaking out upward), meaning we are NOT entering into a volatility spike that precedes reversals

Exit to cash (close position) when ANY condition fails.

## Signals Needed

- `mom_20`: `close.pct_change(20)` — 20-day price momentum
- `vol_spike`: `volume / volume.rolling(20).mean()` — volume ratio vs 20-day mean
- `rvol_10`: `np.log(close/close.shift(1)).rolling(10).std()` — 10-day realized volatility
- `rvol_30`: `np.log(close/close.shift(1)).rolling(30).std()` — 30-day realized volatility
- Composite entry signal: `(mom_20 > 0) & (vol_spike > 1.5) & (rvol_10 < rvol_30)`

## Universe Rationale

SOLUSDT chosen because:
- Highest buy-hold Sharpe (2.1) in IS period, but with embedded -40/50% corrections that timing can avoid
- SOL has more pronounced momentum cycles and vol-expansion warning patterns vs BTC (smoother) or ETH (less vol)
- At daily resolution, SOL volume spikes are more informationally dense than BTC (larger whale impact relative to float)
- Single-symbol keeps complexity low for first daily-bar iteration

## Why Trend-Follow Not Mean-Reversion

At daily resolution in crypto bull markets, mean-reversion strategies face severe adverse selection: the "mean" drifts upward continuously and reversion entries into drawdowns get punished by continued sell-offs. Trend-following with a cash escape avoids holding through -30% episodes.

## Why Volume Gate

Momentum without volume confirmation is weak in crypto: price can drift up on thin volume (low conviction) then reverse sharply. Requiring volume > 1.5x mean filters out low-conviction momentum and keeps win-rate higher.

## Why Volatility Regime Filter

When short-term realized vol exceeds long-term (vol is expanding), it typically signals a regime change: either a breakdown (stop triggered) or a spike-and-crash. Exiting to cash avoids these episodes. This filter is directional-agnostic — it fires whether vol expands into a rally or a sell-off.

## Knowledge References

- KRX lessons (cross-domain): OBI momentum has no edge when fees dominate — at 10 bps crypto fee, momentum signals ARE viable
- Lesson 017: transition-based signals fire at informationally neutral points — this design uses a sustained state (all 3 conditions must hold), not a crossover transition, to avoid firing too late
- Lesson 005: mean-reversion entry fires after reversal exhausted — consistent with choosing trend-follow over reversion for this domain

## Constraints Passed To Execution-Designer

- Signal is computed at prior day's close; entry must be at next day's open (no lookahead)
- Position is binary: full-long or full-cash (no partial sizing in v1)
- Volume condition uses prior day volume (yesterday), NOT intraday volume
- Lookback warmup: minimum 30 bars required before first signal (cold-start constraint)
- Rebalance: once per day (daily bar resolution — no intraday management needed)
- Fee is 10 bps round-trip; at daily horizon a round-trip costs ~0.1% which is small vs typical 2-5% daily moves in SOL

```json
{
  "name": "bar_s1_sol_vol_momentum",
  "hypothesis": "SOL daily momentum confirmed by above-average volume and non-expanding realized volatility identifies persistent trend regimes; exiting to cash when vol expands avoids the -40% drawdown episodes that suppress buy-hold Sharpe, generating measurable timing skill (rank-N/A from signal_brief — daily-bar domain, no brief exists).",
  "entry_condition": "Enter long when: (1) 20-day return > 0, (2) yesterday volume > 1.5x 20-day volume mean, (3) 10-day realized vol < 30-day realized vol. Exit to cash when any condition fails.",
  "market_context": "Binance SOLUSDT daily OHLCV; IS 2023-2024 crypto bull run with embedded -40/50% corrections; long-only with cash parking, daily rebalance at close/open boundary.",
  "signals_needed": [
    "mom_20: close.pct_change(20)",
    "vol_spike: volume / volume.rolling(20).mean()",
    "rvol_10: log_returns.rolling(10).std()",
    "rvol_30: log_returns.rolling(30).std()"
  ],
  "missing_primitive": null,
  "needs_python": true,
  "paradigm": "trend_follow",
  "multi_date": true,
  "parent_lesson": null,
  "universe_rationale": "SOLUSDT: highest buy-hold Sharpe in IS but with sharp drawdown episodes that vol-regime timing can avoid; stronger momentum cycles and more informative volume spikes than BTC or ETH at daily resolution.",
  "signal_brief_rank": null,
  "deviation_from_brief": null,
  "target_horizon": "daily",
  "target_symbol": "SOLUSDT",
  "escape_route": null,
  "alpha_draft_path": "strategies/_drafts/bar_s1_alpha.md"
}
```
