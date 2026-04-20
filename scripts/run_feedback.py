#!/usr/bin/env python3
"""Phase 4 — Programmatic feedback.

Extracts an analysis from a strategy's backtest + validation + BH
benchmark into:
  strategies/<id>/feedback_auto.json    — structured facts
  strategies/<id>/feedback_auto.md      — draft lesson (human/agent can extend)
  strategies/_iterate_context.md        — appended iteration block

This complements (does not replace) the LLM critic agents — it ensures
every strategy has a baseline programmatic lesson even if the agent
pipeline is not run.

Usage:
    python scripts/run_feedback.py --id crypto_1h_weekly_meanrev_btc
    python scripts/run_feedback.py --pattern 'crypto_1h_weekly*'
"""
from __future__ import annotations

import argparse
import fnmatch
import json
from datetime import datetime
from pathlib import Path
from textwrap import dedent

import yaml

REPO = Path(__file__).resolve().parent.parent


def _f(v, default: float = 0.0) -> float:
    """Safe float coercion for report fields (None → default) to survive format strings."""
    try:
        return float(v) if v is not None else default
    except (TypeError, ValueError):
        return default


def summarize(strat_dir: Path) -> dict:
    r = json.loads((strat_dir / "report.json").read_text())
    spec = yaml.safe_load((strat_dir / "spec.yaml").read_text())
    vp = strat_dir / "validation.json"
    v = json.loads(vp.read_text()) if vp.exists() else None

    rt = int(r.get("n_roundtrips", 0) or 0)
    wr_pct = _f(r.get("win_rate_pct"), 0.0)
    wins = int(round((wr_pct / 100.0) * rt)) if rt else 0
    losses = rt - wins
    exit_mix = r.get("invariant_violation_by_type", {}) or {}

    # Alpha / execution diagnosis (safe fallbacks for LOB reports that
    # omit bar-market fields like avg_exposure / ic_pearson / icir).
    notes: list[str] = []
    avg_exp = _f(r.get("avg_exposure"), None)
    if rt > 0 and avg_exp is not None and avg_exp < 0.1:
        notes.append("low exposure (<10%) — signal rarely fires; intentional sparse entry")
    if rt == 0:
        notes.append("zero roundtrips — signal never triggered in this period")
    ir = _f(r.get("information_ratio"), 0.0)
    if ir > 0.5:
        notes.append("strong positive IR vs buy-and-hold")
    elif ir < -0.5:
        notes.append("strongly negative IR — strategy materially underperforms BH")
    n_inv = int(r.get("invariant_violation_count", 0) or 0)
    if n_inv > 0:
        notes.append(f"invariant violations: {n_inv} ({list(exit_mix.keys())})")

    # LOB market has no target_symbol/target_horizon; derive from universe.
    uni = spec.get("universe") or {}
    market = str(uni.get("market", "") or "")
    symbols = uni.get("symbols") or []
    paradigm = spec.get("paradigm") or (
        (spec.get("handoff_metadata") or {}).get("alpha", {}).get("paradigm")
        if isinstance(spec.get("handoff_metadata"), dict) else None
    )
    symbol_display = spec.get("target_symbol") or (",".join(symbols) if symbols else "—")
    horizon_display = spec.get("target_horizon") or (market or "—")

    return {
        "strategy_id": strat_dir.name,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "spec": {
            "paradigm": paradigm or "—",
            "symbol": symbol_display,
            "horizon": horizon_display,
            "market": market or None,
            "params": spec.get("params", {}),
        },
        "backtest": {
            "return_pct": _f(r.get("return_pct"), 0.0),
            "sharpe": _f(r.get("sharpe_annualized"), 0.0),
            "mdd_pct": _f(r.get("mdd_pct"), 0.0),
            "ic_pearson": _f(r.get("ic_pearson"), 0.0),
            "ic_spearman": _f(r.get("ic_spearman"), 0.0),
            "icir": _f(r.get("icir"), 0.0),
            "information_ratio": _f(r.get("information_ratio"), 0.0),
            "n_roundtrips": rt,
            "win_rate_pct": wr_pct,
            "avg_exposure": _f(r.get("avg_exposure"), 0.0),
        },
        "validation": v["gates"] if v else None,
        "oos": v["oos_result"] if v else None,
        "notes": notes,
    }


