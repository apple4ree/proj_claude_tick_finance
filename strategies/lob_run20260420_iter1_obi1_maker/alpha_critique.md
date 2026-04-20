# Alpha Critique — lob_run20260420_iter1_obi1_maker

**Invariant violations first**: `invariant_violation_by_type = {"max_position_exceeded": 4}` (fills 12, 13, 14, 22; SOLUSDT×1, ETHUSDT×2, BTCUSDT×1). `clean_pct_of_total` is not computed (attribute_pnl.py not run), but since all 11 roundtrips are losses and there are 0 wins, the invariant violations cannot account for the negative PnL via artificial upside — they at most layer additional losses on top of genuine alpha failure. Reference PnL used below: `clean_pnl ≈ total_pnl = -0.01%` (losses only; violations are additive loss, not profit). `signal_edge_assessment` is therefore evaluated on the actual loss distribution, not contaminated by bug profits.

---

## Step 1 — Selectivity (signal_diagnostics.md §2)

- n_roundtrips: 11
- total_events: 1,553,771 (100ms LOB ticks across BTC/ETH/SOL over 16h)
- entry_pct: 11 / 1,553,771 × 100 = **0.00071%**

This is far below the 0.1% "too_sparse" threshold. The signal fired on only 11 of 1.55M ticks — extraordinarily restrictive by any bar-strategy calibration, and by tick-strategy standards implies either an extreme threshold or a filter that almost never passes. Assessment: **too_restrictive** (statistically thin — n=11 conclusions are low-confidence).

---

## Step 2 — Hit-rate vs Edge decomposition (signal_diagnostics.md §3)

- wins: 0, losses: 11
- WR: 0.0%
- avg_win_bps: 0.0 (no wins)
- avg_loss_bps: 2.67 bps
- total_edge = 0.0 × 0 − 1.0 × 2.67 = **−2.67 bps**
- payoff_ratio: undefined (no wins)

Total edge is negative at −2.67 bps per trade. Per-symbol decomposition: BTC −3.21 bps (n=4), ETH −2.37 bps (n=3), SOL −2.34 bps (n=4). Loss is consistent across all three symbols.

**Critical finding — OBI gate not firing**: Every single one of the 11 entries has a **negative** OBI at entry (avg = −0.455, range −0.995 to −0.075). The hypothesis requires OBI ≥ symbol-specific threshold (BTC 0.919, ETH 0.942, SOL 0.750). Zero entries satisfied the OBI threshold. This is not a borderline failure — the direction is inverted (ask-side pressure dominant at entry, not bid-side). The strategy.py OBI gate for the LIMIT_AT_BID path is not applying the threshold correctly; entries are firing on the opposite side of the book.

---

## Step 3 — Regime-dependency (signal_diagnostics.md §4)

All 11 entries occur on 2026-04-19, concentrated in two bursts: 06:06–06:09 UTC (7 trades) and 07:01–07:06 UTC (4 trades). Total active trading window: ~10 minutes of an available 16-hour window. The market was in a down-trending session (BTC −1.38%, ETH −2.33%, SOL −0.87% over IS window per per_symbol data). The long-only entries in a short-side dominant period compound the OBI-direction bug — even if OBI gate were fixed, the first 10 minutes of entry clustering in a declining market is regime-adverse for a bid-side signal.

Per-regime sample sizes are all n=11 (single day, one regime), making formal regime decomposition infeasible. Assessment: concentrated_days = 1 of 1, heavily time-clustered within day — regime dependency unresolvable at n=11.

---

## Step 4 — MFE/MAE gap / capture_pct (signal_diagnostics.md §5)

