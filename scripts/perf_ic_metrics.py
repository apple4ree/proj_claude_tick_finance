"""IC / ICIR / IR helpers for bar-level strategies.

Definitions (per the standard factor-investing convention):
  IC (Information Coefficient)
      Correlation between signal_t (the prediction for bar t -> t+1)
      and the realized forward return over that bar.
      Both Pearson and Spearman are reported.
  ICIR (Information Coefficient Information Ratio)
      mean(IC_k) / std(IC_k) across non-overlapping chunks, scaled by
      sqrt(chunks_per_year). Measures IC stability over time.
  IR (Information Ratio)
      mean(strat_ret - bench_ret) / std(strat_ret - bench_ret), annualized.
      Benchmark is buy-and-hold of the underlying.
"""
from __future__ import annotations

import numpy as np


def _avg_rank(x: np.ndarray) -> np.ndarray:
    """Average-rank of `x` (1-indexed), assigning the mean rank to ties.

    Equivalent to `scipy.stats.rankdata(x, method="average")` but keeps
    this module dependency-free (only numpy).
    """
    order = np.argsort(x, kind="mergesort")
    sorted_x = x[order]
    ranks = np.empty(len(x), dtype=np.float64)
    n = len(x)
    i = 0
    while i < n:
        j = i
        while j + 1 < n and sorted_x[j + 1] == sorted_x[i]:
            j += 1
        avg = (i + j) / 2.0 + 1.0  # 1-indexed mid-rank across the tie group
        ranks[order[i:j + 1]] = avg
        i = j + 1
    return ranks


def _spearman(x: np.ndarray, y: np.ndarray) -> float:
    """Tie-aware Spearman rank correlation.

    Signals are discrete {-1, 0, +1} so plain `argsort(argsort(·))` gives
    distinct ordinal ranks to ties and is implementation-order dependent.
    We use average ranks (standard Spearman convention).
    """
    if len(x) < 2:
        return 0.0
    rx = _avg_rank(x)
    ry = _avg_rank(y)
    if np.std(rx) == 0.0 or np.std(ry) == 0.0:
        return 0.0
    return float(np.corrcoef(rx, ry)[0, 1])


def compute_signal_metrics(signal: np.ndarray,
                            forward_ret: np.ndarray,
                            strat_ret: np.ndarray,
                            bench_ret: np.ndarray,
                            bars_per_year: float,
                            ic_chunk_bars: int | None = None) -> dict:
    """Return IC / ICIR / IR.

    signal       : per-bar predicted direction at bar t (used for t -> t+1)
    forward_ret  : realized return from bar t -> t+1 (length n-1)
    strat_ret    : net strategy per-bar returns (length n-1)
    bench_ret    : buy-and-hold per-bar returns (length n-1)
    bars_per_year: annualization factor (must be > 0; e.g. 365 for daily,
                   24*365 for 1h)
    ic_chunk_bars: non-overlapping chunk size for ICIR. If None, defaults
                   to max(bars_per_year/52, 10) — ≈ weekly for intraday
                   horizons but clamped at 10 bars (≈ 2 calendar weeks)
                   at daily or coarser cadence.
    """
    out = {"ic_pearson": 0.0, "ic_spearman": 0.0, "icir": 0.0,
           "information_ratio": 0.0, "ic_n": 0, "icir_chunks": 0}

    if not (isinstance(bars_per_year, (int, float))
            and np.isfinite(bars_per_year)
            and bars_per_year > 0):
        return out
    if ic_chunk_bars is not None:
        # Must be a positive integer — range() and array slicing require it.
        if not isinstance(ic_chunk_bars, (int, np.integer)) or ic_chunk_bars <= 0:
            return out

    sig = np.asarray(signal, dtype=np.float64)
    fr = np.asarray(forward_ret, dtype=np.float64)
    # Align: signal at bar t predicts return over bar t -> t+1.
    n = min(len(sig) - 1, len(fr))
    if n < 3:
        return out
    sig = sig[:n]
    fr = fr[:n]
    mask = np.isfinite(sig) & np.isfinite(fr)
    sig = sig[mask]
    fr = fr[mask]
    if len(sig) < 3:
        return out

    out["ic_n"] = int(len(sig))

    if np.std(sig) > 1e-12 and np.std(fr) > 1e-12:
        out["ic_pearson"] = float(np.corrcoef(sig, fr)[0, 1])
        out["ic_spearman"] = _spearman(sig, fr)

    # ICIR across non-overlapping chunks. Target is ≈ weekly cadence for
    # intraday horizons; for daily (and coarser) the minimum chunk size is
    # clamped at 10 bars (~2 calendar weeks) so per-chunk correlations have
    # enough samples to be meaningful. The annualization factor below is
    # computed from the *actual* chunk size, so the IR-style scaling stays
    # self-consistent regardless of the floor.
    if ic_chunk_bars is None:
        ic_chunk_bars = max(int(bars_per_year / 52.0), 10)
    n_chunks = len(sig) // ic_chunk_bars
    if n_chunks >= 3:
        ics: list[float] = []
        for k in range(n_chunks):
            s = sig[k * ic_chunk_bars:(k + 1) * ic_chunk_bars]
            f = fr[k * ic_chunk_bars:(k + 1) * ic_chunk_bars]
            if np.std(s) > 1e-12 and np.std(f) > 1e-12:
                ics.append(float(np.corrcoef(s, f)[0, 1]))
        # Always record how many chunks actually had signal dispersion so
        # sparse-signal cases can be distinguished from missing data.
        out["icir_chunks"] = len(ics)
        # Require ≥5 active chunks so ICIR isn't dominated by a handful of
        # windows where a sparse signal happened to fire.
        if len(ics) >= 5 and np.std(ics) > 1e-12:
            # Annualize by sqrt(chunks/year) — classic IR-style scaling.
            chunks_per_year = bars_per_year / ic_chunk_bars
            out["icir"] = float(np.mean(ics) / np.std(ics) * np.sqrt(chunks_per_year))

    # IR vs benchmark.
    m = min(len(strat_ret), len(bench_ret))
    if m >= 2:
        sr = np.asarray(strat_ret[:m], dtype=np.float64)
        br = np.asarray(bench_ret[:m], dtype=np.float64)
        # Mirror the IC path: drop non-finite bars so a single NaN/inf in the
        # return stream does not silently poison the IR into a neutral 0.0.
        finite = np.isfinite(sr) & np.isfinite(br)
        sr = sr[finite]
        br = br[finite]
        if len(sr) >= 2:
            diff = sr - br
            te = float(np.std(diff))
            if te > 1e-12:
                out["information_ratio"] = float(np.mean(diff) / te * np.sqrt(bars_per_year))

    return out
