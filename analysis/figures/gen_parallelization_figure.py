"""Sequential vs Parallel pipeline 시각화."""
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

OUT = Path(__file__).resolve().parent


def fig_pipeline_comparison():
    fig, axes = plt.subplots(2, 1, figsize=(12, 6.5), sharex=True)

    # Sequential timeline
    ax = axes[0]
    ax.set_title("Sequential pipeline (current — 35min)", fontsize=12, weight="bold")
    ax.set_xlim(0, 36); ax.set_ylim(-0.5, 4.5); ax.set_yticks([])
    ax.set_xlabel("minutes"); ax.grid(axis="x", alpha=0.3)

    stages_seq = [
        (0, 2, "gen", "#a8e6cf"),
    ]
    t = 2
    for s_idx in range(4):
        for label, dur, color in [("eval", 1, "#dcedc1"), ("cgen", 1, "#dcedc1"),
                                    ("fid", 0.5, "#888"),
                                    ("BACKTEST", 5, "#ffd3b6"),
                                    ("fb", 1.5, "#dcedc1")]:
            stages_seq.append((t, t + dur, f"s{s_idx+1}.{label}", color))
            t += dur
    stages_seq.append((t, t + 1, "improve", "#a8e6cf"))

    for (start, end, label, color) in stages_seq:
        ax.barh(2.0, end - start, left=start, height=0.6, color=color, edgecolor="k", linewidth=0.4)
        if end - start >= 1.5:
            ax.text((start + end) / 2, 2.0, label, ha="center", va="center", fontsize=7)
    ax.text(36, 2.0, "  35min", ha="left", va="center", fontsize=10, color="#d33", weight="bold")

    # Parallel timeline
    ax = axes[1]
    ax.set_title("Parallel pipeline (--parallel — ~11min)", fontsize=12, weight="bold")
    ax.set_xlim(0, 36); ax.set_ylim(-0.5, 4.5)
    ax.set_yticks([0.5, 1.5, 2.5, 3.5]); ax.set_yticklabels(["spec1", "spec2", "spec3", "spec4"])
    ax.set_xlabel("minutes"); ax.grid(axis="x", alpha=0.3)

    # Generator (single)
    ax.barh(2.0, 2, left=0, height=0.6, color="#a8e6cf", edgecolor="k", linewidth=0.4)
    ax.text(1, 2.0, "gen (4 specs)", ha="center", va="center", fontsize=8)

    # 4 specs in parallel
    spec_pipeline = [("eval", 1, "#dcedc1"), ("cgen", 1, "#dcedc1"),
                     ("fid", 0.5, "#888"),
                     ("BACKTEST", 5, "#ffd3b6"),
                     ("fb", 1.5, "#dcedc1")]
    for s_idx in range(4):
        t = 2
        y = 0.5 + s_idx
        for label, dur, color in spec_pipeline:
            ax.barh(y, dur, left=t, height=0.6, color=color, edgecolor="k", linewidth=0.4)
            if dur >= 1.5:
                ax.text(t + dur/2, y, label, ha="center", va="center", fontsize=7)
            t += dur

    # Improver
    ax.barh(2.0, 1, left=11, height=0.6, color="#a8e6cf", edgecolor="k", linewidth=0.4)
    ax.text(11.5, 2.0, "imp", ha="center", va="center", fontsize=8)

    ax.text(36, 2.0, "  ~11min (3.2x faster)", ha="left", va="center", fontsize=10, color="#3a7", weight="bold")

    fig.tight_layout()
    fig.savefig(OUT / "fig_parallelization_comparison.png", dpi=140); plt.close(fig)
    print(f"OK fig_parallelization_comparison.png")


if __name__ == "__main__":
    fig_pipeline_comparison()
