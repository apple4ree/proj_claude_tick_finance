---
stage: execution
name: lob_run20260420_iter1
created: 2026-04-20
---

# Execution Design: lob_run20260420_iter1

## Brief Calibration

**Source**: `data/signal_briefs_v2/crypto_lob.json`, `top_robust[0]` (signal_brief_rank=1, 1-indexed).
- Feature: `obi_1`, horizon: `fwd_10t`
- `optimal_exit.pt_bps`: 1.21 bps (p75 of positive entry-bar forward returns)
- `optimal_exit.sl_bps`: 1.64 bps (|p25| of negative entry-bar forward returns)
- `optimal_exit.win_rate_pct`: 40.36% — above 30% floor, no flag needed
- `optimal_exit.mean_fwd_bps`: 0.39 bps
- `optimal_exit.note`: "terminal-return approximation over tick horizon; no intra-horizon path simulation"

**Fee regime**: This is a spread_capture paradigm with LIMIT_AT_BID entry. Maker fee = 0 bps in backtest (Binance maker, near-rebate model). Round-trip cost = 0 bps. This eliminates the standard 4 bps taker break-even concern entirely.

**Win rate check**: 40.36% > 30% threshold — viable. At fee=0, EV = mean_fwd_bps = 0.39 bps > 0.

---

## Adverse Selection Assessment

**Entry type**: Passive LIMIT at best bid. This is the paradigm shift from iter1/iter2 (which used MARKET/taker entry at fee=4 bps, consuming 94.7% of gross edge).

**Adverse selection profile for this signal**: LOW-to-MODERATE, for the following reason:

When `obi_1 >= 0.92` (BTC/ETH) or `>= 0.75` (SOL), the bid side holds 92-96% of top-of-book volume vs ask. Placing a passive BID limit order in this regime is informed by the signal — we are joining a heavily bid-heavy book at a moment when the 10-tick forward mid is statistically biased upward (+0.39 bps avg). The fill condition (price reaches or drops to our bid) still implies adversarial fills to some degree — if a marketable seller hits our bid, they may be informed. However, the OBI gate at the 90th percentile means we only quote when aggregate bid pressure is extreme, making it statistically unlikely that the seller is informed (a momentum seller would need to overcome >92% bid imbalance).

**Reference**: `market_making.md §4.2` (OBI-skew guard): We are using OBI as a directional filter, which inverts the standard adverse-selection logic — when obi_1 >= 0.92, the book is so bid-heavy that adverse selection risk from fills is structurally reduced.

**Residual adverse selection risk**: The 1.17 bps SOL spread gate from prior iterations remains mandatory. A fill on a wide-spread tick implies the spread itself imposes an immediate mark-to-market loss greater than PT. This is the spread_gate_bps guard (`spread_bps >= profit_target_bps` = 1.21 bps rejects entry).

**Prior iteration validation**: iter1/iter2 confirmed time_stop as primary exit at 91% of roundtrips. This implies passive fills are completing within the 10-tick horizon — consistent with the back-of-queue model in LOB (market_making.md §2.2) where bid-heavy environments see sell orders arriving against the bid queue.

**Conclusion**: TTL = 10 ticks (signal horizon), cancel_on_bid_drop_ticks = 1 (immediate cancel if bid drops — reverses OBI regime signal, stale quote risk). These are aggressive adverse-selection protections appropriate for the 100ms LOB cadence.

---

## Entry Order

