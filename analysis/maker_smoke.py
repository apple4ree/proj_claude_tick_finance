"""Maker spread capture smoke test (single-run version).

Runs each spec ONCE in regime-state mode; the new backtest_runner records both
mid_to_mid and maker_optimistic gross per regime, aggregated. We just compare
aggregate_expectancy_bps (mid) vs aggregate_expectancy_maker_bps (maker) from
a single run.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / ".claude" / "agents" / "chain1" / "_shared"))

TARGETS = [
    ("iter_013", "iter013_opening_burst_conviction"),
    ("iter_016", "iter016_stable_pressure_on_fragile_book"),
    ("iter_009", "iter009_stable_imbalance_vs_fragile_book"),
    ("iter_000", "iter000_full_book_consensus"),
    ("iter_020", "iter020_magnitude_consensus_at_open"),
]

V5_DATES = ["20260316", "20260317", "20260318", "20260319",
            "20260320", "20260323", "20260324", "20260325"]
V5_SYMS = ["005930", "000660", "005380"]
KRX_FEE_BPS = 23.0


def main():
    from chain1.backtest_runner import run_backtest
    from schemas import GeneratedCode, SignalSpec  # noqa: E402

    print(f"=== Maker spread smoke (top 5 v5 specs, single-run) ===\n")
    print(f"{'spec_id':45} {'mid':>7} {'maker':>7} {'spread':>7} {'gain':>7} {'net_mk':>8}")

    rows = []
    for iter_dir, spec_id in TARGETS:
        t0 = time.time()
        spec_path = REPO_ROOT / "iterations" / iter_dir / "specs" / f"{spec_id}.json"
        code_path = REPO_ROOT / "iterations" / iter_dir / "code" / f"{spec_id}.py"
        if not spec_path.exists() or not code_path.exists():
            print(f"  ! missing: {spec_id}")
            continue

        spec_dict = json.loads(spec_path.read_text())
        spec = SignalSpec(**spec_dict)
        code = GeneratedCode(
            agent_name="manual",
            iteration_idx=spec.iteration_idx,
            spec_id=spec.spec_id,
            code_path=str(code_path),
            entry_function="signal",
            template_used="manual",
        )

        # Single run — records both mid and maker. execution_mode=mid_to_mid keeps
        # primary expectancy_bps = mid; maker is in expectancy_maker_bps.
        try:
            res = run_backtest(
                spec=spec, code=code,
                symbols=V5_SYMS, dates=V5_DATES,
                save_trace=False,
                mode="regime_state",
                execution_mode="mid_to_mid",  # primary = mid; maker also recorded
            )
        except Exception as e:
            print(f"  ! {spec_id} failed: {e}")
            continue

        mid_g = res.aggregate_expectancy_bps
        maker_g = res.aggregate_expectancy_maker_bps or 0.0
        spread = res.aggregate_avg_spread_bps or 0.0
        gain = maker_g - mid_g
        net_maker = maker_g - KRX_FEE_BPS
        net_str = f"{net_maker:+.2f}" + (" ✓" if net_maker > 0 else "")

        elapsed = time.time() - t0
        print(f"  {spec_id:45} {mid_g:>7.2f} {maker_g:>7.2f} {spread:>7.2f} "
              f"{gain:>+7.2f} {net_str:>8}  ({elapsed:.0f}s)")
        rows.append({
            "spec_id": spec_id, "mid": mid_g, "maker": maker_g,
            "spread": spread, "gain": gain, "net_maker": net_maker,
            "n_regimes": res.aggregate_n_regimes,
        })

    print(f"\nFee floor: {KRX_FEE_BPS} bps RT (KRX cash, sell tax mechanical).")
    if rows:
        avg_gain = sum(r["gain"] for r in rows) / len(rows)
        avg_spread = sum(r["spread"] for r in rows) / len(rows)
        n_pass = sum(1 for r in rows if r["net_maker"] > 0)
        print(f"Mean maker gain: {avg_gain:+.2f} bps (avg measured spread: {avg_spread:.2f} bps)")
        print(f"Specs passing fee in maker mode: {n_pass}/{len(rows)}")

        # Save summary
        out_path = REPO_ROOT / "analysis" / "maker_smoke_results.json"
        out_path.write_text(json.dumps({"fee_bps": KRX_FEE_BPS, "rows": rows}, indent=2))
        print(f"\n✓ saved {out_path}")


if __name__ == "__main__":
    main()
