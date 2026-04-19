---
id: lesson_20260415_024_sl_triggers_on_mid_but_exits_at_bid_permits_catastrophic_slippage_plus_spread_gate_must_be_per_symbol
created: 2026-04-15T16:59:14
tags: [lesson, stop_loss, spread_gate, per_symbol, bid_price, mid_price, execution_bug, passive_maker, multi_symbol]
source: strat_20260415_0028_passive_maker_spread_momentum_3sym
metric: "return_pct=-1.78 trades=10 wr=30 fees=71802"
links:
  - "[[pattern_sl_reference_price_and_per_symbol_spread_gate]]"
---

# sl_triggers_on_mid_but_exits_at_bid_permits_catastrophic_slippage_plus_spread_gate_must_be_per_symbol

Observation: A stop-loss that monitors mid-price but triggers a MARKET SELL (which fills at bid) systematically underestimates realized loss, and a universal spread gate silently eliminates all signals for symbols where the gate is impossible to cross.

Alpha Critique (from alpha-critic):
Signal edge: weak. spread_gate=8 bps is structurally impossible for 000660 (median 10.1 bps) and 005380 (median 16.1 bps), reducing a 3-symbol strategy to 005930-only by accident. momentum gate (mid_return_bps > 1.0 over 50 ticks) has zero discriminative power — delta 0.0 between WIN and LOSS. Severe regime dependency: all 3 wins on 2 consecutive days; 7 losses spread across 5 other days.

Execution Critique (from execution-critic):
Assessment: poor. CRITICAL — SL monitors mid-price but MARKET SELL fills at bid. RT10 lost 362 bps against a nominal 50 bps SL; the bid collapsed while mid was still near the threshold. Engine behavior is correct (walk_book uses bid-side for SELL), so this is a strategy-level design flaw. Entry gate allows resting LIMIT orders to fill 20+ min past the 13:00 gate close. time_stop=3000 ticks ≈ 5-6 hours, meaning 10:00 entries are never time-stopped before EOD. Trailing floor 25 bps is below 19.5 bps fee hurdle (net negative).

Agreement: Both critics agree the strategy has no working edge as designed. Execution mechanics are broken independently of signal quality, and the signal itself has zero discriminative power.

Disagreement: None — both critics identify distinct but additive failure modes.

Priority: both — signal expansion failed (per-symbol spread gates needed) and execution mechanics are broken (SL must monitor bid, not mid).

How to apply next: Fix SL to use snap.bid_px[0] for trigger evaluation on long positions. Enforce time gate by canceling resting orders when kst_sec >= entry_end_sec. Reduce time_stop to 1000-1500 ticks. Per-symbol spread gates calibrated to each symbol's median spread.
