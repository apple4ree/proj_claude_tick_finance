---
stage: execution
name: crypto_1h_btc_mean_rev_168h_iter1
created: 2026-04-17
---

# Execution Design: crypto_1h_btc_mean_rev_168h_iter1

## Adverse Selection Assessment

**Risk level: NONE.** Entry is MARKET BUY at bar close (taker). There is no order queue, no passive limit fill mechanics, and no bid-drop risk. The signal executes against the best ask at the bar's close price. The only cost is the 4 bps round-trip taker fee (2 bps per leg), which is already priced into the brief's EV calculation. No TTL or bid-drop cancel parameters are needed or applicable.

BTC-specific caveat: the raw entry-level mean_fwd_bps for BTCUSDT is -10.07 bps (WR 36.64%), which is weak. The brief's pooled optimal exit (PT/SL filter) is load-bearing — it carves the profitable subset from a noisy population. Both PT and SL exits must be enforced; a time-exit-only variant would have negative expectancy on BTC alone.

## Entry Order

- Price: `ask` (MARKET BUY at bar close; taker)
- TTL: none — MARKET order fills immediately at the close of the triggering bar
- Bid-drop cancel: disabled — not applicable to MARKET orders
- Rationale: Bar-level resolution does not support intra-bar limit queue modeling. MARKET BUY is the only appropriate entry type for a signal that fires at bar close. There is no passive-fill adverse selection to mitigate.

## Exit Structure

- Profit target: **1312.07 bps** (LIMIT SELL at entry_price × (1 + 0.131207)); no deviation from brief
- Stop loss: **450.79 bps** (MARKET SELL when mark-to-market loss reaches this threshold; monitor bar close price)
- Trailing stop: **enabled**
  - Activation: **600.0 bps** profit (once position gains 6%, trailing kicks in)
  - Distance: **300.0 bps** from peak (if price retraces 3% from peak, close position)
- Rationale:
  - PT 1312.07 bps kept at brief's computed optimal. BTC raw edge is weak (-10 bps mean_fwd), so the PT must not be raised (phantom) or lowered (leaves money on table for the subset that does recover strongly). 0% deviation.
  - SL 450.79 bps kept at brief's computed optimal. BTC forward return std is 479.66 bps; a tighter stop would whipsaw frequently. 0% deviation.
  - Break-even WR = 450.79 / (1312.07 + 450.79) = **25.6%**. Required pooled WR from brief is 61.96%, giving 36+ percentage point headroom above break-even. This is robust.
  - Trailing stop: Given the 168-bar hold window and BTC's elevated volatility, a trailing stop protects accumulated gains once the reversion is well underway. Activation at 600 bps (roughly 46% of PT distance) ensures the trailing only engages after meaningful profit is realized. Distance of 300 bps is within the SL envelope (300 < 450), maintaining tighter protection once activated. This prevents a large winner from becoming a loser on a late-stage reversal, which is a material risk for a 7-day hold on BTC.

## Position & Session

- Lot size: 1
- Max entries per session: 1 (interpreted as per-day for 24/7 crypto)
- Rationale:
  - Lot size 1 is standard for bar-level crypto strategies. The engine models one unit (BTC position) per entry. No pyramiding is intended.
  - Signal fires ~10% of bars (~2.4 bars/day). With a 168-bar hold, allowing multiple concurrent entries would create unintended pyramid positions. Cap at 1 entry per day to enforce single-position discipline while the prior trade is still active. If a new signal fires while a position is open, it is suppressed by max_position constraint.

## Fee Math

- Round-trip cost: 4 bps (2 bps buy taker + 2 bps sell taker, Binance)
- Break-even WR at PT=1312 / SL=451: **450.79 / (1312.07 + 450.79) = 25.6%**
- Brief pooled WR: 61.96% — edge above break-even: **+36.4 percentage points**
- BTC-specific WR warning: the raw BTCUSDT entry-level WR at the unfiltered threshold is 36.64%, which is above break-even (25.6%) but materially below the pooled 61.96%. The PT/SL carving from the brief's optimal_exit is critical to achieving the pooled WR. If BTC-only WR in backtest falls below 35%, flag to alpha-designer that the signal edge on BTC alone may be insufficient.
- EV estimate: brief's adjusted EV 414.49 bps >> 4 bps fee. Fee is immaterial at this scale.

