---
section: 3_framework
paper: The Tick-Level Fidelity Gap
status: draft v1 (2026-04-17)
target_length: ~2 pages (≈1000–1200 words)
---

# 3. Framework

Our measurement layer consists of four deterministic components that
compose into an end-to-end pipeline. Given a strategy specification emitted
by an LLM agent, we (i) infer a set of runtime invariants from the spec
parameters, (ii) run the strategy through a dual-mode tick-level backtest
engine that additionally produces a spec-strict counterfactual, (iii) log
each agent invocation along the generation chain for handoff-fidelity
accounting, and (iv) replay the resulting fill stream through an
engine-agnostic invariant checker. Figure 2 shows the high-level structure.
We describe each component in turn; throughout, we use snake_case names
(e.g., `sl_overshoot`) that match the identifiers in the released code.

## 3.1 Domain and data

The pilot operates on KRX 10-level limit-order-book tick data for the top-10
liquid equities (tickers 005930, 000660, 005380, 034020, 010140, 006800,
272210, 042700, 015760, 035420) over an in-sample window from 2026-03-05
to 2026-03-20 (12 trading days, mixed up/down regime). An out-of-sample
window (2026-03-23 to 2026-03-30) is reserved for final validation and is
not used anywhere in the present work. The fee model is KRX-realistic:
1.5 bps commission per side plus 18 bps seller tax, totaling 21 bps
round-trip. Latency is deterministic-stochastic: a 5 ms mean with 1 ms
jitter, seeded for reproducibility. Our framework does not assume KRX
specifics; §6 demonstrates the measurement layer operating on synthetic
HFTBacktest-style fill streams under arbitrary fee/latency settings, and
the KRX fee is used here only because it makes the tick-level
fee-to-signal-edge constraint bind tightly, sharpening the failure modes
we wish to document.

## 3.2 Spec schema and LLM-written specs

Each strategy is represented by a `spec.yaml` file containing a `params:`
block with fields such as `profit_target_bps`, `stop_loss_bps`,
`entry_start_time_seconds`, `entry_end_time_seconds`,
`max_entries_per_session`, `max_position_per_symbol`, `time_stop_ticks`,
`sl_guard_ticks`, and strategy-specific signal thresholds. The spec is
written by the `spec-writer` LLM agent consuming upstream outputs from an
`alpha-designer` (signal choice and entry condition) and an
`execution-designer` (order mechanics and exit structure). For Python-path
strategies, a `strategy-coder` agent then produces the corresponding
`strategy.py` implementation of the spec.

We do not constrain *what* the LLM may place in the spec beyond the schema;
the invariant layer operates on whatever parameters the LLM declared. This
is central to our contribution: the checker's fidelity target is **the
LLM's own stated intent**, not a human-written test oracle. A strategy that
declares no `stop_loss_bps` has no `sl_overshoot` invariant to violate.

## 3.3 Spec-invariant inference

We maintain a registry of seven invariant types, each keyed to a specific
spec parameter (Table 1). At spec-load time, `infer_invariants(spec)` walks
the registry and emits an active invariant for every spec parameter that
is present and non-null. For example, a spec containing
`stop_loss_bps: 30.0` induces an active `sl_overshoot` invariant with
threshold 30 bps and high severity; a spec without that parameter omits
the invariant entirely (no false positives on strategies that deliberately
do not cap loss).

| Invariant              | Spec parameter              | Severity | Tolerance   |
|------------------------|-----------------------------|----------|-------------|
| `sl_overshoot`         | `stop_loss_bps`             | high     | 10 bps      |
| `pt_overshoot`         | `profit_target_bps`         | low      | 20 bps      |
| `entry_gate_end_bypass`| `entry_end_time_seconds`    | high     | 0           |
| `entry_gate_start_bypass`| `entry_start_time_seconds`| high     | 0           |
| `max_entries_exceeded` | `max_entries_per_session`   | high     | 0           |
| `max_position_exceeded`| `max_position_per_symbol`   | high     | 0           |
| `time_stop_overshoot`  | `time_stop_ticks`           | medium   | 50 ticks    |

**Table 1.** The 7-type invariant registry. Tolerances absorb legitimate
discrete-tick slack; violations are reported only when realized
out-of-spec magnitude exceeds `threshold + tolerance`.

During the backtest, an `InvariantRunner` subscribes to the engine's fill
stream and records a violation each time a fill's realized semantics exceed
the active threshold + tolerance. For stop-loss and profit-target checks,
realized bps are computed against the original entry price of the same
position. For entry-gate checks, the fill's wall-clock second is compared
against the spec's gate bounds. For max-entries and max-position, per-day
counters and running per-symbol quantities are maintained.

## 3.4 Dual-mode backtest and counterfactual attribution

The backtest engine supports two execution modes sharing the same data
stream, latency model, and strategy code:

- **Normal mode** — the default. The strategy's own Python logic decides
  order submission and exit timing. Invariants are checked but not
  enforced: violations are recorded to `report.json` post hoc.
