---
id: lesson_20260415_001_market_maker_stalls_at_zero_roundtrips_hard_stop_fires_before_spread_is_harvested
created: 2026-04-15T03:01:57
tags: [lesson, market-making, fee-burn, hard-stop, spread-gate, adverse-selection]
source: strat_20260415_0001_krx_as_market_maker_000660
metric: "return_pct=-0.3025 trades=4 fees=20245.5"
---

# Market maker stalls at zero roundtrips: hard stop fires before spread is harvested

Observation: With only 4 trades (2 roundtrips) and 0% win rate, both roundtrips hit the -30 bps mid-return hard stop before a single earn-side close fired. Total fees 20 245 KRW consumed 2x the realized PnL loss of 10 000 KRW, confirming fee drag compounds stop-triggered losses.
Why: A -30 bps adverse stop with a 25 bps spread gate means the strategy abandons a position at roughly -30 bps mid movement — barely 1.2x the required spread to break even. If the market drifts against the resting quote by 30 bps before the other side fills, the stop trips and the maker pays both the fee-in and fee-out with zero spread capture. Low lot_size=5 also means per-round fee cost is a larger fraction of spread potential.
How to apply next: Widen the hard stop to at least 60 bps (2x spread gate) to give both legs room to fill; simultaneously tighten obi_neutral_band to 0.10 so quotes are skewed off sooner when inventory accumulates, reducing the probability of holding through a full adverse move.

## Update — strat_20260415_0002_krx_as_mm_000660_wider_stop

Applying the "widen stop to 60 bps + tighten OBI to 0.10" recommendation reduced fee burn (10 248 KRW vs 20 246 KRW) but did not recover spread: result was still 1 RT, 0% WR, return_pct=-0.1025. The stop-widening alone cannot fix a structural fill asymmetry — the earn-side (passive ask) is systematically never reached. Root cause shifted from stop-too-tight to two-sided quoting failure; see lesson_20260415_002.
