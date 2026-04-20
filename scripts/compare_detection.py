#!/usr/bin/env python3
"""Compare critic-found gaps vs automated invariant violations.

For each strategy:
  - Load critic findings from alpha_critique.md and execution_critique.md
    (parse for gap-type keywords)
  - Load invariant_violations from report.json
  - Compute precision/recall per invariant type

Output: table of (gap_type, critic_count, checker_count, overlap, critic_only, checker_only).
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# Keywords each critique might use to describe each invariant type
CRITIC_KEYWORDS = {
    "sl_overshoot": [
        "sl overshoot", "sl not working", "stop loss bypass",
        "bid-vs-mid", "sl mid", "stop loss failure",
    ],
    "pt_overshoot": [
        "pt overshoot", "profit target overshoot", "pt over",
    ],
    "entry_gate_end_bypass": [
        "gate bypass", "past entry_end", "13:00 bypass",
        "gate close bypass", "entry gate bypass", "late fill",
    ],
    "entry_gate_start_bypass": [
        "before entry_start", "pre-gate fill", "early fill",
    ],
    "max_entries_exceeded": [
        "max entries exceeded", "double-fill", "double fill",
        "duplicate entry", "multiple entries",
    ],
    "max_position_exceeded": [
        "position exceeded", "max position", "pos=10", "phantom position",
    ],
    "time_stop_overshoot": [
        "time_stop failure", "time stop did not fire",
        "time_stop overshoot", "time stop failure",
    ],
}


def parse_critique_file(path: Path) -> set[str]:
    """Return set of invariant types mentioned in the critique."""
    if not path.exists():
        return set()
    text = path.read_text().lower()
    found = set()
    for inv_type, keywords in CRITIC_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            found.add(inv_type)
    return found


def main():
    strategies_root = Path("strategies")
    dirs = sorted(d for d in strategies_root.iterdir()
                  if d.is_dir() and d.name.startswith("strat_"))

    # Counts per invariant type
    critic_total: dict[str, int] = defaultdict(int)
    checker_total: dict[str, int] = defaultdict(int)
    overlap: dict[str, int] = defaultdict(int)
    critic_only: dict[str, int] = defaultdict(int)
    checker_only: dict[str, int] = defaultdict(int)

    n_strategies_with_critique = 0

    for d in dirs:
        # Load critic findings
        critic_found = set()
        critic_found |= parse_critique_file(d / "alpha_critique.md")
        critic_found |= parse_critique_file(d / "execution_critique.md")

        has_critique = (d / "alpha_critique.md").exists() or (d / "execution_critique.md").exists()
        if has_critique:
            n_strategies_with_critique += 1

        # Load invariant violations
        rpt = d / "report.json"
        if not rpt.exists():
            rpt = d / "report_per_symbol.json"
        if not rpt.exists():
            continue
        try:
            data = json.loads(rpt.read_text())
        except Exception:
            continue
        checker_found = set((data.get("invariant_violation_by_type") or {}).keys())

        for inv_type in CRITIC_KEYWORDS.keys():
            in_critic = inv_type in critic_found
            in_checker = inv_type in checker_found

            if in_critic:
                critic_total[inv_type] += 1
            if in_checker:
                checker_total[inv_type] += 1
            if in_critic and in_checker:
                overlap[inv_type] += 1
            if in_critic and not in_checker:
                critic_only[inv_type] += 1
            if in_checker and not in_critic:
                checker_only[inv_type] += 1

    # Print header
    print(f"Strategies analyzed: {len(dirs)} total, {n_strategies_with_critique} with critiques")
    print()
    print(f"{'Invariant Type':<28s} {'Critic':>7s} {'Checker':>8s} {'Both':>5s} "
          f"{'Critic-only':>12s} {'Checker-only':>13s}  {'Checker Recall':>14s}")
    print("-" * 95)
    for inv_type in CRITIC_KEYWORDS.keys():
        recall = overlap[inv_type] / critic_total[inv_type] if critic_total[inv_type] > 0 else 0.0
        print(f"{inv_type:<28s} {critic_total[inv_type]:>7d} {checker_total[inv_type]:>8d} "
              f"{overlap[inv_type]:>5d} {critic_only[inv_type]:>12d} {checker_only[inv_type]:>13d}  "
              f"{recall*100:>13.1f}%")

    # Summary
    total_critic = sum(critic_total.values())
    total_checker = sum(checker_total.values())
    total_overlap = sum(overlap.values())
    total_checker_only = sum(checker_only.values())
    print("-" * 95)
    print(f"{'TOTAL':<28s} {total_critic:>7d} {total_checker:>8d} "
          f"{total_overlap:>5d} {sum(critic_only.values()):>12d} {total_checker_only:>13d}")

    print()
    print("Interpretation:")
    print(f"  - Checker-only findings = gaps the critic MISSED but checker caught: {total_checker_only}")
    print(f"  - Critic-only findings = gaps described in natural language without structured evidence: {sum(critic_only.values())}")
    print(f"  - Overlap = both methods found the same gap: {total_overlap}")


if __name__ == "__main__":
    main()
