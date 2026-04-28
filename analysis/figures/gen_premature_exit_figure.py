"""Premature exit 시각화 — chain 1 의 binary signal 한계."""
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

OUT = Path(__file__).resolve().parent


def fig_premature_exit():
    fig, axes = plt.subplots(2, 1, figsize=(12, 6), sharex=True)

    # Top — signal trajectory
    ax = axes[0]
    t = np.arange(0, 25)
    signal = np.array([0,0,1,1,1,1,1,0,0,0,0,1,1,1,1,1,1,1,1,1,1,1,1,1,0])
    ax.fill_between(t, 0, signal, where=(signal == 1), alpha=0.4, color="#3a7", step="mid", label="signal=True")
    ax.fill_between(t, 0, 1, where=(signal == 0), alpha=0.15, color="#888", step="mid", label="signal=False")
    ax.set_ylabel("signal")
    ax.set_yticks([0, 1])
    ax.set_title("Binary signal — current chain 1 design")
    ax.legend(loc="upper left", fontsize=9)
    ax.set_ylim(-0.1, 1.3)

    # Annotate entry/exit
    ax.annotate("ENTER\n(t=2)", xy=(2, 1), xytext=(0.5, 1.2), fontsize=9,
                arrowprops=dict(arrowstyle="->", color="#3a7"))
    ax.annotate("EXIT (t=7)\nsignal=False", xy=(7, 1), xytext=(8, 1.2), fontsize=9, color="#d33",
                arrowprops=dict(arrowstyle="->", color="#d33"))
    ax.annotate("RE-ENTER (t=11)", xy=(11, 1), xytext=(10, 1.2), fontsize=9,
                arrowprops=dict(arrowstyle="->", color="#3a7"))

    # Bottom — mid price trajectory (synthetic, illustrating premature exit)
    ax = axes[1]
    np.random.seed(7)
    base = np.cumsum(np.random.randn(25) * 0.3)
    # Engineer: rise during regime 1, brief dip at t=7-10, rise again
    mid = np.zeros(25)
    mid[0:7] = np.linspace(0, 5, 7)        # 진입 시점부터 +5 bps
    mid[7:11] = np.linspace(5, 4, 4)       # 잠깐 조정 (-1 bps)
    mid[11:25] = np.linspace(4, 18, 14)    # 다시 큰 상승

    ax.plot(t, mid, "-", linewidth=2, color="#444", label="mid (bps from start)")
    ax.fill_between(t, mid.min()-2, mid.max()+2, where=(signal == 1),
                     alpha=0.15, color="#3a7", step="mid")

    # Realized gain
    ax.annotate("", xy=(7, 5), xytext=(2, 0),
                arrowprops=dict(arrowstyle="->", color="#3a7", lw=2))
    ax.text(4.5, 6, "regime 1 realized\n+5 bps (captured)", fontsize=9, color="#3a7", ha="center")

    # Missed gain (premature exit)
    ax.annotate("", xy=(11, 4), xytext=(7, 5),
                arrowprops=dict(arrowstyle="->", color="#d33", lw=1.5, linestyle=":"))
    ax.text(8.5, 8, "premature exit\n(closed on noise)", fontsize=9, color="#d33", ha="center")

    # Recovery + missed
    ax.annotate("", xy=(11, 4), xytext=(11, 18),
                arrowprops=dict(arrowstyle="<->", color="#fa3", lw=2))
    ax.text(12.5, 11, "regime 2 +14 bps\n(re-enter possible,\nbut +fee, entry lag)", fontsize=9, color="#fa3")

    # Hypothetical "no exit" path
    ax.plot([2, 24], [0, 18], ":", linewidth=1.5, color="#888", label="\"no exit\" hypothetical (+18 bps)")

    ax.set_xlabel("time (ticks)")
    ax.set_ylabel("mid (bps from t=0)")
    ax.set_title("Cost of premature exit")
    ax.legend(loc="upper left", fontsize=9)
    ax.grid(alpha=0.3)

    fig.tight_layout()
    fig.savefig(OUT / "fig_premature_exit.png", dpi=140); plt.close(fig)
    print("OK fig_premature_exit.png")


if __name__ == "__main__":
    fig_premature_exit()
