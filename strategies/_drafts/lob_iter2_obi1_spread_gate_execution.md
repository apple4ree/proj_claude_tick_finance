---
stage: execution
name: lob_iter2_obi1_spread_gate
created: 2026-04-20
parent_iteration: lob_iter1_obi1_spread_capture
signal_brief_rank: 1
---

# Execution Design: lob_iter2_obi1_spread_gate

## Brief Calibration (Mandatory Protocol)

`signal_brief_rank=1` in `data/signal_briefs_v2/crypto_lob.json` resolves to `top_robust[1]`:
- Feature: `obi_5`, horizon: `fwd_10t`
- `optimal_exit.pt_bps = 1.21`, `optimal_exit.sl_bps = 1.71`
- `win_rate_pct = 36.64%` — above the 30% weak-signal threshold; no flag required

Note: The alpha-designer selected `obi_1` (top_robust[0]) but assigned `signal_brief_rank=1`. This is a one-index-off discrepancy. The obi_1 entry (index 0) has `pt_bps=1.21, sl_bps=1.62` — essentially the same PT, with SL 5% tighter. Per-protocol I use `top_robust[1]` as the formal baseline, and the deviations are computed against it. The practical difference is negligible (both pt values are 1.21 bps).

Baseline (top_robust[1]):
- PT baseline: 1.21 bps
- SL baseline: 1.71 bps

Iter-2 mandate (forwarded from iter-1 critique): keep PT=1.09, SL=1.78.

Deviations:
- PT: (1.09 - 1.21) / 1.21 = -0.099 (-9.9%) — within ±20% band
- SL: (1.78 - 1.71) / 1.71 = +0.041 (+4.1%) — within ±20% band

## Adverse Selection Assessment

Entry is MARKET at ask — a taker order. There is NO passive adverse-selection risk in the traditional sense: the strategy buys the best ask at signal time and receives an immediate fill at a known price. There is no queue risk and no bid-drop risk because no limit order is resting in the book.

However, a secondary adverse-selection concern exists at the LOB-HFT scale: the 100ms snapshot cadence means that by the time strategy.py processes the obi_1 signal, the OBI state has advanced 1 tick. In iter-1, this lag did not measurably harm BTC/ETH entries (BTC +0.267 bps, ETH +0.184 bps gross edge confirmed). The time_stop-primary exit architecture (91.3% of exits) effectively absorbs this latency because the nominal holding period (10 ticks = 1 second) is long relative to the 100ms observation lag.

The new spread gate (`spread_bps < profit_target_bps`) is an additional adverse-selection filter: it prevents entry when the bid-ask spread alone would consume the full expected profit. SOL's structural exclusion (spread 1.17 bps > PT 1.09 bps at most ticks) is correct and validated by iter-1.

TTL and bid-drop cancel are not applicable for MARKET orders — there is no resting limit to cancel.

## Entry Order

- Price: `ask` (MARKET taker buy)
- TTL: null — no resting limit; MARKET fills immediately
- Bid-drop cancel: null — not applicable to MARKET entry
- Rationale: MARKET at ask is inherited from iter-1 and confirmed correct for this paradigm. The obi_1 edge is a short-horizon directional impulse (10 ticks = 1 second); taker fill guarantees immediate entry at the moment the OBI threshold is crossed, avoiding queue wait that could cause the signal to decay before fill. At fee=0 (smoke construct), there is no taker cost penalty. The spread gate is the sole adverse-selection control replacing the need for passive limit mechanics.

## Exit Structure

- Profit target: 1.09 bps (LIMIT SELL or engine equivalent)
- Stop loss: 1.78 bps (market-sell equivalent on SL breach)
- Trailing stop: disabled
- Rationale:
  - PT=1.09 bps: iter-1 calibration forwarded as-is per the experiment mandate. This is -9.9% below the brief's `optimal_exit.pt_bps=1.21`; the downward adjustment is justified by intra-horizon path concern — the brief's note explicitly states "terminal-return approximation; no intra-horizon path simulation." At the 10-tick horizon, real mid-price paths that briefly touch the terminal-return level are more common than the brief accounts for, so a slightly tighter PT is more likely to actually trigger at the target price than the nominal 1.21 bps.
  - SL=1.78 bps: iter-1 calibration forwarded as-is. This is +4.1% above the brief's `optimal_exit.sl_bps=1.71`. The small upward relaxation is justified by the 100ms gap risk observed in iter-1: 10 of 11 SL exits overshot spec by an average of 3.5 bps due to the 100ms candence gap between SL threshold crossing and next snapshot. A tighter SL would make this overshoot relatively more severe (larger overshoot-to-spec ratio); the current 1.78 bps SL accepts the gap risk at a measured level.
  - Trailing stop disabled: at 10-tick (1-second) holding, trailing mechanics add negligible value and introduce implementation complexity. The time_stop-primary exit (primary architecture from iter-1) efficiently captures the edge without trailing.
  - time_stop_ticks=10: the primary exit trigger. This is a spec param for strategy-coder; not a schema field in ExecutionHandoff. Must be implemented in strategy.py: after 10 ticks since entry, liquidate at market regardless of PT/SL status.