## Deviation From Brief

- PT: 0% deviation (1312.07 bps, unchanged)
- SL: 0% deviation (450.79 bps, unchanged)
- Trailing stop (not in brief): added as discretionary enhancement to lock in profits on the 168-bar hold; does not change the PT/SL floor parameters

## Implementation Notes for spec-writer

1. **Entry price reference**: Record `entry_price = bar.close` at the time of MARKET BUY. This is the reference for all subsequent PT/SL/trailing calculations.

2. **PT implementation**: Place a resting LIMIT SELL at `entry_price * (1 + 1312.07/10000)`. Cancel and re-place if bar.close drifts significantly (or use a persistent resting order at fixed price).

3. **SL implementation**: Monitor `bar.close` each bar (not mid or bid — this is bar-level data with OHLC, use `close` as the mark price). If `(bar.close - entry_price) / entry_price * 10000 <= -450.79`, submit MARKET SELL at next bar open (or bar close, depending on engine convention).

4. **Trailing stop state**:
   - Track `peak_price = max(bar.close since entry)`
   - Once `(peak_price - entry_price) / entry_price * 10000 >= 600.0`, trailing is activated
   - After activation: if `(bar.close - peak_price) / peak_price * 10000 <= -300.0`, submit MARKET SELL
   - Update `peak_price` every bar

5. **Time stop**: Exit at bar 168 since entry if neither PT, SL, nor trailing stop has triggered. This is the `horizon_bars = 168` ceiling from the brief.

6. **Concurrent position guard**: If a new signal fires (roc_168h <= -0.056226) while a position is already open, suppress entry. max_entries_per_session=1 per day; max_position_per_symbol=1.

7. **No SL reference price confusion**: Unlike KRX tick strategies, this is bar-level data. Use `bar.close` as the mark price for all unrealized PnL monitoring. There is no bid/ask spread to account for inside bars.

```json
{
  "name": "crypto_1h_btc_mean_rev_168h_iter1",
  "hypothesis": "When BTCUSDT has lost more than 5.6% over the trailing 168 hours, the market has overextended to the downside and exhibits mean-reverting behavior over the subsequent 168-hour window — exploiting weekly return reversal (rank-0 from signal_brief).",
  "entry_condition": "Enter LONG on BTCUSDT at bar close via MARKET BUY when roc_168h <= -0.056226 (168-bar trailing return in bottom 10th percentile).",
  "market_context": "BTCUSDT 1h bars, 24/7 Binance spot market, ranging to mildly uptrending regime (IS window +2.3% BTC trend). Signal fires ~10% of bars. No time-of-day restriction.",
  "signals_needed": ["roc_168h"],
  "missing_primitive": null,
  "needs_python": true,
  "paradigm": "mean_reversion",
  "multi_date": true,
  "parent_lesson": "crypto_1h_btc_rsi_atr: BTC mean-reversion on 1h bars viable with selective entry (Sharpe +1.32, IR +1.039, 4-Gate PASS)",
  "entry_execution": {
    "price": "ask",
    "ttl_ticks": null,
    "cancel_on_bid_drop_ticks": null
  },
  "exit_execution": {
    "profit_target_bps": 1312.07,
    "stop_loss_bps": 450.79,
    "trailing_stop": true,
    "trailing_activation_bps": 600.0,
    "trailing_distance_bps": 300.0
  },
  "position": {
    "lot_size": 1,
    "max_entries_per_session": 1
  },
  "deviation_from_brief": {
    "pt_pct": 0.0,
    "sl_pct": 0.0,
    "rationale": "PT and SL kept exactly at brief's computed optimal_exit values (1312.07 / 450.79 bps). BTC's weak raw entry edge (-10 bps mean_fwd) means the PT/SL carving is load-bearing — any deviation risks either phantom targets (PT raised) or excess whipsaw (SL tightened). Trailing stop added as a discretionary enhancement (not a brief deviation) to protect accumulated gains across the 168-bar hold window."
  },
  "alpha_draft_path": "strategies/_drafts/crypto_1h_btc_mean_rev_168h_iter1_alpha.md",
  "execution_draft_path": "strategies/_drafts/crypto_1h_btc_mean_rev_168h_iter1_execution.md"
}
```
