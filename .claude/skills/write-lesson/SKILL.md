---
name: write-lesson
description: Append a new lesson MD file under knowledge/lessons/ with Obsidian-compatible frontmatter and wiki links.
---

# write-lesson

## Usage

```bash
python scripts/write_lesson.py \
  --title "<short title>" \
  --body  "<lesson body — keep under 200 words>" \
  --tags  "<comma,separated,tags>" \
  --source <strategy_id> \
  --metric "return_pct=-1.57 trades=360 fees=121315" \
  --links  "<pattern_id1>,<pattern_id2>"
```

Prints the new `lesson_id` on stdout.

## Required body structure

```
Observation: what the backtest showed, concretely.
Why: the causal hypothesis (1–2 sentences).
How to apply next: a specific, actionable constraint for the next iteration's seed.
```

## When to use

- After `feedback-analyst` distills a single primary finding from a report.
- Only when the finding is **non-obvious**: something the next iteration wouldn't re-derive from the spec alone.

## Do NOT

- Duplicate an existing lesson — use `search-lessons` first. Prefer updating via `Edit` over appending.
- Write lessons for routine runs with no surprising outcome.
- Exceed 200 words in `--body`.