## SL Reference Price

For this LOB strategy, mid-price monitoring is acceptable because the entry and exit are both MARKET orders in a spread-capture context. Unlike a KRX passive LIMIT entry (where bid-at-fill immediately worsens), the Binance MARKET exit fills at the current bid. The SL monitor should use `snap.mid` for comparison against the entry mid-price, but the actual exit order goes to market at the prevailing bid. The SL overshoot observed in iter-1 (3.5 bps avg) is entirely attributable to the 100ms snapshot gap, not to mid-vs-bid reference confusion.

Implementation note for strategy-coder: monitor `unrealized_bps = (snap.mid - entry_mid) / entry_mid * 10000` for SL, but submit MARKET SELL when breached. The bid-at-fill will be ~half-spread below mid, which for BTC/ETH is negligible (~0.025 bps).

## Position and Session

- Lot size: 1
- Max entries per session: 500
- Max position per symbol: 1 (enforced by entry_condition "no existing position in this symbol")
- Rationale:
  - Lot size=1: inherited from iter-1. At fee=0 smoke construct, lot-size scaling provides no fee-amortization benefit and is deferred to post-viability iterations when real fee analysis is needed.
  - Max entries=500: signal fires at p90 of the OBI distribution, i.e., 10% of all ticks. Over a 16-hour LOB session (~576,000 ticks), the theoretical maximum per-symbol signal count is ~57,600. Cap at 500 per session preserves the smoke-test nature — it is a practical limit on simulation volume, not an alpha-quality gate. This was validated in iter-1 as non-binding (actual fills well below 500 per symbol once the position lock prevents stacking).

## Fee Math

- Round-trip fee (iter-2 smoke): 0 bps (zero-fee construct)
- Real taker fee (Binance): ~4 bps round-trip
- Break-even WR at PT=1.09, SL=1.78 (fee=0): `SL / (PT + SL) = 1.78 / (1.09 + 1.78) = 62.0%`
- Observed WR from iter-1 (BTC+ETH): ~37-38% — well below break-even WR
- Positive PnL despite below-break-even WR at fee=0: achieved by the time_stop primary exit capturing small positive drift across the 10-tick window even on "losing" trades (the time_stop exit fires before the full SL is hit). The WR from the brief (40.0% pooled) and the break-even WR (62%) are not directly comparable because the time_stop architecture means most exits are neither at PT nor at SL — they are timed exits with small positive or negative returns.
- Structural concern on fees: at real 4 bps taker, fee_to_edge_ratio=94.7% — strategy is non-deployable with MARKET orders. Iter-3 must evaluate LIMIT maker entry. This is a known issue forwarded from iter-1; iter-2 remains a diagnostic smoke run at fee=0.

## Spread Gate: Implementation Notes for Spec-Writer

The spread gate is the sole new constraint in iter-2. It must be enforced in strategy.py as a pre-entry check, executed BEFORE the OBI threshold check:

```python
PROFIT_TARGET_BPS = 1.09  # must match spec.yaml profit_target_bps

for symbol in symbols:
    snap = snapshots[symbol]
    spread_bps = (snap.ask_px[0] - snap.bid_px[0]) / snap.mid * 10000
    
    # Spread gate: reject entry if spread consumes full profit target
    if spread_bps >= PROFIT_TARGET_BPS:
        continue  # structural loss — skip this symbol this tick
    
    # OBI threshold gate (per-symbol)
    obi_1 = (snap.bid_sz[0] - snap.ask_sz[0]) / (snap.bid_sz[0] + snap.ask_sz[0])
    if obi_1 < OBI_THRESHOLD[symbol]:
        continue
    
    # Position gate
    if position[symbol] > 0:
        continue
    
    # Entry: MARKET at ask
    submit_market_buy(symbol, lot_size=1)
```

The spread gate must use `PROFIT_TARGET_BPS` directly (not a hardcoded constant separate from spec) to ensure the gate threshold tracks any future PT recalibration automatically.

Note: this is NOT a per-symbol spread gate in the multi-symbol KRX sense (where different symbols have physically different tick sizes). Here, spread_bps is already normalized to basis points, and PT=1.09 bps is the universal rejection threshold. The effect is symbol-selective (SOL typically excluded, BTC/ETH typically allowed) but the logic is symbol-agnostic.

## Iter-2 Changes vs Iter-1

| Parameter | Iter-1 | Iter-2 | Reason |
|---|---|---|---|
| Entry | MARKET ask | MARKET ask | unchanged |
| PT | 1.09 bps | 1.09 bps | unchanged |
| SL | 1.78 bps | 1.78 bps | unchanged |
| time_stop | 10 ticks | 10 ticks | unchanged |
| Trailing | disabled | disabled | unchanged |
| Spread gate | absent | `spread_bps < PT` | new — lesson_20260420_001 |
| OBI gate | buggy (SOL bypass) | fixed | lesson_20260420_001 |
| lot_size | 1 | 1 | unchanged |
| max_entries | 500 | 500 | unchanged |

