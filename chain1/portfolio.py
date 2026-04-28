"""Chain 1 portfolio analysis — multi-spec correlation + HRP cluster + portfolio
backtest.

Implements:
  - spec_correlation_matrix(traces): pairwise per-trade signed_bps correlation
  - hrp_cluster(corr_matrix): hierarchical clustering, return cluster labels
  - hrp_select_representatives(corr, scores, max_n): choose 1 per cluster
  - portfolio_backtest(spec_traces, weights): aggregate trades, return P&L series
  - diversification_ratio: portfolio_vol / weighted_avg_vol

Reference:
  - López de Prado (2016) "Building Diversified Portfolios that Outperform Out
    of Sample" — HRP foundational paper.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Iterable

import numpy as np
from scipy.cluster.hierarchy import linkage, fcluster
from scipy.spatial.distance import squareform


def _load_trace(path: str | Path) -> list[dict]:
    """Load per-trade signed_bps records from a trace.json file."""
    p = Path(path)
    if not p.exists():
        return []
    try:
        d = json.loads(p.read_text())
        return d.get("records", [])
    except Exception:
        return []


def _trade_keys(records: list[dict]) -> dict[tuple, float]:
    """Build (symbol, date, tick_idx) → signed_bps map for alignment."""
    return {(r["symbol"], r["date"], r["tick_idx"]): r["signed_bps"] for r in records}


def spec_correlation_matrix(
    spec_traces: dict[str, list[dict]],
) -> tuple[np.ndarray, list[str]]:
    """Pairwise correlation of per-trade signed_bps across specs.

    Args:
      spec_traces: spec_id → list of trade records (signed_bps, symbol, date,
        tick_idx fields required).

    Returns:
      corr_matrix: shape (N, N), Pearson correlation aligned by trade key.
      spec_ids: ordered list matching matrix rows/cols.

    Notes:
      - Two specs trading at exactly the same tick contribute aligned data
        points; un-overlapping ticks are excluded for that pair.
      - If two specs share fewer than 30 common trade keys, correlation = NaN
        (and downstream code should treat as 0 or skip).
    """
    spec_ids = sorted(spec_traces.keys())
    n = len(spec_ids)
    if n < 2:
        return np.eye(n), spec_ids

    keyed_traces = {sid: _trade_keys(tr) for sid, tr in spec_traces.items()}
    corr = np.eye(n)
    for i in range(n):
        for j in range(i + 1, n):
            ki = keyed_traces[spec_ids[i]]
            kj = keyed_traces[spec_ids[j]]
            common = set(ki.keys()) & set(kj.keys())
            if len(common) < 30:
                corr[i, j] = corr[j, i] = 0.0  # treat sparse-overlap as uncorrelated
                continue
            x = np.array([ki[k] for k in common])
            y = np.array([kj[k] for k in common])
            if x.std() < 1e-12 or y.std() < 1e-12:
                corr[i, j] = corr[j, i] = 0.0
                continue
            c = float(np.corrcoef(x, y)[0, 1])
            if np.isnan(c):
                c = 0.0
            corr[i, j] = corr[j, i] = c
    return corr, spec_ids


def hrp_cluster(
    corr_matrix: np.ndarray,
    distance_threshold: float = 0.5,
    linkage_method: str = "average",
) -> np.ndarray:
    """Cluster specs by 1 - |corr| distance.

    Args:
      corr_matrix: (N, N) symmetric correlation in [-1, 1]
      distance_threshold: cluster cut at this 1-|corr| distance.
        Default 0.5 → specs with avg |corr| ≥ 0.5 grouped together (with
        average linkage; single linkage has chaining problem with 70+ specs).
      linkage_method: 'single' (López de Prado original; chaining-prone),
        'average' (default; group avg), 'complete' (max-linkage; most
        conservative grouping), 'ward' (variance minimization).

    Returns: cluster_labels[i] = cluster number for spec i (1-indexed).

    Note on choice of linkage: with N >= 50 specs that are mostly
    correlated (e.g., shared primitive families), single linkage tends
    to merge all into one cluster (chaining). Average linkage preserves
    intra-cluster homogeneity better.
    """
    n = corr_matrix.shape[0]
    if n < 2:
        return np.array([1])
    # Distance matrix: convert correlation to 1 - |corr|, force diagonal 0
    dist = 1.0 - np.abs(corr_matrix)
    np.fill_diagonal(dist, 0.0)
    # Symmetrize numerical noise
    dist = (dist + dist.T) / 2
    cond = squareform(dist, checks=False)
    Z = linkage(cond, method=linkage_method)
    labels = fcluster(Z, t=distance_threshold, criterion="distance")
    return labels


def hrp_select_representatives(
    corr_matrix: np.ndarray,
    spec_ids: list[str],
    spec_scores: dict[str, float],
    distance_threshold: float = 0.5,
    max_n: int | None = None,
) -> list[str]:
    """For each cluster, pick the highest-scoring spec as representative.

    Args:
      corr_matrix: from spec_correlation_matrix
      spec_ids: matching spec_id order
      spec_scores: spec_id → composite/promotion score (higher = better)
      distance_threshold: cluster cut threshold (1 - |corr|)
      max_n: optional cap on returned representatives (top N clusters by best score)

    Returns: list of selected spec_ids, mutually distance > threshold (low corr).
    """
    labels = hrp_cluster(corr_matrix, distance_threshold)
    clusters = defaultdict(list)
    for sid, lbl in zip(spec_ids, labels):
        clusters[int(lbl)].append(sid)

    representatives: list[tuple[str, float]] = []
    for lbl, members in clusters.items():
        # Pick highest-score member
        ranked = sorted(members, key=lambda s: spec_scores.get(s, 0.0), reverse=True)
        winner = ranked[0]
        representatives.append((winner, spec_scores.get(winner, 0.0)))

    representatives.sort(key=lambda x: -x[1])
    if max_n is not None:
        representatives = representatives[:max_n]
    return [sid for sid, _ in representatives]


def portfolio_backtest(
    spec_traces: dict[str, list[dict]],
    weights: dict[str, float] | None = None,
    weight_method: str = "equal",
) -> dict:
    """Aggregate per-trade signed_bps across specs to produce portfolio P&L.

    Args:
      spec_traces: spec_id → list of trade records
      weights: optional explicit weights (sum to 1)
      weight_method: 'equal', 'inv_vol', or 'inv_corr_var' (basic HRP weights)

    Returns:
      {
        "portfolio_pnl_per_trade": np.ndarray,  # signed bps per portfolio trade event
        "portfolio_pnl_per_tick": dict,         # tick_key → weighted sum signed_bps
        "n_trade_events": int,
        "agg_mean": float,
        "agg_std": float,
        "agg_sharpe_per_trade": float,
        "diversification_ratio": float,
      }
    """
    spec_ids = sorted(spec_traces.keys())
    if len(spec_ids) == 0:
        return {"n_trade_events": 0}

    # Compute weights
    if weights is None:
        if weight_method == "equal":
            weights = {sid: 1.0 / len(spec_ids) for sid in spec_ids}
        elif weight_method == "inv_vol":
            vols = {sid: max(np.std([r["signed_bps"] for r in tr]) if len(tr) > 1 else 1.0,
                             1e-9)
                    for sid, tr in spec_traces.items()}
            inv = {sid: 1.0 / vols[sid] for sid in spec_ids}
            tot = sum(inv.values())
            weights = {sid: inv[sid] / tot for sid in spec_ids}
        else:
            raise ValueError(f"unknown weight_method: {weight_method}")

    # Aggregate by tick key
    tick_pnl: dict[tuple, float] = defaultdict(float)
    for sid, tr in spec_traces.items():
        w = weights.get(sid, 0.0)
        for r in tr:
            key = (r["symbol"], r["date"], r["tick_idx"])
            tick_pnl[key] += w * r["signed_bps"]

    pnl_arr = np.array(sorted(tick_pnl.values()))
    if len(pnl_arr) == 0:
        return {"n_trade_events": 0}

    agg_mean = float(pnl_arr.mean())
    agg_std = float(pnl_arr.std())
    sharpe = agg_mean / agg_std if agg_std > 1e-12 else 0.0

    # Diversification ratio = portfolio_std / weighted_avg(spec_std)
    weighted_avg_std = sum(weights.get(sid, 0.0) *
                            (np.std([r["signed_bps"] for r in tr]) if len(tr) > 1 else 0.0)
                            for sid, tr in spec_traces.items())
    div_ratio = agg_std / weighted_avg_std if weighted_avg_std > 1e-12 else 1.0

    return {
        "spec_ids": spec_ids,
        "weights": weights,
        "n_trade_events": int(len(tick_pnl)),
        "agg_mean_bps": agg_mean,
        "agg_std_bps": agg_std,
        "agg_sharpe_per_trade": float(sharpe),
        "diversification_ratio": float(div_ratio),
        # diversification_ratio < 1.0 means portfolio more diversified than weighted avg
        # diversification_ratio = 1.0 means specs perfectly correlated (no diversification)
    }


def report_portfolio(
    spec_traces: dict[str, list[dict]],
    spec_scores: dict[str, float],
    distance_threshold: float = 0.5,
    max_n: int | None = 5,
) -> dict:
    """Full pipeline: corr matrix → HRP cluster → select representatives →
    portfolio backtest. Returns combined report.
    """
    corr, spec_ids = spec_correlation_matrix(spec_traces)
    representatives = hrp_select_representatives(corr, spec_ids, spec_scores,
                                                  distance_threshold, max_n)
    rep_traces = {sid: spec_traces[sid] for sid in representatives}
    portfolio = portfolio_backtest(rep_traces, weight_method="equal")

    return {
        "all_spec_ids": spec_ids,
        "n_total": len(spec_ids),
        "correlation_matrix": corr.tolist(),
        "n_clusters": len(set(hrp_cluster(corr, distance_threshold).tolist())),
        "selected_representatives": representatives,
        "portfolio_metrics": portfolio,
    }
