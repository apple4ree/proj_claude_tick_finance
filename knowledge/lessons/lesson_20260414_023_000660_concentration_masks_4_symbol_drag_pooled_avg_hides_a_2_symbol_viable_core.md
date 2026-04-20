---
id: lesson_20260414_023_000660_concentration_masks_4_symbol_drag_pooled_avg_hides_a_2_symbol_viable_core
created: 2026-04-14T12:36:49
tags: [lesson, universe-filter, symbol-concentration, 000660, 005930, resting-limit, krx, win-rate, iteration-stagnation]
source: strat_20260414_0025_krx_resting_limit_5sym_spread18
metric: "return_pct=0.0065 trades=30 win_rate_pct=43.33 n_symbols=5"
links:
  - "[[pattern_universe_filter_per_symbol_win_rate_screen]]"
---

# 000660 concentration masks 4-symbol drag: pooled avg hides a 2-symbol viable core

Observation: 000660 returned +4.78% while the other 4 symbols summed to -2.11% return (015760=-0.36%, 042700=-0.16%, 005930=-1.43%, 006800=+0.44%). Pooled avg +0.0065% is near-zero only because capital is spread equally across all 5. 005930 is now confirmed below breakeven (33% win rate) across strat_0023, _0024, and _0025 — three consecutive strategies.\nWhy: The resting-limit edge at 150/50 bps is instrument-specific. 000660 (SK Hynix) has sufficient intraday volatility to reach the +150 bps profit target; 005930 (Samsung) and 015760 structurally cannot at this spread gate. Loosening spread_gate from 21 to 18 bps added 0 net trade count (stayed at 30) — the gate change was absorbed entirely by the dropped symbol, confirming OBI/imbalance thresholds are the binding constraint, not spread width.\nHow to apply next: Concentrate capital on 000660 and 006800 only (the two symbols with positive return). Drop 005930 permanently — 3 consecutive below-breakeven readings confirm structural incompatibility. Drop 015760 and 042700 unless win rate clears 40% in isolation. With 2 symbols, tighten OBI threshold to 0.35 to raise signal quality rather than loosening gates to raise volume.

## Validation — strat_20260414_0026_krx_resting_limit_2sym_obi35

Confirmed: dropping to [000660, 006800] + OBI 0.35 produced avg_return=+0.0262% (4× strat_0025) with 15 roundtrips. 000660 alone drove 0.048% vs 006800's 0.0044% — revealing a 14× per-trade payoff gap that equal lot_size=1 cannot exploit. Next step: asymmetric lot sizing or single-symbol concentration. See [[lesson_20260414_024_tighter_obi_4x_return_gain_000660_payoff_magnitude_dwarfs_006800_revealing_lot_scale_asymmetry]].
