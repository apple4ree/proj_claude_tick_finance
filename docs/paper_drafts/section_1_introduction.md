---
section: 1_introduction
paper: The Tick-Level Fidelity Gap
status: draft v1 (2026-04-17)
target_length: ~1.5 pages (≈700–900 words)
---

# 1. Introduction

The rapid adoption of large language models as code-generating agents for
quantitative finance has produced a new evaluation paradigm: rather than
asking an LLM to emit buy/sell actions directly, recent benchmarks ask the
model to generate **executable trading-strategy code**, which a deterministic
engine then runs against historical data. AlphaForgeBench [Zhang et al., KDD'26]
formalized this shift and reported that frontier LLMs (Claude Sonnet 4.5,
GPT-5.2, Gemini 3 Pro, Grok 4.1) achieve >96% backtest-code pass rates on a
daily-OHLCV task suite — a seemingly decisive resolution of the run-to-run
instability that had plagued earlier direct-action trading agents. FactorMiner
[Wang et al., 2026] and AlphaLogics [Weng et al., 2026] build similar pipelines
for formulaic alpha discovery on Chinese A-share and S&P 500 equities, both
operating at daily or at most 10-minute bar resolution, and report
Information Ratios in the 1.25–1.53 range. Beyond Prompting [Huang & Fan,
2026] claims annualized Sharpe 2.75 on US equity long-short portfolios
generated entirely by autonomous agents.

We argue that this apparent reliability is a **resolution-dependent
artifact**. When the same code-generation paradigm is evaluated at tick-level
with realistic limit-order-book mechanics — 10-level depth, 5 ms feed/order
latency, queue-position fill simulation, and the kinds of fee structures
that dominate signal economics at microstructure scale — systematic silent
failures emerge that bar-level evaluation cannot surface. These failures
manifest *despite* the code executing to completion without exception, and
therefore do not register on pass-rate metrics. They manifest *despite* the
generator LLM producing structurally correct-looking Python, and therefore
do not register on static code-quality metrics. They manifest *despite*
run-to-run variance being low under temperature=0 decoding, and therefore do
not register on the reproducibility metrics AlphaForgeBench pioneered. What
they do register on is a microstructure-aware measurement layer.

**Example (Figure 1).** A representative LLM-generated multi-symbol strategy
in our corpus (`strat_20260417_0001`, Claude Sonnet 4.6 generator, KRX
equities) reports a normal-mode return of −0.063% over six IS dates — within
the noise band one would read as "roughly flat." Running the same strategy
code through a dual-mode engine that enforces the LLM's own declared spec
yields a strict-mode return of −0.038%. The difference, +0.025%, is not
noise: it is the PnL contribution of three deterministic
`max_position_exceeded` events where the strategy held 11 contracts on a
symbol whose spec declared `max_position_per_symbol=3`. **40.1% of the
reported loss is attributable to a silent spec violation that a daily-bar
evaluation would have smoothed into a single end-of-day P&L number.**

**Positive control (Figure 8).** To rule out the possibility that our
agent pipeline is simply defective at generating profitable code, we
replicate the same architecture at daily bar resolution on Binance spot
crypto (BTC/ETH/SOL; 2023–2024 IS, 2025 OOS; fee 10 bps round-trip).
Five LLM-generated bar-level strategies produce a median IS Sharpe of
+0.54 with best OOS Sharpe 1.12 and lowest OOS drawdown −3.7% — a
credible bar-level performance distribution comparable to the
frontier-model spread reported by AlphaForgeBench on their own
daily-OHLCV tasks. The same LLM, same agent chain, same measurement
layer, different horizon: **tick-level produces 6/6 unprofitable
strategies, bar-level produces 3/5 OOS-profitable strategies**. The
gap between these two distributions is the central empirical finding
of this paper.

## Contributions

This paper makes three methodological and two empirical contributions.

**Methodologically**, we introduce: **(C1)** *spec-invariant inference* —
a 7-type runtime-invariant registry auto-derived from the LLM's own declared
spec parameters (e.g., `stop_loss_bps=30` induces an `sl_overshoot`
invariant); no human-authored test oracles and no LLM-based critique are
required. **(C2)** *Counterfactual PnL attribution* — a dual-mode backtest
in which the engine additionally runs a `strict` variant that enforces the
spec deterministically (rejecting orders that would violate
position/entry-time invariants, force-selling positions that would violate
stop-loss/time-stop invariants). The PnL delta between normal and strict
modes isolates the *magnitude* of each violation's impact, not merely its
frequency. **(C3)** *Engine-agnostic reproduction* — we show the measurement
layer operates purely on `(spec, fill-list)` records and reproduces
byte-identical violation counts across our custom KRX engine and a
standalone replay on synthetic HFTBacktest-style fill streams (Figure 7),
establishing portability to any deterministic LOB backtest engine.

**Empirically**, our pilot on six LLM-generated strategies spanning KRX
top-10 liquid symbols yields: **(C4)** a four-mode failure taxonomy — (i)
spec-implementation drift (e.g., 18 false-positive `entry_gate_end_bypass`
violations caused by a second-convention mismatch between spec-writer and
invariant-checker LLMs); (ii) microstructure domain-knowledge gaps (e.g.,
sub-tick stop-loss thresholds forcing mandatory +200% to +1000% deviations
from brief-optimal exits); (iii) multi-agent handoff decay (mandated fields
`signal_brief_rank` and `deviation_from_brief` present in 0/1 baseline vs.
5/5 with explicit propagation instructions); (iv) invariant-taxonomy
blindspots (e.g., silent entry-gate leakage not detected by any of the 7
auto-inferred invariant types). Each failure mode is illustrated by at
least one concrete strategy in our corpus. **(C5)** a diagnostic analysis
of the `bug_pnl` metric's breakdown regimes, showing that counterfactual
attribution is **conditional** on the invariant taxonomy covering the
failure of interest and on strict-mode respecting all strategy-code guards
that the spec declares.

## Why tick-level

The concentration of recent work at daily/bar resolution has a natural
explanation: LLM training corpora are dominated by textbook treatments
(Fama–French, Alpha101/191, Qlib, FinRL) that operate at that resolution,
and LLMs accordingly have much stronger priors about daily-horizon feature
engineering than about microstructure details such as discrete-tick grids,
inter-level queue dynamics, or latency-induced limit→marketable transitions.
Every failure mode we document in Section 5 is mechanically traceable to
this asymmetry: the LLM's code is not wrong in the sense of failing tests —
it is wrong in the sense of operating with a bar-level mental model at
tick-level stakes, where fee-to-edge ratios tighten 5–10×, tick-size
constraints bind on stop-loss design, and order-flow mechanics dominate
fill quality. Our measurement layer makes this gap observable.

## Roadmap

Section 2 situates our work relative to the bar-level LLM-finance
benchmarks, tick-level LOB simulators, and LLM code-evaluation literatures.
Section 3 describes the invariant-inference pipeline and dual-mode engine.
Section 4 specifies the pilot corpus and cross-engine validation setup.
Section 5 documents the four empirical failure modes. Section 6 establishes
the engine-agnostic replication claim. Section 7 analyzes the
methodological limitations of counterfactual attribution. Section 8
discusses generalization to non-trading deterministic domains.

---

## Draft notes / TODO

- [ ] Check precise numbers against final n≥20 corpus; current numbers are
      pilot n=6.
- [ ] Verify AlphaForgeBench / FactorMiner / AlphaLogics / Beyond Prompting
      citations and exact metrics (ARR/SR values cited here are from §2
      scan, double-check in final camera-ready).
- [ ] Figure 1 will be the F1 teaser in `docs/figures/f1_teaser.png`.
- [ ] Tighten prose pass — currently ~950 words; target 700–900.
- [ ] Add a one-line statement early that profitability is **not** our
      success metric (pre-empt the "why unprofitable?" reviewer question).
      Consider placing at the end of the "apparent reliability is a
      resolution-dependent artifact" paragraph.
- [ ] Code / data release link (anonymized repo).
