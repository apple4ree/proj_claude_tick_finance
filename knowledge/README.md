# Knowledge Vault

Obsidian-compatible knowledge base for the tick strategy framework. Three content types:

- `lessons/` — single-iteration learnings distilled from strategy backtests + critiques
- `patterns/` — cross-lesson patterns (≥3 lessons sharing a root cause)
- `seeds/` — proposed next-iteration directions

Graph index: `.graph.json` (regenerate via `python3 knowledge/graph.py build`).

---

## 2026-04-19 Strategy Archival Notice

On 2026-04-19 the `strategies/` directory was cleaned to 4 meta entries only (`_drafts/`, `_trajectories/`, `_examples/`, `_iterate_context.md`). 65 strategy directories produced between 2026-04-14 and 2026-04-18 were deleted as part of the repository cleanup that followed the agent-handoff-schema rollout (see `docs/superpowers/specs/2026-04-17-agent-handoff-schema-design.md`).

**Implication for this vault:**

- **Lesson frontmatter `source: strat_*` fields** and inline strategy-ID mentions in 47+ lessons point to strategies that **no longer exist on disk**. The analytical claims and distilled patterns in each lesson remain valid — they stand on their own. Only the raw backtest reports and spec YAMLs were removed.
- If a lesson's claim needs to be empirically re-verified, the strategy must be regenerated (via `/experiment --design-mode agent` with a seed that reproduces the original setup). The lesson's `metric` field preserves the original scalar outcome.
- `pilot_s3_034020_spread` is the one strategy whose `idea.json` was preserved — it now lives at `tests/fixtures/pilot_s3_idea.json` and backs the regression test `tests/test_handoff_pilot_s3_replay.py`.

This is a one-time archival event. Post-2026-04-19 lessons are produced under the new portfolio-mode evaluation default and the pydantic handoff schema; their `source:` references point to live strategies.
