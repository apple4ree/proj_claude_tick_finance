#!/usr/bin/env python3
"""Keyword search over knowledge/ MD files.

Token-optimized: returns at most `--top` hits with short snippets, as JSON.
Agents call this instead of reading knowledge/ into context.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KNOW = ROOT / "knowledge"


def search(keyword: str, top: int, scope: str | None) -> list[dict]:
    pattern = re.compile(re.escape(keyword), re.IGNORECASE)
    paths = (KNOW / scope).rglob("*.md") if scope else KNOW.rglob("*.md")
    hits = []
    for p in paths:
        try:
            text = p.read_text(errors="ignore")
        except OSError:
            continue
        matches = list(pattern.finditer(text))
        if not matches:
            continue
        i = matches[0].start()
        snippet = text[max(0, i - 60):i + 140].replace("\n", " ")
        hits.append(
            {
                "file": str(p.relative_to(ROOT)),
                "count": len(matches),
                "snippet": snippet.strip(),
            }
        )
    hits.sort(key=lambda h: -h["count"])
    return hits[:top]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--query", required=True)
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument(
        "--scope",
        choices=["lessons", "patterns", "seeds"],
        default=None,
        help="limit search to a subdirectory",
    )
    args = ap.parse_args()
    print(json.dumps(search(args.query, args.top, args.scope), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
