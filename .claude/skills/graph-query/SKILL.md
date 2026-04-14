---
name: graph-query
description: Query the knowledge graph — neighbors, related subgraphs, shortest paths, orphans, or tag stats. Token-optimized JSON output.
---

# graph-query

The knowledge base under `knowledge/` is an Obsidian-compatible vault: every MD has YAML frontmatter with `id`, `tags`, and `links:` (or inline `[[wikilinks]]`). `knowledge/graph.py` builds a directed graph from these and exposes CLI queries.

## Commands

```bash
# Rebuild the graph cache (run after adding new lessons/patterns)
python knowledge/graph.py build

# Graph-wide stats: node/edge counts, tag distribution, orphans
python knowledge/graph.py stats

# Adjacency for one note
python knowledge/graph.py neighbors <lesson_id_or_pattern_id>

# Subgraph around any note matching a keyword (in id/title/tags)
python knowledge/graph.py related <keyword>

# Shortest undirected path between two notes
python knowledge/graph.py path <id1> <id2>

# Notes with no links in either direction
python knowledge/graph.py orphans
```

## When to use

- **ideator**: `related <signal_or_concept>` to find a cluster of prior lessons around a theme before proposing a new idea.
- **feedback-analyst**: `neighbors <lesson_id>` to see what existing lessons connect — helps decide whether to link a new lesson or extend an old one.
- **maintenance**: `orphans` periodically to detect unlinked lessons that should reference a parent pattern.

## Cost tips

- Build the graph once per session at most — it scans all MD files.
- Prefer `related` over `neighbors` when you only know a keyword.
- For long paths, `path` returns only the node list (no full content) — do a separate `Read` on any node you actually need.
