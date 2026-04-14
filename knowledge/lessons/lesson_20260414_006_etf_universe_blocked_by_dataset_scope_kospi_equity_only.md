---
id: lesson_20260414_006_etf_universe_blocked_by_dataset_scope_kospi_equity_only
created: 2026-04-14T06:31:33
tags: [lesson, dataset, etf, universe, data-gap, kospi]
source: strat_20260414_0007_etf_obi_momentum_069500
metric: "return_pct=0.0 trades=0 fees=0.0"
---

# ETF universe blocked by dataset scope — KOSPI equity only

Observation: Symbol 069500 (KODEX 200 ETF) is absent from the 20260313 dataset; only 40 KOSPI equity tickers are available. A strategy targeting this ETF produced 0 ticks of market data, 0 trades, and 0 PnL.\nWhy: The dataset was constructed from KOSPI equity order books. ETF tickers (069500, 114800, etc.) are traded on a separate venue segment and were never ingested. The meta-reviewer's primary escape route from the KRX fee hurdle — switching to ETFs with 0% sell tax and ~3 bps round-trip — cannot be tested until the data pipeline is extended.\nHow to apply next: Any strategy referencing ETF tickers (6-digit codes in the 069xxx/114xxx/122xxx range) will silently produce zero activity. Restrict universe to confirmed KOSPI equity symbols from the available 40-ticker list. The fee-hurdle problem remains unsolved within the current dataset; focus instead on hold-time extension or intraday momentum filtering to stretch realized edge above 21 bps.
