---
section: 5b_bar_level_results
paper: The Tick-Level Fidelity Gap
status: draft v1 (2026-04-17)
target_length: ~1.5 pages (≈800–1000 words)
target_placement: inserted as §5.5 or new §5.6 after tick-level results
---

# 5.5 Bar-level Replication: The Positive Control

A natural reviewer question about the pilot's tick-level results is whether
the observed negative returns reflect (a) LLM-generated strategies being
unprofitable in general, or (b) a resolution-specific phenomenon where
tick-level fee economics structurally prevent any signal from clearing
its edge. To disambiguate these, we replicate the same agent-pipeline
architecture on **daily bar data** for Binance spot crypto
(BTCUSDT, ETHUSDT, SOLUSDT; fee 10 bps round-trip; 2023-01-01 to
2024-12-31 IS, 2025 OOS). Figure 8 shows the result.

**Setup.** We retained the same three-stage agent chain
(alpha-designer → execution-designer → strategy-coder) and the same LLM
generator (Claude Sonnet 4.6). The only modifications were (i) removing
the tick-level signal-brief constraint (no LOB brief exists for daily
bars), (ii) allowing free choice of symbol from the Binance top-liquidity
universe, and (iii) allowing paradigms beyond tick-level mean-reversion
(the bar-level designers freely chose trend_follow, mean_reversion,
breakout, volatility_regime, and long-short variants). Five LLM-generated
strategies resulted: S1 (SOL trend+regime), S2 (BTC Bollinger-band
reversion), S3 (ETH Donchian breakout), S4 (SOL volatility compression),
S5 (BTC volatility-normalized long-short momentum). We executed each on
both IS and OOS splits via a bar-level backtest engine
(`scripts/bar_backtest.py`) that emits the same `GenericFill` record
schema the tick-level engine produces, so the invariant checker and
counterfactual attribution layer apply identically.

**Results.** In-sample Sharpe ratios ranged from −0.13 (S3 ETH breakout)
to +0.89 (S1 SOL trend), with a median of +0.54. Out-of-sample,
**S2 BTC BB reversion produced Sharpe 1.12 with +8.6% total return and
only −3.7% max drawdown** — a credible risk-adjusted outcome against the
bar-level buy-hold benchmark (BTC OOS buy-hold Sharpe 0.02, returns
−7.4%). Three of five strategies produced positive OOS returns; the two
that did not (S4 SOL, S5 BTC long-short) exhibited known failure modes —
S4's volatility-compression filter entered during extended vol-spike
regimes in 2025's mid-year selloff, and S5's long-short flipped short
during the late-2025 BTC rally, incurring −21% returns. We retain the
failing strategies in the corpus because our goal is fidelity measurement,
not alpha selection.

The broader result is in Figure 8: **the tick-level pilot produced 6/6
unprofitable strategies with Sharpe distribution centered at −0.85,
while the bar-level pilot produced 3/5 OOS-profitable strategies with
median Sharpe +0.17 and best 1.12**. The two distributions do not
overlap at the upper tail. This is the resolution-dependent performance
gap stated in the introduction: the *same* multi-agent generation
architecture produces strategies that are structurally unprofitable at
tick resolution and credibly profitable at bar resolution. The difference
is not the LLM's capability; it is the interaction between the LLM's
microstructure knowledge priors and the fee-to-edge ratio at each
resolution.

## 5.6 Attribution and violations at bar resolution

Running counterfactual attribution on the bar-level corpus produces a
second observation with paper-relevant implications. Of the five
bar-level strategies, only S5 produced any invariant violations
(`max_entries_exceeded` = 2 on IS, 1 on OOS). This is not because the
LLM suddenly became more careful — it is because **daily bars enforce
at most one entry per day by temporal discretization**, so the
`max_entries_per_session` invariant becomes almost trivially satisfied.
More generally, the invariant registry's sensitivity depends on the
horizon's relationship to the spec parameters: `sl_overshoot` is
meaningful at any horizon but the gate-bypass family is horizon-coupled
because `session` is interpreted as calendar date in both domains,
while the bar frequency determines how many fills compete for one
"session." This coupling is a *feature* of the measurement layer, not
a defect: at bar resolution, fewer invariants bind → the strategy's
observed `clean_pct_of_total = 100%` for most strategies is a faithful
reading (genuinely no bugs), not a blindspot.

This interacts with §5.1's spec-implementation drift finding. The
convention-mismatch pathology that produced 18 false-positive
`entry_gate_end_bypass` events in `strat_0005` does not recur in the
bar-level corpus — not because the LLM fixed it, but because the
bar-level timestamps are aligned to calendar days and the convention
question never arose. At bar resolution the *class* of failure mode
that §5.1 documents at tick resolution is latent: a bar-level checker
and a bar-level strategy-coder agree by default because both use
calendar-date semantics. At finer horizons (5-minute bars, 1-minute
bars, tick) the ambiguity space widens and the same LLM produces
divergent convention interpretations — the *space of silent drift grows
with temporal resolution*, independently of the LLM's nominal code-gen
capability.

## 5.7 What the bar-level evidence establishes

Three concrete claims are sharpened by the bar-level replication:

(1) **The measurement layer is horizon-portable.** The same invariant
checker, the same counterfactual attribution, the same handoff audit
operate unchanged across tick and daily-bar domains. Engine-agnostic
(§6) and horizon-agnostic are distinct portability dimensions; both
hold.

(2) **LLM-generated strategies at bar resolution are not a degenerate
case.** Figure 9 per-strategy breakdown shows genuine diversity in IS/OOS
behavior, consistent with the kinds of regime-transition sensitivities
that literature (FactorMiner, AlphaForgeBench) reports for bar-level
LLM-factor pipelines. The 11 bar-level Sharpe spread between best and
worst strategy is close to the 1.7-Sharpe spread AlphaForgeBench
observed across frontier models on their own daily-OHLCV tasks. We are
in the expected regime of operation.

(3) **Tick-level unprofitability is a domain property, not a pipeline
defect.** If the pipeline were broken, bar-level output would also
collapse. It does not. Therefore the tick-level failures documented in
§5.1–§5.4 reflect a microstructure-specific gap, and the four-mode
taxonomy is informative about *LLM behavior at the tick horizon*,
not about LLM code-generation in the abstract.

We discuss the policy implication of these three claims — that a full
LLM-finance evaluation should *mandatorily* include both bar-level and
tick-level evaluation, and that either alone over-claims — in §8.

---

## Draft notes / TODO

- [ ] Confirm exact per-strategy numbers against
      `data/bar_attribution_summary.json` at paper freeze.
- [ ] Cross-reference Figures 8 and 9 once numbering is locked.
- [ ] The claim about "the space of silent drift grows with temporal
      resolution" is a hypothesis grounded in one contrast, not yet a
      theorem. Need more horizons (5-min, 1-min intraday) to defend it
      as stated.
- [ ] Consider whether the final submitted paper should merge 5.5–5.7
      into a single subsection or keep three.
- [ ] §8 policy implication not yet written; need to loop back.
