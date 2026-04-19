# Experiment — run_20260419_035024

**Market**: crypto_1h · **Symbols**: BTCUSDT,ETHUSDT,SOLUSDT
**IS**: 2025-07-01 → 2025-10-31 · **OOS**: 2025-11-01 → 2025-12-31
**Design**: agent · **Feedback**: both · **N iterations**: 1 (scoped down from 3 for smoke test)

## Purpose

First end-to-end run of `/experiment` after the agent-handoff-schema rollout and crypto pivot (Option C). Goal: prove the unified pipeline can (a) generate a strategy via agent chain, (b) validate it at Pydantic handoff boundaries, (c) backtest + validate + feedback end-to-end, (d) produce a lesson that the next iteration's agents can read.

## Top robust signals (Phase 1 v2)

Read from `data/signal_briefs_v2/crypto_1h.json`.

| rank | feature | horizon | avg_IC | min\|IC\| | ev_bps_after_fee | viable |
|---|---|---|---|---|---|---|
| 0 | roc_168h | fwd_168h | -0.2093 | 0.0511 | +441.49 | ✓ |
| 1 | hl_range_mean_48h | fwd_168h | -0.1219 | 0.0419 | +322.22 | ✓ |
| 2 | zscore_168h | fwd_24h | +0.0885 | 0.0562 | +114.34 | ✓ |
| 3 | taker_buy_persistence | fwd_168h | +0.0755 | 0.0404 | +250.44 | ✓ |
| 4 | zscore_168h | fwd_12h | +0.0664 | 0.0460 | +58.07 | ✓ |
| 5 | lower_wick_rel | fwd_24h | -0.0599 | 0.0434 | +41.40 | ✓ |
| 6 | hl_range_z_48h | fwd_24h | -0.0582 | 0.0494 | +11.56 | ✓ |

## Iterations executed

| iter | strategies generated | passed 4 gates | meta-review? |
|---|---|---|---|
| 1 | 1 (BTCUSDT × rank-0 roc_168h) | 1/1 | no (< K=3) |

## Final leaderboard (sorted by OOS IR)

| strategy | origin | IS ret | OOS ret | OOS IR vs BH | 4 gates |
|---|---|---|---|---|---|
| crypto_1h_btc_mean_rev_168h_iter1 | agent chain | -7.07% | -8.41% | **+2.35** | ✓ |

**Note**: Strategy is absolute-money-losing on both IS and OOS, but IR is strongly positive because BH during OOS window was -19.62% (BTC crashed Nov-Dec 2025). Strategy avoided most of the drawdown — downside-filter effect rather than positive alpha.

## Lessons added

- `knowledge/lessons/20260419_crypto_1h_btc_mean_rev_168h_iter1_signal_edge_didnt_transfer_and_exits_broken.md`
  - Pooled cross-symbol EV (+441 bps) did NOT transfer to BTC-only (raw mean_fwd -10 bps)
  - Exit-tag mislabeling: all 12 roundtrips tagged `exit_signal` — PT/SL/trailing never fire (suspected `intraday_full_artifacts.py` bar-runner bug, not strategy.py)

## Pipeline verification (ALL stages verified)

| Stage | Status | Notes |
|---|---|---|
| Step 0 audit_principles | ✅ 12/12 | pre-flight clean |
| Step 1 discover_alpha | ✅ (cached) | signal_brief_v2 with calibration |
| 2a alpha-designer | ✅ 1st try pass | Pydantic BriefRealismCheck passed |
| 2a execution-designer | ⚠️ → ✅ | **1st try FAILED** (legacy flat shape, 18 schema errors); retry with nested shape PASSED — schema layer worked as designed |
| 2a spec-writer | ✅ | spec.yaml + strategy.py stub + alpha_design.md/execution_design.md copied |
| 2a strategy-coder | ✅ | replaced stub with full implementation |
| 2b intraday_full_artifacts | ✅ | backtest ran, 12 roundtrips, 0 invariant violations |
| 2c validate 4 gates | ✅ 4/4 | inv, oos (RT count), ir, cross-symbol (soft-pass) |
| 2d benchmark_vs_bh | ✅ | beat BH (-7.07% vs -17.86%) |
| 2e programmatic feedback | ✅ | feedback_auto.* generated |
| 2e alpha-critic | ✅ | identified weak edge + regime dependency |
| 2e execution-critic | ✅ | **identified CRITICAL exit-tag bug** |
| 2e feedback-analyst | ✅ | reconciled, lesson written, FeedbackOutput schema validated |
| 2f iterate_finalize | ✅ | handoff_audit + _iterate_context.md appended |
| Step 4 post-flight audit | ✅ 12/12 | engine sane |

## Artifacts

- `data/signal_briefs_v2/crypto_1h.json`
- `strategies/crypto_1h_btc_mean_rev_168h_iter1/` (19 files: spec.yaml, strategy.py, report.json, report.html, trace.json, analysis_trace.*, report_summary.md, alpha_design.md, execution_design.md, alpha_critique.md, execution_critique.md, feedback.json, feedback_auto.*, handoff_audit.json, idea.json, report_strict.json)
- `knowledge/lessons/20260419_*.md` (new, 3009 bytes)
- `strategies/_iterate_context.md` (appended)
- `experiments/run_20260419_035024/bh_benchmark.json`

## Findings (meta-level)

1. **Pydantic schema caught drift in practice** — execution-designer defaulted to legacy flat shape; hard-fail + retry with explicit structure example fixed it. This is exactly the mechanism we designed for.
2. **Critic agents found a real implementation bug** (exit-tag mislabeling) that pure pydantic validation couldn't catch — the narrative + quantitative critique layer is necessary.
3. **4-gate validation has a loophole**: absolute-loss strategies can pass if IR vs BH is positive (downside filter ≠ alpha). Gate 2 only checks roundtrip count, not profitability. Worth revising.
4. **Self-accumulation proved** — lesson saved, `_iterate_context.md` appended. Next iteration's agents would read these.

## Follow-up items surfaced

- [ ] Fix exit-tag assignment in `intraday_full_artifacts.py` (structural_concern from feedback-analyst)
- [ ] Consider tightening 4-gate validation (Gate 2 should require positive absolute return, not just roundtrips≥1)
- [ ] Re-run iter 2 on ETHUSDT where raw 168h mean_fwd is +613 bps (next_idea_seed)
