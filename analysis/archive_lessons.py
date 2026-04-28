"""v3-v6 누적 archive 의 lessons 정제 — LLM cheat sheet 로 변환.

Inputs:
  iterations_archive_v3_20260426_075510/  (v3, 80 specs, fixed-H paradigm — over-counting bias)
  iterations_v4_archive/                  (v4, 72 specs, fixed-H + net reward)
  iterations_v5_archive_20260428/         (v5, 103 specs, regime-state)
  iterations/                              (v6 진행 중, regime-state + maker)

Outputs:
  chain1/_shared/references/cheat_sheets/tried_failure_modes.md
  chain1/_shared/references/cheat_sheets/cumulative_lessons.md
"""
from __future__ import annotations

import json
import re
import os
from collections import Counter, defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CHEAT_DIR = REPO_ROOT / ".claude" / "agents" / "chain1" / "_shared" / "references" / "cheat_sheets"

ARCHIVES = [
    ("v3", REPO_ROOT / "iterations_archive_v3_20260426_075510", "fixed-H (over-counting bias)"),
    ("v4", REPO_ROOT / "iterations_v4_archive",                 "fixed-H + net reward"),
    ("v5", REPO_ROOT / "iterations_v5_archive_20260428",         "regime-state"),
    ("v6", REPO_ROOT / "iterations",                              "regime-state + maker"),
]


def collect(root: Path) -> list[dict]:
    rows = []
    if not root.exists():
        return rows
    for d in sorted(root.glob("iter_*/")):
        for spec_path in d.glob("specs/*.json"):
            try:
                spec = json.load(open(spec_path))
                rname = spec_path.name
                result = None
                rp = d / "results" / rname
                if rp.exists():
                    try:
                        result = json.load(open(rp))
                    except Exception:
                        pass
                rows.append({
                    "iter": int(d.name.split("_")[1]),
                    "spec_id": spec_path.stem,
                    "formula": spec.get("formula", ""),
                    "primitives": spec.get("primitives_used", []),
                    "threshold": spec.get("threshold"),
                    "direction": spec.get("direction"),
                    "horizon": spec.get("prediction_horizon_ticks"),
                    "hypothesis": spec.get("hypothesis", ""),
                    "result": result,
                })
            except Exception:
                pass
    return rows


def family_of(prims: list[str], formula: str) -> str:
    """Categorize spec by primitive family."""
    p = set(prims)
    f = formula or ""
    if any("zscore" in x for x in p) or "zscore(" in f:
        return "zscore_tail"
    if any("trade_imb" in x for x in p):
        return "trade_imb"
    if any("ofi" in x for x in p):
        return "ofi"
    if any("microprice" in x for x in p):
        return "microprice"
    if any(x.startswith("obi_") for x in p):
        return "obi"
    if any(x in {"book_thickness", "book_pressure", "depth_concentration"} for x in p):
        return "book_shape"
    return "other"


def time_gate_of(formula: str) -> str:
    if not formula: return "all_day"
    if "is_opening_burst" in formula or "minute_of_session < 30" in formula or "minute_of_session < 15" in formula:
        return "opening"
    if "is_closing_burst" in formula or "minute_of_session > 360" in formula:
        return "closing"
    if "is_lunch_lull" in formula or "minute_of_session" in formula and ("180" in formula or "240" in formula):
        return "lunch"
    return "all_day"


def detect_failure_mode(row: dict) -> str | None:
    """Classify failure mode if any. Returns label or None."""
    r = row.get("result") or {}
    n = r.get("aggregate_n_trades") or 0
    mid = r.get("aggregate_expectancy_bps")
    maker = r.get("aggregate_expectancy_maker_bps")
    duty = r.get("aggregate_signal_duty_cycle")
    mdur = r.get("aggregate_mean_duration_ticks")

    if mid is None and maker is None:
        return "no_result"
    if n < 50:
        return "trigger_fragile"
    if duty and duty > 0.95:
        return "buy_and_hold_artifact"
    if mdur is not None and mdur < 5 and n > 100:
        return "flickering"
    if maker is not None and mid is not None and abs(mid) < 0.3 and maker > 8:
        return "spread_arbitrage_suspicious"
    if mid is not None and mid < -1:
        return "negative_alpha"
    return None


