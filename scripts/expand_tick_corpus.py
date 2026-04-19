#!/usr/bin/env python3
"""Expand tick-level strategy corpus from 6 to 20 by parameter variants.

Takes existing strategy templates and generates variants with different
thresholds, lot_sizes, max_entries, and SL values. Each variant runs through
backtest + attribute_pnl + invariant check.

Variants designed to probe failure-mode taxonomy:
- Threshold variants — tests whether failure-mode incidence is threshold-sensitive
- Lot-size variants — tests max_position_exceeded sensitivity
- SL variants — tests sl_overshoot sensitivity (e.g., sub-tick SL threshold)
- max_entries variants — tests max_entries_exceeded

Base strategies (reused as templates):
- strat_20260417_0002 (042700 obi_5) -> 4 variants
- strat_20260417_0003 (042700 obi_10) -> 3 variants
- strat_20260417_0004 (010140 spread) -> 3 variants
- strat_20260417_0006 (035420 obi_5) -> 4 variants

Total added: 14 variants -> total corpus 20 tick strategies.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
STRATEGIES_DIR = REPO / "strategies"


# Variant definitions: (base_strategy_id, new_suffix, param_overrides)
# Each variant inherits all base spec params + strategy.py, overrides selected params.
VARIANTS: list[tuple[str, str, dict]] = [
    # 042700 obi_5 base — vary thresholds and lot_size
    ("strat_20260417_0002_smoke_042700_obi5", "0007_v_thr_lo",   {"obi_threshold": 0.50, "lot_size": 2}),
    ("strat_20260417_0002_smoke_042700_obi5", "0008_v_thr_hi",   {"obi_threshold": 0.70, "lot_size": 2}),
    ("strat_20260417_0002_smoke_042700_obi5", "0009_v_lot_hi",   {"lot_size": 5}),
    ("strat_20260417_0002_smoke_042700_obi5", "0010_v_sl_sub",   {"stop_loss_bps": 5.0}),   # sub-tick SL stress
    # 042700 obi_10 base — vary thresholds
    ("strat_20260417_0003_pilot_s1_042700_obi10", "0011_v_thr_lo",  {"obi_threshold": 0.40}),
    ("strat_20260417_0003_pilot_s1_042700_obi10", "0012_v_thr_hi",  {"obi_threshold": 0.55}),
    ("strat_20260417_0003_pilot_s1_042700_obi10", "0013_v_maxent_hi", {"max_entries_per_session": 3}),
    # 010140 spread base — vary thresholds
    ("strat_20260417_0004_pilot_s2_010140_spread", "0014_v_thr_lo",  {"spread_threshold_bps": 15.0}),
    ("strat_20260417_0004_pilot_s2_010140_spread", "0015_v_thr_hi",  {"spread_threshold_bps": 20.0}),
    ("strat_20260417_0004_pilot_s2_010140_spread", "0016_v_sl_wide", {"stop_loss_bps": 45.0}),
    # 035420 obi_5 base — vary
    ("strat_20260417_0006_pilot_s4_035420_obi5", "0017_v_thr_lo",  {"obi_threshold": 0.55}),
    ("strat_20260417_0006_pilot_s4_035420_obi5", "0018_v_thr_hi",  {"obi_threshold": 0.75}),
    ("strat_20260417_0006_pilot_s4_035420_obi5", "0019_v_lot_hi",  {"lot_size": 5}),
    ("strat_20260417_0006_pilot_s4_035420_obi5", "0020_v_sl_sub",  {"stop_loss_bps": 5.0}),
]


def build_variant(base_id: str, suffix: str, overrides: dict) -> str:
    base_dir = STRATEGIES_DIR / base_id
    if not (base_dir / "spec.yaml").exists():
        print(f"  SKIP (no base): {base_id}", file=sys.stderr)
        return ""

    new_id = f"strat_20260418_{suffix}"
    new_dir = STRATEGIES_DIR / new_id
    if new_dir.exists():
        print(f"  already exists: {new_id}")
        return new_id
    new_dir.mkdir(parents=True, exist_ok=True)

    # Copy spec.yaml with overrides
    spec = yaml.safe_load((base_dir / "spec.yaml").read_text())
    spec["name"] = new_id
    spec.setdefault("params", {}).update(overrides)
    (new_dir / "spec.yaml").write_text(yaml.safe_dump(spec, sort_keys=False, allow_unicode=True))

    # Copy strategy.py verbatim
    shutil.copy(base_dir / "strategy.py", new_dir / "strategy.py")

    # Copy idea.json if present, overriding params
    idea_src = base_dir / "idea.json"
    if idea_src.exists():
        try:
            idea = json.loads(idea_src.read_text())
        except Exception:
            idea = {}
        idea["name"] = new_id
        idea["parent_variant_of"] = base_id
        idea["variant_overrides"] = overrides
        (new_dir / "idea.json").write_text(json.dumps(idea, indent=2, ensure_ascii=False))

    print(f"  built: {new_id} (base={base_id}, overrides={overrides})")
    return new_id


def run_backtest_and_attribute(strat_id: str) -> dict | None:
    strat_dir = STRATEGIES_DIR / strat_id
    try:
        subprocess.run(
            [sys.executable, "-m", "engine.runner",
             "--spec", str(strat_dir / "spec.yaml"), "--summary"],
            cwd=REPO, check=True, capture_output=True,
        )
    except subprocess.CalledProcessError as exc:
        print(f"  {strat_id}: BACKTEST FAILED — {exc.stderr[-300:] if exc.stderr else ''}",
              file=sys.stderr)
        return None

    # Attribute PnL (dual-mode run)
    try:
        subprocess.run(
            [sys.executable, str(REPO / "scripts" / "attribute_pnl.py"),
             "--strategy", strat_id],
            cwd=REPO, check=True, capture_output=True,
        )
    except subprocess.CalledProcessError as exc:
        print(f"  {strat_id}: ATTRIBUTE FAILED — {exc.stderr[-300:] if exc.stderr else ''}",
              file=sys.stderr)

    report_path = strat_dir / "report.json"
    if not report_path.exists():
        return None
    r = json.loads(report_path.read_text())
    return {
        "strategy_id": strat_id,
        "return_pct": r.get("return_pct"),
        "sharpe_annualized": r.get("sharpe_annualized"),
        "n_roundtrips": r.get("n_roundtrips"),
        "win_rate_pct": r.get("win_rate_pct"),
        "violations_by_type": r.get("invariant_violation_by_type", {}),
        "violation_count": r.get("invariant_violation_count", 0),
    }


def main() -> None:
    print(f"Building {len(VARIANTS)} tick-level variants...\n")
    built = []
    for base_id, suffix, overrides in VARIANTS:
        new_id = build_variant(base_id, suffix, overrides)
        if new_id:
            built.append(new_id)

    print(f"\n=== Running backtests for {len(built)} new strategies ===")
    results = []
    for sid in built:
        r = run_backtest_and_attribute(sid)
        if r:
            print(f"  {sid}: ret={r['return_pct']:.4f}% "
                  f"RT={r['n_roundtrips']} WR={r['win_rate_pct']:.1f}% "
                  f"viol={r['violation_count']} {r['violations_by_type']}")
            results.append(r)
        else:
            print(f"  {sid}: NO REPORT")

    out = REPO / "data" / "tick_corpus_expansion_results.json"
    out.write_text(json.dumps(results, indent=2))
    print(f"\nsaved -> {out.relative_to(REPO)}")


if __name__ == "__main__":
    main()
