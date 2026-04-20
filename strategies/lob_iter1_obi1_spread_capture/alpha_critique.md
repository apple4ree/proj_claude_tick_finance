---
stage: alpha_critique
strategy_id: lob_iter1_obi1_spread_capture
created: 2026-04-20
critic: alpha-critic
---

# Alpha Critique: lob_iter1_obi1_spread_capture

## Invariant-Aware Preamble

`invariant_violations`: 0. `invariant_violation_by_type`: empty. No invariant issues.

`clean_pnl` / `bug_pnl` / `clean_pct_of_total`: fields absent from report (attribute_pnl.py not run). Total PnL 0.1017% used as-is. The portfolio return is dominated by BTCUSDT (realized_pnl ~100B scaled units vs ETHUSDT ~2.1B, SOLUSDT -0.41B), so any cross-symbol assessment of "positive portfolio return" must be understood as single-symbol concentration, not broad edge.

---

## Step 1. Selectivity

```
entry_pct = 1500 / 1,586,144 × 100 = 0.0946%
```

By the §2 calibration table, 0.0946% falls in the **"thin — statistically acceptable but below recommended floor"** band (0.1–0.5% boundary). At 100ms cadence over 16 hours the 1,500 entries are nominally sufficient for statistical inference (n=500 per symbol), but the entry rate is near the lower bound of the reliable zone.

**Assessment**: borderline — 0.0946% is below the recommended 0.5–3.0% bar-strategy range; for a tick-level LOB strategy at 100ms cadence, the 90th-percentile gate was designed to yield ~10% of snapshots. The actual realized rate of 0.0946% reveals that `max_entries_per_session=500` per symbol is the binding constraint, not the OBI threshold. The signal itself would fire at ~10% of 1.58M events (~158,000 times), but position-capping terminates entries after 500 per symbol. **Entry_pct is artificially depressed by the position cap, not by signal selectivity.**

---

## Step 2. Hit-rate vs Edge Decomposition

Full-portfolio:

| Metric | Value |
|---|---|
| WR | 25.9% (389/1500) |
| avg_win_bps | 0.750 |
| avg_loss_bps (abs) | 0.492 |
| total_edge_bps | 0.26 × 0.750 − 0.74 × 0.492 = **−0.170 bps** |
| payoff_ratio | 0.750 / 0.492 = **1.52** |

Per-symbol decomposition:

| Symbol | n | WR | avg_win_bps | avg_loss_bps | total_edge_bps |
|---|---|---|---|---|---|
| BTCUSDT | 500 | 37.0% | 0.800 | 0.046 | **+0.267 bps** |
| ETHUSDT | 500 | 37.8% | 0.673 | 0.113 | **+0.184 bps** |
| SOLUSDT | 500 | 3.0% | 1.101 | 1.025 | **−0.962 bps** |

**Diagnosis**: BTC and ETH independently demonstrate positive total_edge (+0.267 and +0.184 bps respectively). SOLUSDT catastrophically destroys edge (−0.962 bps), pulling the portfolio total negative. This is a **cross-symbol consistency failure**, not a fundamental signal failure on BTC/ETH.

Signal category (§3 table): BTCUSDT and ETHUSDT are "low WR, moderate payoff" — not a degenerate regime. SOLUSDT is "low WR, low payoff" → signal edge = none for that symbol.

---

## Step 3. Regime Dependency

IS window: **single day** (2026-04-19), 16 hours UTC. All 1,500 entries concentrated on one day:

| Day | n_entries | n_wins | WR |
|---|---|---|---|
| 2026-04-19 | 1500 | 390 | 26.0% |

With a single IS day, regime-dependency analysis cannot be computed in the standard sense (no multi-day bucketing). All three symbols declined on this day (BTC −1.38%, ETH −2.33%, SOL −0.87% buy-and-hold). The mildly bearish intraday trend is consistent with the long-only OBI signal capturing short micro-bursts of bid pressure within a broader sell-off — the signal survived a down day for BTC/ETH, which is marginally positive evidence. However, a single-day IS is insufficient to assess regime generalizability.

**Assessment**: regime dependency is **unassessable** (single day). Concentrated on 1/1 days by definition. The brief itself flagged `regime_compatibility: partial`. Regime gate recommendation is deferred to OOS with multi-day data.

---

## Step 4. MFE/MAE Gap (capture_pct)

The `analysis_trace.md` summary reports:

| Metric | Value |
|---|---|
| avg_mfe_bps | −0.10 |
| avg_mae_bps | −0.10 |
| avg_capture_pct | 1108.0% |
| n_give_back_trades (LOSS with MFE > 100 bps) | 0 |

Only 36/1,500 roundtrips contain non-null MFE/MAE values. The remaining 1,464 roundtrips have `mfe_bps: null` and `capture_pct: null`. **MFE tracking is incomplete — the engine's `track_mfe` setting did not capture intra-path extremes for 97.6% of trades.**

The avg_mfe_bps of −0.10 bps (negative) indicates the sampled trades never reached a positive MFE before time_stop fired. avg_capture_pct = 1108% is arithmetically nonsensical (realized > MFE implies negative MFE denominator), confirming the MFE data is unreliable. This metric is **inconclusive** for this run.

