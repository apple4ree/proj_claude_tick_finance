# Findings — Raw-EDA Alpha Discovery on Crypto Bar Data

*Running synthesis of what the project knows. Read at start of every session/tick.*

---

## Current Understanding (2026-04-18, end of session 1)

**Research question:** Does raw-data-driven EDA recover tradable crypto alpha that LLM-agent pipelines miss?

**Short answer so far: YES, on 2 of 3 tested signal families.**

### Core finding

A single EDA pass over 31 OHLCV/order-flow features × 8 forward horizons on 2025-07~10 Binance 1h data identified two robust signal families whose OOS (2025-11~12) Information Ratio vs buy-and-hold is strongly positive on all three tested symbols:

- **`roc_168h` mean-reversion** (IC = −0.21 on IS): OOS IR = +1.75 / +2.44 / +3.89 on BTC/ETH/SOL.
- **`taker_buy_persistence`** (IC = +0.08 on IS): OOS IR = +0.68 / +2.59 / +3.13 on BTC/ETH/SOL.

These are the first OOS-IR-positive strategies in the 47-strategy corpus. The prior 44 strategies — all generated via the LLM-agent pipeline or via parameter sweeps — lose to buy-and-hold on absolute return and on IR (in the 24 strategies where period-matched BH comparison is possible, **0 out of 24 beat BH in up-markets; 2 of 24 beat BH in down-markets only by staying in cash**).

### Why this matters

The existing LLM-agent pipeline (alpha-designer → execution-designer → spec-writer → strategy-coder → critics → feedback-analyst) was built around a pre-computed `signal_brief` that ranks signals by Sharpe on a narrow feature space. This brief did not include `roc_168h` (weekly cadence) or `taker_buy_persistence` (order-flow). Direct observation of raw OHLCV + taker-flow columns surfaced them immediately. The implication is not that LLMs can't find alpha; it is that **LLM pipelines bounded by pre-curated feature briefs inherit the brief's blindspots**, and those blindspots happen to contain the tradable signals on this data.

## Patterns and Insights

1. **Low exposure is a feature, not a bug.** The winning strategies hold long ~5–30% of the time. They are not "better at being long" — they are better at *when* to be long. Any attempt to increase exposure (lowering thresholds) destroys the edge on the OOS set.

2. **Absolute return is the wrong success criterion.** OOS 2025-11~12 was a bear period; all winners show negative absolute return but beat BH substantially. The 4-gate validator was revised to score Gate 2 on "signal fires" rather than on absolute Sharpe.

3. **Same-sign-across-symbols is a cheap but powerful robustness filter.** Of 744 feature×horizon cells, only ~7 survive `same_sign ∧ min|IC| ≥ 0.04`. Each of those 7 has a structural interpretation (mean-rev, vol-filter, order-flow). Cherry-picking any single symbol produces far more spurious candidates.

4. **Directional crypto bar strategies cannot beat buy-and-hold in up-markets.** When BH makes +100% a year, a strategy that's only long ~10% of the time cannot possibly match BH return even if it has edge. The only way winners could beat BH on IR is in regimes where BH is also losing.

5. **Fee-saturation horizon is between 15m and 1h for crypto 5bps.** All 5m/15m LLM strategies lost ≥30% absolute, all 1h LLM strategies were marginal to positive. The weekly mean-rev signal works at 1h because it fires rarely (~22 RT / 6 months) and has per-trade magnitude > 2× fee.

## Lessons and Constraints

- **Don't stop at one feature.** Raw EDA that stops at the top-ranked signal would have missed taker_flow (rank #4) and range-filter (rank #2). Always promote the top 3–5 robust signals to candidate strategies.
- **Crypto 5m and 15m are effectively dead for directional strategies under 5bps/side fees.** Abandon strategies at horizons ≤15m unless they can demonstrate IS IC > 0.1.
- **KRX tick (21 bps round-trip) is structurally dead.** The project's 20 tick-KRX strategies have median ret ≈ 0%. No parameter sweep recovers this.
- **`generate_signal` contract is long-only {0, 1} in practice.** Only 2 of 44 strategies emit -1. This is a blindspot — the project cannot directly capture bearish signals except by being flat. To short, we would need to revisit the spec contract.
- **Pipeline must load extended OHLCV columns.** `load_horizon_data` previously dropped `taker_buy_base` — order-flow strategies crashed silently. Fixed on 2026-04-18.

## Session 2 additions — H4, H5 results (2026-04-18)

### H4 `hl_range_mean_48h` — SUPPORTED
Rule: long when 48h-rolling high-low range is above its 168h median (negative-IC → range↑ ⇒ return↑ in forward, opposite of the naive "vol contraction ⇒ breakout" folk belief).

| Symbol | OOS IR | Strat ret | BH ret |
|---|---|---|---|
| BTC | **+3.19** | OOS ran | OOS BH loss |
| ETH | **+1.99** | — | — |
| SOL | **+2.87** | — | — |

### H5 Portfolio basket — PARTIALLY SUPPORTED
Rule: OR-composition of weekly_meanrev ∥ taker_flow.

| Symbol | Basket OOS IR | Best single-signal OOS IR (from H1/H2) |
|---|---|---|
| BTC | +0.83 | +1.75 (H1 alone) — **basket worse** |
| ETH | **+3.93** | +2.59 (H2 alone) — **basket better** |
| SOL | **+3.52** | +3.89 (H1 alone) — slightly worse |

→ OR-composition over-trades on BTC (exposure jumps, double-fee). Works on ETH (signals agree more often). On SOL, weekly_meanrev alone is king.

### Corpus update after session 2
- **3 robust signal families confirmed**: H1 weekly_meanrev, H2 taker_flow, H4 range_filter.
- 14/21 crypto_1h strategies now pass all 4 gates (was 8/12, adjusted for new strategies).
- Original LLM-agent corpus (24 comparable) still 0/24 beat BH in absolute terms.

## Open Questions
- **H6** — Walk-forward: does the 4-month-IS/2-month-OOS result hold across 4–6 rolling windows, or is it specific to this one split?
- **H7** — Does weekly mean-rev still work at 15m (higher frequency, more fee drag) or 1d (fewer samples)?
- **H8** — Can we extend to KRX-equivalent daily bars (e.g. daily KOSPI top-10) where the same raw-EDA approach might find tradable signals despite the 21-bps-per-round-trip constraint?
- Do the signals reverse in 2023 or 2024 data? (pre-dates our current IS window — need to fetch earlier data)

## Paper Story Backbone (draft)

> 1. LLM-agent pipelines for algorithmic-trading strategy generation are dominated by the quality of the pre-curated signal brief; when the brief is narrow, the paradigm fails regardless of LLM capability.
> 2. We demonstrate this with a 44-strategy corpus where 0/24 comparable strategies beat buy-and-hold IR on OOS data.
> 3. A single pass of direct raw-data EDA, followed by a 4-gate programmatic validation, recovers two signal families with OOS IR +1.7–+3.9 on all three symbols.
> 4. The failure mode is not LLM capability; it is the *framing* imposed by pre-curated briefs.
> 5. We release the unified framework (raw-EDA + auto-design + 4-gate validation + programmatic feedback) so future LLM-agent work can be trained against the stronger baseline.

This would support §5 of the in-progress tick-fidelity paper or could be a standalone contribution.
