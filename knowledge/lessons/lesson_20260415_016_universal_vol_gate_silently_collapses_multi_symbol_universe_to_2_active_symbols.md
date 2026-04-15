---
id: lesson_20260415_016_universal_vol_gate_silently_collapses_multi_symbol_universe_to_2_active_symbols
created: 2026-04-15T06:28:57
tags: [lesson, universe, volume-gate, symbol-filter, krx, multi-symbol]
source: strat_20260415_0020_krx_resting_limit_6sym_screened
metric: "return_pct=0.4902 trades=16 fees=31455"
---

# Universal vol gate silently collapses multi-symbol universe to 2 active symbols

Observation: A single min_entry_volume=1M gate applied uniformly across 6 symbols (000660, 006800, 006400, 051910, 035420, 055550) produced 0 trades for 4 symbols. Only semiconductors 000660 and 006800 generate enough intraday share volume to pass a 1M acml_vol threshold in the 10:30-13:00 window; diversification and statistical power gains are entirely illusory.\nWhy: Share price differs drastically across sectors. 1M shares is trivially passable for high-float semiconductors (~50k KRW/share), but is out of reach for POSCO (006400), LG Chem (051910), Naver (035420) and Hana (055550) given their lower daily share counts — even if nominal turnover KRW is comparable.\nHow to apply next: Replace the universal min_entry_volume with per-symbol dynamic thresholds calibrated to each symbol's typical daily share volume (e.g. X% of 20-day avg daily volume), OR convert the gate to a KRW-notional turnover criterion so it is share-price-agnostic.