**Assessment**: MFE/MAE analysis cannot drive conclusions due to near-total data absence. Require engine-side `track_mfe=true` with per-tick intra-path extremes before Step 4 can be evaluated.

---

## Step 5. Cross-Symbol Consistency

| Symbol | n | WR | avg_entry_obi | total_edge_bps | realized_pnl (scaled) | BH return % |
|---|---|---|---|---|---|---|
| BTCUSDT | 500 | 37.0% | 0.876 | +0.267 | +100.0B | −1.38% |
| ETHUSDT | 500 | 37.8% | 0.871 | +0.184 | +2.12B | −2.33% |
| SOLUSDT | 500 | 3.0% | −0.028 | −0.962 | −0.41B | −0.87% |

**Critical finding**: SOLUSDT's avg_entry_obi at entry is −0.028 — **below zero and far below the spec threshold of 0.749589**. Zero of 500 SOLUSDT entries had OBI ≥ 0.749589 at the time of fill. The strategy-coder's `strategy.py` has a **threshold bypass bug for SOLUSDT**: entries fire regardless of the OBI condition. This is a signal implementation defect, not an alpha design defect.

Evidence: OBI values at SOLUSDT entries range [−0.23, +0.31] with median −0.04. The threshold gate (≥ 0.749589) is never triggered. All 500 SOLUSDT trades are noise entries.

For BTC and ETH, threshold adherence is partial:
- BTCUSDT: 307/500 entries (61.4%) have OBI ≥ 0.91469
- ETHUSDT: 210/500 entries (42.0%) have OBI ≥ 0.942049

The sub-threshold entries in BTC/ETH still show moderate WR (~32–35% estimated for below-threshold group), suggesting the 1-second time horizon captures some directional micro-signal even at moderate OBI levels — but this is untested.

**wr_std** (across symbols): std([0.370, 0.378, 0.030]) = **0.163** — exceeds the §6 threshold of 0.15, confirming **cross-sectional inconsistency**. The SOL threshold bypass is the primary driver.

---

## WIN/LOSS Entry Context Separation

Computed across all 1,500 trades:

| Feature | WIN avg | LOSS avg | Delta |
|---|---|---|---|
| OBI at entry | 0.869 | 0.469 | **+0.401** |
| spread_bps at entry | 0.065 | 0.524 | **−0.459** |
| acml_vol at entry | 0 | 0 | 0 |

OBI separation of +0.401 is large — but this is confounded by the SOLUSDT bypass. SOLUSDT entries have OBI ≈ 0 and WR = 3%, while BTC/ETH entries have OBI ≈ 0.87 and WR ≈ 37%. The apparent OBI separation is mostly a SOL-vs-BTC/ETH symbol effect, not within-symbol OBI discriminating power.

**Spread_bps separation** (−0.459) is also driven by SOLUSDT: SOL has fixed spread_bps = 1.17 for all 500 trades and nearly all are losses. BTC spread ≈ 0.0 bps, ETH spread ≈ 0.04 bps.

acml_vol is uniformly 0 across all trades — the engine is not populating cumulative volume at the entry context tick. This field provides no discriminative information.

---

## Hypothesis Validity Assessment

**Hypothesis**: "OBI_1 at 90th-percentile threshold predicts upward mid-price movement over 10 snapshots (~1s), yielding 0.38 bps EV at fee=0."

**BTC/ETH evidence**: Consistent with hypothesis. Both symbols show positive total_edge (+0.184–0.267 bps) at WR ~37–38%, which at fee=0 is viable. The signal brief's cross-symbol IC (BTC=0.253, ETH=0.263) appears to be realized in the backtest.

**SOLUSDT evidence**: Contradicts hypothesis — but only because the threshold gate was not enforced in strategy.py. The alpha hypothesis is untested for SOL.

**Hypothesis supported (conditional)**: True for BTC/ETH; untested for SOL.

---

## Verdict

```
Signal edge: moderate (BTC/ETH only; SOL untestable due to implementation bug)
Primary lever: alpha (fix SOL threshold bypass; then re-evaluate SOL signal quality)
Recommend: fix implementation (SOL entry gate) then same family
Confidence: medium (n=1000 BTC+ETH, n=500 SOL all invalidated)
```

**Basis**: BTC/ETH total_edge = +0.225 bps pooled (WR 37.4%, payoff 9.3x), which aligns with the brief's 0.38 bps raw EV post-regime adjustment. The OBI_1 × fwd_10t signal has demonstrated edge on BTC and ETH across a single-day IS window. The portfolio-level negative total_edge (−0.170 bps) is entirely attributable to the SOLUSDT strategy.py implementation defect that fires 500 entries with OBI near zero — violating the threshold gate in the spec. Once the SOL bypass is corrected, the expected portfolio edge is +0.225 bps or better (subject to SOL signal having its own edge at threshold, which is plausible given IC=0.235 in brief).

**Implementation defect (non-alpha): strategy.py does not enforce `obi_thresholds['SOLUSDT'] = 0.749589` at entry. All 500 SOLUSDT entries have entry_context.obi < 0.315, with 71.2% negative. This must be fixed before any further alpha analysis of SOL.**

