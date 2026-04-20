#!/usr/bin/env python3
"""Adversarial recall calibration for the invariant checker.

For each of the 7 invariant types in INVARIANT_REGISTRY, we construct:
  (a) a minimal spec with the relevant threshold parameter, and
  (b) a synthetic GenericFill stream that *deliberately* violates the
      invariant at a known frequency.

We then run the standalone checker and verify it catches the injected
violations — a recall of 1.0 is the expected outcome for a correctly
implemented detector.

Output: per-invariant recall + a summary table suitable for paper figure F6.

This is a deterministic, dependency-free test. No LLM calls. No real backtest.
No external data. Suitable for CI and paper reproducibility.

Usage:
  python scripts/adversarial_recall_test.py
  python scripts/adversarial_recall_test.py --out data/adversarial_recall.json
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.check_invariants_from_fills import GenericFill, run_checker

_KST = timezone(timedelta(hours=9))


def kst_ns(date: str, hms: str) -> int:
    """date='20260320', hms='10:30:00' -> epoch ns in KST."""
    y, m, d = int(date[:4]), int(date[4:6]), int(date[6:8])
    h, mi, s = [int(x) for x in hms.split(":")]
    dt = datetime(y, m, d, h, mi, s, tzinfo=_KST)
    return int(dt.timestamp() * 1e9)


# ---------------------------------------------------------------------------
# Scenario builders: each returns (spec, fills, expected_counts_by_type)
# ---------------------------------------------------------------------------

DATE = "20260320"
SYM = "005930"
BASE_PX = 80000.0


def _bp(price: float, bps: float) -> float:
    return price * (1.0 + bps / 1e4)


def scenario_sl_overshoot() -> tuple[dict, list[GenericFill], dict]:
    """Entry at 80000, SL spec=30 bps (+10 tolerance -> threshold=40).
    Exit at -60 bps -> injected violation."""
    spec = {"params": {"stop_loss_bps": 30.0, "lot_size": 1}}
    fills = [
        GenericFill(kst_ns(DATE, "10:00:00"), SYM, "BUY", 1, BASE_PX, "entry_obi",
                    position_after=1, lot_size=1),
        GenericFill(kst_ns(DATE, "10:05:00"), SYM, "SELL", 1, _bp(BASE_PX, -60.0),
                    "stop_loss", position_after=0, lot_size=1),
        # 2nd clean pair to ensure non-violating cases don't register
        GenericFill(kst_ns(DATE, "11:00:00"), SYM, "BUY", 1, BASE_PX, "entry_obi",
                    position_after=1, lot_size=1),
        GenericFill(kst_ns(DATE, "11:05:00"), SYM, "SELL", 1, _bp(BASE_PX, -35.0),
                    "stop_loss", position_after=0, lot_size=1),
    ]
    return spec, fills, {"sl_overshoot": 1}


def scenario_pt_overshoot() -> tuple[dict, list[GenericFill], dict]:
    """PT spec=50 bps (+20 tolerance -> threshold=70). Exit at +100 bps -> violation."""
    spec = {"params": {"profit_target_bps": 50.0, "lot_size": 1}}
    fills = [
        GenericFill(kst_ns(DATE, "10:00:00"), SYM, "BUY", 1, BASE_PX, "entry_obi",
                    position_after=1, lot_size=1),
        GenericFill(kst_ns(DATE, "10:05:00"), SYM, "SELL", 1, _bp(BASE_PX, 100.0),
                    "profit_target", position_after=0, lot_size=1),
        # Clean PT exit within tolerance
        GenericFill(kst_ns(DATE, "11:00:00"), SYM, "BUY", 1, BASE_PX, "entry_obi",
                    position_after=1, lot_size=1),
        GenericFill(kst_ns(DATE, "11:05:00"), SYM, "SELL", 1, _bp(BASE_PX, 65.0),
                    "profit_target", position_after=0, lot_size=1),
    ]
    return spec, fills, {"pt_overshoot": 1}


def scenario_entry_gate_end_bypass() -> tuple[dict, list[GenericFill], dict]:
    """entry_end=13:00. Entry at 13:15 -> injected violation."""
    spec = {"params": {"entry_end_time_seconds": 13 * 3600, "lot_size": 1}}
    fills = [
        GenericFill(kst_ns(DATE, "10:00:00"), SYM, "BUY", 1, BASE_PX, "entry_obi",
                    position_after=1, lot_size=1),
        GenericFill(kst_ns(DATE, "10:05:00"), SYM, "SELL", 1, BASE_PX, "profit_target",
                    position_after=0, lot_size=1),
        GenericFill(kst_ns(DATE, "13:15:00"), SYM, "BUY", 1, BASE_PX, "entry_obi",
                    position_after=1, lot_size=1),   # violation
        GenericFill(kst_ns(DATE, "13:20:00"), SYM, "SELL", 1, BASE_PX, "profit_target",
                    position_after=0, lot_size=1),
    ]
    return spec, fills, {"entry_gate_end_bypass": 1}


def scenario_entry_gate_start_bypass() -> tuple[dict, list[GenericFill], dict]:
    """entry_start=09:30. Entry at 09:15 -> injected violation."""
    spec = {"params": {"entry_start_time_seconds": 9 * 3600 + 30 * 60, "lot_size": 1}}
    fills = [
        GenericFill(kst_ns(DATE, "09:15:00"), SYM, "BUY", 1, BASE_PX, "entry_obi",
                    position_after=1, lot_size=1),   # violation
        GenericFill(kst_ns(DATE, "09:20:00"), SYM, "SELL", 1, BASE_PX, "profit_target",
                    position_after=0, lot_size=1),
        GenericFill(kst_ns(DATE, "10:00:00"), SYM, "BUY", 1, BASE_PX, "entry_obi",
                    position_after=1, lot_size=1),
        GenericFill(kst_ns(DATE, "10:05:00"), SYM, "SELL", 1, BASE_PX, "profit_target",
                    position_after=0, lot_size=1),
    ]
    return spec, fills, {"entry_gate_start_bypass": 1}


def scenario_max_entries_exceeded() -> tuple[dict, list[GenericFill], dict]:
    """max_entries=2 per day. 4 entries -> 2 violations (entries 3 and 4)."""
    spec = {"params": {"max_entries_per_session": 2, "lot_size": 1}}
    fills = []
    hours = ["10:00:00", "10:30:00", "11:00:00", "11:30:00"]
    pos = 0
    for i, hm in enumerate(hours):
        fills.append(GenericFill(kst_ns(DATE, hm), SYM, "BUY", 1, BASE_PX, "entry_obi",
                                 position_after=pos + 1, lot_size=1))
        pos += 1
        # Close immediately to allow re-entry (max_entries is the tracked invariant)
        fills.append(GenericFill(kst_ns(DATE, hm), SYM, "SELL", 1, BASE_PX, "profit_target",
                                 position_after=pos - 1, lot_size=1))
        pos -= 1
    return spec, fills, {"max_entries_exceeded": 2}


def scenario_max_position_exceeded() -> tuple[dict, list[GenericFill], dict]:
    """max_position=2, lot_size=1 -> cap=2 qty. 3 accumulating buys -> 1 violation (3rd buy)."""
    spec = {"params": {"max_position_per_symbol": 2, "lot_size": 1,
                       "max_entries_per_session": 99}}
    fills = [
        GenericFill(kst_ns(DATE, "10:00:00"), SYM, "BUY", 1, BASE_PX, "entry_obi",
                    position_after=1, lot_size=1),
        GenericFill(kst_ns(DATE, "10:01:00"), SYM, "BUY", 1, BASE_PX, "entry_obi",
                    position_after=2, lot_size=1),
        GenericFill(kst_ns(DATE, "10:02:00"), SYM, "BUY", 1, BASE_PX, "entry_obi",
                    position_after=3, lot_size=1),   # exceeds cap
        GenericFill(kst_ns(DATE, "10:10:00"), SYM, "SELL", 3, BASE_PX, "profit_target",
                    position_after=0, lot_size=1),
    ]
    return spec, fills, {"max_position_exceeded": 1}


def scenario_time_stop_overshoot() -> tuple[dict, list[GenericFill], dict]:
    """time_stop=1000 ticks (+50 tolerance -> threshold=1050). Hold 2000 ticks -> violation."""
    spec = {"params": {"time_stop_ticks": 1000, "lot_size": 1}}
    fills = [
        GenericFill(kst_ns(DATE, "10:00:00"), SYM, "BUY", 1, BASE_PX, "entry_obi",
                    position_after=1, lot_size=1),
        GenericFill(kst_ns(DATE, "10:05:00"), SYM, "SELL", 1, BASE_PX, "time_stop",
                    ticks_held=2000, position_after=0, lot_size=1),  # violation
        # Clean time_stop at exactly threshold
        GenericFill(kst_ns(DATE, "11:00:00"), SYM, "BUY", 1, BASE_PX, "entry_obi",
                    position_after=1, lot_size=1),
        GenericFill(kst_ns(DATE, "11:05:00"), SYM, "SELL", 1, BASE_PX, "time_stop",
                    ticks_held=1000, position_after=0, lot_size=1),
    ]
    return spec, fills, {"time_stop_overshoot": 1}


SCENARIOS = {
    "sl_overshoot": scenario_sl_overshoot,
    "pt_overshoot": scenario_pt_overshoot,
    "entry_gate_end_bypass": scenario_entry_gate_end_bypass,
    "entry_gate_start_bypass": scenario_entry_gate_start_bypass,
    "max_entries_exceeded": scenario_max_entries_exceeded,
    "max_position_exceeded": scenario_max_position_exceeded,
    "time_stop_overshoot": scenario_time_stop_overshoot,
}


def run_all(verbose: bool = True) -> dict:
    per_type: list[dict] = []
    for name, builder in SCENARIOS.items():
        spec, fills, expected = builder()
        violations = run_checker(spec, fills)
        actual: dict[str, int] = {}
        for v in violations:
            actual[v.invariant_type] = actual.get(v.invariant_type, 0) + 1

        injected = expected.get(name, 0)
        detected = actual.get(name, 0)
        recall = (detected / injected) if injected > 0 else None
        # False positives: anything detected that is not the injected type
        fp_types = {t: c for t, c in actual.items() if t != name}
        row = {
            "invariant_type": name,
            "injected": injected,
            "detected": detected,
            "recall": recall,
            "false_positive_types": fp_types,
            "n_fills": len(fills),
        }
        per_type.append(row)
        if verbose:
            status = "PASS" if recall == 1.0 and not fp_types else "FAIL"
            fp_str = f" | FP={fp_types}" if fp_types else ""
            print(f"  {status:<4} {name:<28} injected={injected} detected={detected} "
                  f"recall={recall}{fp_str}")

    all_pass = all(r["recall"] == 1.0 and not r["false_positive_types"] for r in per_type)
    mean_recall = (
        sum(r["recall"] for r in per_type if r["recall"] is not None) /
        max(1, sum(1 for r in per_type if r["recall"] is not None))
    )
    summary = {
        "overall_pass": all_pass,
        "mean_recall": mean_recall,
        "n_invariant_types": len(per_type),
        "per_type": per_type,
    }
    return summary


def main() -> None:
    ap = argparse.ArgumentParser(description="Adversarial recall calibration for invariant checker.")
    ap.add_argument("--out", help="Write result JSON to this path")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    if not args.quiet:
        print("=== Adversarial Recall Calibration (F6) ===\n")

    summary = run_all(verbose=not args.quiet)

    if not args.quiet:
        print()
        print(f"Overall: {'PASS' if summary['overall_pass'] else 'FAIL'}, "
              f"mean_recall={summary['mean_recall']:.3f}, "
              f"types={summary['n_invariant_types']}")

    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(summary, indent=2))
        if not args.quiet:
            print(f"wrote {args.out}")

    sys.exit(0 if summary["overall_pass"] else 1)


if __name__ == "__main__":
    main()
