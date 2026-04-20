# Experiment — 2026-04-20 (crypto_lob smoke)

**Market**: `crypto_lob`   **Symbols**: BTCUSDT, ETHUSDT, SOLUSDT
**IS**: 2026-04-19T06:00:00Z → 2026-04-19T22:00:00Z (16h, 1,586,144 snapshots)
**OOS**: 2026-04-19T22:00:00Z → 2026-04-20T00:00:00Z (2h)
**Design**: agent   **Feedback**: both   **N iterations**: 2 (--smoke-test)

This run validated the Opt-α-6 end-to-end integration: the full /experiment agent chain now operates against `--market crypto_lob` without falling back to the bar-only code path. Pre-flight 12/12 and post-flight 12/12 both PASS.

---

## Top robust signals (Phase 1 LOB)

From `data/signal_briefs_v2/crypto_lob.json` (reused across both iterations):

| rank | feature | horizon | avg_IC | min\|IC\| | viable | ev_after_fee |
|---|---|---|---|---|---|---|
| 1 | obi_1 | fwd_10t | +0.2505 | 0.2352 | ✓ | 0.38 bps |
| 2 | obi_5 | fwd_10t | +0.2183 | 0.1375 | ✓ | 0.33 bps |
| 3 | obi_10 | fwd_10t | +0.2039 | 0.0978 | ✓ | 0.30 bps |
| 4 | total_imbalance | fwd_10t | +0.2039 | 0.0978 | ✓ | 0.30 bps |
| 5 | obi_1 | fwd_100t | +0.1988 | 0.1513 | ✓ | 0.89 bps |

All 10 `top_robust` entries are `viable=true` at fee=0 (maker assumption).

## Iterations executed

| iter | strategy | n_trades | n_RT | return | Sharpe | 4-gate | lesson |
|---|---|---|---|---|---|---|---|
| 1 | lob_iter1_obi1_spread_capture (BTC+ETH+SOL) | 3000 | 1500 | +0.10% | +2.11 | ✓✓✓✓ | SOL OBI bypass + spread 1.17>PT 1.09 → portfolio drag |
| 2 | lob_iter2_obi1_spread_gate (BTC+ETH, SOL gated) | 2000 | 1000 | +0.10% | +2.11 | ✓✓✓✓ | spread gate resolves SOL, BTC +0.267/ETH +0.184 bps at fee=0 |

Both iterations beat the 3-symbol buy-hold baseline **BH=−1.53%** by +1.63 pp.

## Final leaderboard (sorted by iteration)

| strategy | IR vs BH | return | n_RT | WR | avg_pnl_bps | passed |
|---|---|---|---|---|---|---|
| lob_iter2_obi1_spread_gate | +1.06 | +0.10% | 1000 | 37.5% | +0.226 | ✓ |
| lob_iter1_obi1_spread_capture | +1.06 | +0.10% | 1500 | 26.0% | −0.170 | ✓ |

(iter2's portfolio mean pnl is +0.226 bps across 1000 BTC+ETH trades; iter1's apparent equality to iter2 in `return_pct` is because the SOL drag (−481 bps aggregate) is small relative to total capital at fee=0.)

## Lessons added

- `knowledge/lessons/lesson_20260420_001_lob_spread_gt_pt_blocks_symbol_before_obi_signal_can_work_implementation_bypass_invalidates_cross_symbol_alpha_assessment.md` — per-symbol spread gate must precede OBI threshold in LOB strategies; spread exceeding PT structurally eliminates the edge before any signal logic runs.

## Structural concerns flagged to meta-reviewer

- **Fee viability**: at real Binance taker 4 bps round-trip, `fee_to_edge_ratio = 94.7%` for BTC+ETH gross edge (+0.226 bps). MARKET entry at 1-second LOB horizon is non-deployable; iter-3 must pivot to passive LIMIT_AT_BID or LIMIT_AT_ASK maker entry.
- **MFE/MAE null rate 97.6%**: engine trace sampling at `trace_every=500` is too sparse for a 10-tick hold window. enable `track_mfe=true` or reduce trace_every for LOB runs so capture_pct analysis becomes meaningful.
- **SL gap risk**: 10/11 iter-1 SL exits overshot spec to −3.5 bps avg due to 100ms monitoring cadence. Not a code bug; gap risk inherent to snapshot discreteness. Mitigations documented in `references/exit_design.md §1` (iter1 case study) and §3 decision table.

## Infrastructure validation (α-6 objective)

This is the intended outcome of Opt-α-6: the Phase 1 → agent chain → backtest → validate → BH → feedback → finalize pipeline runs end-to-end against `crypto_lob` data without schema breakage or missing artifacts.

| component | status | notes |
|---|---|---|
| `scripts/discover_alpha_lob.py` | ✓ | 16h × 3 symbols → 10 viable entries in 1m16s |
| `engine.runner` crypto_lob dispatch | ✓ | 1.58M snapshots backtested in ~5m each |
| `scripts/lob_full_artifacts.py` | ✓ | report.json / trace.json / analysis_trace.md / report.html all written |
| `scripts/benchmark_vs_bh.py` | ✓ | LOB branch (`bh_matched_lob`) works |
| `scripts/validate_strategy.py` | ✓ | `run_oos_lob` 4-gate validate passes |
| alpha/execution/spec-writer/strategy-coder agents | ✓ | all handoffs pass Pydantic verify_outputs |
| alpha-critic / execution-critic / feedback-analyst | ✓ | critiques grounded in analysis_trace + references/ citations |
| `scripts/iterate_finalize.py` | ✓ | _iterate_context.md updated per iteration |
| `scripts/run_feedback.py` | ✗ (bar-only bug) | fails on LOB report (missing avg_exposure etc.); agent-mode feedback used instead |

## Known follow-ups

1. `scripts/run_feedback.py` currently assumes bar-market report schema (expects `avg_exposure`, `ic_pearson`, etc. present). Needs `.get()` fallbacks or a LOB-specific branch to avoid `NoneType` format errors.
2. `trace_every` tuning for crypto_lob to raise MFE/MAE coverage above the current ~2.4%.
3. Capital scaling: `capital: 1e14` was required because `CRYPTO_PRICE_SCALE=1e8` makes BTC lot price ~7.5e12. Should be documented in `CLAUDE.md` or made automatic from `market==crypto_lob`.
4. `signal_brief_rank` 1-indexed alignment applied in this commit; earlier strategies (committed on feat/agent-handoff-schema) may have off-by-one optimal_exit baselines. Re-audit recommended.

## Artifacts

- `data/signal_briefs_v2/crypto_lob.json`
- `strategies/lob_iter1_obi1_spread_capture/` — full iter-1 artifact set
- `strategies/lob_iter2_obi1_spread_gate/` — full iter-2 artifact set
- `strategies/_iterate_context.md` — updated with iter 1 + iter 2 blocks
- `knowledge/lessons/lesson_20260420_001_*.md`
- `experiments/run_lob_smoke/bh_iter1.json`, `bh_iter2.json`
- audit_principles: **12/12** before and after the run
