"""Compare smoke iter_000 (post A+C+D) vs v5 baseline iter_000.

Reads:
  - iterations/iter_000/results/*.json (current smoke)
  - iterations_archive_v3_20260426_075510/iter_000/results/*.json (legacy v3)
  - or any older iter_000 if available

Reports:
  - Per-spec gross / WR / duty / mean_dur (smoke vs v5 if available)
  - Hypothesis quality keywords (duty / mean_dur / Category / axis / fee)
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent

KEYWORDS = {
    "duty":        re.compile(r"duty[\s_-]?(cycle)?", re.I),
    "mean_dur":    re.compile(r"mean[\s_-]?(regime)?[\s_-]?duration|mean[\s_-]?dur", re.I),
    "category":    re.compile(r"Category\s+(A|B1|B2|B3|C)", re.I),
    "axis":        re.compile(r"axis\s+(A|B|C)|magnitude\s+mechanism", re.I),
    "fee":         re.compile(r"\bfee\b|23\s?bps", re.I),
    "expectancy":  re.compile(r"expectancy|edge", re.I),
}


def score_hypothesis(text: str) -> dict[str, bool]:
    return {kw: bool(rx.search(text)) for kw, rx in KEYWORDS.items()}


def load_specs_and_results(iter_dir: Path) -> list[dict[str, Any]]:
    """For one iter_NNN dir, pair specs and results."""
    rows = []
    spec_dir = iter_dir / "specs"
    res_dir = iter_dir / "results"
    if not spec_dir.exists():
        return rows
    for sf in sorted(spec_dir.glob("*.json")):
        try:
            spec = json.load(open(sf))
        except Exception:
            continue
        result = None
        rf = res_dir / sf.name
        if rf.exists():
            try:
                result = json.load(open(rf))
            except Exception:
                pass
        rows.append({
            "spec_id":     spec.get("spec_id"),
            "formula":     spec.get("formula"),
            "hypothesis":  spec.get("hypothesis", ""),
            "primitives":  spec.get("primitives_used", []),
            "threshold":   spec.get("threshold"),
            "direction":   spec.get("direction"),
            "horizon":     spec.get("prediction_horizon_ticks"),
            "references":  spec.get("references", []),
            "gross":       (result or {}).get("aggregate_expectancy_bps"),
            "n":           (result or {}).get("aggregate_n_trades"),
            "duty":        (result or {}).get("aggregate_signal_duty_cycle"),
            "mean_dur":    (result or {}).get("aggregate_mean_duration_ticks"),
        })
    return rows


def main():
    cur = load_specs_and_results(REPO_ROOT / "iterations" / "iter_000")
    # Filter to specs created after timestamp 21:10 (smoke run)
    new_specs = []
    spec_dir = REPO_ROOT / "iterations" / "iter_000" / "specs"
    for r in cur:
        sf = spec_dir / f"{r['spec_id']}.json"
        if sf.exists() and sf.stat().st_mtime > (1761567000 + 600):  # ~21:10 today
            new_specs.append(r)

    if not new_specs:
        # fall back to all in iter_000
        new_specs = cur

    print(f"=== Smoke iter_000 specs (post A+C+D, n={len(new_specs)}) ===\n")
    print(f"{'spec_id':45} {'gross':>7} {'n':>6} {'duty':>5} {'mdur':>6}")
    for r in new_specs:
        g = f"{r['gross']:.2f}" if r['gross'] is not None else "—"
        n = f"{r['n']}" if r['n'] is not None else "—"
        d = f"{r['duty']:.2f}" if r['duty'] is not None else "—"
        md = f"{r['mean_dur']:.0f}" if r['mean_dur'] is not None else "—"
        print(f"  {r['spec_id']:45} {g:>7} {n:>6} {d:>5} {md:>6}")

    print("\n=== Hypothesis keyword coverage ===")
    print(f"{'spec_id':45} {'duty':>5} {'mdur':>5} {'cat':>4} {'axis':>5} {'fee':>4} {'exp':>4}  refs(new?)")
    for r in new_specs:
        sc = score_hypothesis(r["hypothesis"])
        cs = lambda b: " ✓" if b else " ✗"
        # Check refs include new (quick_ref / empirical_baselines / t_scaling)
        refs = r["references"]
        new_ref_used = any("quick_ref" in s or "empirical_baselines" in s or "t_scaling" in s for s in refs)
        print(f"  {r['spec_id']:45} {cs(sc['duty']):>5} {cs(sc['mean_dur']):>5} "
              f"{cs(sc['category']):>4} {cs(sc['axis']):>5} {cs(sc['fee']):>4} {cs(sc['expectancy']):>4}  "
              f"{'NEW' if new_ref_used else '-'}")

    # v5 comparison
    v5_iter0_specs_old = [s for s in cur if s not in new_specs]
    if v5_iter0_specs_old:
        print(f"\n=== v5 iter_000 baseline (n={len(v5_iter0_specs_old)}) for comparison ===")
        print(f"{'spec_id':45} {'gross':>7} {'n':>6} {'duty':>5} {'mdur':>6}")
        for r in v5_iter0_specs_old:
            g = f"{r['gross']:.2f}" if r['gross'] is not None else "—"
            n = f"{r['n']}" if r['n'] is not None else "—"
            d = f"{r['duty']:.2f}" if r['duty'] is not None else "—"
            md = f"{r['mean_dur']:.0f}" if r['mean_dur'] is not None else "—"
            print(f"  {r['spec_id']:45} {g:>7} {n:>6} {d:>5} {md:>6}")

    # Summary
    if new_specs:
        n_pass_template = sum(1 for r in new_specs if all(score_hypothesis(r['hypothesis']).values()))
        n_new_ref = sum(1 for r in new_specs if any('quick_ref' in s or 'empirical_baselines' in s or 't_scaling' in s for s in r['references']))
        gross_new = [r['gross'] for r in new_specs if r['gross'] is not None]
        print(f"\n=== Summary ===")
        print(f"  n_specs:                       {len(new_specs)}")
        print(f"  hypothesis template complete:  {n_pass_template}/{len(new_specs)}")
        print(f"  new-cheat-sheet referenced:    {n_new_ref}/{len(new_specs)}")
        if gross_new:
            print(f"  best gross_bps:                {max(gross_new):.2f} (vs v5 best 4.74)")
            print(f"  mean gross_bps:                {sum(gross_new)/len(gross_new):.2f}")


if __name__ == "__main__":
    main()
