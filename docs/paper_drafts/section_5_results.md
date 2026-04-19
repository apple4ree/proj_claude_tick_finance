---
section: 5_results
paper: The Tick-Level Fidelity Gap
status: draft v1 (2026-04-17)
target_length: ~2.5 pages (≈1400–1700 words)
---

# 5. Results — Four Failure Modes

We organize the empirical findings around four structurally distinct
failure modes observed in the pilot corpus. Each subsection pairs one
*mode* with one *representative strategy* that exhibits it in isolation,
and then surveys the mode's prevalence across the remaining strategies.
Our claim is not that any single failure mode dominates LLM code
generation — the pilot is too small (n = 6) for aggregate prevalence
statistics — but that all four modes **can be observed and attributed to
the LLM**, that each generates detectable signals under a different
subset of our measurement layer, and that *none* of the four would be
detected by a bar-level benchmark that reports only backtest pass rates
and Sharpe ratios. Table 3 summarizes which strategy exemplifies each
mode.

| Strategy                              | Mode (i) drift | (ii) knowledge | (iii) handoff | (iv) blindspot |
|---------------------------------------|:---:|:---:|:---:|:---:|
| `strat_0001_trajectory_multi_3sym`    |     |  ●  |  ●  |     |
| `strat_0002_smoke_042700_obi5`        |     |  ●  |     |  ●  |
| `strat_0003_pilot_s1_042700_obi10`    |     |  ●  |     |  ●  |
| `strat_0004_pilot_s2_010140_spread`   |     |  ●  |     |     |
| `strat_0005_pilot_s3_034020_spread`   |  ●  |  ●  |     |  ●  |
| `strat_0006_pilot_s4_035420_obi5`     |     |  ●  |     |  ●  |

**Table 3.** Failure-mode incidence across the pilot corpus. A filled
circle indicates the strategy was documented in the cited subsection as
exhibiting the mode clearly; absence does not rule out a subtler form.

## 5.1 Spec-implementation drift

*Representative: `strat_20260417_0005_pilot_s3_034020_spread`.*

The `spec-writer` agent for this strategy emitted
`entry_start_time_seconds: 1800` and `entry_end_time_seconds: 14400`,
interpreting these values as **relative to market open** (09:00 KST).
Under that convention, the active entry window is 09:30–13:00 KST, which
is what the strategy-coder agent implemented in `strategy.py` using a
`kst_sec - 32400` offset. The invariant checker, however, uses the
**absolute-from-midnight** convention that every other spec in our corpus
follows (09:30 = 34200 s, 13:00 = 46800 s). Consequently, every one of
the strategy's 18 live entries — all occurring between 09:30 and 12:02
KST on IS dates — was flagged as an `entry_gate_end_bypass` violation by
the invariant checker, because the checker observed `kst_sec > 14400` on
every BUY fill. Table 2 in §6 records the full 18 "violations" that are
in fact **false positives induced by a convention mismatch between two
LLM-authored components** of the same pipeline.

This is drift, not bug: the `strategy-coder` did not violate the
`spec-writer`'s stated intent; rather, the two agents silently
disagreed about what the integer `14400` means. In the generated
`idea.json` this disagreement is invisible — both agents emit
structurally valid JSON — and in a bar-level evaluation it would be
invisible entirely, since the P&L impact would be absorbed into the
daily return figure. Our measurement layer surfaces it deterministically
by noticing that 18 fills share a systematic gate-bypass signature, and
our attribution metric flags the pathology: strict-mode enforcement
blocks *all* 18 entries, producing `strict_pnl = 0` and a nonsensical
`clean_pct = -0.0%`. The attribution metric breakdown itself is the
signal. We discuss this regime more fully in §7.

Narrower forms of the same pattern appeared in earlier strategies.
`strat_20260417_0001` submitted orders with `max_position_per_symbol = 3`
and observed live positions of 11 on symbol 010140 — a 3.67× overrun
driven by a latency-window race condition the strategy-coder did not
anticipate. Here the semantic mismatch is between the coder's mental
model of "how many pending orders can be in flight" and the engine's
actual queue model. The violation is real (strict mode produces a
positive `clean_pct = 59.9%`; see Figure 1), but the root cause is the
same class of cross-agent mental-model disagreement.

