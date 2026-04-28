# Cumulative lessons — v3 to v6 (auto-generated)

*Auto-generated from archives. Updated each run.*

Reading order: §1 (top signals — but read with caveats), §2 (failure patterns), 
§3 (untouched areas — try these), §4 (paradigm-specific notes).

## §1. Top signals across all measured runs

**Caveat 1**: v3/v4 used fixed-H paradigm — mid_gross values inflated by trigger over-counting (see `fixed-h-overcounting-bias` concept). Re-measurement under regime-state shows true alpha is much smaller. Use v3/v4 mid_gross numbers as *upper bound only*.

**Caveat 2**: v6's iter_008 (maker 21.64) is suspicious — mid≈0, spread arbitrage only.

Top 10 by mid_gross under regime-state paradigm (v5/v6 only — these are real alpha):

| run | iter | spec | mid | maker | n | mean_dur | family |
|---|---:|---|---:|---:|---:|---:|---|
| v5 | 013 | iter013_opening_burst_conviction | 4.74 | 0.00 | 6444 | 117 | obi |
| v5 | 014 | iter014_opening_burst_long_hold | 4.74 | 0.00 | 6444 | 117 | obi |
| v6 | 004 | iter004_durable_book_consensus | 4.46 | 14.12 | 1231 | 519 | obi |
| v6 | 015 | iter015_long_horizon_pressure_conse | 4.21 | 14.52 | 902 | 978 | obi |
| v5 | 016 | iter016_stable_pressure_on_fragile_ | 4.08 | 0.00 | 1049 | 87 | obi |
| v5 | 009 | iter009_stable_imbalance_vs_fragile | 3.85 | 0.00 | 1273 | 77 | obi |
| v5 | 000 | iter000_full_book_consensus | 3.44 | 0.00 | 11846 | 34 | obi |
| v5 | 006 | iter006_opening_burst_conviction | 3.44 | 0.00 | 11846 | 34 | obi |
| v5 | 020 | iter020_magnitude_consensus_at_open | 3.42 | 0.00 | 6840 | 27 | obi |
| v5 | 023 | iter023_opening_burst_pressure_cons | 3.36 | 0.00 | 9336 | 30 | obi |

## §2. Failure patterns recap

See `tried_failure_modes.md` for full catalog. Quick summary:

- **no_result**: 73 occurrences (27.9% of measured)
- **flickering**: 29 occurrences (11.1% of measured)
- **trigger_fragile**: 27 occurrences (10.3% of measured)
- **negative_alpha**: 23 occurrences (8.8% of measured)
- **spread_arbitrage_suspicious**: 7 occurrences (2.7% of measured)
- **buy_and_hold_artifact**: 2 occurrences (0.8% of measured)

## §3. Tried area map — primitive family × time gate

Density of past attempts. **Untouched cells (░) are good targets** for new exploration.

| family \ time | opening | lunch | closing | all_day |
|---|:---:|:---:|:---:|:---:|
| obi | ██ (7) | ░ (0) | ▓ (1) | ███ (58) |
| ofi | ░ (0) | ░ (0) | ░ (0) | ██ (4) |
| microprice | ██ (3) | ░ (0) | ▓ (1) | ███ (18) |
| trade_imb | ░ (0) | ░ (0) | ░ (0) | ██ (9) |
| zscore_tail | ██ (3) | ░ (0) | ░ (0) | ███ (70) |
| book_shape | ░ (0) | ░ (0) | ░ (0) | ░ (0) |
| other | ░ (0) | ░ (0) | ░ (0) | ██ (9) |

**Untouched / under-explored cells (░ or ▓)**:
  - obi × lunch (count=0)
  - obi × closing (count=1)
  - ofi × opening (count=0)
  - ofi × lunch (count=0)
  - ofi × closing (count=0)
  - microprice × lunch (count=0)
  - microprice × closing (count=1)
  - trade_imb × opening (count=0)
  - trade_imb × lunch (count=0)
  - trade_imb × closing (count=0)

## §4. Paradigm-specific notes

- **v3 (fixed-H)**: max mid_gross 13.32 bps. **This is fixed-H over-counting inflation**. Regime-state re-measurement of same signals gives -0.25 bps mean. Do NOT use v3 numbers as targets.
- **v4 (fixed-H + net reward)**: similar mid magnitudes (~12 bps), same inflation. Reward shaping moved LLM hypothesis distribution (expectancy keyword 0→13 occurrences).
- **v5 (regime-state)**: max mid_gross 4.74 bps under proper regime-state measurement. True chain 1 ceiling.
- **v6 (regime-state + maker)**: similar 4.46 bps mid + 14.12 bps maker. Path D effect extended mean_dur to 519 ticks (vs v5's 117).

**Implication**: chain 1 spec language's true mid_gross ceiling ≈ 4-5 bps under regime-state. Need Level 2+4 (raw column + tool-use, Task #108) or paradigm shift (chain 2, multi-day) to break it.