- avg_mfe_bps: −9.66 (single RT with MFE populated; trade #10, BTCUSDT, 82-second hold)
- avg_mae_bps: −9.78
- capture_pct: None across all 11 trades (MFE tracking requires positive MFE to compute ratio)

MFE is null for 10 of 11 trades and negative on the one populated trade (−9.66 bps). A negative MFE means price never moved in the favorable direction after entry — these are not "give-back" trades but entries that went adverse immediately. The classic "shook out early" pattern (MFE > 100 bps then lost) does not exist here: n_give_back_trades = 0, sum_missed_profit = 0. No wins were available to give back. capture_pct is undefined because MFE never exceeded zero. This is consistent with wrong-side entry (ask-heavy OBI at entry → price moves down immediately).

---

## Step 5 — Cross-symbol consistency (signal_diagnostics.md §6)

Per-symbol WR: BTC 0%, ETH 0%, SOL 0%. wr_std = 0.0 (perfectly consistent — all zeros). The consistency is trivial (uniform failure, not uniform success). Rank correlation between symbol WR and signal IC (BTC 0.2556, ETH 0.2633, SOL 0.2352) cannot be computed as WR is 0/0/0. Cross-symbol edge rank ordering predicted by the brief (ETH > BTC > SOL) is unobservable.

---

## WIN/LOSS Bucketing (signal_diagnostics.md §7)

WIN group: n=0. KS-test cannot be computed. The separation analysis below is descriptive of the LOSS-only distribution.

| Feature | WIN avg | LOSS avg | Delta |
|---|---|---|---|
| obi | N/A | −0.455 | N/A |
| spread_bps | N/A | 0.589 | N/A |
| acml_vol | N/A | 0.0 | N/A |

Structural note: avg_loss entry OBI = −0.455 vs required threshold ≥ +0.750 (SOL) to +0.942 (ETH). The distance between observed entry OBI and the OBI threshold is −1.21 standard units on the ask side — these entries fired when book pressure was strongly ASK-heavy, the literal opposite of the bid-heavy signal condition.

---

## Hypothesis Assessment

**Hypothesis**: obi_1 ≥ symbol-specific 90th-pct threshold (BTC 0.919, ETH 0.942, SOL 0.750) predicts 10-tick upward mid-price movement exploitable via passive LIMIT_AT_BID.

**Supported**: No. The hypothesis was never tested. All 11 fills occurred when OBI was negative (mean −0.455), meaning the OBI gate in strategy.py is either inverted or absent in the LIMIT_AT_BID execution branch. The brief IC (avg 0.2514) was measured on OBI ≥ threshold entries; the actual fills are drawn from the complementary distribution where OBI is strongly negative. The signal itself (obi_1 × fwd_10t, IC=0.2514) retains its brief-validated predictive value for the intended condition — it was simply never applied.

---

## Critique

The 11-roundtrip sample is statistically insufficient for signal quality conclusions (signal_diagnostics.md §3: n < 20, "샘플 부족"). However the root cause here is not statistical but structural: entry_context.obi is negative at every single fill (avg −0.455), while the signal hypothesis requires obi_1 ≥ +0.75 to +0.94 per symbol. The LIMIT_AT_BID passive fill path in strategy.py does not gate on the OBI threshold before posting the limit order — it posts limits on the opposite side of the intended signal, filling precisely when ask-side pressure is dominant (the worst possible entry for a bid-side directional bet). The prior MARKET-entry iterations (lob_iter1/lob_iter2) did apply the OBI threshold correctly (those roundtrips showed avg entry OBI matching the threshold band); the refactor to passive maker execution broke the gate. The 4 max_position_exceeded violations compound this: the strategy re-entered on the same inverted signal within the same second (fills 12–14, entries at 06:09 UTC duplicated on the same timestamp).

The obi_1 IC=0.2514 is brief-validated and cross-symbol robust. The issue is a strategy.py implementation defect, not alpha failure.

---

## Verdict

- **Signal edge**: none (n=11; Confidence: low — implementation defect prevents true signal evaluation; brief IC=0.2514 untested)
- **Primary lever**: alpha (implementation — OBI gate absent/inverted in LIMIT_AT_BID code path; also note max_position_exceeded×4 invariant violations)
- **Recommend**: same family — fix strategy.py to apply `if obi_1 < threshold: skip` before posting LIMIT order; re-run with corrected gate; also fix duplicate-entry guard to prevent max_position violation
- **Confidence**: low (n=11; 0 wins; 100% implementation-fault; brief edge untested)