def render_failure_modes(all_rows: list[dict]) -> str:
    """Tried failure modes catalog — LLM cheat sheet."""
    by_mode = defaultdict(list)
    for r in all_rows:
        mode = detect_failure_mode(r)
        if mode:
            by_mode[mode].append(r)

    md = ["# Tried failure modes — what NOT to do (auto-generated from v3-v6 archive)",
          "",
          "*This sheet is auto-generated from cumulative experiment archives. Updated each run.*",
          "",
          "Quick rule: when designing a new spec, **scan this list first**. If your hypothesis ",
          "matches a known failure mode, it will likely produce the same outcome.",
          "",
          f"Total specs analyzed: {sum(len(rows) for rows in by_mode.values())} failures across "
          f"{sum(1 for r in all_rows if r.get('result'))} measured specs (out of {len(all_rows)} total).",
          ""]

    fail_descriptions = {
        "buy_and_hold_artifact": ("**Buy-and-hold artifact** — signal is True ≥ 95% of session. "
                                   "Effectively a buy-and-hold, not a signal. duty_cycle > 0.95."),
        "flickering": ("**Flickering** — mean_duration < 5 ticks with n > 100 regimes. "
                       "Signal toggles every 1-2 ticks. fee accumulation prohibitive."),
        "trigger_fragile": ("**Trigger fragility** — n < 50 trades total. Statistical noise dominates. "
                             "Threshold likely too tight."),
        "spread_arbitrage_suspicious": ("**Spread arbitrage (suspicious)** — mid_gross ≈ 0 but maker_gross "
                                          "> 8 bps. Signal triggers only when spread is unusually wide. "
                                          "Likely not real alpha — would not survive maker_realistic queue + adverse selection."),
        "negative_alpha": ("**Negative alpha** — mid_gross < -1 bps. Direction wrong, or signal "
                           "captures mean-reversion at wrong sign."),
        "trigger_fragile": ("**Trigger fragility** — n < 50 trades total. Statistical noise dominates."),
        "no_result": ("**No backtest result** — code generation or fidelity check failed."),
    }

    for mode, examples in sorted(by_mode.items(), key=lambda x: -len(x[1])):
        n_failures = len(examples)
        desc = fail_descriptions.get(mode, "**" + mode + "**")
        md.append(f"## {desc}")
        md.append(f"")
        md.append(f"Count: {n_failures}")
        md.append("")
        md.append("Concrete examples (top 5):")
        for r in examples[:5]:
            res = r.get('result') or {}
            mid = res.get('aggregate_expectancy_bps') or 0
            maker = res.get('aggregate_expectancy_maker_bps')
            dur = res.get('aggregate_mean_duration_ticks') or 0
            duty = res.get('aggregate_signal_duty_cycle') or 0
            n = res.get('aggregate_n_trades') or 0
            md.append(f"- `{r['formula'][:70]}` "
                      f"(n={n}, mid={mid:.2f}, dur={dur:.0f}, duty={duty:.2f})")
        md.append("")

    md.append("## Anti-pattern checklist (review before submitting any spec)")
    md.append("")
    md.append("- [ ] If `formula` evaluates True > 95% of session → buy-and-hold artifact")
    md.append("- [ ] If your `threshold` makes the signal trigger only at `> 0.99` extremes → trigger fragility (n < 50)")
    md.append("- [ ] If your spec uses zscore < 2.0 — that's not really 'tail', try ≥ 2.5")
    md.append("- [ ] If your spec triggers only when spread > 15 bps → likely spread-arbitrage, not real alpha")
    md.append("- [ ] If `mean_duration_ticks` will be < 5 → flickering, fee will eat alpha")
    md.append("- [ ] Category B3 (deep book extreme contra direction) has 67% accuracy — cite-but-fail risk")
    return "\n".join(md)