## 5.2 Microstructure domain-knowledge gaps

*Representative: `strat_20260417_0004_pilot_s2_010140_spread`.*

In this strategy the `execution-designer` explicitly stated "KRX tick
grid for prices in the 10,000–50,000 KRW band is 100 KRW per tick."
This is incorrect: the actual tick for the 10–50k band is 50 KRW;
100 KRW applies to 50–100k. 010140 at ~30,625 KRW therefore has a real
tick of approximately 16.3 bps, not the 32.65 bps the
execution-designer computed. The SL threshold was set to
`stop_loss_bps = 32.65`, ostensibly "one tick" but actually 1.9 ticks,
with a 5-tick guard. In execution, this produced realized stop losses
clustered at −18 bps (≈1-tick drop) and −34 bps (≈2-tick drop) —
roughly 2× the nominal spec loss — and a silent transformation of
what the designer intended as an aggressive 1-tick SL into a wider
2–3-tick SL that no longer matched the brief's Sharpe-optimal exit
structure.

The same class of error recurs in a sharper form across the pilot: in
*every* strategy that carried forward the `signal_brief.optimal_exit`
recommendation of `sl_bps = 3`, the LLM-written execution design had
to widen the SL by +200% to +1000% to clear the target symbol's
physical tick floor. On 042700 at ~303k KRW (`strat_0002`, `_0003`),
tick = 16.5 bps → SL widened to 21–33 bps; on 035420 at ~222k KRW
(`strat_0006`), tick = 22.4 bps → SL widened to 22.44 bps; on 010140
(`_0004`), tick = 16.3 bps real → widened to 32.65 bps nominal. In
each case the execution-designer correctly flagged the deviation in a
`deviation_from_brief.rationale` field and the
`structural_concern` escalation path, and in each case the final SL
value was a function of the designer's *computed* tick size, which was
incorrect in one case out of four.

None of these mistakes produce runtime errors. None would register on
a bar-level pass-rate metric. They surface in our layer because (i) we
record the `sl_overshoot` realized distribution and (ii) we record the
`deviation_from_brief` field as a structured artifact, letting us
distinguish "deliberate deviation with rationale" from "unexamined
domain error."

## 5.3 Multi-agent handoff decay

*Representative: `strat_20260417_0001_trajectory_multi_3sym` baseline vs.
`strat_0002`–`_0006` with explicit propagation instructions.*

The `alpha-designer` agent prompt mandates returning an integer field
`signal_brief_rank` in its JSON output, and the `execution-designer`
agent prompt mandates a `deviation_from_brief` object with
`pt_pct`, `sl_pct`, and `rationale` subfields. Both fields are
*required*. Both are consumed by downstream critics and by the paper's
handoff audit.

**Baseline (strat_0001).** The strategy was generated without any
explicit instruction on propagation. The resulting `idea.json` did not
contain `signal_brief_rank` or `deviation_from_brief`. The fields were
dropped silently somewhere between alpha-designer's JSON output and
spec-writer's serialization, and no downstream agent complained.

**With explicit propagation instructions (strat_0002 through 0006).**
When the orchestration instruction was amended to say "idea.json MUST
preserve signal_brief_rank and deviation_from_brief VERBATIM," all five
subsequent strategies successfully propagated both fields. Our
handoff-audit metric `signal_brief_rank_presence` moved from 0/1 (0%)
to 5/5 (100%).

This is an instruction-sensitivity result, not a reliability result.
The field-propagation rate is not a function of the underlying LLM's
capability; it is a function of how explicitly the orchestration layer
reminds the LLM of the requirement. We interpret this as evidence that
multi-agent pipelines silently drop mandated fields by default, and
that the reliability of downstream auditing is conditional on an
additional layer of orchestrator-level nagging that the current
literature on agent pipelines does not adequately emphasize. Figure 4
plots the cumulative field-propagation rate by pipeline stage with and
without explicit propagation instructions.