- **Price**: `bid` — passive LIMIT at best bid. LIMIT_AT_BID = maker fee tier, zero spread crossing.
- **TTL**: 10 ticks — strictly aligned to signal measurement horizon (obi_1 predicts 10-tick forward return; any unfilled order beyond 10 ticks is operating outside the signal's valid window). `market_making.md §2.3` hybrid pattern: cancel if not filled within signal horizon.
- **Bid-drop cancel**: 1 tick — if best_bid drops by 1 tick, cancel immediately. At 100ms cadence and BTC tick size $0.01, a 1-tick bid drop signals the bid-side pressure has shifted; our OBI condition that fired is now stale. This prevents "adverse fill on retreating bid" (fills that occur after market structure reversal). `market_making.md §4.2` OBI-skew guard principle applied to order management.
- **Rationale**: The OBI signal is extremely short-horizon (10 ticks = 1 second). Any residency beyond this window represents pure inventory risk without alpha support. TTL=10 enforces the signal boundary. bid_drop_cancel=1 provides adversarial-fill protection within the TTL window.

---

## Exit Structure

### PT/SL Derivation (Data-Driven)

**Brief baseline (used as-is)**:
- `profit_target_bps = 1.21` (brief's `optimal_exit.pt_bps`, = p75 of positive entry-bar returns)
- `stop_loss_bps = 1.64` (brief's `optimal_exit.sl_bps`, = |p25| of negative entry-bar returns)

**Intra-horizon path consideration**: The brief note flags "terminal-return approximation; no intra-horizon path simulation." At 10 ticks (1 second), the path is extremely short. For BTC, std_fwd_bps=0.69 over 10 ticks. PT=1.21 bps is approximately +1.75 standard deviations above mean (+0.39), meaning it will be hit on some paths during the 10-tick window. This is desirable — when PT is hit early in the path, it locks in above-expected returns. No adjustment needed; intra-path hits at PT=1.21 are a feature, not a problem. (`exit_design.md §0` — MFE capture: PT near MFE distribution center is appropriate for this paradigm.)

**SL assessment**: SL=1.64 bps is |p25| of negative returns. At the 10-tick horizon with time_stop as primary exit (confirmed 91% hit rate from iter1/iter2), SL functions as an emergency protection for large adverse moves only. The brief's value is appropriate — no structural reason to widen or tighten.

**No adjustment from brief optimal**: Both PT and SL used as-is. `deviation_from_brief: {pt_pct: 0.0, sl_pct: 0.0}`.

- **Profit target**: 1.21 bps (LIMIT SELL at entry_mid + 1.21 bps)
- **Stop loss**: 1.64 bps (MARKET SELL — must monitor `snap.bid_px[0]`, NOT `snap.mid`)
- **Trailing stop**: DISABLED — market_making.md §3: MM/spread_capture paradigms are "position-flat-seeking." The edge is in fast round-trip capture, not momentum ride. Trailing stop would extend holding time beyond the 10-tick signal window, converting spread_capture into an unintended directional bet. (`market_making.md §3` exit urgency escalation favors time-stop over trailing for this paradigm.)
- **Time stop**: 10 ticks (primary exit, consistent with 91% rate in prior iterations)

### SL Reference Price Rule

**MANDATORY**: SL monitoring must use `snap.bid_px[0]`, not `snap.mid`.
- For a LONG position, the exit is a MARKET SELL, which executes at the current best bid.
- Using `snap.mid` would compute unrealized PnL against a price that is not achievable for the sell order.
- Lesson from strat_0028 (lesson_024): 50 bps SL set vs mid resulted in 362 bps realized loss (7x overshoot) because mid was higher than bid at execution.
- Correct implementation: `unrealized_bps = (snap.bid_px[0] - entry_mid) / entry_mid * 10000; if unrealized_bps <= -stop_loss_bps and ticks_since_entry >= 5: # MARKET SELL`

---

## Position & Session

- **Lot size**: 1
  - Rationale: spread_capture targets sub-bps edge per round-trip. Lot=1 keeps slippage near zero (fee_aware_sizing.md §3: BTC lot << 1 BTC means slippage ≈ 0 bps). Multiple fast round-trips at lot=1 are preferred over few large-lot trades. At 10% trigger frequency (54k-57k entries over 16h IS), there are abundant opportunities — no need to size up.
- **Max entries per session**: 5
  - Rationale: With TTL=10 ticks and cancel_on_bid_drop=1, many signals will be cancelled before filling. A session cap of 5 allows the strategy to capture repeated strong-OBI windows across the session without over-committing. After SL hit, the 5-entry budget allows 4 more attempts. exit_design.md §2.5 (cooldown re-entry): the session cap of 5 effectively provides cooldown between SL events without needing complex state logic.

---

## Fee Math

- **Maker fee (entry)**: 0 bps (Binance maker, LIMIT_AT_BID)
- **Taker fee (exit SL)**: Exit via MARKET SELL on SL is taker. However, backtest fee_bps=0 for this construct. In production, a 4 bps SL exit adds ~4 bps per SL roundtrip. At 40% WR, ~60% of exits are loss events. If 50% exit via SL (rest via time_stop at near-PT), production fee drag = 0.50 × 0.60 × 4 = 1.2 bps per trade average. This is a deployment consideration flagged to alpha-designer.
- **Round-trip cost (backtest)**: 0 bps
- **Break-even WR at these params (fee=0)**: SL / (PT + SL) = 1.64 / (1.21 + 1.64) = **57.5%** — BUT this is the break-even for a binary PT/SL-only strategy. Since time_stop is the primary exit at tick 10, the actual realized PnL distribution follows the terminal forward return distribution (mean 0.39 bps), not the binary PT/SL outcome. At fee=0, EV > 0 by construction.
- **Fee-to-edge ratio (backtest)**: 0 / (0.39 + 0) = **0%** — fully viable at fee=0.
- **Fee-to-edge ratio (production at 4 bps taker)**: Would be 94.7% (confirmed from iter1 feedback) — non-deployable without maker access.

---

## Multi-Symbol Spread Gate

Per-symbol spread gates are mandatory (no universal gate):
```python
SPREAD_GATES = {"BTCUSDT": 1.21, "ETHUSDT": 1.21, "SOLUSDT": 1.21}
```

The gate equals profit_target_bps. Entry is rejected if `spread_bps >= SPREAD_GATES[symbol]`. This dynamically excludes SOL when its spread is 1.17+ bps (empirically confirmed in iter1/iter2) while allowing SOL participation when spreads tighten. The 1.21 bps gate is equal to the profit_target_bps, which is the structural minimum: a spread >= PT means even a perfect fill-to-opposite-side would not cover the spread cost. (`market_making.md §4.3`: spread regime check — pause if spread < minimum viable.)

---

## Implementation Notes for spec-writer

1. **SL must monitor `snap.bid_px[0]`, not `snap.mid`**. Compute unrealized as `(snap.bid_px[0] - entry_mid) / entry_mid * 10000`. Reference: `pattern_sl_reference_price_and_per_symbol_spread_gate`.

2. **Per-symbol spread gate dict** (reject entry before OBI check):
   ```python
   SPREAD_GATES = {"BTCUSDT": 1.21, "ETHUSDT": 1.21, "SOLUSDT": 1.21}
   ```
   This replaces any universal spread gate. Computed as `floor_bps = tick_size/mid_price * 10000`; gate = profit_target_bps (structural minimum).

3. **OBI thresholds per symbol** (from brief top_robust[0]):
   ```python
   OBI_THRESHOLDS = {"BTCUSDT": 0.918997, "ETHUSDT": 0.942049, "SOLUSDT": 0.749589}
   ```

4. **TTL=10 ticks**: Cancel unexecuted LIMIT order at tick 10 from submission.

5. **cancel_on_bid_drop_ticks=1**: Track `best_bid` at submission time; if current `snap.bid_px[0] < submitted_bid - 1_tick`, cancel order immediately.

6. **time_stop=10 ticks** is the primary exit (consistent with 91% historical rate). PT and SL are emergency exits.

7. **Entry price for PT computation**: Use `entry_mid` (snap.mid at fill time) as reference for PT LIMIT SELL price; use `snap.bid_px[0]` for SL computation (MARKET SELL).

8. **track_mfe=true**: Enable MFE tracking in this iteration to capture capture_pct distribution. Alpha-designer requested this in iter2 seed.

9. **Stateful tracking per symbol**: Maintain `{symbol: {submitted_bid, submit_tick, ticks_since_entry, entry_mid, peak_mid}}` to support TTL and bid_drop_cancel logic without cross-symbol interference.

```json
{
  "strategy_id": null,
  "timestamp": "2026-04-20T00:00:00",
  "agent_name": "execution-designer",
  "model_version": "claude-sonnet-4-6",
  "draft_md_path": "strategies/_drafts/lob_run20260420_iter1_execution.md",
  "alpha": {
    "strategy_id": null,
    "timestamp": "2026-04-20T00:00:00",
    "agent_name": "alpha-designer",
    "model_version": "claude-sonnet-4-6",
    "draft_md_path": "strategies/_drafts/lob_run20260420_iter1_alpha.md",
    "name": "lob_run20260420_iter1",
    "hypothesis": "When top-of-book OBI (obi_1) reaches or exceeds the symbol-specific 90th-percentile threshold (rank-1 from top_robust, avg_IC=0.2514, min_abs_IC=0.2352 across BTC/ETH/SOL), the 10-tick forward mid exhibits a robust upward bias exploitable via passive LIMIT_AT_BID spread_capture entry, converting the previously non-deployable taker-fee-dominated edge into a fee-neutral directional harvest.",
    "entry_condition": "For each 100ms LOB snapshot: (1) reject if spread_bps >= 1.21 bps; (2) compute obi_1; (3) enter long when obi_1 >= symbol-specific threshold (BTC: 0.918997, ETH: 0.942049, SOL: 0.749589); (4) place passive LIMIT order at best_bid price.",
    "market_context": "LOB 100ms cadence, IS 2026-04-19T06:00-22:00 UTC. 10-tick horizon. BTC+ETH gross edge ~+0.226 bps (confirmed by iter1+2); SOL gated by spread.",
    "signals_needed": ["obi(depth=1)", "spread_bps", "best_bid", "mid"],
    "missing_primitive": null,
    "needs_python": true,
    "paradigm": "spread_capture",
    "multi_date": false,
    "parent_lesson": "lesson_20260420_001_lob_spread_gt_pt_blocks_symbol_before_obi_signal_can_work_implementation_bypass_invalidates_cross_symbol_alpha_assessment",
    "signal_brief_rank": 1,
    "universe_rationale": "BTC/ETH/SOL all show positive obi_1 IC above 0.04 robustness floor; SOL gated runtime.",
    "escape_route": null,
    "brief_realism": {
      "brief_ev_bps_raw": 0.39,
      "entry_order_type": "LIMIT_AT_BID",
      "spread_cross_cost_bps": 0.0,
      "brief_horizon_ticks": 10,
      "planned_holding_ticks_estimate": 10,
      "horizon_scale_factor": 1.0,
      "symbol_trend_pct_during_target_window": -1.53,
      "regime_compatibility": "match",
      "regime_adjustment_bps": 0.0,
      "adjusted_ev_bps": 0.39,
      "decision": "proceed",
      "rationale": "LIMIT_AT_BID spread_capture; spread_cross=0; horizon_scale=1; regime match; adjusted_ev=0.39>0; proceed."
    }
  },
  "entry_execution": {
    "price": "bid",
    "ttl_ticks": 10,
    "cancel_on_bid_drop_ticks": 1
  },
  "exit_execution": {
    "profit_target_bps": 1.21,
    "stop_loss_bps": 1.64,
    "trailing_stop": false,
    "trailing_activation_bps": null,
    "trailing_distance_bps": null
  },
  "position": {
    "lot_size": 1,
    "max_entries_per_session": 5
  },
  "deviation_from_brief": {
    "pt_pct": 0.0,
    "sl_pct": 0.0,
    "rationale": "Brief's optimal_exit used as-is (pt=1.21, sl=1.64). Paradigm: spread_capture LIMIT_AT_BID at fee=0. Consulted: market_making.md §3 (position-flat-seeking exit, trailing disabled for MM/spread_capture), market_making.md §4.2 (OBI-skew guard informs cancel_on_bid_drop=1), fee_aware_sizing.md §4 (maker vs taker: passive LIMIT at fee=0 is the correct execution path; taker at 4bps would give 94.7% fee-to-edge from iter1 feedback), exit_design.md §0 (intra-horizon path: PT=1.21 ≈ p75 of positive returns, hitting it during 10-tick path is desirable not problematic; no upward adjustment needed). Win rate 40.36% > 30% floor — no signal weakness flag. Time_stop=10 ticks is the dominant exit (91% rate confirmed iter1/iter2); PT/SL serve as emergency guards only."
  }
}
```
