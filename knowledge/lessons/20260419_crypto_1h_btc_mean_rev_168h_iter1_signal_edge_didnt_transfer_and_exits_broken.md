---
id: 20260419_crypto_1h_btc_mean_rev_168h_iter1_signal_edge_didnt_transfer_and_exits_broken
created: 2026-04-19T00:00:00Z
tags: [lesson, crypto, btc, mean-reversion, exit-wiring, cross-symbol-ev, regime-dependency, exit-bug, weekly-roc, implementation-fidelity]
source: crypto_1h_btc_mean_rev_168h_iter1
metric: "return_pct=-7.07 trades=12 wr=41.67 sharpe=-0.42 oos_ir=+2.35"
links:
  - "[[lesson_20260418_002_direct_is_eda_finds_weekly_mean_reversion_oos_validated]]"
---

# BTC 168h mean-reversion: pooled cross-symbol EV did not transfer to BTC, and PT/SL exits never fired

## Observation

The roc_168h mean-reversion strategy on BTCUSDT (IS 2025-07 to 2025-12) produced -7.07% return, 41.67% WR, and -45.95 avg net bps across 12 roundtrips, despite the signal brief projecting +441 bps adjusted EV. OOS returned -8.41% but outperformed buy-and-hold (-19.62%) with IR +2.35 — the strategy beats the benchmark by losing less during a bear period, not by generating absolute alpha.

## Alpha Critique

Signal edge assessed as **weak** on BTC in isolation. The brief's pooled EV was driven by ETH (+613 bps) and SOL (+733 bps) raw mean_fwd; BTC's own entry stat was -10 bps. Realized WR of 41.67% vs projected 61.96% confirms the pooled EV did not transfer. Strong regime dependency: 4 of 7 losses (57%) clustered in November 2025's persistent -25% BTC drawdown, where the signal fired 4 consecutive times into a continuing decline. Hypothesis not supported for BTC standalone.

## Execution Critique

Execution assessed as **poor** due to a critical implementation bug: all 12 exits are tagged `exit_signal` — zero exits fired as PT, SL, trailing, or time_stop. Five losing trades exceeded the 450.79 bps SL threshold (overshoots of 38–101 bps) without triggering an exit. The PT of 1312 bps is phantom — best wins were +1007 and +1095 bps at the 168-bar horizon. The strategy ran as a pure 168-bar time-exit with no downside protection, amplifying losses on trades that should have been cut early.

## Agreement

Both critics agree: (1) the strategy lost money and the signal hypothesis is not supported on BTC; (2) the exit mechanics failed to protect against downside; (3) the OOS IR is a soft validation of downside protection, not of mean-reversion alpha.

## Disagreement

Alpha-critic focused on BTC's intrinsic weak mean_fwd vs pooled EV. Execution-critic identified the exit-wiring bug as the independent structural failure. Both are correct and non-overlapping — the strategy has two separate problems: wrong symbol choice and broken exit code.

## Priority: both

Fix exit wiring AND switch to ETH/SOL where raw mean_fwd is genuinely positive before investing in signal refinement.

## How to apply next

Iter 2: (1) rewrite exit loop to check bar.close against SL/PT each bar before evaluating exit_signal; (2) test the corrected implementation on ETHUSDT or SOLUSDT where brief-projected EV is reliable; (3) add roc_24h >= 0 as momentum confirmation gate on BTC if BTC is retried.