def render_markdown(summary: dict) -> str:
    s = summary
    b = s["backtest"]
    v = s.get("validation") or {}
    oos = s.get("oos") or {}
    gates_table = ""
    if v:
        gates_table = "\n".join(
            f"| {k} | {'✓' if info['pass'] else '✗'} | {info['detail']} |"
            for k, info in v.items()
        )
    return dedent(f"""
        # Feedback — {s['strategy_id']}

        *Generated: {s['timestamp']}* (programmatic)

        ## Spec
        - paradigm: `{s['spec']['paradigm']}`
        - symbol: `{s['spec']['symbol']}`, horizon: `{s['spec']['horizon']}`
        - params: `{json.dumps(s['spec']['params'])}`

        ## Backtest (full period)
        - return: **{b['return_pct']:+.2f}%**,  Sharpe: **{b['sharpe']:+.2f}**,  MDD: **{b['mdd_pct']:+.2f}%**
        - IC (Pearson): {b['ic_pearson']:+.4f}  |  ICIR: {b['icir']:+.3f}  |  IR vs BH: **{b['information_ratio']:+.3f}**
        - roundtrips: {b['n_roundtrips']},  win rate: {b['win_rate_pct']:.1f}%,  exposure: {b['avg_exposure']:.3f}

        ## 4-Gate Validation
        | gate | pass | detail |
        |---|---|---|
        {gates_table}

        ## OOS
        - window: {oos.get('window')}
        - return: {oos.get('total_ret_pct', '—')}  |  Sharpe: {oos.get('sharpe', '—')}  |  IR: {oos.get('information_ratio', '—')}  |  RT: {oos.get('n_rt', '—')}

        ## Notes
        {chr(10).join('- ' + n for n in s['notes']) or '- (none)'}
        """).lstrip()


def append_iterate_context(summary: dict, path: Path) -> None:
    s = summary
    b = s["backtest"]
    v = s.get("validation") or {}
    oos = s.get("oos") or {}
    passed = all(info["pass"] for info in v.values()) if v else False
    block = dedent(f"""

        ## {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}Z — {s['strategy_id']} [programmatic feedback]
        - **Spec**: {s['spec']['paradigm']} on {s['spec']['symbol']} {s['spec']['horizon']}
        - **Backtest**: return {b['return_pct']:+.2f}%, Sharpe {b['sharpe']:+.2f}, MDD {b['mdd_pct']:+.2f}%, RT {b['n_roundtrips']}
        - **IC/ICIR/IR**: {b['ic_pearson']:+.4f} / {b['icir']:+.3f} / {b['information_ratio']:+.3f}
        - **4-Gate**: {'PASS' if passed else 'FAIL'}  ({', '.join(k for k, info in v.items() if info['pass']) if v else '—'})
        - **OOS**: ret {oos.get('total_ret_pct', '—')}, IR {oos.get('information_ratio', '—')}
        - **Notes**: {'; '.join(s['notes']) or '(none)'}
        """).rstrip() + "\n"
    # idempotent: skip if block already present for this timestamp+id
    key = f"{s['strategy_id']}"
    existing = path.read_text() if path.exists() else ""
    if f"{key} [programmatic feedback]" in existing and datetime.utcnow().strftime("%Y-%m-%d") in existing.split(key)[-1][:80]:
        return  # already appended today for this strategy
    with path.open("a") as f:
        f.write(block)


def process(strat_dir: Path, ctx_path: Path) -> dict:
    summary = summarize(strat_dir)
    (strat_dir / "feedback_auto.json").write_text(json.dumps(summary, indent=2, default=str))
    (strat_dir / "feedback_auto.md").write_text(render_markdown(summary))
    append_iterate_context(summary, ctx_path)
    return summary


def main() -> None:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--all", action="store_true")
    g.add_argument("--id")
    g.add_argument("--pattern")
    ap.add_argument("--ctx", default="strategies/_iterate_context.md")
    args = ap.parse_args()

    strategies_dir = REPO / "strategies"
    if args.id:
        targets = [strategies_dir / args.id]
    elif args.pattern:
        targets = [d for d in sorted(strategies_dir.iterdir())
                   if d.is_dir() and fnmatch.fnmatch(d.name, args.pattern)]
    else:
        targets = [d for d in sorted(strategies_dir.iterdir())
                   if d.is_dir() and not d.name.startswith("_") and (d / "report.json").exists()]

    ctx = REPO / args.ctx
    for d in targets:
        if not (d / "report.json").exists():
            continue
        s = process(d, ctx)
        passed = all(g["pass"] for g in (s["validation"] or {}).values()) if s["validation"] else None
        mark = "✓" if passed else ("✗" if passed is False else "·")
        print(f"  {mark} {d.name:<48} IR={s['backtest']['information_ratio']:+.2f}  "
              f"notes={'; '.join(s['notes']) or '(none)'}")
    print(f"\nupdated → {ctx.relative_to(REPO)}")


if __name__ == "__main__":
    main()
