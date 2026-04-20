---
stage: execution
name: lob_iter1_obi1_spread_capture
created: 2026-04-20
---

# Execution Design: lob_iter1_obi1_spread_capture

## Adverse Selection Assessment

**Risk level: LOW-MODERATE for MARKET entry.**

Entry is MARKET BUY (taker), not passive LIMIT. Adverse selection in the traditional sense (passive fill at bid when price is falling) does not apply — the fill is guaranteed at the current ask price at time of signal fire.

However, there is a subtler adverse selection concern: OBI_1 at the 90th percentile (>91% bid dominance for BTC) represents a fleeting state. If the LOB snapshot that triggers the signal is already 100ms stale by the time the engine submits the order (5ms latency + queue), the OBI condition may have partially reversed. At 100ms cadence this is a 5% staleness window — acceptable, but real fills will see slightly diluted conditions relative to the signal snapshot.

The alpha-designer's choice of MARKET entry is correct for this horizon. A passive LIMIT at bid faces two structural problems when OBI_1 is heavily bid-skewed:
1. Sellers are scarce — bid limit may not fill before the 10-tick window expires.
2. If OBI_1 is genuinely informative, the mid will tick up, moving the best ask away from a resting bid limit.

Market_making.md §2.1 (price-improve) and §2.3 (hybrid TTL) are designed for market-making where passive fill at spread is the goal. Here the goal is directional signal capture at a 1-second horizon, which requires fill certainty above spread capture. MARKET entry is retained.

## Entry Order

- **Price**: ask (MARKET BUY equivalent — aggressive taker fill at best ask)
- **TTL**: none — MARKET fills immediately; TTL not applicable
- **Bid-drop cancel**: disabled — no resting limit order to cancel
- **Rationale**: MARKET entry is mandated by the signal's ephemeral nature (10-tick / 1-second horizon). A passive LIMIT at bid would face fill uncertainty in a heavily bid-skewed LOB. Market_making.md §2 queue-position analysis confirms that back-of-queue fill in a skewed book delivers stale fills. Latency (5ms) is well within one 100ms snapshot interval; staleness risk is bounded.

**Note on paradigm label**: the strategy is labeled `spread_capture` by the alpha-designer, which conventionally implies passive quoting. In this implementation, it is a directional taker entry triggered by LOB imbalance, which is more accurately "LOB-informed momentum capture." The entry mechanics reflect this: aggressive entry to ensure fill at the signal-fire price.

## Exit Structure

### Brief Baseline (top_robust[0])
- PT: 1.21 bps (p75 of positive 10-tick terminal returns)
- SL: 1.62 bps (|p25| of negative 10-tick terminal returns)
- WR: 40.0% (fraction of 10-tick terminal returns > 0)
- Note: "terminal-return approximation; no intra-horizon path simulation"

### Warning — WR = 40% is above the 30% floor but below the break-even threshold for pure PT/SL exits

Under static PT/SL monitoring (tick-by-tick), break-even WR = SL/(PT+SL).
- At brief's baseline: 1.62/(1.21+1.62) = 57.2% — above the observed 40% terminal WR.
- This means static PT/SL exits CANNOT be the primary exit mechanism; they must function as safety caps.

**Primary exit = time stop at tick 10.** The brief's 40% WR and +0.38 bps mean are measured at the 10-tick terminal snapshot. The strategy collects this terminal return distribution by holding for the full 10-tick window. PT and SL are early-exit caps for extreme paths only.

### Adjusted PT/SL

