# Strategy-Design References

Practitioner cheatsheets for strategy-generation agents. **Purpose**: concrete formulas + code snippets + real-failure case studies, not theory. Filling specific gaps identified in iter1 post-mortem.

## Available references

| File | Primary consumer | Failure mode addressed |
|---|---|---|
| **`exit_design.md`** | execution-designer | MFE give-back pattern (peak +292 → SL -480). Scale-out / ATR trailing / break-even shift / cooldown-after-SL. |
| **`mean_reversion_entry.md`** | alpha-designer | Oversold ≠ bounce imminent. Reversal confirmation + regime gate to avoid falling knife entries. |
| **`fee_aware_sizing.md`** | both designers | Break-even WR formula, fee-dominated regime detection, maker-vs-taker EV, lot-size slippage. |
| **`microstructure_primer.md`** | alpha-designer (LOB paradigm) | LOB signal formulas beyond engine's SIGNAL_REGISTRY (OFI, VPIN, depth slope, queue). |
| **`market_making.md`** | execution-designer (MM paradigm) | Avellaneda-Stoikov quoting, inventory skew, adverse-selection mitigation, MM-specific exit. |
| **`trend_momentum_entry.md`** | alpha-designer (trend_follow) | False breakout — retest / volume / ATR / regime gate / pullback vs breakout entry. |
| **`python_impl_patterns.md`** | strategy-coder | Engine API cheatsheet, SL-on-mid 7× overshoot fix, trailing state machine, TTL + bid-drop cancel, anti-pattern catalog. |
| **`portfolio_allocation.md`** | portfolio-designer | Kelly fractional, correlation-adjusted sizing (effective_n), EV-weighted allocation, concentration cap. |
| **`signal_diagnostics.md`** | alpha-critic | 5-step fixed-order diagnostic (selectivity → edge decomp → regime → capture_pct → cross-symbol), verdict grammar. |

## How agents use these

1. **On-demand consult** (not auto-loaded). Agent's `Read` tool pulls specific file when its prompt identifies relevance (paradigm, parent failure type).
2. **Citation in rationale** (soft requirement). Agent cites "`exit_design.md §2.4 break-even shift, BE threshold=20`" in `deviation_from_brief.rationale`. Critic can flag unreferenced exits.
3. **Not in Pydantic schema** — references are guidance, not validated output.

## Injection path in agent prompts

- `alpha-designer.md`: consult `mean_reversion_entry.md`, `trend_momentum_entry.md`, `fee_aware_sizing.md` (bar), `microstructure_primer.md` (LOB)
- `execution-designer.md`: consult `exit_design.md`, `fee_aware_sizing.md`, `market_making.md` (LOB)
- `strategy-coder.md`: consult `python_impl_patterns.md` (항상), `exit_design.md` §2.2 / `market_making.md` §2.3,§7 (trailing/MM 구현 시)
- `portfolio-designer.md`: consult `portfolio_allocation.md` (항상), `fee_aware_sizing.md` §3 (lot slippage)
- `alpha-critic.md`: consult `signal_diagnostics.md` (항상), `mean_reversion_entry.md` §2 / `trend_momentum_entry.md` §2 (paradigm별 진단 예시)
- `execution-critic.md`: consult `exit_design.md` §1,§4, `fee_aware_sizing.md` §6, `market_making.md` §3,§4 (MM 리뷰 시)
- `spec-writer.md`: no direct consult (번역 레이어)

## When to add a new reference

Add only when:
1. A specific failure pattern occurs across ≥ 2 iterations
2. The pattern's resolution is consistent across instances (formula, not heuristic)
3. The knowledge is **domain-external** (not captured in `knowledge/lessons/` which is project-empirical)

Otherwise, prefer updating `knowledge/lessons/` or agent prompts directly.

## Maintenance

- References here are **frozen snapshots** of best-practice knowledge at time of writing. They do NOT auto-update from external sources.
- When a reference's claim is invalidated by new empirical evidence (in `knowledge/lessons/`), flag with `[DISPUTED, see lesson_<id>]` inline.
- Expect refactoring once every ~50 iterations or major paradigm shifts.
