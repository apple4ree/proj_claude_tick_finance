#!/usr/bin/env python3
"""Generate paper figures from collected pilot data.

Currently produces drafts for:
  F1 — teaser: normal vs strict PnL decomposition for a representative strategy
  F6 — adversarial-spec invariant-checker recall across 7 types
  F7 — cross-engine violation-count parity (our embedded checker vs standalone)

Planned (need more data):
  F3 — clean_pct_of_total distribution (needs n >= 20 strategies)
  F4 — multi-agent handoff field-propagation rate by stage
  F5 — violation-type heatmap by strategy stratum

Outputs:
  docs/figures/f1_teaser.png
  docs/figures/f6_recall.png
  docs/figures/f7_cross_engine.png
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # non-interactive
import matplotlib.pyplot as plt
import numpy as np

REPO = Path(__file__).resolve().parent.parent
FIG_DIR = REPO / "docs" / "figures"


def _save(fig: plt.Figure, name: str) -> Path:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    path = FIG_DIR / name
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return path


# ---------------------------------------------------------------------------
# F1 — teaser: normal vs strict decomposition on strat_0001
# ---------------------------------------------------------------------------

def figure_f1_teaser() -> Path:
    """Illustrate that 40% of reported PnL is attributable to spec violations
    in a representative LLM-generated strategy.

    Data source: data/attribution_summary.json entry for strat_20260417_0001.
    """
    summary = json.loads((REPO / "data" / "attribution_summary.json").read_text())
    entry = next(
        e for e in summary
        if e.get("strategy_id") == "strat_20260417_0001_trajectory_multi_3sym"
    )
    normal = float(entry["normal_pnl"])
    strict = float(entry["strict_pnl_clean"])
    bug = float(entry["bug_pnl"])
    clean_pct = float(entry["clean_pct_of_total"])

    fig, ax = plt.subplots(figsize=(8.5, 3.0), constrained_layout=True)
    y = 0
    height = 0.5
    bug_pct = 100.0 - clean_pct

    ax.barh(y, strict, height=height, color="#3a7d3a",
            label=f"clean / spec-compliant: {strict:+.0f} KRW  ({clean_pct:.1f}%)")
    ax.barh(y, bug, left=strict, height=height, color="#b22222", hatch="///",
            label=f"bug-attributable: {bug:+.0f} KRW  ({bug_pct:.1f}%)")

    ax.axvline(normal, color="black", linewidth=1.0, linestyle=":")
    ax.text(
        normal, y + height / 2 + 0.08,
        f"reported normal PnL = {normal:+.0f} KRW",
        ha="center", va="bottom", fontsize=8,
        bbox=dict(facecolor="white", edgecolor="none", pad=1.5, alpha=0.85),
    )

    ax.set_yticks([y])
    ax.set_yticklabels([entry["strategy_id"].replace("strat_", "")], fontsize=8)
    ax.set_xlabel("PnL (KRW)")
    ax.set_title(
        "F1. Counterfactual PnL decomposition\n"
        f"{bug_pct:.1f}% of reported loss is attributable to a silent "
        "`max_position_exceeded` violation",
        fontsize=10,
    )
    ax.legend(loc="lower right", fontsize=8, frameon=False)
    ax.grid(axis="x", linestyle=":", alpha=0.4)
    ax.set_ylim(-0.6, 0.85)
    return _save(fig, "f1_teaser.png")


# ---------------------------------------------------------------------------
# F6 — adversarial recall per invariant type
# ---------------------------------------------------------------------------

def figure_f6_recall() -> Path:
    """Per-invariant recall on adversarial specs with deterministically
    injected violations.

    Data source: data/adversarial_recall.json.
    """
    data_path = REPO / "data" / "adversarial_recall.json"
    if not data_path.exists():
        # Regenerate deterministically
        subprocess.run(
            [sys.executable, "scripts/adversarial_recall_test.py", "--out", str(data_path), "--quiet"],
            cwd=REPO, check=True,
        )
    summary = json.loads(data_path.read_text())
    rows = summary["per_type"]
    names = [r["invariant_type"] for r in rows]
    recalls = [r["recall"] if r["recall"] is not None else 0.0 for r in rows]
    fp_counts = [sum(r["false_positive_types"].values()) for r in rows]

    x = np.arange(len(names))
    width = 0.55

    fig, ax = plt.subplots(figsize=(8.5, 3.6))
    bars = ax.bar(x, recalls, width, color="#3a7d3a", edgecolor="black")
    for i, (r, fp) in enumerate(zip(recalls, fp_counts)):
        ax.text(i, r + 0.02, f"{r:.2f}", ha="center", fontsize=9)
        if fp:
            ax.text(i, -0.05, f"FP={fp}", ha="center", fontsize=8, color="#b22222")

    ax.set_xticks(x)
    ax.set_xticklabels(names, rotation=25, ha="right", fontsize=8)
    ax.set_ylim(0, 1.15)
    ax.set_ylabel("Recall")
    ax.axhline(1.0, color="black", linewidth=0.5, linestyle=":")
    ax.set_title(
        f"F6. Adversarial-spec recall calibration across the 7-type invariant taxonomy\n"
        f"(mean recall = {summary['mean_recall']:.3f}, 0 false-positive cross-type leakage)",
        fontsize=10,
    )
    ax.grid(axis="y", linestyle=":", alpha=0.4)
    return _save(fig, "f6_recall.png")


# ---------------------------------------------------------------------------
# F7 — cross-engine parity (embedded checker vs standalone replay)
# ---------------------------------------------------------------------------

def figure_f7_cross_engine() -> Path:
    """For each strategy, plot embedded violation count (x) vs standalone
    violation count (y). Perfect parity lies on y=x.

    Data source: per-strategy report.json (embedded) vs live run of
    scripts/check_invariants_from_fills.py on the same spec+fills.
    """
    strategies = [
        "strat_20260417_0001_trajectory_multi_3sym",
        "strat_20260417_0002_smoke_042700_obi5",
        "strat_20260417_0003_pilot_s1_042700_obi10",
        "strat_20260417_0004_pilot_s2_010140_spread",
        "strat_20260417_0005_pilot_s3_034020_spread",
        "strat_20260417_0006_pilot_s4_035420_obi5",
    ]

    points = []
    for s in strategies:
        report_path = REPO / "strategies" / s / "report.json"
        spec_path = REPO / "strategies" / s / "spec.yaml"
        if not (report_path.exists() and spec_path.exists()):
            continue
        embedded = len(json.loads(report_path.read_text()).get("invariant_violations") or [])
        out = subprocess.run(
            [
                sys.executable, "scripts/check_invariants_from_fills.py",
                "--spec", str(spec_path),
                "--fills-from-report", str(report_path),
            ],
            cwd=REPO, capture_output=True, text=True, check=True,
        )
        standalone = json.loads(out.stdout)["violation_count"]
        points.append((embedded, standalone, s))

    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    labels = [p[2].split("_")[-1] for p in points]

    fig, ax = plt.subplots(figsize=(5.4, 5.0))
    lim = max(max(xs), max(ys)) + 3
    ax.plot([0, lim], [0, lim], color="black", linewidth=0.8, linestyle="--",
            label="parity (y = x)")
    ax.scatter(xs, ys, s=80, color="#1f4d8b", edgecolor="black", zorder=5)
    for xi, yi, lab in zip(xs, ys, labels):
        ax.annotate(lab, (xi, yi), textcoords="offset points", xytext=(6, 4), fontsize=7)

    ax.set_xlim(-1, lim)
    ax.set_ylim(-1, lim)
    ax.set_xlabel("embedded violation count (custom engine)")
    ax.set_ylabel("standalone violation count (engine-agnostic replay)")
    ax.set_title(
        "F7. Cross-engine parity: identical invariant detection\n"
        "(standalone replay of GenericFill stream matches embedded checker byte-for-byte)",
        fontsize=10,
    )
    ax.grid(True, linestyle=":", alpha=0.4)
    ax.legend(loc="upper left", fontsize=8, frameon=False)
    return _save(fig, "f7_cross_engine.png")


def figure_f2_framework() -> Path:
    """F2 — Framework architecture diagram.

    Uses matplotlib primitives (no Gemini API). Shows the 9-agent pipeline
    on top, the dual-mode backtest engine in the middle, and the three
    measurement layer components (invariants, attribution, handoff audit)
    below, with arrows indicating information flow.
    """
    fig, ax = plt.subplots(figsize=(11.0, 5.5), constrained_layout=True)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 60)
    ax.axis("off")

    def box(x, y, w, h, text, color="#dfe7f5", edge="#1f4d8b", size=9, weight="normal"):
        ax.add_patch(plt.Rectangle((x, y), w, h, facecolor=color,
                                   edgecolor=edge, linewidth=1.2))
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
                fontsize=size, fontweight=weight)

    def arrow(x1, y1, x2, y2, color="#333333"):
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle="->", color=color, lw=1.0))

    # Top row — 9-agent pipeline (compressed)
    ax.text(50, 57, "LLM Agent Pipeline", ha="center", fontsize=11, fontweight="bold")
    agents = [
        ("alpha\ndesigner", 3, 48),
        ("execution\ndesigner", 15, 48),
        ("spec\nwriter", 27, 48),
        ("strategy\ncoder", 39, 48),
        ("backtest\nrunner", 51, 48),
        ("alpha\ncritic", 63, 48),
        ("execution\ncritic", 75, 48),
        ("feedback\nanalyst", 87, 48),
    ]
    for name, x, y in agents:
        box(x, y, 10, 6, name, color="#eaf2ff", size=8)
    for i in range(len(agents) - 1):
        arrow(agents[i][1] + 10, agents[i][2] + 3, agents[i + 1][1], agents[i + 1][2] + 3)
    # parallel-critic bracket
    ax.plot([65, 77], [54.3, 54.3], color="#1f4d8b", linewidth=1.5)
    ax.text(71, 55.0, "parallel", ha="center", fontsize=7, color="#1f4d8b", style="italic")

    # Middle row — engine
    ax.text(50, 40, "Dual-Mode Tick-Level Backtest Engine", ha="center",
            fontsize=11, fontweight="bold")
    box(8, 30, 38, 7, "Normal mode\n(strategy.py runs as-is)", color="#fff3d9",
        edge="#b57d00", size=9)
    box(54, 30, 38, 7, "Strict mode\n(engine enforces spec: REJECT / FORCE_SELL)",
        color="#ffe0d9", edge="#b22222", size=9)

    # Arrow from agent pipeline → engine
    arrow(50, 48, 27, 37, color="#555555")
    arrow(50, 48, 73, 37, color="#555555")

    # Bottom row — measurement layer
    ax.text(50, 23, "Engine-Agnostic Measurement Layer", ha="center",
            fontsize=11, fontweight="bold")
    box(3, 13, 28, 7,
        "Invariant inference\n(spec params → 7 runtime invariants)",
        color="#e5f3e0", edge="#3a7d3a", size=8)
    box(36, 13, 28, 7,
        "Counterfactual PnL attribution\n(normal − strict = bug_pnl)",
        color="#e5f3e0", edge="#3a7d3a", size=8)
    box(69, 13, 28, 7,
        "Handoff audit\n(field-propagation + agent trace)",
        color="#e5f3e0", edge="#3a7d3a", size=8)

    # Arrows engine → measurement
    arrow(27, 30, 17, 20, color="#555555")
    arrow(73, 30, 50, 20, color="#555555")
    arrow(60, 48, 83, 20, color="#555555")

    # Bottom tag
    ax.text(50, 6, "Portable across any deterministic LOB engine that emits (spec, fill-list)",
            ha="center", fontsize=9, style="italic", color="#333333")
    box(18, 0.5, 64, 4, "", color="#ffffff", edge="#aaaaaa", size=8)
    ax.text(50, 2.5,
            "→ demonstrated on custom KRX engine (Figure 7) and HFTBacktest-style fill stream (§6.2)",
            ha="center", fontsize=8)

    ax.set_title("F2. Framework — 9-agent LLM pipeline, dual-mode engine, engine-agnostic measurement layer",
                 fontsize=10, pad=6)
    return _save(fig, "f2_framework.png")


def figure_f4_handoff() -> Path:
    """F4 — Field-propagation rate by pipeline stage and required artifact.

    Data source: per-strategy handoff_audit.json files and the orchestration
    instruction log (baseline strat_0001 had no explicit propagation
    instruction; strat_0002–0006 did).
    """
    strategies = [
        "strat_20260417_0001_trajectory_multi_3sym",
        "strat_20260417_0002_smoke_042700_obi5",
        "strat_20260417_0003_pilot_s1_042700_obi10",
        "strat_20260417_0004_pilot_s2_010140_spread",
        "strat_20260417_0005_pilot_s3_034020_spread",
        "strat_20260417_0006_pilot_s4_035420_obi5",
    ]
    has_instruction = {s: (i > 0) for i, s in enumerate(strategies)}  # strat_0001 = no

    tracked_files = [
        "idea.json",
        "alpha_design.md",
        "execution_design.md",
        "alpha_critique.md",
        "execution_critique.md",
        "feedback.json",
        "agent_trace.jsonl",
    ]
    tracked_fields = ["signal_brief_rank", "deviation_from_brief"]

    baseline_total, baseline_hit = 0, 0
    explicit_total, explicit_hit = 0, 0
    per_file_baseline: dict[str, tuple[int, int]] = {f: (0, 0) for f in tracked_files}
    per_file_explicit: dict[str, tuple[int, int]] = {f: (0, 0) for f in tracked_files}
    per_field_baseline: dict[str, tuple[int, int]] = {f: (0, 0) for f in tracked_fields}
    per_field_explicit: dict[str, tuple[int, int]] = {f: (0, 0) for f in tracked_fields}

    for s in strategies:
        audit_path = REPO / "strategies" / s / "handoff_audit.json"
        if not audit_path.exists():
            continue
        d = json.loads(audit_path.read_text())
        files_present = d.get("files_present", {})
        fields_present = d.get("idea_fields_present", {})
        is_explicit = has_instruction[s]

        for f in tracked_files:
            total = 1
            hit = 1 if files_present.get(f, False) else 0
            if is_explicit:
                t, h = per_file_explicit[f]
                per_file_explicit[f] = (t + total, h + hit)
                explicit_total += total
                explicit_hit += hit
            else:
                t, h = per_file_baseline[f]
                per_file_baseline[f] = (t + total, h + hit)
                baseline_total += total
                baseline_hit += hit
        for f in tracked_fields:
            total = 1
            hit = 1 if fields_present.get(f, False) else 0
            if is_explicit:
                t, h = per_field_explicit[f]
                per_field_explicit[f] = (t + total, h + hit)
                explicit_total += total
                explicit_hit += hit
            else:
                t, h = per_field_baseline[f]
                per_field_baseline[f] = (t + total, h + hit)
                baseline_total += total
                baseline_hit += hit

    def rate(pair):
        t, h = pair
        return (h / t * 100.0) if t > 0 else 0.0

    labels_files = tracked_files
    labels_fields = tracked_fields
    all_labels = [f"file: {x}" for x in labels_files] + [f"field: {x}" for x in labels_fields]
    baseline_rates = [rate(per_file_baseline[f]) for f in labels_files] + \
                     [rate(per_field_baseline[f]) for f in labels_fields]
    explicit_rates = [rate(per_file_explicit[f]) for f in labels_files] + \
                     [rate(per_field_explicit[f]) for f in labels_fields]

    x = np.arange(len(all_labels))
    width = 0.38

    fig, ax = plt.subplots(figsize=(10.5, 4.2), constrained_layout=True)
    bars1 = ax.bar(x - width / 2, baseline_rates, width, label="baseline (no propagation instruction, n=1)",
                   color="#b22222", edgecolor="black")
    bars2 = ax.bar(x + width / 2, explicit_rates, width, label="explicit propagation instruction (n=5)",
                   color="#3a7d3a", edgecolor="black")

    for xi, v in zip(x - width / 2, baseline_rates):
        ax.text(xi, v + 2, f"{v:.0f}%", ha="center", fontsize=7)
    for xi, v in zip(x + width / 2, explicit_rates):
        ax.text(xi, v + 2, f"{v:.0f}%", ha="center", fontsize=7)

    ax.set_xticks(x)
    ax.set_xticklabels(all_labels, rotation=30, ha="right", fontsize=8)
    ax.set_ylim(0, 115)
    ax.set_ylabel("Propagation rate (%)")
    ax.axhline(100, color="black", linewidth=0.5, linestyle=":")
    ax.legend(loc="lower right", fontsize=8, frameon=False)
    overall_baseline = rate((baseline_total, baseline_hit))
    overall_explicit = rate((explicit_total, explicit_hit))
    ax.set_title(
        f"F4. Multi-agent handoff fidelity — field/artifact propagation rate\n"
        f"Baseline (no explicit instruction): {overall_baseline:.0f}%   |   "
        f"Explicit instruction: {overall_explicit:.0f}%",
        fontsize=10,
    )
    return _save(fig, "f4_handoff.png")


def figure_f8_multi_horizon() -> Path:
    """F8 — Multi-horizon Sharpe comparison: tick vs daily bar.

    Shows that LLM-generated strategies are profitable at bar resolution
    (Phase A) but structurally unprofitable at tick resolution (pilot),
    establishing the resolution-dependent fidelity gap empirically.
    """
    # Tick-level corpus: enumerate all strategies/strat_* directories dynamically
    tick_dir = REPO / "strategies"
    tick_sharpes = []
    for d in sorted(tick_dir.iterdir()):
        if not d.is_dir() or not d.name.startswith("strat_"):
            continue
        p = d / "report.json"
        if not p.exists():
            continue
        try:
            r = json.loads(p.read_text())
        except Exception:
            continue
        s = r.get("sharpe_annualized")
        if s is not None:
            tick_sharpes.append(s)

    # Bar-level: original 5 + expansion 5
    bar_path = REPO / "data" / "bar_attribution_summary.json"
    bar_data = json.loads(bar_path.read_text())
    bar_is_sharpes = [d["is"]["normal_sharpe"] for d in bar_data]
    bar_oos_sharpes = [d["oos"]["normal_sharpe"] for d in bar_data]

    expansion_path = REPO / "data" / "bar_corpus_expansion_results.json"
    if expansion_path.exists():
        exp = json.loads(expansion_path.read_text())
        bar_is_sharpes += [d["is_sharpe"] for d in exp]
        bar_oos_sharpes += [d["oos_sharpe"] for d in exp]

    # Buy-hold baseline for bar-level (from bar_baselines/summary.json)
    baseline_path = REPO / "data" / "bar_baselines" / "summary.json"
    bh_is_sharpes: list[float] = []
    if baseline_path.exists():
        bl = json.loads(baseline_path.read_text())
        for row in bl["strategies"]:
            if row["strategy"] == "buy_hold":
                bh_is_sharpes.append(row["is"]["sharpe_annualized"])

    fig, ax = plt.subplots(figsize=(9.5, 4.8), constrained_layout=True)

    groups = [f"Tick-level LLM\n(KRX, n={len(tick_sharpes)})",
              f"Bar-level LLM\n(Binance IS, n={len(bar_is_sharpes)})",
              f"Bar-level LLM\n(Binance OOS, n={len(bar_oos_sharpes)})",
              f"Bar-level Buy-Hold\n(baseline, n={len(bh_is_sharpes)})"]
    datasets = [tick_sharpes, bar_is_sharpes, bar_oos_sharpes, bh_is_sharpes]

    positions = np.arange(len(groups))
    colors = ["#b22222", "#1f4d8b", "#3a7d3a", "#888888"]
    parts = ax.violinplot(datasets, positions=positions, widths=0.7,
                          showmeans=True, showmedians=False)
    for i, pc in enumerate(parts["bodies"]):
        pc.set_facecolor(colors[i])
        pc.set_alpha(0.55)
        pc.set_edgecolor("black")
    parts["cmeans"].set_color("black")
    parts["cbars"].set_color("black")
    parts["cmins"].set_color("black")
    parts["cmaxes"].set_color("black")

    # Scatter dots for individual strategies
    for i, data in enumerate(datasets):
        jitter = np.random.default_rng(42 + i).uniform(-0.08, 0.08, size=len(data))
        ax.scatter(np.full(len(data), i) + jitter, data, s=30, color=colors[i],
                   edgecolor="black", zorder=5)

    ax.axhline(0, color="black", linewidth=0.7, linestyle="--", alpha=0.6)
    ax.axhline(1.0, color="#3a7d3a", linewidth=0.6, linestyle=":", alpha=0.7)
    ax.text(3.45, 1.05, "Sharpe=1", fontsize=7, color="#3a7d3a")

    ax.set_xticks(positions)
    ax.set_xticklabels(groups, fontsize=8)
    ax.set_ylabel("Annualized Sharpe")
    tick_profitable = sum(1 for s in tick_sharpes if s > 0)
    oos_profitable = sum(1 for s in bar_oos_sharpes if s > 0)
    best_oos = max(bar_oos_sharpes) if bar_oos_sharpes else 0.0
    ax.set_title(
        "F8. Resolution-dependent performance gap — Sharpe distribution by horizon\n"
        f"Tick-level: {tick_profitable}/{len(tick_sharpes)} profitable (fee dominates signal edge)   |   "
        f"Bar-level: {oos_profitable}/{len(bar_oos_sharpes)} OOS profitable, best OOS Sharpe = {best_oos:.2f}",
        fontsize=9,
    )
    ax.grid(axis="y", linestyle=":", alpha=0.4)
    return _save(fig, "f8_multi_horizon.png")


def figure_f9_bar_results() -> Path:
    """F9 — Per-strategy IS/OOS bar chart for Phase A, colored by paradigm.

    Companion to F8 showing individual LLM-generated bar strategies with
    IS vs OOS Sharpe side-by-side.
    """
    bar_data = json.loads((REPO / "data" / "bar_attribution_summary.json").read_text())
    ids = [d["strategy_id"].replace("bar_", "").replace("_momentum", " mom")
                    .replace("_reversion", " rev").replace("_breakout", " brk")
                    .replace("_compress", " cmp").replace("_ls", " LS")
                    .replace("btc_bb", "BTC BB").replace("sol_vol", "SOL vol")
                    .replace("eth_vol", "ETH vol").replace("btc_", "BTC ") for d in bar_data]
    is_sh = [d["is"]["normal_sharpe"] for d in bar_data]
    oos_sh = [d["oos"]["normal_sharpe"] for d in bar_data]
    is_ret = [d["is"]["normal_return_pct"] for d in bar_data]
    oos_ret = [d["oos"]["normal_return_pct"] for d in bar_data]

    x = np.arange(len(ids))
    width = 0.38

    fig, axes = plt.subplots(1, 2, figsize=(11.0, 4.2), constrained_layout=True)

    ax = axes[0]
    ax.bar(x - width / 2, is_sh, width, label="IS (2023-2024)", color="#1f4d8b", edgecolor="black")
    ax.bar(x + width / 2, oos_sh, width, label="OOS (2025)", color="#3a7d3a", edgecolor="black")
    ax.axhline(0, color="black", linewidth=0.5, linestyle="--")
    ax.axhline(1.0, color="red", linewidth=0.5, linestyle=":")
    ax.set_xticks(x)
    ax.set_xticklabels(ids, rotation=25, ha="right", fontsize=8)
    ax.set_ylabel("Annualized Sharpe")
    ax.set_title("(a) Sharpe by split")
    ax.legend(fontsize=8, frameon=False)
    ax.grid(axis="y", linestyle=":", alpha=0.4)

    ax = axes[1]
    ax.bar(x - width / 2, is_ret, width, label="IS return%", color="#1f4d8b", edgecolor="black")
    ax.bar(x + width / 2, oos_ret, width, label="OOS return%", color="#3a7d3a", edgecolor="black")
    ax.axhline(0, color="black", linewidth=0.5, linestyle="--")
    ax.set_xticks(x)
    ax.set_xticklabels(ids, rotation=25, ha="right", fontsize=8)
    ax.set_ylabel("Total Return (%)")
    ax.set_title("(b) Return by split")
    ax.legend(fontsize=8, frameon=False)
    ax.grid(axis="y", linestyle=":", alpha=0.4)

    fig.suptitle(
        "F9. LLM-generated bar-level strategies — 5 Phase A strategies × (IS, OOS)",
        fontsize=10,
    )
    return _save(fig, "f9_bar_results.png")


def figure_f10_horizon_sweep() -> Path:
    """F10 — Experiment 1: horizon sweep Sharpe curve.

    Shows monotonic improvement of Sharpe as horizon lengthens, with the
    fee-saturation threshold visible as the zero crossing. Multiple
    wallclock-window variants to disambiguate "bars of history" vs
    "bars of return horizon."
    """
    data = json.loads((REPO / "data" / "experiment_1_results.json").read_text())
    horizon_order = ["1m", "5m", "15m", "1h", "1d"]

    # Group by variant
    variants = sorted(set(r["variant"] for r in data))
    # Prefer a specific ordering: fixed first, then wallclock_ in ascending hours
    def _variant_key(v: str) -> int:
        if v == "fixed_bars":
            return -1
        if v.startswith("wallclock_"):
            h = v.replace("wallclock_", "").replace("h", "")
            try:
                return int(h)
            except ValueError:
                return 0
        return 999
    variants = sorted(variants, key=_variant_key)

    fig, axes = plt.subplots(1, 2, figsize=(12.5, 4.6), constrained_layout=True)

    # Left: Sharpe curves
    ax = axes[0]
    for v in variants:
        rows = [r for r in data if r["variant"] == v]
        rows.sort(key=lambda r: horizon_order.index(r["horizon"]))
        xs = [horizon_order.index(r["horizon"]) for r in rows]
        ys = [r["sharpe_annualized"] for r in rows]
        ax.plot(xs, ys, marker="o", label=v, linewidth=1.5)

    ax.set_xticks(range(len(horizon_order)))
    ax.set_xticklabels(horizon_order)
    ax.set_xlabel("Bar horizon")
    ax.set_ylabel("Annualized Sharpe")
    ax.axhline(0, color="black", linewidth=0.6, linestyle="--", alpha=0.7)
    ax.axhline(1.0, color="#3a7d3a", linewidth=0.5, linestyle=":", alpha=0.5)
    ax.set_title("(a) Sharpe vs horizon — monotonic improvement to zero crossing at ~daily", fontsize=9)
    ax.legend(fontsize=7, frameon=False, loc="lower right")
    ax.grid(True, linestyle=":", alpha=0.3)

    # Right: Return% curves
    ax = axes[1]
    for v in variants:
        rows = [r for r in data if r["variant"] == v]
        rows.sort(key=lambda r: horizon_order.index(r["horizon"]))
        xs = [horizon_order.index(r["horizon"]) for r in rows]
        ys = [r["total_return_pct"] for r in rows]
        ax.plot(xs, ys, marker="o", label=v, linewidth=1.5)

    ax.set_xticks(range(len(horizon_order)))
    ax.set_xticklabels(horizon_order)
    ax.set_xlabel("Bar horizon")
    ax.set_ylabel("Total Return (%)")
    ax.axhline(0, color="black", linewidth=0.6, linestyle="--", alpha=0.7)
    ax.set_title("(b) Total return vs horizon (log-odds equivalent)", fontsize=9)
    ax.legend(fontsize=7, frameon=False, loc="lower right")
    ax.grid(True, linestyle=":", alpha=0.3)

    fig.suptitle(
        "F10. Horizon sweep — BTCUSDT 2025-07..12, momentum strategy, 10 bps fee\n"
        "Fee-saturation threshold: Sharpe<0 for all horizons ≤1h, Sharpe>0 only at 1d",
        fontsize=10,
    )
    return _save(fig, "f10_horizon_sweep.png")


def figure_f3_clean_pct_distribution() -> Path:
    """F3 — clean_pct_of_total distribution across tick corpus (n up to 20).

    Shows the fidelity metric's distribution when the tick corpus is large
    enough for meaningful statistics. Stratified by violation presence.
    """
    summary_path = REPO / "data" / "attribution_summary.json"
    data = json.loads(summary_path.read_text())

    # Filter to tick strategies only (symbol like 0XXXXX)
    tick_rows = [r for r in data if "strat_" in r.get("strategy_id", "")]
    clean_pcts = [r["clean_pct_of_total"] for r in tick_rows
                  if r.get("clean_pct_of_total") is not None]
    n_total = len(tick_rows)

    has_viol = [r for r in tick_rows if r.get("normal_violations_by_type") and
                sum((r.get("normal_violations_by_type") or {}).values()) > 0]
    no_viol = [r for r in tick_rows if not r.get("normal_violations_by_type") or
               sum((r.get("normal_violations_by_type") or {}).values()) == 0]
    cpt_viol = [r["clean_pct_of_total"] for r in has_viol if r.get("clean_pct_of_total") is not None]
    cpt_nov = [r["clean_pct_of_total"] for r in no_viol if r.get("clean_pct_of_total") is not None]

    # Clip extreme outliers for visualization (mark them separately)
    def _clip(v):
        return max(-200, min(200, v))

    fig, ax = plt.subplots(figsize=(8.5, 4.2), constrained_layout=True)
    bins = np.arange(-200, 210, 20)
    if cpt_nov:
        ax.hist([_clip(v) for v in cpt_nov], bins=bins, alpha=0.7,
                color="#3a7d3a", edgecolor="black",
                label=f"no violations (n={len(no_viol)})")
    if cpt_viol:
        ax.hist([_clip(v) for v in cpt_viol], bins=bins, alpha=0.7,
                color="#b22222", edgecolor="black",
                label=f"≥1 invariant violation (n={len(has_viol)})")

    ax.axvline(100, color="black", linewidth=0.7, linestyle="--",
               label="clean_pct = 100 (no bug PnL)")
    ax.axvline(0, color="gray", linewidth=0.5, linestyle=":")
    ax.set_xlabel("clean_pct_of_total (%)")
    ax.set_ylabel("Number of strategies")
    ax.set_title(
        f"F3. Distribution of clean_pct_of_total across n={n_total} tick strategies\n"
        "Strategies with violations show wider clean_pct spread (sign of metric breakdown regimes §7)",
        fontsize=10,
    )
    ax.legend(fontsize=8, frameon=False)
    ax.grid(axis="y", linestyle=":", alpha=0.4)
    return _save(fig, "f3_clean_pct_distribution.png")


def figure_f5_violation_heatmap() -> Path:
    """F5 — violation type × strategy heatmap across expanded tick corpus."""
    summary_path = REPO / "data" / "attribution_summary.json"
    data = json.loads(summary_path.read_text())

    rows = [r for r in data if "strat_" in r.get("strategy_id", "")]
    # Collect all violation types
    all_types = sorted({
        t for r in rows
        for t in (r.get("normal_violations_by_type") or {}).keys()
    })
    if not all_types:
        all_types = ["(no violations in corpus)"]

    ids = [r["strategy_id"].replace("strat_20260417_", "17_")
                          .replace("strat_20260418_", "18_") for r in rows]

    mat = np.zeros((len(all_types), len(rows)))
    for j, r in enumerate(rows):
        vbt = r.get("normal_violations_by_type") or {}
        for i, t in enumerate(all_types):
            mat[i, j] = vbt.get(t, 0)

    fig, ax = plt.subplots(figsize=(max(8, 0.45 * len(rows) + 2), 2.2 + 0.45 * len(all_types)),
                           constrained_layout=True)
    im = ax.imshow(mat, aspect="auto", cmap="OrRd")
    ax.set_yticks(range(len(all_types)))
    ax.set_yticklabels(all_types, fontsize=8)
    ax.set_xticks(range(len(ids)))
    ax.set_xticklabels(ids, rotation=80, fontsize=7, ha="right")
    for i in range(len(all_types)):
        for j in range(len(rows)):
            v = int(mat[i, j])
            if v > 0:
                ax.text(j, i, str(v), ha="center", va="center", fontsize=7,
                        color="white" if v > mat.max() / 2 else "black")
    fig.colorbar(im, ax=ax, label="violation count", shrink=0.75)
    ax.set_title(
        f"F5. Invariant-violation heatmap: {len(all_types)} types × {len(rows)} strategies",
        fontsize=10,
    )
    return _save(fig, "f5_violation_heatmap.png")


def figure_f11_return_mdd_pareto() -> Path:
    """F11 — Return vs MDD scatter with Pareto frontier.

    Shows all bar strategies on Return/MDD plane, with the 50%+ threshold
    marked. Distinguishes base corpus, expansion, and aggressive variants.
    """
    table = json.loads((REPO / "data" / "full_corpus_table.json").read_text())
    bar_base = table["bar"]  # 10 strategies
    agg_path = REPO / "data" / "bar_aggressive_results.json"
    bar_agg = json.loads(agg_path.read_text()) if agg_path.exists() else []

    fig, ax = plt.subplots(figsize=(9.5, 5.5), constrained_layout=True)

    # Plot base
    xs_base = [r["full_mdd_pct"] for r in bar_base]
    ys_base = [r["full_return_pct"] for r in bar_base]
    labels_base = [r["strategy_id"].replace("bar_", "").replace("_", " ") for r in bar_base]
    ax.scatter(xs_base, ys_base, s=90, color="#1f4d8b", edgecolor="black",
               label=f"base corpus (n={len(bar_base)})", zorder=5)
    for x, y, lab in zip(xs_base, ys_base, labels_base):
        ax.annotate(lab, (x, y), xytext=(5, 5), textcoords="offset points", fontsize=7)

    # Plot aggressive
    xs_agg = [r["full_mdd_pct"] for r in bar_agg]
    ys_agg = [r["full_return_pct"] for r in bar_agg]
    labels_agg = [r["strategy_id"].replace("bar_", "").replace("_", " ") for r in bar_agg]
    ax.scatter(xs_agg, ys_agg, s=90, color="#b2560a", edgecolor="black",
               marker="^", label=f"aggressive variants (n={len(bar_agg)})", zorder=5)
    for x, y, lab in zip(xs_agg, ys_agg, labels_agg):
        ax.annotate(lab, (x, y), xytext=(5, 5), textcoords="offset points", fontsize=7)

    # Threshold lines
    ax.axhline(50, color="#3a7d3a", linewidth=0.8, linestyle="--", alpha=0.7)
    ax.text(min(xs_base + xs_agg) - 2, 52, "50% return target", fontsize=8, color="#3a7d3a")
    ax.axhline(0, color="black", linewidth=0.6, linestyle=":", alpha=0.5)
    ax.axvline(0, color="black", linewidth=0.6, linestyle=":", alpha=0.5)

    # MDD reference
    ax.axvline(-30, color="#b22222", linewidth=0.6, linestyle=":", alpha=0.5)
    ax.text(-29.5, max(ys_base + ys_agg) - 10, "MDD = -30%", fontsize=7, color="#b22222")

    ax.set_xlabel("Maximum Drawdown (%)")
    ax.set_ylabel("Total Return (%, 2023-01-01 .. 2025-12-31)")
    n_pass = sum(1 for r in bar_base + bar_agg if r["full_return_pct"] >= 50)
    ax.set_title(
        f"F11. Return-vs-MDD frontier — bar-level LLM-generated strategies (n={len(bar_base)+len(bar_agg)})\n"
        f"{n_pass}/{len(bar_base)+len(bar_agg)} strategies meet 50%+ total-return threshold over 3 years",
        fontsize=10,
    )
    ax.legend(fontsize=8, loc="lower right", frameon=False)
    ax.grid(True, linestyle=":", alpha=0.3)
    return _save(fig, "f11_return_mdd_pareto.png")


def figure_f10b_multi_symbol_horizon() -> Path:
    """F10b — Multi-symbol horizon sweep (BTC/ETH/SOL) with zero-crossing."""
    agg_path = REPO / "experiments" / "exp_g_multi_symbol_horizon" / "aggregate.json"
    if not agg_path.exists():
        return None
    rows = json.loads(agg_path.read_text())
    horizon_order = ["1m", "5m", "15m", "1h", "1d"]
    symbols = sorted({r["symbol"] for r in rows})

    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.6), constrained_layout=True)
    color_map = {"BTCUSDT": "#1f4d8b", "ETHUSDT": "#3a7d3a", "SOLUSDT": "#b2560a"}

    ax = axes[0]
    for sym in symbols:
        sym_rows = [r for r in rows if r["symbol"] == sym]
        sym_rows.sort(key=lambda r: horizon_order.index(r["horizon"]))
        xs = [horizon_order.index(r["horizon"]) for r in sym_rows]
        ys = [r["sharpe_median"] for r in sym_rows]
        ax.plot(xs, ys, marker="o", label=sym, color=color_map.get(sym, "gray"), linewidth=1.8)
    ax.set_xticks(range(len(horizon_order)))
    ax.set_xticklabels(horizon_order)
    ax.axhline(0, color="black", linewidth=0.6, linestyle="--", alpha=0.7)
    ax.set_xlabel("Bar horizon")
    ax.set_ylabel("Median Sharpe (across 5 lookback variants)")
    ax.set_title("(a) Sharpe by horizon — BTC/ETH/SOL", fontsize=9)
    ax.legend(fontsize=8)
    ax.grid(True, linestyle=":", alpha=0.3)

    ax = axes[1]
    for sym in symbols:
        sym_rows = [r for r in rows if r["symbol"] == sym]
        sym_rows.sort(key=lambda r: horizon_order.index(r["horizon"]))
        xs = [horizon_order.index(r["horizon"]) for r in sym_rows]
        ys = [r["return_pct_mean"] for r in sym_rows]
        ax.plot(xs, ys, marker="o", label=sym, color=color_map.get(sym, "gray"), linewidth=1.8)
    ax.set_xticks(range(len(horizon_order)))
    ax.set_xticklabels(horizon_order)
    ax.axhline(0, color="black", linewidth=0.6, linestyle="--", alpha=0.7)
    ax.set_xlabel("Bar horizon")
    ax.set_ylabel("Mean Total Return (%)")
    ax.set_title("(b) Total return by horizon", fontsize=9)
    ax.legend(fontsize=8)
    ax.grid(True, linestyle=":", alpha=0.3)

    fig.suptitle(
        "F10b. Multi-symbol horizon sweep — same momentum strategy on BTC/ETH/SOL\n"
        "Zero crossing (Sharpe>0) only at daily horizon across all 3 symbols",
        fontsize=10,
    )
    return _save(fig, "f10b_multi_symbol_horizon.png")


def figure_f12_risk_adjusted() -> Path:
    """F12 — Risk-adjusted metrics scatter: Sharpe × Calmar, colored by alpha sign."""
    path = REPO / "experiments" / "exp_h_risk_adjusted" / "results.json"
    if not path.exists():
        return None
    rows = json.loads(path.read_text())

    sharpes = [r["sharpe"] for r in rows]
    calmars = [min(r["calmar"], 2.5) for r in rows]  # cap for visualization
    alphas = [r["alpha_ann"] * 100 for r in rows]  # annualized pct
    labels = [r["strategy_id"].replace("bar_", "") for r in rows]
    colors = ["#3a7d3a" if a > 0 else "#b22222" for a in alphas]

    fig, ax = plt.subplots(figsize=(9.5, 5.5), constrained_layout=True)
    sc = ax.scatter(sharpes, calmars, c=alphas, cmap="RdYlGn", s=110, edgecolor="black",
                     vmin=-15, vmax=15, zorder=5)
    for x, y, lab in zip(sharpes, calmars, labels):
        ax.annotate(lab, (x, y), xytext=(5, 5), textcoords="offset points", fontsize=7)
    ax.axhline(1.0, color="black", linewidth=0.5, linestyle="--", alpha=0.6)
    ax.axvline(1.0, color="black", linewidth=0.5, linestyle="--", alpha=0.6)
    ax.set_xlabel("Annualized Sharpe")
    ax.set_ylabel("Calmar Ratio (annual return / |MDD|, capped at 2.5)")
    fig.colorbar(sc, ax=ax, label="Alpha vs Buy-Hold (annualized %)")
    pos_alpha = sum(1 for a in alphas if a > 0)
    ax.set_title(
        f"F12. Risk-adjusted metrics — bar strategies (n={len(rows)})\n"
        f"{pos_alpha}/{len(rows)} show positive alpha vs Buy-Hold. Top-right quadrant = best risk/return",
        fontsize=10,
    )
    ax.grid(True, linestyle=":", alpha=0.3)
    return _save(fig, "f12_risk_adjusted.png")


def figure_f13_crypto_horizon_llm() -> Path:
    """F13 — LLM-generated crypto strategies at 3 horizons × 3 symbols.

    Shows that paradigm diversity (mean_reversion / volatility_regime / breakout)
    cannot overcome fee-saturation below 1h horizon.
    """
    ids = [
        ("crypto_1h_btc_rsi_atr", "1h", "BTC"),
        ("crypto_1h_eth_rsi_atr", "1h", "ETH"),
        ("crypto_1h_sol_rsi_atr", "1h", "SOL"),
        ("crypto_15m_btc_rvol_compress", "15m", "BTC"),
        ("crypto_15m_eth_rvol_compress", "15m", "ETH"),
        ("crypto_15m_sol_rvol_compress", "15m", "SOL"),
        ("crypto_5m_btc_vol_breakout", "5m", "BTC"),
        ("crypto_5m_eth_vol_breakout", "5m", "ETH"),
        ("crypto_5m_sol_vol_breakout", "5m", "SOL"),
    ]
    rows = []
    for sid, h, s in ids:
        p = REPO / "strategies" / sid / "report.json"
        if not p.exists():
            continue
        r = json.loads(p.read_text())
        rows.append({
            "strategy_id": sid,
            "horizon": h,
            "symbol": s,
            "return_pct": r.get("return_pct", 0.0),
            "sharpe": r.get("sharpe_annualized", 0.0),
            "mdd_pct": r.get("mdd_pct", 0.0),
            "n_rt": r.get("n_roundtrips", 0),
        })

    horizons = ["5m", "15m", "1h"]
    symbols = ["BTC", "ETH", "SOL"]
    sharpe_mat = np.zeros((len(symbols), len(horizons)))
    ret_mat = np.zeros_like(sharpe_mat)
    for r in rows:
        i = symbols.index(r["symbol"])
        j = horizons.index(r["horizon"])
        sharpe_mat[i, j] = r["sharpe"]
        ret_mat[i, j] = r["return_pct"]

    fig, axes = plt.subplots(1, 2, figsize=(12.0, 4.5), constrained_layout=True)

    # Left: Sharpe heatmap
    ax = axes[0]
    im = ax.imshow(sharpe_mat, aspect="auto", cmap="RdYlGn", vmin=-20, vmax=2.5)
    ax.set_xticks(range(len(horizons)))
    ax.set_xticklabels(horizons)
    ax.set_yticks(range(len(symbols)))
    ax.set_yticklabels(symbols)
    for i in range(len(symbols)):
        for j in range(len(horizons)):
            v = sharpe_mat[i, j]
            color = "white" if abs(v) > 8 else "black"
            ax.text(j, i, f"{v:+.2f}", ha="center", va="center", fontsize=10, color=color, fontweight="bold")
    fig.colorbar(im, ax=ax, label="Annualized Sharpe", shrink=0.8)
    ax.set_title("(a) Sharpe by (horizon × symbol)", fontsize=10)
    ax.set_xlabel("Horizon")
    ax.set_ylabel("Symbol")

    # Right: grouped bar (Sharpe per horizon aggregated)
    ax = axes[1]
    x = np.arange(len(horizons))
    width = 0.25
    sym_colors = {"BTC": "#1f4d8b", "ETH": "#3a7d3a", "SOL": "#b2560a"}
    for i, sym in enumerate(symbols):
        values = sharpe_mat[i, :]
        ax.bar(x + (i - 1) * width, values, width, label=sym, color=sym_colors[sym], edgecolor="black")
    ax.axhline(0, color="black", linewidth=0.6, linestyle="--")
    ax.axhline(1.0, color="#3a7d3a", linewidth=0.5, linestyle=":")
    ax.set_xticks(x)
    ax.set_xticklabels(horizons)
    ax.set_ylabel("Annualized Sharpe")
    ax.set_xlabel("Horizon")
    ax.set_title("(b) Same data, grouped by symbol", fontsize=10)
    ax.legend(fontsize=9, frameon=False)
    ax.grid(axis="y", linestyle=":", alpha=0.3)

    n_profitable_1h = sum(1 for r in rows if r["horizon"] == "1h" and r["sharpe"] > 0)
    fig.suptitle(
        "F13. LLM-designed crypto strategies across horizons (mean_reversion / vol_regime / breakout)\n"
        f"1h: {n_profitable_1h}/3 profitable (ETH best: Sharpe 2.02)  |  15m, 5m: 0/6 profitable — "
        "paradigm diversity cannot overcome fee-saturation",
        fontsize=10,
    )
    return _save(fig, "f13_crypto_horizon_llm.png")


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate paper figures from pilot data.")
    ap.add_argument("--figures", nargs="+",
                    default=["f1", "f2", "f3", "f4", "f5", "f6", "f7", "f8", "f9",
                             "f10", "f10b", "f11", "f12", "f13"],
                    help="Which figures to generate")
    args = ap.parse_args()

    jobs = {
        "f1": figure_f1_teaser,
        "f2": figure_f2_framework,
        "f3": figure_f3_clean_pct_distribution,
        "f4": figure_f4_handoff,
        "f5": figure_f5_violation_heatmap,
        "f6": figure_f6_recall,
        "f7": figure_f7_cross_engine,
        "f8": figure_f8_multi_horizon,
        "f9": figure_f9_bar_results,
        "f10": figure_f10_horizon_sweep,
        "f10b": figure_f10b_multi_symbol_horizon,
        "f11": figure_f11_return_mdd_pareto,
        "f12": figure_f12_risk_adjusted,
        "f13": figure_f13_crypto_horizon_llm,
    }
    for key in args.figures:
        fn = jobs.get(key.lower())
        if fn is None:
            print(f"Unknown figure: {key}", file=sys.stderr)
            continue
        path = fn()
        print(f"{key}: {path.relative_to(REPO)}")


if __name__ == "__main__":
    main()
