"""Chain 1 statistical utilities — López de Prado 2018 + Benjamini-Hochberg 1995.

Provides deterministic statistical functions to replace LLM fabricated numbers
in chain2-gate, feedback-analyst, and similar agents.

References:
  - López de Prado (2014, 2018): Deflated Sharpe Ratio, PBO
  - Harvey, Liu & Zhu (2016): Multiple-testing for factor research
  - Benjamini & Hochberg (1995): FDR control procedure

No agent call. Pure numpy/scipy. Deterministic for a given input.
"""
from __future__ import annotations

from typing import Iterable

import numpy as np
from scipy.stats import norm, t as t_dist


# ---------------------------------------------------------------------------
# Per-trade primitives
# ---------------------------------------------------------------------------


def per_trade_stats(signed_bps: np.ndarray | Iterable[float]) -> dict:
    """Compute moments + lag-1 autocorrelation from a trace of signed returns.

    Input:
      signed_bps: per-trade signed return in bps. Sign convention: positive if
        prediction matches realized direction.

    Output dict keys:
      n, mean, std, skew, excess_kurt, autocorr_lag1, sharpe_per_trade
    """
    arr = np.asarray(list(signed_bps), dtype=np.float64)
    n = len(arr)
    if n < 2:
        return {"n": n, "mean": 0.0, "std": 0.0, "skew": 0.0,
                "excess_kurt": 0.0, "autocorr_lag1": 0.0,
                "sharpe_per_trade": 0.0}
    mean = float(arr.mean())
    std = float(arr.std(ddof=1))
    if std > 1e-12:
        diffs = arr - mean
        skew = float((diffs ** 3).mean() / std ** 3)
        excess_kurt = float((diffs ** 4).mean() / std ** 4 - 3.0)
        sharpe = mean / std
    else:
        skew = 0.0
        excess_kurt = 0.0
        sharpe = 0.0
    if n >= 2 and std > 1e-12:
        cov = float(np.corrcoef(arr[:-1], arr[1:])[0, 1])
        if np.isnan(cov):
            cov = 0.0
    else:
        cov = 0.0
    return {
        "n": int(n),
        "mean": mean,
        "std": std,
        "skew": skew,
        "excess_kurt": excess_kurt,
        "autocorr_lag1": float(cov),
        "sharpe_per_trade": float(sharpe),
    }


# ---------------------------------------------------------------------------
# Significance test per spec (for downstream FDR)
# ---------------------------------------------------------------------------


def spec_one_sided_pvalue(signed_bps: np.ndarray | Iterable[float]) -> float:
    """One-sided t-test: H_0 mean <= 0 vs H_1 mean > 0.

    Returns p-value in [0, 1]. Conservative t-distribution (not normal) with
    df = n - 1.
    """
    arr = np.asarray(list(signed_bps), dtype=np.float64)
    n = len(arr)
    if n < 2:
        return 1.0
    mean = float(arr.mean())
    std = float(arr.std(ddof=1))
    if std < 1e-12:
        # All equal — p = 0 if mean > 0 else 1
        return 0.0 if mean > 0 else 1.0
    t_stat = mean / (std / np.sqrt(n))
    return float(1.0 - t_dist.cdf(t_stat, df=n - 1))


# ---------------------------------------------------------------------------
# Deflated Sharpe Ratio (López de Prado 2014/2018)
# ---------------------------------------------------------------------------


# Euler-Mascheroni constant (from López de Prado Eq. 14.4)
_EULER_GAMMA = 0.5772156649015329


def expected_max_sr_under_null(n_trials: int) -> float:
    """Expected value of max Sharpe across n_trials i.i.d. null-SR trials.

    This is the selection bias we subtract from observed SR before claiming edge.
    López de Prado (2018) Eq. 14.4.
    """
    if n_trials <= 1:
        return 0.0
    return ((1.0 - _EULER_GAMMA) * norm.ppf(1.0 - 1.0 / n_trials) +
            _EULER_GAMMA * norm.ppf(1.0 - 1.0 / (np.e * n_trials)))


