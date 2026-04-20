---
id: lesson_20260420_001_lob_spread_gt_pt_blocks_symbol_before_obi_signal_can_work_implementation_bypass_invalidates_cross_symbol_alpha_assessment
created: 2026-04-20T05:25:13
tags: [lesson, lob, obi, spread_gate, implementation_bug, cross_symbol, crypto_lob, solusdt, market_making]
source: lob_iter1_obi1_spread_capture
metric: "return_pct=0.1017 trades=1500 fees=0 btc_edge_bps=0.267 eth_edge_bps=0.184 sol_edge_bps=-0.962 fee_to_edge_ratio_4bps=94.7"
links:
  - "[[lesson_20260415_024_sl_triggers_on_mid_but_exits_at_bid_permits_catastrophic_slippage_plus_spread_gate_must_be_per_symbol]]"
  - "[[lesson_20260417_004_strategy_py_gate_enforcement_bugs_nullify_obi_spread_filters]]"
---

# LOB spread gt PT blocks symbol before OBI signal can work; implementation bypass invalidates cross-symbol alpha assessment

Observation: When per-symbol spread_bps exceeds profit_target_bps, any MARKET entry is structurally loss-generating independent of the OBI signal — and if strategy.py additionally fails to enforce the per-symbol OBI threshold, the two defects compound to produce catastrophic drag on the portfolio.

Alpha Critique (from alpha-critic):
Signal edge = moderate for BTC+ETH (total_edge +0.267 / +0.184 bps, WR 37-38%); none/untestable for SOL. SOLUSDT avg_entry_obi = -0.028, well below the spec threshold 0.749589 — all 500 SOL entries violated the OBI gate in strategy.py. The apparent OBI separation (WIN OBI 0.869 vs LOSS OBI 0.469) is a SOL vs BTC/ETH symbol artifact, not within-symbol discriminating power. Hypothesis supported for BTC/ETH only; untested for SOL due to the code defect.

Execution Critique (from execution-critic):
SOL spread = 1.17 bps at all 500 entries vs PT = 1.09 bps — spread structurally exceeds the profit target, making even a correct OBI signal unwinnable. BTC/ETH time_stop exits produce +0.147 / +0.113 bps positive avg — execution architecture (time_stop primary) is sound. At 4 bps real taker fee, fee_to_edge_ratio = 94.7% — strategy non-deployable with market orders.

Agreement: Both critics identify SOLUSDT as the sole source of portfolio drag (−0.962 bps per trade, −481 bps aggregate). Both confirm BTC/ETH show independent positive edge and the time_stop-as-primary-exit design is architecturally correct.

Disagreement: Alpha-critic leads with the code bug (threshold bypass in strategy.py); execution-critic adds that even a correctly gated SOL trade would still lose (spread 1.17 bps > PT 1.09 bps). These are complementary, not conflicting — both fixes are required.

Priority: both — fix strategy.py OBI gate enforcement AND add per-symbol spread gate (reject if spread_bps >= profit_target_bps).

How to apply next: iter 2 should (1) audit and fix the SOL OBI threshold bypass in strategy.py, (2) add a spread gate rejecting entry when spread_bps >= profit_target_bps, (3) optionally restrict live universe to BTC+ETH until SOL spread normalises, (4) enable track_mfe=true for intra-path MFE/MAE data.
