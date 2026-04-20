---
stage: alpha
name: sol_5m_vol_breakout
created: 2026-04-18
target_symbol: SOLUSDT
target_horizon: 5m
domain: binance_crypto
fee_bps: 10
---

# Alpha Design: sol_5m_vol_breakout

## Hypothesis
When SOLUSDT forms a tight consolidation range (low ATR-to-price ratio) and the next 5m bar closes above the N-bar rolling high with volume exceeding the 20-bar average by ≥50%, a short-term momentum breakout edge exists over the next 1-3 bars before mean-reversion reasserts.

## Market Context
- Crypto 5m bars; signal is regime-agnostic but strongest during moderate volatility (ATR not extreme).
- No time-of-day restriction (24/7 market).
- Entry disabled for K=10 bars after any prior entry (cooldown) to suppress cluster-firing and cap turnover.
- Range compression pre-filter (ATR_14 / close < 0.012) selects genuine consolidation, not random noise.

## Entry Condition
All four gates must be true on bar close:

1. **Consolidation**: ATR_14 / close < 0.012 (price range tight relative to level)
2. **Breakout close**: close > rolling_max(high, N=20) of the *previous* 20 bars (bar-1 through bar-20; current bar excluded to avoid look-ahead)
3. **Volume confirm**: volume > 1.5 × SMA(volume, 20) on the breakout bar
4. **Cooldown clear**: at least 10 bars since last entry signal fired

Enter long at the open of the next bar (bar+1 market order).

## Signals Needed
- `rolling_max(high, 20)` — pandas rolling max, shifted by 1
- `ATR(14)` — Wilder's ATR from OHLCV
- `SMA(volume, 20)` — 20-bar volume average
- `cooldown_counter` — stateful bar count since last signal (needs Python state)

## Universe Rationale
SOLUSDT on Binance: high liquidity (tight spread, low slippage on market orders), 10 bps round-trip fee is manageable with selective entries, SOL has exhibited repeated consolidation-breakout patterns in 2024-2026.

## Trade Count Estimation
- 6 months ≈ 26,280 bars (5m, 24/7)
- ATR compression filter passes ~30% of bars ≈ 7,884
- Volume gate passes ~25% of those ≈ 1,971
- Breakout close condition passes ~40% of those ≈ 789
- Cooldown (10-bar suppress) further reduces by ~50% → ~395 signals
- Well under 3,000 target.

## Knowledge References
- No direct KRX LOB knowledge applicable (different domain).
- Lesson: volume confirmation prevents false breakouts that fire at range extremes (analogous to lesson_017: transition-based entries fire at informationally neutral points).
- Lesson: cooldown suppression analogous to entry-gate-end mechanisms that block cluster firing.

## Constraints Passed To Execution-Designer
- Entry is at bar+1 open (market order); signal is bar-close-triggered.
- Exposure target: <15% of portfolio at any time (position sizing constraint).
- Max hold: 3 bars (15 minutes) — signal is short-horizon momentum.
- No overnight accumulation concern (crypto 24/7, but max-hold enforces exposure cap).
- Do NOT use time-of-day gates (24/7 market).
- Cooldown of 10 bars is part of the alpha signal logic — execution designer must preserve it.

```json
{
  "name": "sol_5m_vol_breakout",
  "hypothesis": "rank-null from signal_brief: when SOLUSDT consolidates (low ATR/price) and breaks the 20-bar high on close with volume ≥1.5x average, short-term momentum carries 1-3 bars before reversion — exploiting the informational asymmetry of volume-confirmed range expansion.",
  "entry_condition": "bar close > shift(rolling_max(high,20),1) AND ATR_14/close < 0.012 AND volume > 1.5*SMA(volume,20) AND bars_since_last_entry >= 10; enter long at next bar open",
  "market_context": "24/7 Binance crypto 5m bars; regime-agnostic; cooldown gate caps turnover; consolidation pre-filter selects low-noise setups",
  "signals_needed": ["rolling_max_high_20", "ATR_14", "SMA_volume_20", "cooldown_counter"],
  "missing_primitive": null,
  "needs_python": true,
  "paradigm": "breakout",
  "multi_date": true,
  "parent_lesson": null,
  "target_symbol": "SOLUSDT",
  "target_horizon": "5m",
  "signal_brief_rank": null,
  "deviation_from_brief": null,
  "universe_rationale": "SOLUSDT Binance: high liquidity, 10 bps round-trip fee viable with selective entry (<400 trades / 6 months estimated), strong historical breakout character",
  "escape_route": null,
  "alpha_draft_path": "strategies/_drafts/sol_5m_vol_breakout_alpha.md",
  "params": {
    "breakout_window": 20,
    "atr_period": 14,
    "atr_compression_threshold": 0.012,
    "volume_multiplier": 1.5,
    "volume_sma_period": 20,
    "cooldown_bars": 10,
    "max_hold_bars": 3
  }
}
```
