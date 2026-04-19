---
stage: execution
name: bar_s1_sol_vol_momentum
created: 2026-04-17
target_symbol: SOLUSDT
target_horizon: daily
---

# Execution Design: bar_s1_sol_vol_momentum

## Adverse Selection Assessment

None structural. Entry is MARKET BUY at next-day open — taker order, no passive fill
risk, no adverse selection from queue position. Open slippage on Binance spot is
typically 1-3 bps for a retail-sized SOL position. This is well inside the 10 bps
round-trip fee budget and irrelevant at daily-bar resolution where expected move is
hundreds of bps per holding period.

## Entry Order

- Price: next-day market open (MARKET BUY)
- TTL: N/A — market order, immediate fill
- Bid-drop cancel: disabled — market order
- Rationale: signal is computed at prior day's close; entry at next-day open is
  strictly lookahead-free. No passive limit needed; fill certainty > fill price
  optimization at daily resolution.

## Exit Structure

- Primary exit: signal-driven — MARKET SELL at next-day open when any of the three
  conditions fails (mom_20 <= 0 OR vol_spike <= 1.5 OR rvol_10 >= rvol_30)
- Profit target: none — trend-follow; capping upside truncates the right tail that
  makes momentum strategies profitable
- Stop loss: -8% from entry day's close (hard daily-bar stop)
  - SOL 1-sigma daily move ~3%; -8% = ~2.5 sigma, filters genuine breakdown without
    noise-triggering
  - Checked at daily close (not intraday); fires as MARKET SELL next open
  - Rationale: signal exit is primary but can hold through a -20%+ gap if vol only
    expands slowly; hard stop prevents catastrophic single-session drawdown
- Trailing stop: disabled — alpha-designer explicitly delegated exit entirely to
  signal; introducing trailing would override signal logic
- Max holding period: none — let signal decide

## Position and Session

- Allocation: 100% of available capital (binary: full-long or full-cash)
- Lot size: 1 (full allocation unit; fractional sizing deferred to portfolio layer)
- Max entries per session: 1 (daily bar; one position at a time, binary state)
- Rebalance frequency: once per day at open (after close-of-prior-day signal eval)

## Fee Math

- Round-trip cost: 10 bps (Binance spot: maker/taker ~5 bps each side)
- Expected avg win per trade: ~200-400 bps (multi-day trend hold at 3-5% daily drift)
- Break-even WR (signal exit, no fixed PT): not bounded by classic WR formula —
  trend strategies are right-skewed; require win_rate x avg_win > loss_rate x avg_loss
- At 10 bps round-trip vs ~300 bps avg win target: fee drag is ~3% of gross PnL,
  acceptable
- Hard stop at -8% (800 bps) sets worst-case per-trade loss; requires avg_win > 800 bps
  x (SL_trades / total_trades) to remain positive — expected SL hit rate ~5-15% given
  the vol regime filter pre-screens most breakdowns

## Structural Concerns

1. SIGNAL_EXIT_LAG: Signal computed at T close, exit executed at T+1 open. A -10%
   overnight gap (not uncommon in SOL) means stop_loss_pct=-8% is breached with no
   ability to intervene. Hard stop mitigates but does not eliminate gap risk.
   Acceptable at research-strategy level; production would add a pre-open alert.

2. VOL_FILTER_TIMING: rvol_10 < rvol_30 filter may pass on the day vol begins
   expanding (first day of breakout), then flip at T+1 close and exit T+2 open — one
   bar of adverse exposure. This is structural to daily-bar lag, not an execution flaw.

3. NO_BRIEF_BASELINE: SOLUSDT daily-bar has no signal_brief (data/signal_briefs/ has
   no SOLUSDT entry). PT/SL values are first-principles estimates, not
   empirically-calibrated. Recommend generating a signal brief before production use.

## Implementation Notes for spec-writer

- SL is monitored at daily close (not tick-level): check if close < entry_close * (1 -
  0.08) at end-of-day; if true, execute MARKET SELL at next-day open
- Entry price reference for SL: use entry day's CLOSE (not open) — this is the price
  at which the signal was evaluated and the -8% threshold is most meaningful
- Position state: boolean (in_position: True/False); no partial positions in v1
- Cold-start guard: require >= 30 bars of history before first signal eval
  (warmup for rvol_30 lookback)
- No intraday management required — all decisions are end-of-day

```json
{
  "name": "bar_s1_sol_vol_momentum",
  "hypothesis": "SOL daily momentum confirmed by above-average volume and non-expanding realized volatility identifies persistent trend regimes; exiting to cash when vol expands avoids the -40% drawdown episodes that suppress buy-hold Sharpe.",
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
  "signal_brief_rank": null,
  "deviation_from_brief": null,
  "target_horizon": "daily",
  "target_symbol": "SOLUSDT",
  "entry_execution": {
    "order_type": "MARKET",
    "exec_price": "next_open",
    "stop_loss_pct": -0.08
  },
  "exit_execution": {
    "profit_target_pct": null,
    "trailing_pct": null,
    "signal_exit": true,
    "stop_loss_checked_at": "daily_close",
    "stop_loss_reference": "entry_close"
  },
  "position": {
    "lot_size": 1,
    "allocation_pct": 100,
    "max_entries_per_session": 1
  },
  "structural_concern": [
    "No SOLUSDT signal brief exists — PT/SL are first-principles, not empirically calibrated. Generate brief before production.",
    "Overnight gap risk: -8% SL cannot be enforced intraday; a gap-down open can breach stop by 2-5x.",
    "Signal-exit lag of 1 bar (T close signal -> T+1 open exit) means one-bar adverse exposure on regime change."
  ],
  "alpha_draft_path": "strategies/_drafts/bar_s1_alpha.md",
  "execution_draft_path": "strategies/_drafts/bar_s1_execution.md"
}
```
