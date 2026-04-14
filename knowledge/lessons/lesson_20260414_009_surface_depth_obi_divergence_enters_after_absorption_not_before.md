---
id: lesson_20260414_009_surface_depth_obi_divergence_enters_after_absorption_not_before
created: 2026-04-14T07:35:14
tags: [lesson, obi, surface-depth, signal-timing, absorption, anti-edge, lob]
source: strat_20260414_0011_obi_surface_depth_divergence_momentum
metric: "return_pct=-1.4753 trades=56 fees=108233 win_rate=0 sharpe=-3.84"
---

# surface-depth OBI divergence enters after absorption, not before

Observation: obi(depth=3) - obi(depth=10) > 0.10 combined with mid_return_bps(5) in (0,5] produced 0% win rate over 28 roundtrips on 005930; best trade was still a loss (-3847 KRW), and pre-fee PnL per roundtrip was -1403 KRW (~-0.77 bps gross) — worse than random.
Why: The surface-depth divergence condition fires when shallow queue is already bid-heavy and a short positive return is already visible. At that point, the surface imbalance has been partially absorbed into price (the 0-to-5 bps move is the absorption leg, not a precursor). Market makers and queue replenishment then dominate, reversing the remaining imbalance. The mid_return_bps(5) > 0 filter inadvertently selects post-absorption ticks — the signal requires the price to have already moved, confirming it arrives structurally late.
How to apply next: Require that mid_return_bps(5) == 0 (flat price, divergence not yet absorbed) and surface-depth divergence is widening (delta over last 3 ticks is positive), so entry fires at divergence onset rather than after price has begun to respond. Alternatively, flip to fade: enter SHORT when surface-depth divergence collapses after a small positive return, targeting mean reversion.
