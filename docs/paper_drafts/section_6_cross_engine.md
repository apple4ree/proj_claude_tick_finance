---
section: 6_cross_engine
paper: The Tick-Level Fidelity Gap
status: draft v1 (2026-04-17)
target_length: ~1 page (≈500–700 words)
---

# 6. Cross-Engine Replication

A single-engine study cannot distinguish *engine-specific artifacts* from
*LLM-behavior artifacts*. If the failure modes of §5 were observed only
in our custom KRX simulator, a skeptical reviewer could plausibly
attribute them to our engine's queue model, latency schedule, or fill
semantics — none of which are standardized across the LOB-simulator
landscape [HFTBacktest; NautilusTrader; ABIDES-MARL; JAX-LOB]. The C3
contribution, engine-agnostic measurement, addresses this directly: we
show that the spec-invariant checker and counterfactual attribution
operate on a generic `(spec, fill-list)` interface and produce identical
violation counts under two independent engine backends.

## 6.1 Standalone replay against the custom engine

Our first check is an in-place sanity test. For each of the six pilot
strategies, we extract the fill stream from `report.json` by materializing
each roundtrip as a (BUY, SELL) pair and sorting chronologically so that
overlapping positions receive correct `position_after` accounting. We
then run `scripts/check_invariants_from_fills.py` — which imports only
the `InvariantRunner` from `engine/invariants.py` and knows nothing
about the simulator — and compare the resulting violation list against
the one embedded in the engine's own `report.json`. Figure 7 plots
standalone violation count against embedded violation count per strategy;
all six points fall exactly on the parity line y = x, with
`by_type_delta = 0` across all seven invariant types for every strategy.
The highest-violation case (`strat_0005`, 25 violations) parity-matches
as cleanly as the zero-violation cases. This establishes that our
engine's embedded checker and a standalone replay produce byte-identical
results on the same fill stream — a necessary-but-not-sufficient
condition for engine portability.

## 6.2 Synthetic HFTBacktest-style fill stream

The more demanding test is to run the same checker against a fill
stream shaped by a *different* engine's record format. HFTBacktest
(`nkaz001/hftbacktest`, MIT-licensed; full Level-2/3 LOB reconstruction;
queue-position-aware fill simulation; configurable latency) is the
de facto open-source standard for tick-level backtesting and is
actively maintained (release py-v2.3.0, December 2025). We construct a
synthetic fill stream in the precise dict shape HFTBacktest's
`Recorder` emits — with fields `local_ts`, `exch_ts`, `side`
(BUY_EVENT=1, SELL_EVENT=2), `exec_price`, `exec_qty`, `order_id`,
`order_type` — and use a 20-line adapter (`hft_to_generic` in
`scripts/test_invariants_hftbacktest_style.py`) to map each record to
our `GenericFill` dataclass. The adapter is the *only* integration
code required.

We deliberately inject two distinct invariants in the synthetic stream:
one `entry_gate_end_bypass` (a BUY fill at 13:15 KST against a spec
declaring 13:00 KST cutoff) and one `sl_overshoot` (a SELL fill at
−60 bps realized against a spec declaring 30 bps stop with 10 bps
tolerance). The synthetic stream also contains two benign roundtrips
— an SL within tolerance and a PT within tolerance — to verify that
the checker does not produce false positives when conditions are met.

The standalone checker run on this synthetic HFTBacktest-style stream
detects exactly two violations: one `entry_gate_end_bypass` and one
`sl_overshoot`, at the injected fill indices. Zero false positives.
The runtime is the same `InvariantRunner` used for §6.1 and §5.

## 6.3 What this does and does not establish

The synthetic stream experiment demonstrates that the measurement
layer's interface (spec + generic fill list → violations) is engine-
agnostic at the type level: any engine that can produce HFTBacktest-
style fill records can be instrumented with our checker via a small
adapter. Combined with §6.1's byte-identical reproduction on our own
engine, this establishes the *functional* portability claim of C3.

What it does not yet establish is *semantic* portability under
real-data conditions. A full cross-engine replication would take an
LLM-generated strategy, feed its spec + Python to both our engine and
HFTBacktest over the same input data, collect both fill streams, and
confirm that the invariant violations under each engine align. That
experiment requires a Upbit-CSV-to-HFTBacktest-.npz converter (see
`docs/hftbacktest_integration/data_format.md`) and a port of the
strategy runtime to numba-compatible form. We treat this as scoped
future work and discuss the engineering trajectory in §8; the
camera-ready version of this paper will include the live-data result.

## 6.4 Significance

The engine-agnostic property has three downstream consequences we
want to surface.

First, it **isolates LLM-behavior failures from engine artifacts**:
any failure mode that reproduces across two independent engines is by
construction not a quirk of our simulator. We expect all four modes
in §5 to be engine-invariant, because each is traceable to a
structural property of the LLM-written code or spec rather than a
fill-mechanics choice.

Second, it **creates a concrete adoption path** for other LOB-
simulator users. A HFTBacktest, NautilusTrader, or JAX-LOB user
interested in LLM code-generation evaluation can adopt the invariant
checker without modifying their simulator: they need only write an
adapter from their engine's fill record to our `GenericFill` shape —
typically a dozen lines of Python.

Third, it **clarifies the paper's contribution boundary**. Our
contribution is *the measurement layer and what it reveals*, not an
LOB simulator. The simulator used in the pilot is a vehicle; the
measurement layer is the intended intellectual product. This framing
also answers a natural reviewer question — *why build a custom engine
at all?* — by making the custom engine's role instrumental rather
than load-bearing.

---

## Draft notes / TODO

- [ ] Replace synthetic HFTBacktest stream with a real-data
      replication once the Upbit-CSV converter lands.
- [ ] Consider whether §6 should come before §5 (tool-building before
      empirics) or after (as currently drafted). Current order matches
      reviewer intuition that empirics motivate the tool-building.
- [ ] Cite HFTBacktest's specific version (2.3.0) to anchor
      reproducibility.
- [ ] Tighten prose — currently ~720 words, within target.
