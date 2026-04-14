---
id: lesson_20260414_020_symbol_heterogeneity_4_of_10_krx_symbols_structurally_below_win_rate_breakeven
created: 2026-04-14T12:09:59
tags: [lesson, universe-filter, win-rate, krx, resting-limit, symbol-heterogeneity]
source: strat_20260414_0022_krx_resting_limit_150bps_8000t
links: ["[[pattern_universe_filter_per_symbol_win_rate_screen]]"]
metric: "avg_return_pct=-0.0226 pooled_win_rate_pct=32.73 total_fees=25641.68 n_symbols=10"
---

# Symbol heterogeneity: 4 of 10 KRX symbols structurally below win-rate breakeven

Observation: With a 150/50 bps profit/stop and 21 bps effective fee, breakeven win rate is 35.5%. Across 10 symbols, 4 (010140 14.3%, 035420 16.7%, 005380 20.0%, 272210 28.6%) are far below this threshold, dragging the pooled rate to 32.73% from what would be ~40% on the 6 remaining symbols. The worst 4 are consistent losers regardless of entry gate tightness.\nWhy: OBI/spread gate signals are aggregated across the universe; symbols with naturally wide realized spreads or thin book depth hit the entry condition but fail to reach the 150 bps target before the 8000-tick time exit fires, repeatedly losing the 50 bps stop + fees.\nHow to apply next: Screen universe by per-symbol historical win rate on first iteration; exclude symbols with win rate < 30% over last N sessions; apply resting-limit strategy only to the 6 symbols that consistently clear the 35.5% threshold.
