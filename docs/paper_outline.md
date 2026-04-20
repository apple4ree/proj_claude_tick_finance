# Paper Outline — v3

**Target venue (priority)**: NeurIPS 2026 Datasets & Benchmarks track · fallback: KDD 2027 · COLM 2027
**Status**: v3 post-literature-review + cross-engine POC (2026-04-17)
**Working title**: *The Tick-Level Fidelity Gap: LLM-Generated Trading Code Under Microstructure Scrutiny*

v3 replaces v1 ("Silent Spec Drift" mono-axis fidelity framing, abandoned after
n=6 pilot showed bug_pnl narrative too narrow to carry the paper). Core change:
scope the contribution at **resolution granularity (bar-level vs tick-level)**
rather than at absolute fidelity percentage, and position as a measurement
layer on top of *any* LOB engine rather than a single-engine study.

---

## One-paragraph abstract (draft)

Recent LLM-finance benchmarks (FactorMiner, Tsinghua 2026; AlphaForgeBench,
KDD'26; AlphaLogics, SZU 2026; Beyond Prompting, PKU 2026) evaluate
LLM-generated trading strategies at daily or N-minute bar resolution, reporting
backtest-code pass rates >96% and stable risk-adjusted performance. We argue
this apparent reliability is a **resolution-dependent artifact**: at tick-level
with realistic order-book mechanics, LLM-generated code exhibits systematic
silent failures that bar-level evaluation cannot surface. Using a 10-level
limit-order-book backtesting substrate with 5ms latency, queue-position fills,
and explicit spec-invariant checking, we document four structurally distinct
failure modes in LLM strategy-generation pipelines: **(i)** spec-implementation
drift (e.g., time-convention mismatches between generator and checker),
**(ii)** microstructure-domain knowledge gaps (e.g., sub-tick SL thresholds,
tick-size rule errors), **(iii)** multi-agent handoff information decay
(required fields dropped across the generator → spec-writer → coder chain),
**(iv)** invariant-taxonomy blindspots (e.g., limit-order crossover adverse
selection, entry-signal gate leakage). We introduce **counterfactual PnL
attribution** — a dual-mode (normal vs. spec-strict) backtest that quantifies
each failure mode's contribution to reported PnL — and demonstrate that this
measurement layer is **engine-agnostic**, reproducing identical violation
counts across our custom KRX engine and a synthetic HFTBacktest-style fill
stream. Across N strategies spanning K symbols, we find that X% of reported
PnL deviates from spec-compliant counterfactual; tick-size and time-convention
errors alone account for Y% of cataloguable failures. These results establish
that bar-level reliability claims do **not** generalize to microstructure-scale
execution and motivate tick-level evaluation as a mandatory complement to
existing LLM-finance benchmarks.

---

## Core claims (paper sells these)

- **C1 (methodological)**: Spec-invariant inference *from the LLM's own
  declared spec* — without human-authored test oracles — is sufficient to
  detect a non-trivial class of LLM code-gen failures deterministically.
- **C2 (methodological)**: Counterfactual PnL attribution (dual-mode backtest:
  normal vs. strict-spec enforcement) isolates the *magnitude* of each
  violation's impact on reported performance, not merely its frequency.
- **C3 (methodological)**: The measurement layer (spec-invariant checker +
  counterfactual attribution + agent trace + handoff audit) is
  **engine-agnostic**: it operates on `(spec, fill-list)` records and applies
  to any deterministic LOB backtest engine. We demonstrate on two engines
  (our KRX simulator; HFTBacktest-style synthetic fills) and intend to
  replicate on a live Binance-data HFTBacktest pilot.
- **C4 (empirical)**: Tick-level evaluation exposes failure modes that
  bar-level benchmarks miss. We enumerate four distinct, mechanistically
  different failure classes — each illustrated by at least one strategy in
  our corpus — and show their prevalence is non-negligible (not rare edge
  cases).
- **C5 (methodological, diagnostic)**: Our pilot exposes *limitations* of the
  invariant-checker taxonomy itself (e.g., silent gate-enforcement bypass,
  limit→marketable crossover, sub-tick SL thresholds), motivating a second
  tier of invariants for microstructure domains.

---

## Structural blueprint (8 sections + appendix)

### 1. Introduction

- Hook: LLM-finance benchmarks converged on "LLM writes executable code,
  engine runs" paradigm (AlphaForgeBench, FactorMiner, AlphaLogics). All
  report high code-execution pass rates. All operate at daily/N-minute bar
  resolution.
- Twist: at tick-level, systematic failures emerge that are invisible to
  bar-level evaluation. These failures exist *despite* the code running to
  completion without exception.
- Example (teaser figure F1): strategy strat_20260417_0001 reports -0.063%
  normal return; strict-spec counterfactual reports -0.038%. 40.1% of the
  *reported loss* is attributable to a silent `max_position_exceeded`
  violation the LLM's code permitted. Daily-bar evaluation of the same code
  would have smoothed this artifact.
- Contributions (C1–C5, compressed to 4 sentences).

### 2. Related Work

- **LLM strategy / factor generation at bar-level**: FactorMiner (10-min
  bars, CSI500/1000/HS300 + Binance), AlphaForgeBench (daily-OHLCV, KDD'26),
  Beyond Prompting (daily, PKU), AlphaLogics (daily via qlib).
- **Multi-agent trading systems**: TradingAgents, FinMem, AgenticTrading,
  Expert Investment Teams (Japan/Oxford).
- **Tick-level / LOB infrastructure**: HFTBacktest (nkaz001, MIT,
  Level-2/3, latency+queue), ABIDES-MARL (Nov 2025), JAX-LOB
  (GPU-parallel), LOB-Bench (Feb 2025, generative-model realism, *not
  LLM-agent*), NautilusTrader.
- **LLM code evaluation**: HumanEval, SWE-bench, LiveCodeBench — outcome =
  test pass. Our setting: outcome = fidelity metric, because stochastic
  trading domain has no unit-test oracle. Closest analogue: AlphaForgeBench
  which also eschews direct PnL in favor of code-gen stability, but stops
  at bar level.
- **Gap we fill**: tick-level × LLM-strategy-gen × spec-fidelity is empty.

### 3. Framework

- **3.1 Domain**: KRX (top-10 liquid symbols) + Upbit crypto; 10-level LOB;
  fee 21 bps round-trip (KRX) vs 4 bps (crypto).
- **3.2 Spec schema**: YAML with params for signal thresholds, PT/SL,
  trailing, entry gates, position limits. Written by a `spec-writer` LLM
  agent consuming upstream alpha + execution designs.
- **3.3 Invariant inference**: 7-type taxonomy auto-derived from spec
  parameter presence — `sl_overshoot`, `pt_overshoot`,
  `entry_gate_{start,end}_bypass`, `max_{entries,position}_exceeded`,
  `time_stop_overshoot`. No LLM involvement; fully deterministic.
- **3.4 Counterfactual engine**: dual-mode backtest. Normal = strategy code
  as-is. Strict = engine blocks orders / forces exits *as spec prescribes*.
  `bug_pnl := normal_pnl − strict_pnl`. `clean_pct := strict_pnl / normal_pnl
  × 100`. Note known limitations (§7).
- **3.5 Multi-agent pipeline**: 9-agent chain (alpha-designer →
  execution-designer → spec-writer → [code-generator | strategy-coder] →
  backtest-runner → {alpha-critic | execution-critic} → feedback-analyst).
  Per-agent trace logs (`agent_trace.jsonl`) and field-propagation audit
  (`handoff_audit.json`).
- **3.6 Engine-agnostic claim**: measurement layer decouples cleanly.
  `scripts/check_invariants_from_fills.py` reproduces byte-identical
  violation counts across our engine's embedded checker and standalone
  replay on any conformant `GenericFill` stream.

### 4. Experimental Setup

- **4.1 Corpus construction**: N LLM-generated strategies stratified across
  (a) top-crossover viable symbols, (b) mid-tier forced-rank signals, (c)
  execution-parameter stress. Generator: Claude Sonnet 4.6 (pinned; model
  versions logged in `agent_trace.jsonl`).
- **4.2 Data universe**: IS 2026-03-05 to 2026-03-20 (12 days, mixed
  regime); OOS reserved.
- **4.3 Metrics**: invariant violation count by type, `clean_pct_of_total`,
  `bug_pnl`, handoff field-propagation rate, agent_trace model-version
  coverage.
- **4.4 Adversarial control**: 5 hand-crafted buggy specs → checker recall
  (should approach 100% for the known injected invariants).
- **4.5 Engine cross-check**: same specs applied to `GenericFill`
  reconstruction from our engine + HFTBacktest-style synthetic stream →
  standalone checker yields identical violation shape.

### 5. Results — Four Failure Modes (C4)

- **5.1 Spec-implementation drift** (strat_20260417_0005): spec-writer
  emitted `entry_end_time_seconds=14400` (interpreted as *relative-to-open*
  by strategy-coder), while invariant checker interpreted as *absolute
  from midnight*. Result: 18 false-positive `entry_gate_end_bypass`
  violations — which *look* like failures but are actually a convention
  mismatch between two LLM-authored components.
- **5.2 Domain-knowledge gaps** (strat_20260417_0004, _0006):
  execution-designer stated "010140 tick size = 100 KRW" (incorrect, real
  tick is 50 KRW at ~30k KRW mid); "035420 tick = 500 KRW" correct; all
  LLM-chosen SL values at brief's optimal_exit=3 bps fall *below* 1-tick
  for the target symbols. In 3/4 pilot strategies the SL was mandatorily
  widened 200–1000% to clear the microstructure tick floor.
- **5.3 Multi-agent handoff decay** (baseline vs. explicit-propagation):
  without explicit propagation instructions, `signal_brief_rank` and
  `deviation_from_brief` are present in 0/1 strategies despite being
  *required fields* in the alpha-/execution-designer prompt specifications.
  With explicit propagation instructions, present in 5/5. We measure this as
  an instruction-sensitivity curve.
- **5.4 Invariant-taxonomy blindspots** (strat_20260417_0005 exec-critic):
  strategy.py gate-enforcement bugs (OBI condition bypassed in 8/18 fills,
  spread gate bypassed in 7/18) produce silently incorrect entries that the
  current 7-type invariant taxonomy cannot detect. We discuss two candidate
  new invariant types: `entry_signal_gate_breach` (decision-time condition
  not satisfied at submission time) and `limit_marketable_crossover`
  (passive limit becomes marketable during latency window → effective taker
  fill at worse price).

### 6. Results — Cross-Engine Replication (C3)

- Our custom KRX engine's embedded invariant check vs.
  `check_invariants_from_fills.py` replaying same fills: 6/6 strategies,
  `by_type_delta = 0` across all violation types.
- Synthetic HFTBacktest-style fill stream (KRX conventions, 4 scenarios
  with injected violations): standalone checker detects all injected
  violations.
- Planned: live-data Binance BTC pilot with HFTBacktest engine (future
  work in this paper's scope, or companion paper).

### 7. Methodological Limitations of `bug_pnl` (C5)

The `bug_pnl` metric has three breakdown regimes observed in our pilot:
- **Breakdown A** (strat_0003): strategy.py uses a 5-tick SL guard;
  strict-mode `should_force_sell` has no analog → strict PnL collapses by
  -$10k even when normal mode has *zero* invariant violations. `bug_pnl`
  becomes a phantom artifact of checker conservatism.
- **Breakdown B** (strat_0005): checker convention mismatch (§5.1) blocks
  all strict-mode entries → `strict_pnl = 0` by construction → `clean_pct`
  divergence is meaningless.
- **Breakdown C** (strat_0004, _0006): 0 violations but negative clean_pnl
  → metric correctly reports `clean_pct = 100%` (no bugs, pure alpha
  failure) but provides no actionable diagnostic — the failure is real and
  belongs elsewhere in the pipeline.

We propose that counterfactual attribution be **conditional** on the
checker taxonomy covering the failure of interest (per §5.4) AND on strict
mode respecting all strategy-code guards present in spec (e.g.
`sl_guard_ticks` must be added as a spec parameter AND honored by strict
force_sell).

### 8. Discussion

- Generalization: the measurement layer transfers to any deterministic LOB
  backtest engine with `(spec, fills)` exposure. Candidate substrates
  include HFTBacktest (MIT, Binance-native), NautilusTrader, ABIDES-MARL,
  JAX-LOB.
- Non-trading domains: invariant-inference-from-spec is applicable wherever
  (a) the spec has quantitative parameters with runtime semantics and (b)
  the execution environment is deterministic. SQL query plan validation,
  HPC numerical-kernel generation, and RL policy code are candidates.
- Limits: (i) taxonomy is necessarily incomplete (§5.4); (ii) attribution
  metric breaks down under conditions enumerated in §7; (iii) tick-level
  KRX corpus is 2026 market snapshot — alpha saturation phenomena (none of
  our viable signal picks produced profitable strategies) may be
  regime-specific; (iv) profitability is deliberately **not** a success
  metric — we measure failure modes, not returns.

### 9. Conclusion

Tick-level evaluation of LLM-generated trading code exposes failure modes
that bar-level benchmarks hide. We contribute an engine-agnostic measurement
layer (spec-invariant inference + counterfactual attribution + handoff
audit) validated across two engine backends, a four-mode failure taxonomy
grounded in empirical pilot data, and a constructive catalogue of invariant
types that microstructure-level LLM evaluation should adopt.

### Appendices

- A. Invariant-inference algorithm (pseudocode + 7-type registry)
- B. Strict-mode engine semantics (REJECT vs FORCE_SELL; known limits)
- C. Agent prompts for all 9 agents
- D. GenericFill schema and HFTBacktest adapter
- E. Adversarial spec corpus
- F. Per-strategy results (full table with clean_pct, violations,
  deviation_from_brief)
- G. Reproducibility checklist (LLM model versions, seeds, data dates,
  engine versions)

---

## Figure & table plan

| ID | Type | Content | Data status |
|---|---|---|---|
| **F1 (teaser)** | Stacked bar | `normal_pnl` vs `strict_pnl_clean` for strat_0001, `bug_pnl` wedge highlighted | ✓ have (real numbers: -0.063%, -0.038%, 40% bug share) |
| F2 | Framework diagram | Spec → invariant inference → dual-mode engine → attribution → handoff audit; engine-agnostic decomposition | Needs illustration |
| F3 | Box / violin | `clean_pct_of_total` distribution across corpus, stratified by failure mode | Needs n≥20 |
| F4 | Sankey / stacked bar | Multi-agent handoff — field-propagation rate at each pipeline stage, with instruction-sensitivity comparison | Partially available (n=6 current) |
| F5 | Heatmap | Invariant-violation-type × strategy-stratum frequency | Needs n≥20 |
| F6 | Recall calibration | Adversarial spec recall per invariant type | Needs 5 adversarial strategies |
| F7 | Cross-engine match | Parity plot of violation counts: our engine embedded vs standalone replay | ✓ have (6/6 strategies, delta=0) |
| T1 | Per-invariant table | Mean count, strategies affected, mean PnL impact, 95% CI (when n permits) | Needs n≥20 |
| T2 | Per-agent-stage table | Required fields, observed propagation rate, worked example | Partially available |
| T3 | Failure-mode matrix | 4 modes × 4–6 strategies, indicating which mode each exhibits | ✓ have (6/6 categorized) |

---

## Assets inventory (current)

### Code & infrastructure
- ✓ Custom KRX engine (`engine/`) with deterministic 5ms latency, queue-model
  resting limits, spec-invariant checker
- ✓ Engine-agnostic checker (`scripts/check_invariants_from_fills.py`) —
  byte-identical replay
- ✓ Counterfactual attribution (`scripts/attribute_pnl.py`)
- ✓ Handoff audit (`scripts/audit_handoff.py`)
- ✓ Iteration finalize (`scripts/iterate_finalize.py`)
- ✓ Agent-call trace (`scripts/log_agent_call.py`)
- ✓ HFTBacktest integration docs (`docs/hftbacktest_integration/`)
- ✓ 9-agent pipeline (`.claude/agents/`) + 2 orchestration commands
  (`.claude/commands/`)

### Data
- ✓ 6 LLM-generated strategies with full agent_trace + handoff_audit +
  attribution
- ✓ 45+ lessons + 18 patterns in knowledge graph (62 nodes, 84 edges)
- ✓ Signal briefs for 10 KRX symbols + BTC (crypto)
- ⊘ n=30 corpus — deferred (pilot showed diminishing marginal value for
  current paper scope; consider for camera-ready expansion)
- ⊘ 5 adversarial specs — next session
- ⊘ HFTBacktest live-data cross-engine pilot — next session(s)

### Narrative
- ✓ Literature positioning (AlphaForgeBench / FactorMiner / AlphaLogics /
  Beyond Prompting all bar-level; tick-level blue ocean)
- ✓ Two-sentence test passes
- ✓ 4 failure modes grounded in real pilot data
- ✓ Cross-engine replication POC result in hand

---

## Open storyline questions

1. How strongly to sell C4 (four failure modes)? If strong: figure F3 and
   table T3 are section-5 anchors. If weak: absorb into C2 attribution
   discussion. Current evidence supports strong framing.
2. Should the paper include live HFTBacktest results (hard dependency on
   Step 4 pilot completion), or keep cross-engine claim at
   "synthetic-fill-stream POC + roadmap"? For 2026 submission window,
   synthetic POC is defensible; live replication strengthens camera-ready.
3. How to handle profitability critique upfront (§1 or §8)? Proposal: address
   in §1 ("profitability is not our metric; fidelity is") and again in §8
   limitations (alpha saturation as scope condition).

---

## Next-session roadmap

1. Run 5 adversarial specs → produce F6 recall-calibration figure
2. Expand corpus from n=6 to n=20 (stratified, ~4–6 hours of agent runtime)
3. Upbit-CSV → HFTBacktest-.npz converter (see
   `docs/hftbacktest_integration/data_format.md`) + 1 live crypto pilot
   (crossengine replication with real fills)
4. Draft F1, F2, F7 in matplotlib; shell for T1, T3
5. Write §1 + §3 + §6 first (strongest evidence); fill §4–§5 as corpus
   expands
