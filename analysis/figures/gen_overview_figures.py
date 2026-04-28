"""Project overview 용 추가 figure.

1. fig_paths_diagnosis_mapping — v5 천장의 4 원인 → 4 lever 매핑 (causal)
2. fig_full_trajectory — v3-v6 의 best mid + maker + fee floor trajectory (확장)
"""
from __future__ import annotations

from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

OUT = Path(__file__).resolve().parent
OUT.mkdir(exist_ok=True)


def fig_paths_diagnosis_mapping():
    """4 causes -> 4 levers visual mapping."""
    fig, ax = plt.subplots(figsize=(11, 6))
    ax.set_xlim(0, 10); ax.set_ylim(0, 10); ax.axis("off")

    # Title
    ax.text(5, 9.5, "v5 ceiling diagnosis: 4 causes -> 4 levers (Path A/B/C/D)",
            fontsize=14, ha="center", weight="bold")
    ax.text(5, 8.9, "v5 best 4.74 bps  vs  KRX fee 23 bps  =>  18 bps gap",
            fontsize=11, ha="center", color="#666")

    # Cause boxes (left side)
    causes = [
        (0.3, 7.0, "Cause 1: LLM magnitude\nguess unanchored\n(±100% off)", "#fdd"),
        (0.3, 5.3, "Cause 2: prompt bloat\n(872 lines logs)\nattention diluted", "#fdd"),
        (0.3, 3.6, "Cause 3: backtest mid-only\nno spread accounting", "#fdd"),
        (0.3, 1.9, "Cause 4: pattern saturation\n(top10 v5 = same\nobi+open+shape)", "#fdd"),
    ]
    for (x, y, label, color) in causes:
        ax.add_patch(plt.Rectangle((x, y), 3.0, 1.3, facecolor=color, edgecolor="k"))
        ax.text(x + 1.5, y + 0.65, label, ha="center", va="center", fontsize=9)

    # Lever boxes (right side)
    levers = [
        (6.5, 7.0, "Path A — LLM calibration\nquick_ref + AGENTS trim\n(150 lines)", "#dfd"),
        (6.5, 5.3, "Path B — Maker mode\nbacktest BID/ASK accounting\nfee floor 23 -> 14", "#dfd"),
        (6.5, 3.6, "Path C — Empirical baselines\n15 cells partition\n(3.78M ticks)", "#dfd"),
        (6.5, 1.9, "Path D — T-scaling\n9 T x 5 primitives\nalpha vs drift adjusted", "#dfd"),
    ]
    for (x, y, label, color) in levers:
        ax.add_patch(plt.Rectangle((x, y), 3.0, 1.3, facecolor=color, edgecolor="k"))
        ax.text(x + 1.5, y + 0.65, label, ha="center", va="center", fontsize=9)

    # Connections (cause -> lever) — many-to-many but show primary
    connections = [
        (1, 0, "primary"),  # cause 1 -> path A
        (1, 2, "secondary"),
        (1, 3, "secondary"),
        (2, 0, "primary"),  # cause 2 -> path A
        (3, 1, "primary"),  # cause 3 -> path B
        (4, 0, "secondary"),
        (4, 2, "primary"),  # cause 4 -> path C
        (4, 3, "secondary"),
    ]
    for cause_idx, lever_idx, kind in connections:
        c_y = causes[cause_idx-1][1] + 0.65
        l_y = levers[lever_idx][1] + 0.65
        color = "#3a7" if kind == "primary" else "#aaa"
        lw = 1.5 if kind == "primary" else 0.7
        alpha = 0.9 if kind == "primary" else 0.4
        ax.annotate("", xy=(6.5, l_y), xytext=(3.3, c_y),
                    arrowprops=dict(arrowstyle="->", color=color, lw=lw, alpha=alpha))

    # Legend
    ax.plot([], [], "-", color="#3a7", linewidth=2, label="primary mapping")
    ax.plot([], [], "-", color="#aaa", linewidth=1, alpha=0.5, label="secondary mapping")
    ax.legend(loc="lower center", fontsize=9, ncol=2)

    fig.tight_layout()
    fig.savefig(OUT / "fig_paths_diagnosis_mapping.png", dpi=140); plt.close(fig)
    print("OK fig_paths_diagnosis_mapping.png")


def fig_full_trajectory():
    """v3 -> v6 의 best mid + maker + fee floor trajectory (annotated)."""
    versions = ["v3\n(fixed-H, WR)", "v4\n(fixed-H, net)", "v5\n(regime, net)", "v6 (in progress)\n(+ Path A/B/C/D)"]
    best_mid = [13.32, 12.85, 4.74, 4.46]  # v6 best mid so far (iter_004)
    best_maker = [None, None, 14.01, 21.64]  # v6 iter_008 best maker (suspicious)
    best_maker_clean = [None, None, 14.01, 14.12]  # v6 iter_004 (real alpha)

    fig, ax = plt.subplots(figsize=(11, 6))
    x = np.arange(len(versions))

    ax.plot(x, best_mid, "o-", linewidth=2.5, markersize=11, color="#888",
            label="best mid_gross (real alpha)")

    valid_x = [i for i, v in enumerate(best_maker) if v is not None]
    valid_v = [best_maker[i] for i in valid_x]
    valid_v_clean = [best_maker_clean[i] for i in valid_x]
    ax.plot(valid_x, valid_v, "s--", linewidth=1.5, markersize=10, color="#fa3", alpha=0.7,
            label="best maker_gross (incl. spread-only specs)")
    ax.plot(valid_x, valid_v_clean, "s-", linewidth=2.5, markersize=11, color="#3a7",
            label="best maker_gross (real alpha specs only)")

    ax.axhline(23, color="r", linestyle="--", linewidth=2, label="KRX RT fee 23 bps (deploy threshold)")
    ax.axhline(14, color="orange", linestyle=":", alpha=0.7,
               label="maker mode floor (= 23 - 9 spread)")

    ax.set_xticks(x); ax.set_xticklabels(versions, fontsize=10)
    ax.set_ylabel("best gross expectancy (bps)")
    ax.set_title("Project trajectory: best gross over v3 -> v6\n(higher = better; 23 bps = KRX deploy threshold)")

    # Annotations
    for i, v in enumerate(best_mid):
        ax.annotate(f"{v:.2f}", (i, v), textcoords="offset points", xytext=(0, 12),
                    ha="center", fontsize=10, color="#666")
    for i, v in zip(valid_x, valid_v_clean):
        ax.annotate(f"{v:.2f}", (i, v), textcoords="offset points", xytext=(0, 12),
                    ha="center", fontsize=10, color="#3a7")

    # Annotate iter_008 outlier
    ax.annotate("iter_008 (mid=0,\nspread spike\nsuspicious)", xy=(3, 21.64), xytext=(2.6, 18),
                fontsize=8, color="#fa3", ha="center",
                arrowprops=dict(arrowstyle="->", color="#fa3", alpha=0.6))

    ax.legend(loc="upper right", fontsize=9)
    ax.grid(alpha=0.3)
    ax.set_ylim(0, 26)
    fig.tight_layout()
    fig.savefig(OUT / "fig_full_trajectory.png", dpi=140); plt.close(fig)
    print("OK fig_full_trajectory.png")


if __name__ == "__main__":
    fig_paths_diagnosis_mapping()
    fig_full_trajectory()
