#!/usr/bin/env python3
"""Render every strategy's report.html using engine/report_html.py's render()
(the full Korean dashboard: metric cards + Plotly chart + sensitivity panel +
per-day breakdown + WIN/LOSS context + spec footer).

For tick strategies this is the native renderer — no adapter needed.
For bar strategies we add minimal compatibility fields to spec/report where
needed so the template fills cleanly.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from engine.report_html import render as render_html


def ensure_bar_compat(strat_dir: Path) -> None:
    """Inject tick-compatible fields (fees/latency/universe) into spec.yaml
    if missing. Bar specs only carry target_symbol and params; the renderer
    needs a bit more context for the 'universe & fees' block to make sense.

    Also infer a fees block from fee_side_bps so the break-even panel works.
    """
    spec_path = strat_dir / "spec.yaml"
    report_path = strat_dir / "report.json"
    if not (spec_path.exists() and report_path.exists()):
        return
    spec = yaml.safe_load(spec_path.read_text())
    if spec.get("kind") or not spec.get("target_symbol"):
        # Already tick-style or no target_symbol; don't modify tick specs
        return

    mutated = False
    if "universe" not in spec:
        report = json.loads(report_path.read_text())
        spec["universe"] = {
            "symbols": [spec["target_symbol"]],
            "dates": report.get("dates", []),
        }
        mutated = True
    if "fees" not in spec:
        fee_side = float(spec.get("params", {}).get("fee_side_bps", 5.0))
        spec["fees"] = {"commission_bps": fee_side, "tax_bps": 0.0}
        mutated = True
    if "latency" not in spec:
        spec["latency"] = {"submit_ms": 0, "jitter_ms": 0}
        mutated = True
    if "capital" not in spec:
        report = json.loads(report_path.read_text())
        spec["capital"] = int(report.get("starting_cash", 10_000_000))
        mutated = True

    if mutated:
        spec_path.write_text(yaml.safe_dump(spec, sort_keys=False, allow_unicode=True))


def main() -> None:
    strategies = sorted((REPO / "strategies").iterdir())
    rendered = []
    failed = []
    for d in strategies:
        if not d.is_dir():
            continue
        if d.name.startswith("_"):
            continue
        report_path = d / "report.json"
        trace_path = d / "trace.json"
        spec_path = d / "spec.yaml"
        if not (report_path.exists() and spec_path.exists()):
            continue

        try:
            if d.name.startswith("bar_"):
                ensure_bar_compat(d)
            out = render_html(d)
            rendered.append(d.name)
        except Exception as e:
            failed.append((d.name, str(e)))

    print(f"Rendered {len(rendered)} strategies")
    for n in rendered:
        print(f"  ✓ {n}")
    if failed:
        print(f"\nFAILED: {len(failed)}")
        for n, e in failed:
            print(f"  ✗ {n}: {e}")


if __name__ == "__main__":
    main()
