# Research Log — Raw-EDA Alpha Discovery

Decision timeline. One dated entry per meaningful choice.

---

## 2026-04-18

### Bootstrap (session 1)

- Reframed the project from "LLM-pipeline strategy generator" to "does raw-EDA recover alpha that LLM-pipeline misses?"
- Context: prior 44-strategy corpus across tick KRX, bar daily, crypto horizons showed 0/24 beating buy-and-hold IR on period-matched comparison.
- Decision: establish a buy-and-hold benchmark as the official null model (3 new `bar_baseline_bh_*` strategies added).
- Decision: add IC / ICIR / IR plumbing to the standard metric set so all strategies are scored on the same axis.
- Decision: IS/OOS split = 2025-07~10 / 2025-11~12 on Binance 1h for crypto.

### Phase 1 EDA

- Ran 31 features × 8 horizons × 3 symbols = 744 IC cells on IS only.
- Top robust (same sign across BTC/ETH/SOL, min|IC|≥0.04): 7 cells.
- Rank 1: `roc_168h → fwd_168h` IC = −0.2093 (weekly mean-reversion).
- Rank 2: `hl_range_mean_48h → fwd_168h` IC = −0.12 (vol-filter).
- Rank 3/4/5: zscore momentum + taker-flow + zscore @12h.

### Phase 2 first prototypes

- Built `crypto_1h_weekly_meanrev_{btc,eth,sol}` as transparent one-line rule: `(roc_168h < -θ).astype(int)`.
- IS sweep picked θ = 0.10 (BTC), 0.05 (ETH), 0.05 (SOL).

### Phase 3 OOS results (param frozen)

| Symbol | Strat ret | BH ret | Strat Sharpe | **IR vs BH** | RT |
|---|---|---|---|---|---|
| BTC | −7.83% | −19.48% | −2.12 | **+1.75** | 30 |
| ETH | −4.20% | −22.91% | −0.27 | **+2.44** | 34 |
| SOL | −4.67% | −33.26% | −0.21 | **+3.89** | 64 |

Result: first OOS-positive-IR strategies in the project. Logged as lesson_20260418_002.

### Pipeline unification

- Built 5 new scripts: `discover_alpha.py`, `benchmark_vs_bh.py`, `validate_strategy.py`, `run_feedback.py`, `full_pipeline.py`.
- Created `gen_strategy_from_brief.py` (auto-design from signal_brief).
- Created `.claude/commands/experiment.md` — unified entry point.
- Updated CLAUDE.md.

### Extended experiment — 6 more raw-EDA strategies

- Added `crypto_1h_zscore_trend_*` (H3) and `crypto_1h_taker_flow_*` (H2).
- Pipeline ran 12 strategies in ~1 min, 8/12 passed all 4 gates.
- H2 taker_flow: PASS on all 3 symbols, supporting the hypothesis.
- H3 zscore_trend: BTC fails G3 (OOS IR −0.10), ETH/SOL fail G4 (cross-symbol mismatch). Partially refuted.

### Decisions for next inner-loop cycle

- Promote H4 (hl_range_mean_48h) to a strategy and validate.
- Build H5 (portfolio basket) — combine H1 weekly_meanrev + H2 taker_flow into a multi-signal strategy.
- Plan H6 (walk-forward) — 4 rolling IS/OOS windows covering full 6-month data.
- Investigate whether BTC is unusually hard for trend-follow (H3 BTC fail) — is there a BTC-specific regime the other symbols don't share?
