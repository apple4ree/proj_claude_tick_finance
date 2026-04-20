---
id: lesson_20260416_001_passive_maker_eod_exit_dominates_fill_at_ask_erodes_passive_edge_double_fill_is_strategy_bug
created: 2026-04-16T00:56:04
tags: [lesson, passive_maker, double_fill, fill_at_ask, eod_dominance, strategy_bug, regime_dependent, 005930, execution]
source: strat_20260415_0032_passive_maker_bid_sl_3entry_005930
metric: "return_pct=0.573 trades=8 fees=17746"
links:
  - "[[pattern_sl_reference_price_and_per_symbol_spread_gate]]"
---

# passive_maker_eod_exit_dominates_fill_at_ask_erodes_passive_edge_double_fill_is_strategy_bug

Observation: strat_0032 achieved +0.573%, 75% WR (n=8, p=0.145) through undesigned EOD exits (78.6% of gross PnL) while structural bugs — double-fill on 03/16 and fill-at-ask on all entries — inflate both cost and roundtrip count.

Alpha Critique (from alpha-critic): Signal edge is weak. OBI inverted (WIN avg 0.593 vs LOSS avg 0.704, delta -0.111), spread zero delta (+0.037 bps), volume inverted (-0.30M). 75% WR with n=8 is not significant (p=0.145). 66.5% of net PnL from single day 03/23. max_entries=3 cap is always binding; 3rd entry quality is mixed. No within-session discriminative power. Hypothesis: intraday momentum confirmation (mid above session-open by N bps) before entry could add genuine direction filter.

Execution Critique (from execution-critic): Assessment is suboptimal. Confirmed working: bid-anchored SL (-80.1 bps exact), cancel-at-gate-close (0 fills past 13:00). Critical issues: (1) Double-fill bug — two BUY orders fill at same tick on 03/16 (pos=10 instead of 5); caused by pending_buy guard relying on pos_qty>0 confirmation, which arrives one tick late, permitting a second submission at same tick; this is a STRATEGY bug (entry submitted before fill confirmed by portfolio), not an engine bug. (2) Fill-at-ask — LIMIT BUY at bid fills at ask_px consistently (+5.4 bps cost per entry, ~27.6 bps total for 5 trades). (3) EOD exits contribute 78.6% of gross (+213 bps avg) — trend-riding on trending IS period, not designed exit. Fee burden: 23.6% of gross (acceptable if fill-at-ask not counted separately).

Agreement: Strategy positive return is regime-dependent and not statistically validated. EOD exit is the actual profit mechanism, not PT or trailing. Signal gates add no discrimination.

Disagreement: Alpha wants intraday momentum gate to filter signal; execution wants double-fill guard and fill-at-ask investigation. Both are independent fixes targeting different failure modes.

Priority: execution first — fix double-fill guard (gate entry on pos_qty==0 AND no pending_buy at tick level, not just cleared from dict), then investigate fill-at-ask model behavior. Then alpha: add intraday momentum confirmation.

How to apply next: Add guard: do not submit new BUY if _pending_buy still in dict OR pos_qty>0. Confirm fill-at-ask is engine queue model behavior (LIMIT at bid fills at ask when spread=1 tick). Then add mid_vs_open momentum gate (N=10-20 bps) as alpha filter.
