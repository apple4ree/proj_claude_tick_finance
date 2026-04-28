"""Chain 1 per-symbol primitive calibration.

Different KRX symbols have different microstructure scales:
  - 005930 (~180K KRW, tick=100): obi_1 std ≈ 0.30
  - 000660 (~140K KRW, tick=50):  obi_1 std ≈ 0.45
  - etc.

A spec like `obi_1 > 0.5` means **different things** statistically across
symbols. To make signals fair-comparable, we precompute per-symbol
distribution statistics for each primitive and provide a normalization
helper that the backtest runner can apply when `calibration_mode=True`.

Usage:
  1. Run `compute_calibration_stats(symbols, dates) → table`.
  2. Save to `data/calibration/<run_id>.json`.
  3. backtest_runner reads table when given `calibration_table=...`.
  4. With calibration on, `threshold` in SignalSpec is interpreted as
     **z-score** units (number of σ from per-symbol mean), not raw value.

Schema of table:
  {
    "stats": {
      "<symbol>": {
        "<primitive_name>": {"mean": float, "std": float, "n": int}
      }
    },
    "metadata": {"dates": [...], "computed_at": iso}
  }
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Iterable

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
SHARED_DIR = REPO_ROOT / ".claude" / "agents" / "chain1" / "_shared"
if str(SHARED_DIR) not in sys.path:
    sys.path.insert(0, str(SHARED_DIR))


def compute_calibration_stats(
    symbols: list[str],
    dates: list[str],
    primitive_names: list[str] | None = None,
    sample_per_pair: int = 50_000,
) -> dict:
    """Compute mean/std of each primitive for each symbol over given dates.

    Args:
      symbols: KRX symbol codes.
      dates: YYYYMMDD strings.
      primitive_names: subset of primitives to calibrate. None = all stateless.
        (Stateful primitives need prev — handled by sequential iteration.)
      sample_per_pair: max ticks sampled from each (symbol, date) for speed.

    Returns: calibration table dict (per schema above).
    """
    from chain1.backtest_runner import load_day, iter_snaps  # avoid circular import
    from chain1.primitives import PRIMITIVE_WHITELIST

    if primitive_names is None:
        # Default: stateless primitives only (stateful require prev tracking)
        primitive_names = [
            name for name, meta in PRIMITIVE_WHITELIST.items()
            if not meta["stateful"]
        ]

    table: dict = {"stats": {sym: {} for sym in symbols}, "metadata": {}}

    for sym in symbols:
        print(f"[calib] {sym}", flush=True)
        per_primitive_values: dict[str, list[float]] = {n: [] for n in primitive_names}

        for date in dates:
            try:
                df = load_day(sym, date)
            except FileNotFoundError:
                continue
            if len(df) == 0:
                continue
            # Sample evenly across the day (every k-th tick)
            step = max(1, len(df) // sample_per_pair)

            prev_snap = None
            for i, snap in enumerate(iter_snaps(df)):
                # Track prev for stateful (not used here, but for completeness)
                setattr(snap, "prev", prev_snap)
                prev_snap = snap
                if i % step != 0:
                    continue
                for pname in primitive_names:
                    fn = PRIMITIVE_WHITELIST[pname]["fn"]
                    is_stateful = PRIMITIVE_WHITELIST[pname]["stateful"]
                    try:
                        if is_stateful:
                            val = float(fn(snap, prev_snap))
                        else:
                            val = float(fn(snap))
                        if np.isfinite(val):
                            per_primitive_values[pname].append(val)
                    except Exception:  # noqa: BLE001
                        pass

        # Compute mean/std per primitive
        for pname, vals in per_primitive_values.items():
            arr = np.asarray(vals, dtype=np.float64)
            if len(arr) < 100:
                continue
            table["stats"][sym][pname] = {
                "mean": float(arr.mean()),
                "std": float(arr.std()),
                "n":   int(len(arr)),
            }
        print(f"[calib] {sym}: {len(table['stats'][sym])} primitives calibrated", flush=True)

    table["metadata"] = {
        "dates":       list(dates),
        "symbols":     list(symbols),
        "n_primitives": len(primitive_names),
        "sample_per_pair": int(sample_per_pair),
        "computed_at": datetime.utcnow().isoformat(),
    }
    return table


def save_table(table: dict, path: str | Path) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(table, indent=2))


def load_table(path: str | Path) -> dict:
    return json.loads(Path(path).read_text())


def normalize(value: float, symbol: str, primitive_name: str, table: dict) -> float:
    """Convert raw primitive value → z-score using per-symbol stats.

    Returns NaN if calibration unavailable for (symbol, primitive).
    """
    stats = table.get("stats", {}).get(symbol, {}).get(primitive_name)
    if stats is None:
        return float("nan")
    std = stats["std"]
    if std < 1e-12:
        return 0.0
    return (value - stats["mean"]) / std


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", nargs="+", required=True)
    ap.add_argument("--dates",   nargs="+", required=True)
    ap.add_argument("--out",     default="data/calibration/default.json")
    ap.add_argument("--sample",  type=int, default=50_000)
    args = ap.parse_args()

    table = compute_calibration_stats(args.symbols, args.dates,
                                       sample_per_pair=args.sample)
    save_table(table, args.out)
    print(f"\nSaved → {args.out}")
    for sym, stats in table["stats"].items():
        print(f"  {sym}: {len(stats)} primitives calibrated")
