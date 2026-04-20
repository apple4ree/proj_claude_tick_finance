---
stage: alpha
name: eth15m_rvol_compression
created: 2026-04-18
target_symbol: ETHUSDT
target_horizon: 15m
paradigm: volatility_regime
signal_brief_rank: null
deviation_from_brief: "15m-bar OHLCV domain. No LOB signal brief exists for this data format. Signal family is OHLCV-derived realized volatility, structurally inapplicable to LOB-primitive briefs. Proceeding under ESCAPE protocol (bar-domain, different data source, different signal family)."
---

# Alpha Design: eth15m_rvol_compression

## Hypothesis

ETH 15-minute bars exhibit predictable volatility clustering: periods of realized-vol compression (narrow range, low ATR relative to its own history) represent coiled regimes where the market is accumulating before a directional expansion — entering on compression and exiting on expansion captures the asymmetric breakout that follows quiet accumulation, exploiting the autocorrelation of volatility itself at 10 bps round-trip.

## Why Volatility Regime (Not Price Momentum)

Crypto at 15m resolution has two failure modes well-documented in this knowledge base:
- Lesson 014: mean-reversion at 15-30 min timescale is anti-edge (18% win rate); the signal fires after the move, not before.
- Lesson 010: loose entry conditions (e.g., price above MA) become regime descriptors on trending days, causing overtrading and fee saturation.

Volatility compression is a **state-change event**: rvol must drop from a recent elevated level to a newly compressed level. This is detectably transitional (not a persistent background condition), avoids the price-direction problem (no view on whether the subsequent move is up or down — the strategy enters long and lets the breakout determine exit), and directly targets the observation that vol is mean-reverting while price is not.

## Signal Construction (Pure OHLCV Pandas)

### Realized Vol (rvol)

```python
bar_range = high - low                           # per-bar true range proxy
rvol = bar_range.rolling(RVOL_WINDOW).mean()    # rolling mean range (realized vol proxy)
```

Using bar range (high - low) rather than close-to-close returns because:
- 15m bars in crypto have significant intrabar noise; range captures realized volatility within the bar including wicks
- No log-return computation needed; range is already in price units
- Consistent with ATR literature for short-horizon volatility measurement

### Compression Percentile

```python
rvol_pct = rvol.rolling(LOOKBACK).rank(pct=True)  # percentile of current rvol vs LOOKBACK history
```

`LOOKBACK = 96` bars = 24 hours of 15m bars. This provides exactly one full trading day of history as the normalization window — long enough to capture intraday vol cycles, short enough to remain adaptive to weekly regime shifts.

`RVOL_WINDOW = 4` bars = 1 hour rolling mean (smooths single-bar spikes without introducing excessive lag).

### Entry: Compression State

```python
compressed = rvol_pct < COMPRESS_THRESH   # e.g., 0.20 → rvol in bottom 20th percentile
```

**Threshold: COMPRESS_THRESH = 0.20**

Rationale: bottom quintile ensures the strategy only enters during genuinely quiet periods, not merely below-average periods. At 15m frequency with ~96 bars/day, the 20th percentile selects the 19 quietest bars out of each full-day window. This directly addresses the overtrading risk from lesson 010 — at most ~20% of bars qualify, and in practice the compressed state is contiguous, so entry fires at most a few times per day.

### Expansion Detection (For Exit — Passed to Execution-Designer)

```python
expanding = rvol_pct > EXPAND_THRESH    # e.g., 0.70 → rvol crosses above 70th percentile
```

Exit trigger passed as a constraint: when rvol_pct rises from below 0.20 to above 0.70, the vol expansion is confirmed and the position should exit. The execution-designer chooses the precise exit mechanism (trailing stop, immediate market, or limit).

### Selectivity Gate (Reduce Trades)

To explicitly reduce 15m-bar turnover, add a **minimum-hold filter**:
- After entering, do not allow a new entry for at least `MIN_HOLD_BARS = 8` bars (2 hours).
- This prevents re-entry into consecutive compressed bars during a slow drift, which would chain many small trades at 10 bps each.

