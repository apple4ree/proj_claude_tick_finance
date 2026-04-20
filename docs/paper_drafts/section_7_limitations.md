---
section: 7_limitations
paper: The Tick-Level Fidelity Gap
status: draft v1 (2026-04-17)
target_length: ~1 page (≈500–700 words)
---

# 7. Methodological Limitations of `bug_pnl`

The counterfactual attribution metric in §3.4 has three breakdown
regimes that every user of the measurement layer should recognize.
Omitting this analysis would produce a paper that over-claims the
interpretability of `clean_pct_of_total`, and one of our main
contributions (C5) is the explicit cataloguing of these regimes.

## 7.1 Regime A — strict mode is more conservative than the strategy code

*Observed in `strat_20260417_0003_pilot_s1_042700_obi10`.*

The strategy's Python `strategy.py` implements a **5-tick SL guard**:
the stop-loss condition is not evaluated until the position has been
held for at least five ticks, so that a single-tick bid dip does not
trigger a spurious stop. The guard is a *deliberate design choice*
encoded in the strategy code.

Our strict-mode engine's `should_force_sell` does not know about
this guard. It sees the spec's `stop_loss_bps` value and the current
bid price, and if the latter crosses the threshold it emits a
`FORCE_SELL` at the very next tick — three-to-four ticks earlier than
the strategy code itself would have. In the pilot run the strategy
had 3 profitable roundtrips under normal mode (WR 66.7%,
`normal_pnl = +763` KRW) and zero violations. Strict mode, by
intervening at the first tick threshold crossing, exited all three
positions *before* the profitable reversal, producing
`strict_pnl = −8774` KRW. The resulting
`bug_pnl = normal_pnl − strict_pnl = +9537` KRW and
`clean_pct_of_total = −1150%` are meaningless as fidelity signals:
there are zero actual bugs.

The general lesson is that any strategy-code-side implementation guard
that is **not** declared as a spec parameter creates a phantom
`bug_pnl`. The fix is to promote such guards to spec parameters
(e.g., `sl_guard_ticks: 5`) and to teach the strict-mode engine to
honor them, bringing normal and strict semantics back into alignment
for clean strategies. We added `sl_guard_ticks` to the spec schema
mid-pilot (beginning with `strat_0004`); subsequent strategies do not
exhibit Regime A.

## 7.2 Regime B — strict mode forecloses normal mode

*Observed in `strat_20260417_0005_pilot_s3_034020_spread`.*

When the invariant checker's conventions and the strategy-coder's
conventions disagree on the meaning of a spec parameter (§5.1),
strict mode intervenes at every BUY attempt and blocks all entries.
The result is `strict_pnl = 0` by construction, because no trades
executed. `clean_pct_of_total = 0 / normal_pnl × 100 ≈ 0%` becomes
uninterpretable: it does not mean "the strategy was 100% bugs"; it
means "strict mode disagreed with normal mode about what the spec
allows, so there is no common ground for comparison." The only
signal worth reading in Regime B is the violation count itself, which
here correctly flags 18 `entry_gate_end_bypass` events — but their
cause is a convention mismatch, not a code defect. We recommend that
any pipeline using `clean_pct_of_total` first verify that the
spec-writer and checker share conventions on temporal and
magnitude-unit fields.

## 7.3 Regime C — zero violations, negative clean_pnl

*Observed in `strat_20260417_0004_pilot_s2_010140_spread` and
`_0006_pilot_s4_035420_obi5`.*

When the strategy has genuinely no invariant violations and the
normal-mode PnL is negative, the attribution metric correctly reports
`clean_pct = 100%` (or near it) — meaning none of the observed loss
is attributable to spec violations. This is a **correct** reading of
the metric: the loss is real, and it is the strategy's alpha (or lack
thereof) that is failing. But the metric provides no additional
actionable diagnostic: it neither points at a bug to fix nor gives a
reason why the signal failed. Regime C is the metric's zero-
information null: it says "no bug here, look elsewhere." For our four-
mode taxonomy this is the correct behavior — alpha failures are not
the paper's contribution domain — but users of the measurement layer
should not over-interpret `clean_pct = 100%` as a positive result.

## 7.4 Conditional validity

The consolidated rule that emerges is that `clean_pct_of_total`
produces a meaningful fidelity signal **if and only if** three
conditions hold:

1. The invariant taxonomy covers the failure of interest (Regime C
   excluded when the failure is outside the taxonomy).
2. Strict-mode enforcement is aligned with strategy-code guards that
   the spec declares (Regime A excluded).
3. Spec-writer and checker agree on the conventions used by
   threshold parameters (Regime B excluded).

Users of the measurement layer should verify these three conditions
on their pipeline before quoting `bug_pnl` or `clean_pct` as a
primary result. In practice we find that routine checks — a small
adversarial-spec battery (Figure 6) for condition 1, a
sl_guard_ticks-style audit for condition 2, and a convention-
consistency check between `spec-writer` and `invariant_registry` for
condition 3 — catch the most common failure modes before a full
corpus run.

## 7.5 Other limitations

Beyond the attribution metric, the work has three further limitations
we list briefly. *First*, the 7-invariant taxonomy is incomplete by
construction — §5.4 enumerates three candidate additional invariants
(`entry_signal_gate_breach`, `limit_marketable_crossover`,
`sub_tick_sl_declaration`) that the present taxonomy does not cover.
*Second*, the pilot operates in the 2026 KRX regime in which tick-
level microstructure edges are saturated for most symbols; none of
the LLM-generated strategies in the pilot produced profitable
counterfactuals. This is a scope condition, not a defect —
profitability is not our success metric (§1) — but it limits the
range of market conditions the pilot exercises. *Third*, the LLM
generator is Claude Sonnet 4.6 only; the observed failure modes are
known to be prior-sensitive and we make no claim they generalize to
other frontier models without replication. The camera-ready version
will include Gemini 3 Pro and GPT-5.2 replication.

---

## Draft notes / TODO

- [ ] Confirm that `strat_0003` numbers (WR 66.7%, +763 normal, −8774
      strict, +9537 bug) match `attribution_summary.json` at paper
      freeze.
- [ ] Decide whether §7.4 should be a numbered proposition or
      integrated into the narrative as it currently is.
- [ ] Tighten prose — currently ~820 words, slightly over target.