def render_cumulative_lessons(by_run: dict[str, list[dict]]) -> str:
    """Top + Bottom signals + family distribution + tried-area map."""
    md = ["# Cumulative lessons — v3 to v6 (auto-generated)",
          "",
          "*Auto-generated from archives. Updated each run.*",
          "",
          "Reading order: §1 (top signals — but read with caveats), §2 (failure patterns), ",
          "§3 (untouched areas — try these), §4 (paradigm-specific notes).",
          ""]

    # === §1. Top signals across all runs ===
    md.append("## §1. Top signals across all measured runs")
    md.append("")
    md.append("**Caveat 1**: v3/v4 used fixed-H paradigm — mid_gross values inflated by trigger over-counting "
              "(see `fixed-h-overcounting-bias` concept). Re-measurement under regime-state shows true alpha "
              "is much smaller. Use v3/v4 mid_gross numbers as *upper bound only*.")
    md.append("")
    md.append("**Caveat 2**: v6's iter_008 (maker 21.64) is suspicious — mid≈0, spread arbitrage only.")
    md.append("")
    md.append("Top 10 by mid_gross under regime-state paradigm (v5/v6 only — these are real alpha):")
    md.append("")
    md.append("| run | iter | spec | mid | maker | n | mean_dur | family |")
    md.append("|---|---:|---|---:|---:|---:|---:|---|")

    rs_rows = []
    for run, rows in by_run.items():
        if run not in ("v5", "v6"): continue
        for r in rows:
            res = r.get("result") or {}
            mid = res.get("aggregate_expectancy_bps")
            n = res.get("aggregate_n_trades") or 0
            if mid is not None and n >= 500:
                rs_rows.append({**r, "run": run, "mid": mid,
                                "maker": res.get("aggregate_expectancy_maker_bps") or 0,
                                "n": n,
                                "mean_dur": res.get("aggregate_mean_duration_ticks") or 0})
    rs_rows.sort(key=lambda x: -x["mid"])
    for r in rs_rows[:10]:
        fam = family_of(r["primitives"], r["formula"])
        md.append(f"| {r['run']} | {r['iter']:03d} | {r['spec_id'][:35]} | {r['mid']:.2f} | "
                  f"{r['maker']:.2f} | {r['n']} | {r['mean_dur']:.0f} | {fam} |")
    md.append("")

    md.append("## §2. Failure patterns recap")
    md.append("")
    md.append("See `tried_failure_modes.md` for full catalog. Quick summary:")
    md.append("")
    by_mode = defaultdict(int)
    total_measured = 0
    for run, rows in by_run.items():
        for r in rows:
            if r.get("result"): total_measured += 1
            mode = detect_failure_mode(r)
            if mode: by_mode[mode] += 1
    for mode, n in sorted(by_mode.items(), key=lambda x: -x[1]):
        pct = 100 * n / max(total_measured, 1)
        md.append(f"- **{mode}**: {n} occurrences ({pct:.1f}% of measured)")
    md.append("")

    # === §3. Tried area map ===
    md.append("## §3. Tried area map — primitive family × time gate")
    md.append("")
    md.append("Density of past attempts. **Untouched cells (░) are good targets** for new exploration.")
    md.append("")
    grid: defaultdict[tuple[str, str], int] = defaultdict(int)
    for run, rows in by_run.items():
        if run not in ("v5", "v6"): continue  # only count regime-state
        for r in rows:
            fam = family_of(r["primitives"], r["formula"])
            tg = time_gate_of(r["formula"])
            grid[(fam, tg)] += 1
    families = ["obi", "ofi", "microprice", "trade_imb", "zscore_tail", "book_shape", "other"]
    timegates = ["opening", "lunch", "closing", "all_day"]

    md.append("| family \\ time | opening | lunch | closing | all_day |")
    md.append("|---|:---:|:---:|:---:|:---:|")
    for fam in families:
        cells = []
        for tg in timegates:
            count = grid[(fam, tg)]
            if count == 0:
                cell = "░"
            elif count < 3:
                cell = "▓"
            elif count < 10:
                cell = "██"
            else:
                cell = "███"
            cells.append(f"{cell} ({count})")
        md.append(f"| {fam} | " + " | ".join(cells) + " |")
    md.append("")
    md.append("**Untouched / under-explored cells (░ or ▓)**:")
    untouched = []
    for fam in families:
        for tg in timegates:
            if grid[(fam, tg)] < 2:
                untouched.append(f"  - {fam} × {tg} (count={grid[(fam,tg)]})")
    md.extend(untouched[:10])
    md.append("")

    # === §4. Paradigm-specific notes ===
    md.append("## §4. Paradigm-specific notes")
    md.append("")
    md.append("- **v3 (fixed-H)**: max mid_gross 13.32 bps. **This is fixed-H over-counting inflation**. "
              "Regime-state re-measurement of same signals gives -0.25 bps mean. Do NOT use v3 numbers as targets.")
    md.append("- **v4 (fixed-H + net reward)**: similar mid magnitudes (~12 bps), same inflation. Reward "
              "shaping moved LLM hypothesis distribution (expectancy keyword 0→13 occurrences).")
    md.append("- **v5 (regime-state)**: max mid_gross 4.74 bps under proper regime-state measurement. "
              "True chain 1 ceiling.")
    md.append("- **v6 (regime-state + maker)**: similar 4.46 bps mid + 14.12 bps maker. Path D effect "
              "extended mean_dur to 519 ticks (vs v5's 117).")
    md.append("")
    md.append("**Implication**: chain 1 spec language's true mid_gross ceiling ≈ 4-5 bps under regime-state. "
              "Need Level 2+4 (raw column + tool-use, Task #108) or paradigm shift (chain 2, multi-day) to break it.")

    return "\n".join(md)


def main():
    print("=== Building archive lessons ===\n")
    by_run: dict[str, list[dict]] = {}
    all_rows: list[dict] = []
    for run, root, paradigm in ARCHIVES:
        rows = collect(root)
        by_run[run] = rows
        all_rows.extend(rows)
        n_meas = sum(1 for r in rows if r.get("result"))
        print(f"  {run} ({paradigm}): {len(rows)} specs, {n_meas} with results")

    print(f"\nTotal specs: {len(all_rows)}")
    n_failures = sum(1 for r in all_rows if detect_failure_mode(r))
    print(f"Failures: {n_failures}")

    failure_md = render_failure_modes(all_rows)
    cumulative_md = render_cumulative_lessons(by_run)

    fp = CHEAT_DIR / "tried_failure_modes.md"
    fp.write_text(failure_md)
    print(f"\n✓ {fp} ({len(failure_md.splitlines())} lines)")

    cp = CHEAT_DIR / "cumulative_lessons.md"
    cp.write_text(cumulative_md)
    print(f"✓ {cp} ({len(cumulative_md.splitlines())} lines)")


if __name__ == "__main__":
    main()