Additionally, a **vol-of-vol stability gate**:
```python
rvol_std_8 = rvol.rolling(8).std()           # vol-of-vol over last 2 hours
vol_stable = rvol_std_8 < rvol_std_8.rolling(LOOKBACK).quantile(0.40)
```
Only enter when vol-of-vol itself is also stable (below 40th percentile of its own history). This ensures the compression is a genuine quiet period, not a momentarily flat bar embedded in chaotic choppy action.

### Combined Entry Condition

```python
enter_long = (
    compressed          # rvol in bottom 20th pct of 24h window
    & vol_stable        # vol-of-vol also stable (not spike-embedded)
    & ~position_open    # not already in a position
    & cooldown_ok       # at least 8 bars since last exit
)
```

## Market Context

- Domain: Binance ETHUSDT, 15-minute OHLCV bars
- Regime: volatility compression (low-rvol state preceding directional expansion)
- Entry fires: typically 2-5 times per day in normal conditions; fewer in trending days (vol stays elevated)
- Not time-of-day filtered at v1 — ETH trades 24/7, vol compression occurs across all hours; add session filter only if backtesting reveals a time-of-day skew
- Warm-up: LOOKBACK (96) + RVOL_WINDOW (4) = 100 bars minimum before first signal (~25 hours)
- Target exposure: 20-40% of capital per entry (execution-designer to size); the selectivity of the entry condition (~20% of bars qualify) naturally constrains exposure duration

## Entry Condition (Plain English)

Over the last 96 bars (24 hours), compute the 4-bar rolling mean of the high-low bar range (rvol). If the current rvol sits in the bottom 20th percentile of the 96-bar lookback (compressed), AND the standard deviation of that rvol over the last 8 bars is also in the bottom 40th percentile of its own 96-bar history (vol-of-vol is stable), AND no position is currently open, AND at least 8 bars have elapsed since the last exit: enter long at the open of the next bar.

## Why Long-Only

- Binance spot ETHUSDT: no short without margin
- Volatility compression predicts a move in either direction; but on Binance spot, long-only is the structurally accessible side
- The edge is not directional: it is that the NEXT bar after compression tends to have higher realized range, and entering before that expansion on the long side benefits when the expansion is upward
- This does introduce a downward-expansion risk (enter long, vol expands downward → loss); the execution-designer's stop-loss handles this asymmetry

## Signals Needed

- `bar_range`: `high - low` — intrabar realized volatility proxy
- `rvol`: `bar_range.rolling(4).mean()` — 1-hour smoothed realized vol
- `rvol_pct`: `rvol.rolling(96).rank(pct=True)` — compression percentile vs 24h lookback
- `rvol_std_8`: `rvol.rolling(8).std()` — vol-of-vol (2-hour window)
- `vol_stable`: `rvol_std_8 < rvol_std_8.rolling(96).quantile(0.40)` — stability gate

All computable from standard OHLCV (high, low, close) using pure pandas. No custom primitives required.

## Key Parameters

| Parameter | Value | Rationale |
|---|---|---|
| RVOL_WINDOW | 4 bars (1h) | Smooth single-bar spikes without excessive lag |
| LOOKBACK | 96 bars (24h) | Full intraday cycle normalization; adaptive to weekly shifts |
| COMPRESS_THRESH | 0.20 | Bottom quintile; caps qualifying bars at ~20%, avoids overtrading |
| VOL_STABLE_THRESH | 0.40 | 40th pct of vol-of-vol; ensures stable compression, not noise |
| MIN_HOLD_BARS | 8 bars (2h) | Prevents chain-entry into consecutive compressed bars |

## Universe Rationale

ETHUSDT Binance: second-largest spot market, 24/7 operation, tight spreads (1-2 bps typical), 10 bps round-trip fee is conservative for taker orders. ETH has more frequent intraday vol compression cycles than BTC (higher beta, more responsive to altcoin news), making the compression-expansion signal more recurrent. Single-symbol v1 keeps the design testable before generalization to SOL, BNB.

## Knowledge References