The execution design is identical to iter-1. The only changes are in strategy.py implementation correctness (OBI gate fix + spread gate addition), not in the order mechanics parameters.

```json
{
  "strategy_id": null,
  "timestamp": "2026-04-20T06:30:00",
  "agent_name": "execution-designer",
  "model_version": "claude-sonnet-4-6",
  "draft_md_path": "strategies/_drafts/lob_iter2_obi1_spread_gate_execution.md",
  "alpha": {
    "strategy_id": null,
    "timestamp": "2026-04-20T06:00:00",
    "agent_name": "alpha-designer",
    "model_version": "claude-sonnet-4-6",
    "draft_md_path": "strategies/_drafts/lob_iter2_obi1_spread_gate_alpha.md",
    "name": "lob_iter2_obi1_spread_gate",
    "hypothesis": "When obi_1 >= per-symbol p90 threshold AND spread_bps < profit_target_bps, a 10-tick directional edge exists in BTC/ETH (rank-1 from top_robust); SOL is structurally gated out by its wider spread.",
    "entry_condition": "Enter LONG when: (1) obi_1 >= threshold_per_symbol[symbol] (BTC=0.91469, ETH=0.942049, SOL=0.749589); (2) spread_bps < profit_target_bps [spread gate - new in iter-2]; (3) no existing position in this symbol.",
    "market_context": "24/7 crypto LOB (Binance 100ms snapshots); direction-agnostic at 10-tick horizon; SOL expected excluded by spread gate in most ticks; active universe effectively BTC+ETH until SOL spread normalizes.",
    "signals_needed": ["obi(depth=1)", "spread_bps"],
    "missing_primitive": null,
    "needs_python": true,
    "paradigm": "spread_capture",
    "multi_date": true,
    "parent_lesson": "lesson_20260420_001_lob_spread_gt_pt_blocks_symbol_before_obi_signal_can_work_implementation_bypass_invalidates_cross_symbol_alpha_assessment",
    "signal_brief_rank": 1,
    "universe_rationale": "BTC/ETH/SOL full standard universe; SOL self-excludes via spread gate at runtime, preserving diagnostic visibility into SOL spread regime; BTC+ETH confirmed positive edge from iter-1 (+0.267/+0.184 bps at fee=0).",
    "escape_route": "If spread gate excludes >90% of SOL ticks and BTC+ETH combined n_trade falls below statistical floor, pivot iter-3 to passive LIMIT_AT_BID maker entry to restore full 3-symbol universe viability.",
    "brief_realism": {
      "brief_ev_bps_raw": 0.38,
      "entry_order_type": "MARKET",
      "spread_cross_cost_bps": 0.05,
      "brief_horizon_ticks": 10,
      "planned_holding_ticks_estimate": 10,
      "horizon_scale_factor": 1.0,
      "symbol_trend_pct_during_target_window": null,
      "regime_compatibility": "unknown",
      "regime_adjustment_bps": 0.0,
      "adjusted_ev_bps": 0.33,
      "decision": "proceed_with_caveat",
      "rationale": "Per microstructure_primer.md §1.1, BTC/ETH spread at top-of-book averages ~0.05 bps half-spread cost for MARKET entry; SOL is excluded by the spread gate so its 1.17 bps spread does not enter the EV calculation. Per fee_aware_sizing.md §2, fee_to_edge_ratio at real 4-bps taker = 94.7% — this iteration runs at fee=0 (smoke construct) confirming the gate fix; maker-only execution must be adopted before live deployment. Regime direction for 2026-04-19 LOB sample is unknown (single-day, no macro context), so regime_adjustment=0 and proceed_with_caveat is the appropriate decision pending multi-day OOS confirmation."
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
    "sl_pct": 0.041,
    "rationale": "Baseline is top_robust[1] (obi_5/fwd_10t): pt_bps=1.21, sl_bps=1.71. PT held at iter-1 value 1.09 bps (-9.9% from brief): intra-horizon path concern — brief note states terminal-return approximation with no path simulation; tighter PT is more likely to trigger on real intra-horizon path than the nominal 1.21 bps terminal value, consistent with the time_stop-primary exit architecture where most exits are timed rather than limit-triggered. SL held at iter-1 value 1.78 bps (+4.1% from brief): gap-risk compensation — iter-1 observed 10/11 SL exits overshot spec by avg 3.5 bps due to 100ms cadence gap; a slightly wider formal SL accepts the known gap risk at a calibrated level without masking it. Both deviations are within the ±20% band. Note: signal_brief_rank=1 technically resolves to obi_5 in the brief, but the alpha-designer targets obi_1 (index 0); obi_1 has identical pt_bps=1.21 and sl_bps=1.62, making the SL deviation against obi_1 baseline +9.9% — still within band."
  }
}
```
