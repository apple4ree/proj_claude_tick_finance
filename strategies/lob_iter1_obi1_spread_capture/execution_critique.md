---
stage: execution_critique
strategy_id: lob_iter1_obi1_spread_capture
created: 2026-04-20
critic: execution-critic
---

# Execution Critique: lob_iter1_obi1_spread_capture

## Invariant-Aware Preamble

`invariant_violations`: 0. `invariant_violation_count`: 0. `invariant_violation_by_type`: empty.

The formal invariant checker found zero violations. However, this masks a critical execution-level defect: **10 of 11 SL exits exceeded the spec's −1.78 bps stop-loss threshold**, with realized losses ranging from −2.33 to −7.40 bps. The spec-invariant checker tolerates ±10 bps for `sl_overshoot`, so none of these breaches crossed the formal threshold, but they are still an execution quality failure — the SL is not binding when prices gap across the trigger level between 100ms snapshots. This is a discrete-time monitoring latency artifact, not a code bug, but it contributes to avg_sl_bps = −3.48 bps vs spec −1.78 bps.

`clean_pnl` / `bug_pnl` / `clean_pct_of_total`: fields absent (attribute_pnl.py not run). No PnL attribution available.

---

## 1. Exit Tag Distribution

| Exit Tag | Count | % of Total | Avg PnL (bps) | WR |
|---|---|---|---|---|
| time_stop | 1,369 | 91.3% | −0.264 | 19.6% |
| profit_target | 120 | 8.0% | +1.203 | 100.0% |
| stop_loss | 11 | 0.7% | −3.485 | 9.1% (1/11 wins) |
| eod / trailing | 0 | 0.0% | — | — |

**Primary finding**: time_stop at tick 10 is firing 91.3% of the time. This is structurally correct per the execution design intent — the execution-designer explicitly stated "primary exit = time stop at tick 10." However, the time_stop path averages −0.264 bps portfolio-wide (19.6% WR), which is the opposite of the expected +0.38 bps EV from the brief. The sign inversion is almost entirely attributable to SOLUSDT's structural drag (see §4).

PT fires at 8.0% of trades. Each PT exit averages +1.203 bps — slightly above spec's +1.09 bps, indicating occasional PT overshoot (two exits at +1.63 and +1.17 bps vs spec; within the ±20 bps invariant tolerance). SL fires at 0.7% (11 trades) but with average loss of −3.485 bps, nearly double the spec's −1.78 bps threshold, due to snapshot-frequency monitoring lag.

Per-symbol exit breakdown:

| Symbol | n_tp (%) | n_sl (%) | n_ts (%) | ts_avg_bps | ts_WR |
|---|---|---|---|---|---|
| BTCUSDT | 68 (13.6%) | 2 (0.4%) | 430 (86.0%) | +0.147 | 27.2% |
| ETHUSDT | 37 (7.4%) | 3 (0.6%) | 460 (92.0%) | +0.113 | 32.8% |
| SOLUSDT | 15 (3.0%) | 6 (1.2%) | 479 (95.8%) | −0.994 | 0.0% |

SOLUSDT's time_stop WR is literally 0.0% across 479 trades — zero winning time_stop exits. BTCUSDT and ETHUSDT both show positive time_stop avg (+0.147 and +0.113 bps respectively), which is the expected signal behavior. This divergence is not an exit calibration failure for BTC/ETH — it is the SOLUSDT threshold bypass bug identified by alpha-critic propagating into exit outcome data.

---

## 2. PT/SL Calibration Assessment