- Lesson 014: 15-30 min mean-reversion is anti-edge at KRX (applies analogously to 15m crypto; avoids that paradigm)
- Lesson 010: loose entry conditions cause overtrading (COMPRESS_THRESH=0.20 + vol-of-vol gate directly address this; entry fires <20% of bars by construction)
- bar_s5 (BTC daily momentum): ESCAPE protocol precedent for bar-domain strategies where LOB brief is inapplicable

## Constraints Passed To Execution-Designer

- Entry: at open of bar N+1 after signal fires on close of bar N (no lookahead)
- Exit trigger signal: `rvol_pct > 0.70` (expansion confirmed); execution-designer chooses exit order type and timing
- Minimum hold: 8 bars from entry before exit logic activates (to let the expansion materialize)
- Fee is 10 bps round-trip; at 15m frequency this is significant — do NOT use a time-stop shorter than 4 bars (1 hour)
- Target exposure: 20-40% of capital per position (execution-designer sizes)
- Position direction: long-only (Binance spot)
- The compression signal is fleeting: once rvol_pct rises above 0.30, the entry opportunity has passed — execution-designer should NOT allow re-entry on a stale signal
- Cooldown: MIN_HOLD_BARS=8 is a hard constraint on the alpha side; the execution-designer cannot override it

```json
{
  "name": "eth15m_rvol_compression",
  "target_symbol": "ETHUSDT",
  "target_horizon": "15m",
  "paradigm": "volatility_regime",
  "hypothesis": "ETH 15m bars exhibit predictable volatility clustering; when realized-vol (4-bar rolling mean of high-low range) falls to the bottom 20th percentile of its 24-hour lookback, the market is in a coiled compression regime preceding directional expansion — entering long on confirmed compression and exiting on vol expansion captures the asymmetric breakout premium, exploiting vol autocorrelation at 10 bps round-trip.",
  "entry_condition": "rvol_pct (rolling 96-bar percentile of 4-bar smoothed high-low range) < 0.20 AND vol-of-vol (8-bar std of rvol) < 40th-percentile of its own 96-bar history AND no open position AND >= 8 bars since last exit; enter long at next bar open.",
  "market_context": "Binance ETHUSDT 15m OHLCV, 24/7; entry fires ~2-5x/day during normal conditions; fewer on strongly trending days when vol stays elevated; 100-bar warm-up required; target 20-40% capital exposure per trade.",
  "signals_needed": [
    "bar_range: high - low",
    "rvol: bar_range.rolling(4).mean()",
    "rvol_pct: rvol.rolling(96).rank(pct=True)",
    "rvol_std_8: rvol.rolling(8).std()",
    "vol_stable: rvol_std_8 < rvol_std_8.rolling(96).quantile(0.40)"
  ],
  "params": {
    "rvol_window": 4,
    "lookback": 96,
    "compress_thresh": 0.20,
    "vol_stable_thresh": 0.40,
    "min_hold_bars": 8,
    "expand_thresh": 0.70
  },
  "missing_primitive": null,
  "needs_python": true,
  "multi_date": true,
  "parent_lesson": "lesson_014 (15m mean-reversion anti-edge → avoid); lesson_010 (overtrading via loose condition → COMPRESS_THRESH=0.20 + vol-of-vol gate caps entry frequency); bar_s5 (ESCAPE protocol for bar-domain LOB-inapplicable brief)",
  "universe_rationale": "ETHUSDT Binance spot: 24/7, tight spreads, high intraday vol-compression recurrence, 10 bps taker fee conservative; single-symbol v1 for clean testability.",
  "signal_brief_rank": null,
  "deviation_from_brief": "15m-bar OHLCV domain; no LOB brief applicable. Signal family is OHLCV-derived realized volatility. ESCAPE protocol applied.",
  "escape_route": "LOB-primitive signal briefs are inapplicable to 15m bar OHLCV data. Escape: shift signal family to realized-vol percentile (bar range rolling quantile), shift paradigm to volatility_regime (compression-before-expansion), and enforce selectivity via percentile threshold + vol-of-vol gate to keep trade count low enough that 10 bps fee is survivable.",
  "alpha_draft_path": "strategies/_drafts/eth15m_rvol_compression_alpha.md"
}
```
