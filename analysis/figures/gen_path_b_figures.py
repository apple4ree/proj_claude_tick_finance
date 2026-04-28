"""Path B (maker spread capture) 시각화 — 영어 라벨 (matplotlib 호환).

한국어 캡션은 progress.md 본문에서 figure 아래에 적기.
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
OUT = Path(__file__).resolve().parent
OUT.mkdir(exist_ok=True)


def fig_maker_effect():
    """Top 5 v5 specs: mid_gross vs maker_gross."""
    data = json.load(open(REPO_ROOT / "analysis" / "maker_smoke_results.json"))
    rows = data["rows"]
    names = [r["spec_id"][7:][:32] for r in rows]
    mid = [r["mid"] for r in rows]
    maker = [r["maker"] for r in rows]
    fee = data["fee_bps"]

    fig, ax = plt.subplots(figsize=(10, 5))
    x = np.arange(len(rows))
    w = 0.35
    ax.bar(x - w/2, mid, w, label="mid-to-mid (legacy)", color="#888")
    ax.bar(x + w/2, maker, w, label="maker_optimistic (Path B)", color="#3a7")
    ax.axhline(fee, color="r", linestyle="--", label=f"KRX RT fee = {fee} bps")
    ax.set_xticks(x)
    ax.set_xticklabels(names, rotation=30, ha="right", fontsize=8)
    ax.set_ylabel("aggregate gross expectancy (bps)")
    ax.set_title("Path B effect — Top 5 v5 specs: mid vs maker (8 dates x 3 syms)")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUT / "fig_maker_effect.png", dpi=140)
    plt.close(fig)
    print(f"OK {OUT / 'fig_maker_effect.png'}")


def fig_v5_v6_mean_dur():
    """v5 vs v6 mean_dur distribution."""
    def collect(root):
        out = []
        if not root.exists(): return out
        for d in sorted(root.glob("iter_*/")):
            for f in d.glob("results/*.json"):
                try:
                    r = json.load(open(f))
                    if r.get("aggregate_n_trades", 0) >= 500:
                        md = r.get("aggregate_mean_duration_ticks") or 0
                        if md > 0: out.append(md)
                except: pass
        return out

    v5 = collect(REPO_ROOT / "iterations_v5_archive_20260428")
    v6 = collect(REPO_ROOT / "iterations")

    fig, ax = plt.subplots(figsize=(10, 5))
    bins = np.logspace(0, 4, 30)
    ax.hist(v5, bins=bins, alpha=0.6, label=f"v5 (mid-only, n={len(v5)})", color="#888")
    ax.hist(v6, bins=bins, alpha=0.6, label=f"v6 (maker mode, n={len(v6)})", color="#3a7")
    ax.set_xscale("log")
    ax.set_xlabel("mean regime duration (ticks, log scale)")
    ax.set_ylabel("number of specs")
    ax.set_title("v5 vs v6: mean_duration distribution (Path D effect)")
    if v5: ax.axvline(np.mean(v5), color="#666", linestyle=":", label=f"v5 avg {np.mean(v5):.0f}")
    if v6: ax.axvline(np.mean(v6), color="#3a7", linestyle=":", label=f"v6 avg {np.mean(v6):.0f}")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUT / "fig_v5_v6_mean_dur.png", dpi=140)
    plt.close(fig)
    print(f"OK {OUT / 'fig_v5_v6_mean_dur.png'}")


def fig_fee_floor_reduction():
    """fee floor: mid mode 23 -> maker mode 14 (= 23 - 9 spread)."""
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.barh(["mid-to-mid\n(legacy)"], [23], color="#888", height=0.4, label="fee floor 23 bps")
    ax.barh(["mid-to-mid\n(legacy)"], [4.74], color="#3a7", height=0.2, left=0,
            label="v5 best mid_gross 4.74")
    ax.barh(["maker_optimistic\n(Path B)"], [23], color="#888", height=0.4)
    ax.barh(["maker_optimistic\n(Path B)"], [9], color="#fa3", height=0.2, left=0,
            label="avg spread 9 bps (recovered)")
    ax.barh(["maker_optimistic\n(Path B)"], [14.01], color="#3a7", height=0.2, left=9,
            label="v5 best maker_gross 14.01")
    ax.axvline(23, color="r", linestyle="--", linewidth=1.2, label="KRX RT fee = 23")
    ax.set_xlabel("bps")
    ax.set_xlim(0, 26)
    ax.set_title("Fee floor reduction: mid mode vs maker mode")
    ax.legend(loc="lower right", fontsize=9)
    ax.grid(axis="x", alpha=0.3)
    ax.text(11.5, 0.15, "<- deploy threshold 23 -> 14 (9 bps lower)",
            fontsize=10, color="#fa3", verticalalignment="center")
    fig.tight_layout()
    fig.savefig(OUT / "fig_fee_floor_reduction.png", dpi=140)
    plt.close(fig)
    print(f"OK {OUT / 'fig_fee_floor_reduction.png'}")


if __name__ == "__main__":
    fig_maker_effect()
    fig_v5_v6_mean_dur()
    fig_fee_floor_reduction()