def deflated_sharpe_ratio(
    sr_observed: float,
    n_trades: int,
    n_trials: int,
    skewness: float = 0.0,
    excess_kurtosis: float = 0.0,
    autocorrelation: float = 0.0,
) -> float:
    """Deflated Sharpe Ratio (López de Prado 2014, Eq 9-10; AFML 2018 Ch.14).

    Returns probability that true Sharpe > 0 given all three corrections:
      (1) selection bias (n_trials picked the max)
      (2) non-normality (skew, excess kurt inflate variance)
      (3) autocorrelation (reduces effective sample size)

    Interpretation:
      dsr ≥ 0.95 → strong evidence of genuine edge
      dsr ≥ 0.90 → moderate evidence
      dsr < 0.5  → observed SR below selection-bias expected max; no edge

    Args:
      sr_observed: Observed Sharpe (per-trade, NOT annualized).
      n_trades: Number of trades in backtest.
      n_trials: Number of candidate specs tried (M in López de Prado notation).
      skewness, excess_kurtosis: from per_trade_stats on the same trace.
      autocorrelation: lag-1 autocorrelation of signed returns. If > 0, n_effective drops.
    """
    if n_trades < 2 or n_trials < 1:
        return 0.0

    # Non-normality adjusted variance term (López de Prado 2014 Eq. 9)
    # denominator = 1 − γ₃·SR + ((γ₄)/4)·SR²   (note: γ₄ is excess kurtosis here)
    denom = 1.0 - skewness * sr_observed + (excess_kurtosis / 4.0) * (sr_observed ** 2)
    if denom <= 0:
        return 0.0

    # Effective sample size (autocorrelation adjustment)
    # n_eff = n · (1 − ρ) / (1 + ρ) for AR(1)-like autocorrelation
    if autocorrelation >= 1.0 or autocorrelation <= -1.0:
        n_eff = 1.0
    else:
        n_eff = n_trades * (1.0 - autocorrelation) / (1.0 + autocorrelation + 1e-12)
    if n_eff < 2:
        return 0.0

    # Adjusted SR (López de Prado 2014 Eq. 10 transformed)
    sr_adj = sr_observed * np.sqrt(n_eff - 1.0) / np.sqrt(denom)

    # Expected-max null baseline
    em_null = expected_max_sr_under_null(n_trials)

    # Final: Φ(SR_adj − E[max|null])
    return float(norm.cdf(sr_adj - em_null))


# ---------------------------------------------------------------------------
# Benjamini-Hochberg FDR procedure (1995)
# ---------------------------------------------------------------------------


def bh_fdr_threshold(
    p_values: np.ndarray | Iterable[float],
    q: float = 0.05,
) -> tuple[float, np.ndarray]:
    """Benjamini-Hochberg False Discovery Rate procedure.

    Args:
      p_values: array-like of p-values, one per test.
      q: target FDR level. Default 0.05.

    Returns:
      cutoff_p: largest p-value that still passes BH line.
      rejected_mask: boolean array, True where H_0 rejected (spec is "significant").

    If no p-value passes, cutoff_p = 0.0 and all mask entries False.
    """
    pv = np.asarray(list(p_values), dtype=np.float64)
    m = len(pv)
    if m == 0:
        return (0.0, np.zeros(0, dtype=bool))
    sorted_idx = np.argsort(pv)
    sorted_p = pv[sorted_idx]
    bh_line = np.arange(1, m + 1, dtype=np.float64) / m * q
    passed = sorted_p <= bh_line
    if not passed.any():
        return (0.0, np.zeros(m, dtype=bool))
    k = int(np.where(passed)[0].max())
    cutoff = float(sorted_p[k])
    mask = pv <= cutoff
    return (cutoff, mask)