- **Strict mode** — invariants are *enforced* by engine intervention:
  BUY orders that would violate gate or position invariants are
  `REJECT`ed at match time (`should_block_order`); open positions that
  cross the SL or time-stop threshold trigger a synthetic `FORCE_SELL` at
  the current bid (`should_force_sell`). The strategy Python code is
  unchanged; enforcement lives entirely in the engine.

Given both runs, the counterfactual PnL decomposition is
$$
\texttt{bug\_pnl} \;=\; \texttt{normal\_pnl} \;-\; \texttt{strict\_pnl\_clean}
$$
and the clean-performance fraction is
$$
\texttt{clean\_pct\_of\_total} \;=\; \frac{\texttt{strict\_pnl\_clean}}{\texttt{normal\_pnl}} \times 100\%.
$$
Intuitively, `strict_pnl_clean` is the PnL the strategy would have produced
had it obeyed its own declared spec. `bug_pnl` is the portion of reported
performance attributable to spec violations. `clean_pct` provides a
dimensionless summary; we discuss its breakdown regimes in §7.

## 3.5 Multi-agent generation pipeline and trace logging

Strategy generation proceeds through a 9-agent chain:
`alpha-designer → execution-designer → spec-writer → [code-generator or
strategy-coder] → backtest-runner → {alpha-critic ∥ execution-critic} →
feedback-analyst`. Each agent reads structured output from its predecessor
and emits structured output for its successor; role-specific drafts (e.g.,
`alpha_design.md`, `execution_design.md`) are persisted alongside the spec.

After each agent invocation we append one JSONL record to
`strategies/<id>/agent_trace.jsonl` via `scripts/log_agent_call.py`,
capturing the agent identity, model family, status, optional output hash,
and wall-clock timestamp. The trace is the basis for two diagnostic
queries: (i) *model-version reproducibility* — did we record which model
generated each strategy? and (ii) *handoff fidelity* — did each agent
propagate the mandated fields to its successor? The latter is measured by
`scripts/audit_handoff.py`, which checks the presence of required fields
in `idea.json` (e.g., `signal_brief_rank`, `deviation_from_brief`) and the
existence of downstream artifacts (e.g., `alpha_critique.md`,
`execution_critique.md`, `feedback.json`). Field-presence rates are tracked
per strategy and aggregated across the corpus; the resulting propagation
curve is Figure 4.

An important design decision: the `_iterate_context.md` file that feeds
subsequent-iteration agents **deliberately excludes** handoff-audit data
(though it includes attribution metrics such as `clean_pct` and
`bug_pnl`). Downstream agents should not see fidelity metadata that could
artificially correct their own behavior; the paper pipeline reads the audit
separately from `strategies/<id>/handoff_audit.json`.

## 3.6 Engine-agnostic interface

The invariant checker operates on a generic `Fill` record that any
deterministic LOB backtest engine can produce:
```python
@dataclass
class GenericFill:
    ts_ns: int         # exchange timestamp in nanoseconds
    symbol: str
    side: str          # "BUY" or "SELL"
    qty: float
    price: float
    tag: str           # e.g. "entry_obi", "stop_loss", "profit_target"
    ticks_held: int | None     # for time_stop checks
    position_after: int | None # for max_position checks
    lot_size: int
    context: dict      # per-fill book context, optional
```
A standalone driver, `check_invariants_from_fills.py`, takes a spec and a
list of `GenericFill` records and produces violations identical in schema
to the engine's embedded output. We verify in §6 that this standalone
replay reproduces byte-identical violation counts on our custom engine and
operates correctly on synthetic HFTBacktest-style fill streams. This
separation is what allows us to claim the measurement layer is portable
across any engine that emits `(spec, fill-list)` — a claim we demonstrate
empirically rather than merely architecturally.

## 3.7 Reproducibility artifacts

Every strategy directory produced by the pipeline contains, at completion:
`spec.yaml`, `strategy.py` (for Python-path strategies), `idea.json`,
`report.json` (normal mode), `report_strict.json` (strict mode),
`alpha_design.md`, `execution_design.md`, `alpha_critique.md`,
`execution_critique.md`, `feedback.json`, `agent_trace.jsonl`, and
`handoff_audit.json`. A separate `data/attribution_summary.json` aggregates
per-strategy attribution. The full generation pipeline is deterministic
given (i) fixed data, (ii) fixed simulator seed, and (iii) pinned LLM
model version — the last of which is recorded in `agent_trace.jsonl` at
each invocation. The measurement layer (invariant registry, attribution
script, audit script) has zero stochastic elements.

---

## Draft notes / TODO

- [ ] Figure 2 (framework diagram) still pending; reference will be updated
      once the figure is generated.
- [ ] Confirm Table 1 tolerances match `INVARIANT_REGISTRY` at paper
      freeze time.
- [ ] Decide whether §3.5 goes here or as a standalone §4 "experimental
      setup" — current placement assumes framework-then-experiments
      structure.
- [ ] Cite the `engine-agnostic` POC result numerically (6/6 strategies,
      zero violation-count delta) here, or defer to §6.
- [ ] Tighten prose — currently ~1150 words, within target.
