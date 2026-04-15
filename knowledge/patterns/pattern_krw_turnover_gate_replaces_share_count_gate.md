---
id: pattern_krw_turnover_gate_replaces_share_count_gate
created: 2026-04-15
tags: [pattern, universe-filter, volume-gate, krx, symbol-heterogeneity, krw, entry-filter]
links:
  - lesson_20260415_016_universal_vol_gate_silently_collapses_multi_symbol_universe_to_2_active_symbols
  - lesson_20260415_012_entry_volume_is_the_strongest_win_discriminator_1_7x_higher_volume_at_win_entries_vs_loss
---

# KRW Turnover Gate Replaces Share-Count Gate for Multi-Symbol Universes

## Problem

A universal `min_entry_volume` threshold expressed in **shares** silently collapses a
multi-symbol universe to only the highest-float names (typically semiconductor stocks with
share counts in the billions). Symbols with comparable KRW liquidity but lower share counts
(Naver 035420 at 217k KRW/share, POSCO 006400 at high per-share price) generate zero trades,
creating an illusion of diversification with no actual coverage.

Observed: strat_0020 targeting 6 symbols produced N=16 trades, effectively 2-symbol (000660,
006800). The 4 additional symbols were filtered to zero by `min_entry_volume=1M shares`.

## Solution

Use `krw_turnover` (shares_delta * mid_price) as the activity gate, not raw share count.

DSL expression (now available as `krw_turnover` signal primitive):
```yaml
signals:
  tv: {fn: krw_turnover, args: {lookback: 300}}  # ~300 ticks ≈ 30 seconds

entry:
  when: "obi > 0.35 and tv > 5e8"   # 500M KRW notional in last 30s
```

This gate scales automatically with share price: a 500M KRW threshold passes both
000660 (high-float) and 034020 (mid-float) in active regimes, while blocking genuinely
illiquid periods equally across symbols.

## Calibration Reference (IS window 10:30-13:00)

| Symbol | Price (KRW) | Typical 30-tick turnover |
|--------|-------------|--------------------------|
| 000660 | ~934k | 2–20B KRW |
| 006800 | ~70k | 200M–2B KRW |
| 034020 | ~106k | 500M–5B KRW |
| 010140 | ~29k | 100M–1B KRW |

Threshold 5e8 (500M KRW) passes all four in active periods and blocks them during
illiquid gaps — achieving the intended signal-quality gate without share-count bias.

## When to Apply

- Any strategy targeting more than 2 KRX symbols.
- Whenever you see N_trades concentrated in 1-2 symbols despite 4+ in universe.
- When per-symbol win-rate screening is intended but volume gate kills coverage.

## Engine Note

`sig_krw_turnover` added to `SIGNAL_REGISTRY` in `engine/signals.py` (2026-04-15).
Use `fn: krw_turnover, args: {lookback: N}` in the spec's `signals:` section.
