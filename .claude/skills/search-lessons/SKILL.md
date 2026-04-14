---
name: search-lessons
description: Keyword search over knowledge/ MD files (lessons, patterns, seeds). Token-optimized JSON output.
---

# search-lessons

## Usage

```bash
# Search everything under knowledge/
python scripts/search_knowledge.py --query "<keyword>" --top 5

# Limit to a subfolder
python scripts/search_knowledge.py --query "<keyword>" --scope lessons --top 5
python scripts/search_knowledge.py --query "<keyword>" --scope patterns --top 5
python scripts/search_knowledge.py --query "<keyword>" --scope seeds --top 5
```

## Output

JSON array of hits, each `{file, count, snippet}`. Sorted by match count desc.

## When to use

- **ideator**: before proposing a new idea, search for prior lessons on related signals (`obi`, `spread`, `reversion`, `momentum`, …) — avoid re-learning known failures.
- **feedback-analyst**: before writing a new lesson, search for overlapping lessons — prefer updating an existing lesson over duplicating.

## Cost tip

Read snippets only. If a hit looks critical, `Read` the full file — otherwise one-line snippets are enough.