## 5.4 Invariant-taxonomy blindspots

*Representative: `strat_20260417_0005_pilot_s3_034020_spread` (again),
`_0003`, `_0006`.*

The 7-invariant taxonomy in Table 1 does not cover every deterministic
failure mode LLM-generated trading code exhibits. Three classes we
observed but the current taxonomy misses:

**(a) Entry-signal gate leakage.** In `strat_0005` we audited fill
contexts and found that 8 of 18 live BUY fills had a snapshot OBI
value at or below the spec's 0.50 threshold — including two fills with
negative OBI (buy-side pressure the gate was explicitly designed to
exclude). The strategy-coder's Python evaluated the OBI condition
before calling `update_state()`, producing a stale read. The invariant
checker has no mechanism to re-verify decision-time conditions at
fill-time: the `entry_gate_*` family covers the *temporal* gate, not
the *signal-condition* gate.

**(b) Limit→marketable adverse selection.** In `strat_0002` a passive
LIMIT BUY was submitted at the then-current bid (302,500) with a 5 ms
latency. During the latency window the bid dropped one tick while the
ask remained at the submitted limit price, rendering the order
marketable. The engine's `walk_book` then filled at the ask, producing
a fill price 16.5 bps above the submitted limit. No existing invariant
catches this: the order was legitimately placed and legitimately
filled, yet the fill price diverged materially from the declared
execution intent ("passive at-bid entry").

**(c) Sub-tick threshold declarations.** When `stop_loss_bps` is set
below the symbol's physical 1-tick bps equivalent, every SL fill must
deterministically overshoot by at least half a tick. Our layer catches
the overshoot via `sl_overshoot` but does not catch the upstream
design error. A candidate new invariant, `sub_tick_sl_declaration`,
would check `stop_loss_bps < tick_size_bps(symbol)` at spec-load time
and emit a static-analysis warning before any backtest is run.

We do not propose to resolve these blindspots in the present work. We
document them because they are *diagnostic* of the limits of static
spec-inference. The existence of such cases — three distinct patterns
in a 6-strategy pilot — suggests that microstructure-scale LLM
evaluation will require a second-tier invariant system layered atop
the first, potentially including spec-time static checks
(sub_tick_sl_declaration, convention_consistency) in addition to the
runtime fill-stream checks our layer currently implements.

## 5.5 Aggregate observations

Across the six pilot strategies, `clean_pct_of_total` spans
(−1150%, 100%), with the extreme negative value reflecting the
`bug_pnl` breakdown condition in `strat_0003` (see §7) and the two
100% values corresponding to clean strategies with zero real
violations (`strat_0002`, `_0006`). Of the 31 total invariant
violations in the corpus, 18 (58%) are false positives induced by the
convention-mismatch issue in §5.1, 10 (32%) are real `sl_overshoot`
events traceable to the microstructure-knowledge gaps in §5.2, and 3
(10%) are real `max_position_exceeded` in `strat_0001`.

We emphasize that these fractions are *illustrative* at n = 6 and
should not be reported as statistical prevalence. A full-scale study
(n ≥ 20, stratified across signal families and symbols, with
adversarial controls as in Figure 6) is the subject of ongoing work
to be reported in the camera-ready version of this paper.

---

## Draft notes / TODO

- [ ] Confirm exact numbers (e.g. realized SL cluster bps for
      `strat_0004`) against `report.json` at paper freeze time.
- [ ] Decide whether Table 3 presence pattern should become its own
      figure. Current density is acceptable in-line.
- [ ] §5.5 aggregate statistics are illustrative — rerun once n ≥ 20.
- [ ] Cross-reference Figure 4 (handoff propagation) once the figure is
      generated.
- [ ] Consider elevating §5.4 to a standalone section at final revision:
      the three candidate new invariants are a constructive contribution.