**SL/TP ratio**: 11/120 = **0.092**. This is far below the danger threshold of >3. On its face, SL almost never fires relative to PT — the PT fires 10.9× more often than SL. This sounds favorable but is misleading: the time_stop is the overwhelmingly dominant exit mechanism (91.3%), and SL exits undercount the losses because SOLUSDT losses exit via time_stop (−0.994 bps avg) not via SL (SOL's OBI stays near zero, no dramatic directional move triggers the SL within 10 ticks — prices just drift down by the spread).

**SL calibration issue**: Spec sets SL = −1.78 bps but avg realized SL loss = −3.485 bps. 10 of 11 SL exits are worse than spec, with worst case −7.40 bps (ETHUSDT). Cause: at 100ms tick cadence, the price can gap by 1–2 tick levels between monitoring snapshots, so the SL trigger price is crossed before the engine can issue the exit order — realized exit is at the next available mid/bid, which can be 2–6 bps below trigger. This is a monitoring-frequency artifact, not a code error. Exit_design.md §3 decision table notes the "SL widened to MAE.p95" anti-pattern is not the issue here; rather the issue is gap risk at 1-second resolution with tick-level price moves.

**PT calibration**: Avg realized PT = +1.203 bps vs spec +1.09 bps. Minor positive slippage (occasional exit slightly above trigger on next available mid). PT is functioning as designed.

**Break-even WR for static PT/SL**: Using fee_aware_sizing.md §6 formula — `BE_WR = (SL + fee) / (PT + SL)`:
- At fee = 0: BE_WR = 1.78 / (1.09 + 1.78) = **62.0%**. The observed overall WR = 26.0% is far below 62% — confirming the execution-designer's stated rationale that PT/SL cannot be the primary exit mechanism. Time_stop is correctly the primary exit.
- At fee = 4 bps: BE_WR = (1.78 + 4.0) / (1.09 + 1.78) = **201%** — the PT/SL pair becomes completely non-viable. At 4 bps fee, even with PT at 1.09 bps, there is no win rate that can break even under static PT/SL exits.

---

## 3. Fee Burden Analysis

**Current state (fee = 0 bps)**:

| Metric | Value |
|---|---|
| total_fees | 0.00 |
| gross_pnl | 101,711,967,693 (raw units) |
| fee_pct | 0.0% |
| fee_per_roundtrip | 0.00 |
| avg gross_pnl per roundtrip (bps) | −0.170 bps (portfolio) / +0.226 bps (BTC+ETH only) |

**Assessment at 0 bps**: By construction, fee is not consuming edge. The execution design was explicitly calibrated for fee = 0, which is the backtest condition. This is internally consistent but entirely non-deployable — the strategy only exists as a zero-fee construct.

**Hypothetical re-run at 4 bps round-trip taker fee** (Binance VIP 1-2 tier, fee_aware_sizing.md §1):

Using fee_aware_sizing.md §6 formula — `fee_to_edge_ratio = fee_RT / (ev_bps_after_fee + fee_RT)`:
- BTC+ETH gross edge = +0.226 bps per trade
- fee_to_edge_ratio = 4.0 / (0.226 + 4.0) × 100 = **94.7%**

The fee-to-edge ratio of 94.7% is catastrophically above the 50% abandonment threshold from fee_aware_sizing.md §6: "fee_to_edge > 50% → fee-dominated regime, consider abandonment." Net edge per trade at 4 bps: +0.226 − 4.0 = **−3.774 bps** (even for BTC+ETH only). At default Binance taker (15 bps round-trip), the deficit is −14.77 bps per trade.

fee_aware_sizing.md §5 decision matrix classifies Tick/HFT strategies as "Maker only (often rebate) / Passive LIMIT with aggressive cancel" — market taker is categorically inappropriate for 1-second horizon strategies at any real-world fee level. The execution-designer acknowledged this in execution_design.md ("any taker fee above 0 bps eliminates the edge entirely"), but did not convert it to a structural execution fix; it was treated as a warning rather than a hard stop.

**Per-symbol fee impact at 4 bps**:
- BTCUSDT avg net at 4 bps: +0.267 − 4.0 = **−3.733 bps**
- ETHUSDT avg net at 4 bps: +0.184 − 4.0 = **−3.816 bps**
- SOLUSDT avg net at 4 bps: −0.962 − 4.0 = **−4.962 bps** (already negative before fee)

---

## 4. SOL Spread Structural Drain

SOLUSDT's 1.17 bps spread at every entry creates an immediate structural cost the time_stop cannot overcome. MARKET BUY at ask = 8,544,000,000 units; at time_stop after 10 ticks, exit at bid = 8,543,000,000 units if price is unchanged. Realized PnL = −1.17 bps from spread alone, independent of direction. With OBI near zero (no directional signal), the expected time_stop PnL = −spread_bps = −1.17 bps. Actual SOLUSDT time_stop avg = −0.994 bps — consistent with this prediction (small positive noise offsetting partial spread).

SOL's PT fires 15 times (3.0%) at avg +1.100 bps — these are noise-driven price spikes in a bypassed-threshold context, not OBI-driven events. The PT threshold of +1.09 bps is actually slightly below the 1.17 bps spread, meaning it requires a net price move of only +1.09 − 0 = +1.09 bps at mid — achievable even if bid/ask both shift up by the spread. This means for SOL, the PT fires on price-level noise even when OBI provides no edge.

The execution design (execution_design.md §Implementation Note 4) explicitly excluded a per-symbol spread gate because "Binance spot BTC/ETH/SOL all have spreads < 0.2 bps." This was factually incorrect for SOLUSDT: actual spread = 1.17 bps across all 500 SOL entries. The execution-designer relied on microstructure_primer §1.4 (BTC spread ~0.13 bps) but did not verify per-symbol spread in the LOB data. A spread gate of "skip entry if spread_bps > PT" would have blocked all 500 SOLUSDT entries (1.17 > 1.09) — producing 0 SOL trades and zero SOL drag.

---

## 5. Adverse Selection Assessment

Entry is MARKET BUY (taker), not passive LIMIT. Classical adverse selection (fill at bid when price falling) does not apply. However, MARKET BUY at ask immediately loses the half-spread:

- BTC half-spread ≈ 0.0 bps (spread_bps = 0 at 65% of BTC entries in sample), negligible
- ETH half-spread ≈ 0.02 bps (spread = 0.04 bps; half = 0.02 bps)
- SOL half-spread ≈ 0.585 bps (spread = 1.17 bps; half = 0.585 bps — dominant cost)

For BTC/ETH the MARKET entry cost (half-spread) is consistent with the brief's spread_cross_cost = 0.065 bps. For SOL, the brief's cost estimate was ~0.065 bps but actual is 0.585 bps — a 9× underestimate due to SOL's structural wider spread in this LOB snapshot set.

Tick-by-tick trajectory data after entry fill is not available (MFE/MAE null for 97.6% of trades, confirmed in alpha_critique.md §4). Intra-path adverse selection measurement requires `track_mfe=true` with per-tick extremes.

---

## 6. n_resting_cancelled Anomaly

`n_resting_cancelled = 1,380` with `n_roundtrips = 1,500`. This is 92% of roundtrips. For a MARKET entry strategy with no resting LIMIT orders, this is unexpected. MARKET orders do not rest — they should not generate cancellation events. One possibility: the engine internally creates an order tracking object that gets "cancelled" when the time_stop fires, rather than "filled." If so, this is a bookkeeping artifact, not a meaningful metric. However, if the engine counts these as genuine limit-order cancellations, it may indicate that the strategy is inadvertently submitting limit orders (perhaps the exit leg as a LIMIT) that are being cancelled at time_stop. This warrants investigation — if exit orders are LIMIT (not MARKET), the assumed bid-exit model may be incorrect, and realized exit prices could differ from what the PnL calculation assumes.

---

## 7. Execution Design Validity Assessment

The execution-designer's primary architectural choice — time_stop as primary exit with PT/SL as caps — is **correct in logic** for this signal horizon. The brief's terminal WR of 40% at tick 10 is the relevant WR for time_stop exits, not the static PT/SL break-even WR of 62%. For BTC/ETH, the time_stop exits show +0.147 / +0.113 bps positive average, which is consistent with the brief's +0.38 bps EV at zero fee (lower realization is due to sub-threshold entries, regime noise, and 1/3 of the 0.38 bps being from the signal onset that these entries partially missed).

**Where the execution design is incorrect**:
1. **No spread gate for SOL**: execution_design.md §Implementation Note 4 incorrectly assumed SOL spread < 0.2 bps. Actual = 1.17 bps. A spread filter of `spread_bps < PT_bps` (or `spread_bps < 0.3 bps`) would block SOL entries, eliminating −500 × 0.962 bps = 481 bps of aggregate drag.
2. **SL gap risk unmitigated**: 100ms monitoring cadence allows realized SL exits at 2–5× the spec SL level. At a 1-second horizon, a single tick move can traverse the SL trigger zone between snapshots. Exit_design.md §1 iter1 case study (Trade #8) identifies this pattern — SL fires well below trigger due to discrete monitoring. No intra-tick SL mechanism exists in the current implementation.
3. **Fee viability not enforced**: The execution-designer correctly identified that 4 bps taker fee kills the strategy but did not add a structural guard (e.g., maker-only flag, or an abort condition) — it remained advisory. fee_aware_sizing.md §2 states "if ev_bps_raw < 2 × fee_RT: likely fee-dominated; consider abandonment." At 0.38 bps ev < 2 × 4 bps = 8 bps, the strategy fails this test for any real-world fee.

---

## JSON Output

```json
{
  "strategy_id": "lob_iter1_obi1_spread_capture",
  "execution_assessment": "suboptimal",
  "exit_breakdown": {
    "n_tp": 120,
    "n_sl": 11,
    "n_eod": 0,
    "n_trailing": 0,
    "n_other": 1369,
    "sl_tp_ratio": 0.092,
    "avg_tp_bps": 1.203,
    "avg_sl_bps": -3.485,
    "avg_eod_bps": null,
    "avg_time_stop_bps": -0.264,
    "time_stop_pct": 91.3,
    "note_on_n_other": "1369 time_stop exits (91.3%) — primary exit mechanism as designed; sl_tp_ratio of 0.092 is not interpretable as 'stops rarely fire vs targets' because time_stop dominates both"
  },
  "fee_analysis": {
    "total_fees": 0.0,
    "gross_pnl": 101711967693.0,
    "fee_pct": 0.0,
    "fee_per_roundtrip": 0.0,
    "assessment": "zero-fee backtest by design — non-deployable. At 4 bps round-trip (Binance VIP 1-2), fee_to_edge_ratio = 94.7% (fee_aware_sizing §6 threshold: 50%). BTC+ETH net at 4 bps: -3.77 bps per trade. Strategy is viable ONLY under maker-rebate execution at near-zero fee."
  },
  "stop_target_calibration": "SL/TP ratio 0.092 is superficially favorable but misleading — 91.3% of exits are time_stop. SL at spec -1.78 bps is not binding: 10 of 11 SL exits realize -2.33 to -7.40 bps due to 100ms monitoring granularity gap risk. PT at +1.09 bps fires cleanly (avg +1.203 bps). Break-even WR under static PT/SL: 62.0% (fee=0) and 201% (fee=4bps) — confirming time_stop must be the primary exit; PT/SL are protective caps only.",
  "adverse_selection": "MARKET taker entry — classical adverse selection does not apply. Half-spread cost: BTC ~0.0 bps, ETH ~0.02 bps (acceptable). SOL ~0.585 bps (9× the brief's estimate of 0.065 bps) — SOL spread was mischaracterized as <0.2 bps in execution_design.md §Implementation Note 4, causing structural entry cost underestimation. Intra-path adverse selection measurement requires tick-by-tick trajectory after fill (MFE/MAE null for 97.6% of trades — data not available).",
  "critique": "The time_stop-as-primary-exit architecture is logically sound and matches the brief's design intent. The BTC/ETH time_stop exits produce positive avg pnl (+0.147 / +0.113 bps) consistent with the brief's +0.38 bps EV directional signal. However, three execution failures leak value: (1) missing SOL spread gate — SOLUSDT spread = 1.17 bps > PT = 1.09 bps makes all 500 SOL entries structurally loss-generating, draining -481 bps aggregate from a portfolio that is otherwise +450 bps; (2) SL gap risk at 100ms cadence allows exits 2-5x beyond spec SL; (3) zero-fee assumption is non-deployable — at any real Binance taker fee, fee_to_edge_ratio exceeds 94%, making the strategy unviable for live use.",
  "execution_improvement": "Add per-symbol spread gate: reject entry if spread_bps >= profit_target_bps (this alone eliminates all 500 SOLUSDT structural losses and would convert the portfolio from -0.170 bps to approximately +0.226 bps per trade); separately, pursue maker-only passive LIMIT entry design for the next iteration to reduce fee burden from 4 bps taker to ~0 bps maker.",
  "data_requests": [
    "tick-by-tick mid-price trajectory for 10 ticks after each entry fill (enable track_mfe=true in engine) — required for MFE/MAE capture_pct analysis; 97.6% of trades have null MFE/MAE in this run",
    "per-symbol spread_bps distribution across the full IS window (not just at entry) — to calibrate spread gate threshold per-symbol rather than relying on brief's single-value estimate",
    "n_resting_cancelled=1380 explanation — for a MARKET-entry strategy, clarify whether these are exit-leg LIMIT order cancellations (at time_stop) or internal order tracking artifacts; if exit is submitted as LIMIT not MARKET, realized exit prices may differ from bid-based PnL calculation",
    "OBI threshold adherence logs per entry — alpha_critique found 38.6%/58% of BTC/ETH entries are below-threshold; splitting time_stop pnl_bps by threshold-compliant vs sub-threshold entries would isolate true OBI signal quality from noise entries"
  ]
}
```
