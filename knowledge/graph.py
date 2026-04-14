#!/usr/bin/env python3
"""Knowledge graph indexer over knowledge/**/*.md.

Obsidian-compatible: parses YAML frontmatter and `[[wikilink]]` occurrences
in the body to build a directed graph (source_note -> linked_note).

CLI:
    python knowledge/graph.py build
    python knowledge/graph.py stats
    python knowledge/graph.py neighbors <id>
    python knowledge/graph.py related <keyword>
    python knowledge/graph.py path <id1> <id2>
    python knowledge/graph.py orphans
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import yaml

try:
    import networkx as nx
except ImportError:
    print("networkx is required", file=sys.stderr)
    sys.exit(2)

ROOT = Path(__file__).resolve().parent.parent
KNOW = ROOT / "knowledge"
CACHE = KNOW / ".graph.json"

_FM_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
_WIKI_RE = re.compile(r"\[\[([^\]|#]+?)(?:\|[^\]]+)?\]\]")


def _parse_note(path: Path) -> tuple[dict, str] | None:
    try:
        text = path.read_text(errors="ignore")
    except OSError:
        return None
    m = _FM_RE.match(text)
    frontmatter: dict = {}
    body = text
    if m:
        try:
            frontmatter = yaml.safe_load(m.group(1)) or {}
        except yaml.YAMLError:
            frontmatter = {}
        body = text[m.end():]
    if "id" not in frontmatter:
        frontmatter["id"] = path.stem
    return frontmatter, body


def _extract_links(body: str, frontmatter: dict) -> list[str]:
    links = set(_WIKI_RE.findall(body))
    fm_links = frontmatter.get("links") or []
    if isinstance(fm_links, list):
        for l in fm_links:
            if isinstance(l, str):
                for m in _WIKI_RE.findall(l):
                    links.add(m)
                if l and "[" not in l:
                    links.add(l.strip())
    return sorted(links)


def build_graph() -> nx.DiGraph:
    g = nx.DiGraph()
    for p in KNOW.rglob("*.md"):
        if p.name.startswith("."):
            continue
        parsed = _parse_note(p)
        if parsed is None:
            continue
        fm, body = parsed
        nid = str(fm.get("id") or p.stem)
        tags = fm.get("tags") or []
        if isinstance(tags, str):
            tags = [tags]
        g.add_node(
            nid,
            path=str(p.relative_to(ROOT)),
            tags=list(tags),
            title=fm.get("title") or p.stem,
            source=fm.get("source"),
            metric=fm.get("metric"),
        )
        for target in _extract_links(body, fm):
            g.add_edge(nid, target)
    return g


def save_cache(g: nx.DiGraph) -> None:
    data = {
        "nodes": [{"id": n, **g.nodes[n]} for n in g.nodes],
        "edges": [{"src": u, "dst": v} for u, v in g.edges],
    }
    CACHE.write_text(json.dumps(data, ensure_ascii=False, indent=2))


def load_or_build() -> nx.DiGraph:
    return build_graph()


def cmd_build(args) -> None:
    g = build_graph()
    save_cache(g)
    print(json.dumps({"nodes": g.number_of_nodes(), "edges": g.number_of_edges(), "cache": str(CACHE.relative_to(ROOT))}))


def cmd_stats(args) -> None:
    g = load_or_build()
    tag_counts: dict[str, int] = {}
    for n in g.nodes:
        for t in g.nodes[n].get("tags", []):
            tag_counts[t] = tag_counts.get(t, 0) + 1
    isolated = [n for n in g.nodes if g.degree(n) == 0]
    dangling = [n for n in g.nodes if "path" not in g.nodes[n]]
    print(json.dumps({
        "nodes": g.number_of_nodes(),
        "edges": g.number_of_edges(),
        "isolated": len(isolated),
        "dangling_references": len(dangling),
        "tag_counts": tag_counts,
    }, ensure_ascii=False, indent=2))


def cmd_neighbors(args) -> None:
    g = load_or_build()
    nid = args.id
    if nid not in g:
        print(json.dumps({"error": f"unknown id: {nid}"}))
        sys.exit(1)
    out = {
        "id": nid,
        "outgoing": sorted(g.successors(nid)),
        "incoming": sorted(g.predecessors(nid)),
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))


def cmd_related(args) -> None:
    g = load_or_build()
    kw = args.keyword.lower()
    matches = [
        n for n in g.nodes
        if kw in n.lower()
        or kw in (g.nodes[n].get("title") or "").lower()
        or kw in " ".join(g.nodes[n].get("tags") or []).lower()
    ]
    nodes = set()
    for m in matches:
        nodes.add(m)
        nodes.update(g.successors(m))
        nodes.update(g.predecessors(m))
    edges = [(u, v) for u, v in g.edges if u in nodes and v in nodes]
    print(json.dumps({
        "seed": matches,
        "nodes": sorted(nodes),
        "edges": edges,
    }, ensure_ascii=False, indent=2))


def cmd_path(args) -> None:
    g = load_or_build()
    und = g.to_undirected()
    if args.a not in und or args.b not in und:
        print(json.dumps({"error": "one or both ids unknown"}))
        sys.exit(1)
    try:
        p = nx.shortest_path(und, args.a, args.b)
    except nx.NetworkXNoPath:
        print(json.dumps({"path": None}))
        return
    print(json.dumps({"path": p}, ensure_ascii=False, indent=2))


def cmd_orphans(args) -> None:
    g = load_or_build()
    isolated = [n for n in g.nodes if g.degree(n) == 0 and "path" in g.nodes[n]]
    print(json.dumps({"orphans": sorted(isolated)}, ensure_ascii=False, indent=2))


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("build").set_defaults(fn=cmd_build)
    sub.add_parser("stats").set_defaults(fn=cmd_stats)

    nb = sub.add_parser("neighbors")
    nb.add_argument("id")
    nb.set_defaults(fn=cmd_neighbors)

    rl = sub.add_parser("related")
    rl.add_argument("keyword")
    rl.set_defaults(fn=cmd_related)

    pa = sub.add_parser("path")
    pa.add_argument("a")
    pa.add_argument("b")
    pa.set_defaults(fn=cmd_path)

    sub.add_parser("orphans").set_defaults(fn=cmd_orphans)

    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