def bonferroni_threshold(p_values: np.ndarray | Iterable[float],
                          alpha: float = 0.05) -> tuple[float, np.ndarray]:
    """Strict Bonferroni correction for comparison. alpha_per_test = alpha / m."""
    pv = np.asarray(list(p_values), dtype=np.float64)
    m = len(pv)
    if m == 0:
        return (0.0, np.zeros(0, dtype=bool))
    cutoff = alpha / m
    return (float(cutoff), pv <= cutoff)


# ---------------------------------------------------------------------------
# Probability of Backtest Overfit — CSCV (Combinatorially Symmetric CV)
# ---------------------------------------------------------------------------


def pbo_score(sharpe_matrix: np.ndarray) -> float:
    """Probability of Backtest Overfit via CSCV.

    Args:
      sharpe_matrix: shape (n_specs, n_chunks). sharpe_matrix[i, k] = Sharpe of
        spec i evaluated on chunk k (e.g., one date or one symbol×date partition).

    Procedure:
      For each chunk k:
        - Treat all other chunks as "train": train_SR_i = mean(sharpe_matrix[i, != k])
        - Pick the winner-on-train: winner = argmax(train_SR_i)
        - Check the winner's rank on the held-out chunk k.
        - If rank ≥ n_specs / 2 (below median): count as "overfit".
      PBO = fraction of chunks where above happens.

    Interpretation:
      PBO ≤ 0.05 → selection procedure trustworthy
      PBO ≈ 0.5 → pure coincidence
      PBO > 0.8 → severe overfit
    """
    arr = np.asarray(sharpe_matrix, dtype=np.float64)
    n_specs, n_chunks = arr.shape
    if n_specs < 2 or n_chunks < 2:
        return 0.5  # undefined; return neutral

    below_median = 0
    for k in range(n_chunks):
        mask = np.arange(n_chunks) != k
        train_mean = arr[:, mask].mean(axis=1)
        winner_idx = int(np.argmax(train_mean))
        # Ranks on test chunk k (descending Sharpe)
        test_col = arr[:, k]
        # rank 0 = best, n_specs-1 = worst
        ranks = np.argsort(-test_col)
        winner_rank = int(np.where(ranks == winner_idx)[0][0])
        if winner_rank >= n_specs / 2:
            below_median += 1
    return float(below_median / n_chunks)


# ---------------------------------------------------------------------------
# Convenience: promotion decision
# ---------------------------------------------------------------------------


def promotion_evidence(
    signed_bps: np.ndarray | Iterable[float],
    n_trials: int,
) -> dict:
    """Full evidence package for promotion decision.

    Returns dict with all computed statistics: stats, p_value, dsr.
    Intended for chain2-gate to make auditable MUST_INCLUDE decisions.
    """
    stats = per_trade_stats(signed_bps)
    p_value = spec_one_sided_pvalue(signed_bps)
    if stats["n"] >= 2:
        dsr = deflated_sharpe_ratio(
            sr_observed=stats["sharpe_per_trade"],
            n_trades=stats["n"],
            n_trials=n_trials,
            skewness=stats["skew"],
            excess_kurtosis=stats["excess_kurt"],
            autocorrelation=stats["autocorr_lag1"],
        )
    else:
        dsr = 0.0

    return {
        "n_trades": stats["n"],
        "mean_bps": stats["mean"],
        "std_bps": stats["std"],
        "skewness": stats["skew"],
        "excess_kurtosis": stats["excess_kurt"],
        "autocorr_lag1": stats["autocorr_lag1"],
        "sharpe_per_trade": stats["sharpe_per_trade"],
        "p_value_one_sided": p_value,
        "dsr": dsr,
        "meets_dsr_threshold_0_95": bool(dsr >= 0.95),
        "meets_dsr_threshold_0_90": bool(dsr >= 0.90),
    }


__all__ = [
    "per_trade_stats",
    "spec_one_sided_pvalue",
    "expected_max_sr_under_null",
    "deflated_sharpe_ratio",
    "bh_fdr_threshold",
    "bonferroni_threshold",
    "pbo_score",
    "promotion_evidence",
]
