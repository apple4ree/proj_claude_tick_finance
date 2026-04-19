---
id: lesson_20260417_003_spread_bps_threshold_is_direction_agnostic_obi_gate_required_and_krx_tick_size_for_10k_50k_band_is_50_krw_not_100
created: 2026-04-17T05:19:30
tags: [lesson, spread-signal, direction-agnostic, obi-gate, krx-tick-size, 010140, declining-symbol]
source: strat_20260417_0004_pilot_s2_010140_spread
metric: "return_pct=-0.0182 trades=8 win_rate=12.5 clean_pct=91.8"
links:
  - "[[lesson_20260415_017_wide_spread_declining_symbols_destroy_edge_even_with_correct_volume_gate]]"
---

# spread_bps threshold is direction-agnostic; OBI gate required, and KRX tick size for 10k-50k band is 50 KRW not 100

Observation: A spread_bps >= threshold entry on 010140 (down -6.94%) produced WR 12.5% (1/8), clean_pnl negative — spread width is a regime descriptor, not a directional signal.

Alpha Critique (from alpha-critic):
signal_edge_assessment=none. OBI was the only separating feature (WIN OBI=0.64 vs LOSS avg=0.43, delta=+0.21). Widest-spread entry (34.78 bps) produced the largest loss, inverting the liquidity-vacuum hypothesis. Higher volume at LOSS entries (2x WIN) indicates momentum/shock events, not mean reversion. Symbol in -6.94% downtrend during IS window provides sustained directional headwind for long-only entry. hypothesis_supported=false.

Execution Critique (from execution-critic):
execution_assessment=poor. SL:TP fires 7:1. Trailing never activated — price never traveled +1 real tick before SL. Critical design error: execution assumed 100 KRW tick for 10k-50k KRW band; correct KRX tick is 50 KRW. SL=32.65 bps is ~1.9 real ticks; PT=65.31 bps is ~3.7 ticks — both non-tick-aligned. At correct 50 KRW tick, 1-tick SL=~18.5 bps barely covers round-trip fee of 21 bps. Three entries fired below threshold due to 5ms spread normalization.

Agreement: Both critics agree the strategy has no genuine edge (clean_pnl negative despite 91.8% clean_pct); the spread threshold alone is insufficient as an entry signal.
Disagreement: Alpha-critic points to signal design as the root cause; execution-critic identifies tick-size miscalibration as an additional compounding error. Both are valid and independent.

Priority: alpha — no tick-size fix rescues a direction-agnostic signal in a downtrending symbol; OBI gate must be added first.

How to apply next: Gate entry on OBI > 0.55 in addition to spread_bps >= threshold. Use 50 KRW tick for all 010140 levels (10k-50k KRW band). Exclude symbols with buy-hold return < -3% over the IS window.
