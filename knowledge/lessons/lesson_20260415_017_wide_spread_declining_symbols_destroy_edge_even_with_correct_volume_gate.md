---
id: lesson_20260415_017_wide_spread_declining_symbols_destroy_edge_even_with_correct_volume_gate
created: 2026-04-15T06:40:17
tags: [lesson, universe-filter, spread-gate, symbol-quality, declining-symbol]
source: strat_20260415_0022_krx_resting_limit_5sym_krw_gate
metric: "return_pct=0.0639 trades=32 win_rate=40.625 avg_loss_bps=-78.41"
---

# Wide-spread declining symbols destroy edge even with correct volume gate

Observation: 035420 (Naver) admitted by the KRW turnover gate (50M/300 ticks) but produced 0 wins across all roundtrips with 22-23 bps spread and a -0.92% buy-hold drift — all exits were stops.\nWhy: The KRW gate correctly filters illiquid periods, but it does not screen for structural spread width or directional drift. A symbol trading 50M KRW/300 ticks of declining price still satisfies the gate while the spread cost (22-23 bps) alone exceeds the profit target asymmetry, making any win mathematically improbable. This is a quality filter gap, not a volume gate gap.\nHow to apply next: Add a static universe pre-screen: exclude any symbol where rolling 5-day median spread > 20 bps OR buy-hold return < -0.5% over the backtest window. Alternatively, hard-code the universe to the 4 confirmed symbols (000660, 006800, 006400, 051910) and remove 035420 entirely.
