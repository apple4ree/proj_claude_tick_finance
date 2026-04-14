#!/usr/bin/env python3
"""Create a new lesson MD file under knowledge/lessons/.

Format: Obsidian-compatible frontmatter + wiki links.
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LESSONS = ROOT / "knowledge" / "lessons"


def slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9_]+", "_", s.lower()).strip("_") or "lesson"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--title", required=True)
    ap.add_argument("--body", required=True)
    ap.add_argument("--tags", default="")
    ap.add_argument("--source", default="", help="strategy_id this lesson came from")
    ap.add_argument("--metric", default="")
    ap.add_argument("--links", default="", help="comma-separated wiki link ids")
    args = ap.parse_args()

    today = dt.date.today().strftime("%Y%m%d")
    LESSONS.mkdir(parents=True, exist_ok=True)
    existing = list(LESSONS.glob(f"lesson_{today}_*.md"))
    n = len(existing) + 1
    lid = f"lesson_{today}_{n:03d}_{slugify(args.title)}"

    tags = ["lesson"] + [t.strip() for t in args.tags.split(",") if t.strip()]
    fm = [
        "---",
        f"id: {lid}",
        f"created: {dt.datetime.now().isoformat(timespec='seconds')}",
        f"tags: [{', '.join(tags)}]",
    ]
    if args.source:
        fm.append(f"source: {args.source}")
    if args.metric:
        fm.append(f"metric: \"{args.metric}\"")
    if args.links:
        fm.append("links:")
        for link in args.links.split(","):
            link = link.strip()
            if link:
                fm.append(f"  - \"[[{link}]]\"")
    fm.append("---")

    body = f"# {args.title}\n\n{args.body}\n"
    (LESSONS / f"{lid}.md").write_text("\n".join(fm) + "\n\n" + body)
    print(lid)


if __name__ == "__main__":
    main()
