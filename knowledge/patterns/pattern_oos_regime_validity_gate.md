---
id: pattern_oos_regime_validity_gate
created: 2026-04-15
tags: [pattern, oos, regime, methodology, statistical-power, universe-filter, symbol-quality, declining-symbol]
severity: high
links:
  - lesson_20260415_017_wide_spread_declining_symbols_destroy_edge_even_with_correct_volume_gate
  - lesson_20260415_018_oos_regime_mismatch_invalidates_mean_reversion_passive_maker_evaluation
  - is_oos_split
---

# Pattern: OOS and symbol-quality validity gates — two necessary pre-checks

## Root cause

Two distinct "validity" failures eroded 2 iterations (22-23) without producing valid signal
evidence:

1. **Symbol quality failure (iter 22 / strat_0022)**: A volume-based turnover gate (KRW)
   correctly admits active symbols but does not screen for structural spread width or
   directional drift. 035420 (Naver) passed the KRW gate (50M KRW / 300 ticks) but had
   a 22-23 bps realized spread (above the 150 bps profit target payoff threshold, net of
   the 18 bps fee floor) and a -0.92% IS buy-hold drift. Result: 0 wins on all 035420
   roundtrips — not a signal failure, a universe quality failure.

2. **OOS regime failure (iter 23 / strat_0023)**: OOS dates 20260326-20260330 coincided
   with a -9.4% / -9.3% crash in 000660 / 006800. A passive mean-reversion maker earns
   spread by fading short-term imbalances; in a sustained momentum-down crash, resting
   bids are hit repeatedly as price slides. N=5 roundtrips also gives a ±44 pp 95% CI on
   win rate — insufficient to distinguish signal decay from regime effect.

Both failures invalidated the iteration result as signal-evidence while burning budget.

## Mandatory pre-checks before accepting an OOS run as valid

### Check A — Symbol quality gate (run before IS)

For every symbol in the universe, verify ALL of the following on the IS window:

| Condition | Threshold | Source |
|---|---|---|
| Realized spread (bps) | <= 20 bps | per-symbol median |
| IS buy-hold return | > 0% | buy_hold_return_pct in report |
| IS win rate (prior screen) | >= 30% | per-symbol WR from pattern_universe_filter |

Fail any one → exclude the symbol. Hard-code the 4 confirmed symbols for the current
150/50 bps param set: **000660, 006800, 006400, 051910** (from strat_0014).
Do NOT re-add 035420 or other excluded symbols without re-running Check A.

### Check B — OOS regime validity gate (run before accepting OOS result)

Before treating an OOS run as signal-evidence:

1. Compute the equal-weighted universe buy-hold return over the OOS window.
2. If |universe_return_oos| > 3%: **flag as regime-confounded**, do not use as evidence.
3. Require N_roundtrips_oos >= 15 for any statistical inference on win rate.
   With N < 15, the 95% CI on WR exceeds ±25 pp — too wide for any conclusion.

**For the current dataset**: OOS dates 20260326-20260330 are a crash regime
(-9.4% 000660, -9.3% 006800). These dates cannot serve as regime-neutral OOS.
The IS window (20260316-20260325) also has available pre-IS dates (20260305-20260313,
9 trading days) that are unused — these are the highest-value remaining OOS candidates
IF their universe return is within ±3%.

### Check C — Available OOS date inventory

From `engine/data_loader.py list-dates`, the full date range is:
- Pre-IS holdout: 20260305, 20260306, 20260309, 20260310, 20260311, 20260312, 20260313
  (7 days — **unexplored, not used in any IS or OOS run to date**)
- IS window: 20260316-20260325 (8 days, strat_0014 basis)
- Crash OOS: 20260326, 20260327, 20260330 (3 days, regime-confounded, do not use for WR inference)

**Action**: If OOS validation is needed in iters 25-30, use the pre-IS holdout
(20260305-20260313). These 7 days are temporally prior to the IS window (no look-ahead),
regime is unknown but unlikely to be the same crash, and they provide up to 3.5x more
roundtrips than the crash OOS period.

## Actionable rules for remaining iterations

- **Rule 1**: The IS symbol universe for any new strategy is fixed at
  {000660, 006800, 006400, 051910} unless a structural change (param shift > 25 bps)
  justifies re-screening. Adding 035420 or any other excluded symbol requires explicit
  justification plus Check A results.

- **Rule 2**: If an OOS run returns N < 15 roundtrips or |universe_return| > 3%, do NOT
  count it as a valid signal test. Record it as "regime-confounded" in the lesson and do
  not update the IS/OOS verdict for the strategy.

- **Rule 3**: Before running any OOS, check the universe buy-hold return on the OOS dates
  using the simulator's buy-hold benchmark output. Gate the OOS run if the crash condition
  is met — save the iteration budget.

- **Rule 4**: Pre-IS holdout (20260305-20260313) is the preferred OOS window if OOS
  validation is required. Use it with the same 4-symbol universe and the same 150/50 bps
  params as strat_0014 to measure the OOS signal in a potentially non-crash regime.

## Budget implication for 6 remaining iterations

The regime filter (5-day universe return pre-filter, -2% crash guard) is a strategy-level
parameter, not an engine change. It can be implemented in one iteration on strat_0014 as
a per-day entry gate. The OOS question is separately answered by switching to the
pre-IS holdout dates. Total cost: 1-2 iterations. Remaining 4-5 iterations should focus
on the highest-EV remaining lever — which is NOT OBI threshold tuning (saturated per
lesson_20260415_025) but lot-size asymmetry (000660 generates 14x per-trade KRW vs 006800
at equal lot_size=1, per lesson_20260414_024).

## Update — strat_20260415_0026 (pre-IS OOS outcome, 2026-04-15)

**Pre-IS holdout (20260305-20260313) is ALSO regime-confounded.**

Result: return=-0.0139%, N=4, WR=25.0%. Buy-hold returns: 000660 -7.43%, 006800 -0.86%, 006400 -1.65%, 051910 -1.00%. Universe equally-weighted return ≈ -2.7% over 5 available days — borderline by Check B threshold, but 000660 (the primary P&L driver) was -7.43%, making it a directional-down environment for the dominant symbol.

**Critical conclusion — IS window is the only non-bearish period in the dataset.**

The full date inventory now resolves as:
- Pre-IS (20260305-20260313): 000660 -7.43% — BEARISH, regime-confounded
- IS (20260316-20260325): 000660 +6.5% — UNIQUELY BULLISH
- Post-IS crash (20260326-20260330): 000660 -9.4% — CRASH, regime-confounded

There is no regime-neutral OOS window available in the current dataset. The IS WR=66.7% was earned in the only bullish 8-day window; both surrounding periods are bearish. This means: (a) no valid OOS signal evidence exists, and (b) the IS result may reflect the IS regime rather than a persistent structural edge.

**Revised Rule 4**: The pre-IS holdout is NOT a valid OOS window for this strategy. Do NOT treat the pre-IS OOS as a regime-neutral test. OOS validation requires a dataset extension or a structurally different universe.

**Rule 5 (new)**: Before accepting IS WR as evidence of persistent edge, verify that the IS window is not the only non-bearish window in the full date range. If IS is the unique bullish window, flag IS WR as regime-attributed and require a multi-regime IS period for validation.

Links: [[lesson_20260415_019_session_drop_regime_filter_cleanly_excises_downtrend_losses]] [[lesson_20260415_020_is_period_was_uniquely_bullish_window_passive_maker_is_wr_does_not_generalize_across_regimes]]