**PT: 1.09 bps** (reduced 9.9% from brief's 1.21 bps)
- Rationale: The brief's 1.21 bps is the p75 of positive terminal returns. On intra-path monitoring (100ms ticks), this threshold is reached by fewer trades than the terminal distribution implies, because the mid-price path at 100ms resolution is noisy and mean-reverting within the 1-second window. Reducing PT to approximately p50 of positive terminal returns improves the actual PT-hit rate on winning trades that spike early, without becoming phantom. Exit_design.md §6 anti-pattern #1 warns against PT set above MFE distribution; reducing modestly guards against this.
- Deviation from brief: (1.09 − 1.21) / 1.21 = **−9.9%** (within ±20% band).

**SL: 1.78 bps** (increased 9.9% from brief's 1.62 bps)
- Rationale: The brief's SL of 1.62 bps is the |p25| of negative terminal returns measured at tick 10. However, intra-horizon paths over 10 × 100ms ticks will regularly dip below −1.62 bps even on trades that end positive at tick 10 (standard deviation ≈ 0.68–1.06 bps across symbols — one standard deviation below entry is already at ~−0.7 bps, two sigma at −1.4 bps). Widening SL by 10% to 1.78 bps reduces false stops on trades where the brief predicts a positive terminal return. Market_making.md §3 exit urgency escalation notes that forced exits before the natural exit window destroy value; the 10-tick SL widening provides that breathing room. Deviation from brief: (1.78 − 1.62) / 1.62 = **+9.9%** (within ±20% band).

- **Trailing stop**: disabled. At a 10-tick (~1 second) horizon, trailing activation and distance must be sub-bps. Crypto LOB mid-price noise at 100ms cadence routinely exceeds 0.5 bps per tick. A trailing stop will fire on noise, not on genuine mean-reversion of the profit. Exit_design.md §2.2 explicitly warns: "당 안 쓰지 말 것: 데이터 자체가 적어 ATR이 noisy할 때 (예: 100 bars 미만)." At 10-tick scale, ATR is purely noise.

### Time Stop (Implementation)
- **time_stop_ticks = 10** — mandatory. The primary exit. Strategy.py must track ticks_since_entry and force MARKET SELL at tick 10 if PT and SL have not fired. This is the mechanism that delivers the +0.38 bps mean terminal return.

## Position & Session

- **Lot size**: 1
  - With fee = 0 bps in backtest, lot-size amplification provides no edge-quality improvement (prior lesson: lot_size_scaling_amplifies_nominal_pnl_linearly). At tick-level with 57,000+ potential entries per symbol in 16h IS, lot_size=1 provides ample aggregate PnL signal.
- **Max entries per session**: 500
  - The 16h IS window contains ~576,000 snapshots per symbol. At 10% entry rate ≈ 57,600 triggered snapshots, but position holding blocks re-entry for 10 ticks. Effective capacity ≈ 57,600 / 10 = 5,760 non-overlapping entries per symbol. Capping at 500 per session provides statistical depth for meaningful IS evaluation while preventing unbounded exposure.
  - With 3 symbols active simultaneously, total session entries ≤ 1,500.

## Fee Math

- **Round-trip cost**: 0.0 bps (Binance spot maker fee = 0; backtest fee_bps = 0.0 per brief)
- **Adjusted EV**: +0.115 bps per trade (alpha-designer's brief_realism calculation)
- **Break-even WR (under primary time-stop exit)**: N/A — time-stop collects terminal return regardless of WR. With fee=0, any positive mean_fwd_bps (0.38 bps at terminal tick) is viable.
- **Break-even WR (under static PT/SL exit)**: SL/(PT+SL) = 1.78/(1.09+1.78) = 62.0% — this exceeds observed 40% WR. This confirms PT/SL must NOT be the primary exit path. They are protective caps for extreme paths only.
- **Expected PnL per trade (fee=0)**: +0.38 bps at time-stop; early PT capture at +1.09 bps for right-tail trades; early SL loss at −1.78 bps for left-tail crashes.

## Thin Edge Warning

Adjusted EV = 0.115 bps. This is extremely thin. Key risks:
1. **Any taker fee eliminates the edge entirely.** At Binance standard taker (4 bps), round-trip cost = 4 bps >> 0.38 bps mean return. Strategy is only viable in a zero-fee backtest or with maker-rebate execution.
2. **Single-day IS window** (2026-04-19, 16h). This is insufficient for regime generalization. The alpha is calibrated on a single intraday session; OOS degradation is likely.
3. **Regime partial compatibility** (alpha-designer mark). The +0.38 bps mean could evaporate under different intraday volatility regimes.

## Implementation Notes for spec-writer

1. **Primary exit = time stop at tick 10.** Strategy.py must implement a `ticks_since_entry` counter and force MARKET SELL at tick 10. Without this, the terminal-return EV of +0.38 bps is not captured. This is the most critical correctness requirement.

2. **PT and SL are secondary caps only.** Check PT and SL every tick, but the statistical expectation is that most exits will be time-stop exits.

3. **SL reference price**: Use `snap.ask_px[0]` at entry to set the entry reference price. For unrealized PnL monitoring on a LONG position, use:
   ```python
   unrealized_bps = (snap.mid - entry_mid) / entry_mid * 10000
   ```
   On exit via SL, submit MARKET SELL (fills at bid). The SL condition should be monitored using `snap.mid` not `snap.bid_px[0]` for the 10-tick LOB context since mid is the fair-value reference for OBI signals. Note: the KRX lesson_024 SL-reference rule applies to KRX tick data where bid/ask spreads are wide; at Binance crypto LOB with spread ~0.13 bps, mid vs bid divergence is negligible and mid-based SL is acceptable.

4. **No per-symbol spread gate required**: Binance spot BTC/ETH/SOL all have spreads < 0.2 bps, and fee is 0 bps. The spread gate pattern (pattern_sl_reference_price_and_per_symbol_spread_gate) applies to KRX where spreads are multi-tick and entry costs are significant. In the crypto LOB context, spread gate would block virtually all entries (OBI_1 > 91% threshold implies heavily skewed book where spread may be elevated momentarily).

5. **Entry price tracking**: Record `entry_mid = snap.mid` and `entry_ask = snap.ask_px[0]` at fill time for unrealized PnL computation. The MARKET BUY fills at ask; nominal cost is `snap.ask_px[0]`.

6. **Position re-entry**: After each time-stop exit at tick 10, immediately allow re-entry if the next snapshot fires the OBI signal again. `max_entries_per_session = 500` allows ample re-entry.

7. **Per-symbol thresholds**: Implement as a dict lookup, not a universal value:
   ```python
   OBI_THRESHOLDS = {
       "BTCUSDT": 0.91469,
       "ETHUSDT": 0.942049,
       "SOLUSDT": 0.749589,
   }
   ```

```json
{
  "strategy_id": null,
  "timestamp": "2026-04-20T00:00:00",
  "agent_name": "execution-designer",
  "model_version": "claude-sonnet-4-6",
  "draft_md_path": "strategies/_drafts/lob_iter1_obi1_spread_capture_execution.md",
  "alpha": {
    "strategy_id": null,
    "timestamp": "2026-04-20T00:00:00",
    "agent_name": "alpha-designer",
    "model_version": "claude-sonnet-4-6",
    "draft_md_path": "strategies/_drafts/lob_iter1_obi1_spread_capture_alpha.md",
    "name": "lob_iter1_obi1_spread_capture",
    "hypothesis": "When top-of-book OBI_1 reaches the 90th-percentile threshold per symbol, bid-side dominance at best-level predicts upward mid-price movement over the subsequent 10 snapshots (~1s), yielding 0.38 bps expected value at zero maker fee; this is rank-0 from top_robust (obi_1 x fwd_10t, avg_ic=0.2505, min_abs_ic=0.2352 across BTC/ETH/SOL).",
    "entry_condition": "Enter MARKET BUY on a symbol when obi(depth=1) >= symbol-specific 90th-percentile threshold: BTCUSDT >= 0.91469, ETHUSDT >= 0.942049, SOLUSDT >= 0.749589. Thresholds taken as-is from signal brief threshold_per_symbol.",
    "market_context": "crypto_lob (Binance 100ms LOB snapshots); 24/7 continuous; IS window 2026-04-19 06:00-22:00 UTC; signal fires at ~10% of snapshots (90th percentile selectivity); no intraday session gate needed at 1-second horizon.",
    "signals_needed": ["obi(depth=1)"],
    "missing_primitive": null,
    "needs_python": true,
    "paradigm": "spread_capture",
    "multi_date": false,
    "parent_lesson": null,
    "signal_brief_rank": 1,
    "universe_rationale": "BTCUSDT/ETHUSDT/SOLUSDT pass cross-symbol robustness filter with same-sign IC (BTC=0.253, ETH=0.263, SOL=0.235) and min_abs_ic=0.2352 >> 0.04 floor — strongest robustness of all LOB signals in brief.",
    "escape_route": null,
    "brief_realism": {
      "brief_ev_bps_raw": 0.38,
      "entry_order_type": "MARKET",
      "spread_cross_cost_bps": 0.065,
      "brief_horizon_ticks": 10,
      "planned_holding_ticks_estimate": 10,
      "horizon_scale_factor": 1.0,
      "symbol_trend_pct_during_target_window": 0.5,
      "regime_compatibility": "partial",
      "regime_adjustment_bps": 0.2,
      "adjusted_ev_bps": 0.115,
      "decision": "proceed_with_caveat",
      "rationale": "MARKET entry at half-spread cost (0.065 bps per microstructure_primer §1.4 BTC spread ~0.13 bps) preserves fill certainty at the ephemeral 1-second OBI signal horizon; regime marked partial due to single-day IS window (2026-04-19 only) per market_making.md §0 adverse selection caveat; adjusted EV 0.115 bps is positive but thin — any taker fee above 0 bps eliminates the edge entirely."
    }
  },
  "entry_execution": {
    "price": "ask",
    "ttl_ticks": null,
    "cancel_on_bid_drop_ticks": null
  },
  "exit_execution": {
    "profit_target_bps": 1.09,
    "stop_loss_bps": 1.78,
    "trailing_stop": false,
    "trailing_activation_bps": null,
    "trailing_distance_bps": null
  },
  "position": {
    "lot_size": 1,
    "max_entries_per_session": 500
  },
  "deviation_from_brief": {
    "pt_pct": -0.099,
    "sl_pct": 0.099,
    "rationale": "PT reduced 9.9% from brief's 1.21 bps to 1.09 bps: exit_design.md §6 anti-pattern #1 (phantom PT) — brief's 1.21 bps is p75 of positive terminal returns; on intra-path monitoring at 100ms cadence over 10 ticks, this threshold is reached by fewer trades than the terminal distribution implies due to path noise and mean-reversion within the 1-second window. Reducing to ~p50 of positive returns improves actual capture rate. SL raised 9.9% from brief's 1.62 bps to 1.78 bps: intra-horizon path concern per brief's note ('terminal-return approximation; no intra-horizon path simulation') — at 100ms tick resolution, path std = 0.68–1.06 bps (per-symbol entry_stats), so a −1.62 bps draw is reachable on normal paths even on winning trades. Widening by 10% reduces false stops. Market_making.md §3 exit urgency escalation confirms that premature forced exits destroy value before natural exit window. Primary exit remains time_stop at 10 ticks; PT/SL are caps for extreme paths only."
  }
}
```
