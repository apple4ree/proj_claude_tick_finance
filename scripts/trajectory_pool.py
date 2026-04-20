#!/usr/bin/env python3
"""3-Axis Trajectory Pool Manager.

Manages three independent pools of trajectories:
  - Alpha (signal selection per symbol)
  - Execution (PT/SL/trailing/entry mechanics)
  - Portfolio (cross-symbol capital allocation)

Each trajectory has a score (clean_pnl-based) updated after backtest.
Pools are JSON-backed and persisted under strategies/_trajectories/.

Usage:
    from scripts.trajectory_pool import TrajectoryPool, AlphaTrajectory
    pool = TrajectoryPool()
    pool.load()
    pool.add_alpha(AlphaTrajectory(...))
    top = pool.top_n("alpha", n=3)
    combo = pool.crossover("alpha_001", "exec_002", "port_001")
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path


_DEFAULT_POOL_DIR = Path("strategies/_trajectories")


@dataclass
class AlphaTrajectory:
    traj_id: str
    symbol: str
    signal: str
    threshold: float
    horizon: int
    signal_brief_rank: int
    entry_condition: str = ""
    time_window: list[int] = field(default_factory=lambda: [36000, 46800])
    ic: float = 0.0
    q5_bps: float = 0.0
    score: float = 0.0
    n_backtests: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ExecTrajectory:
    traj_id: str
    entry_mode: str = "passive_maker"
    entry_price: str = "bid"
    ttl_ticks: int = 75
    profit_target_bps: float = 80.0
    stop_loss_bps: float = 50.0
    sl_reference: str = "bid_px"
    trailing: dict = field(default_factory=lambda: {"activation": 60, "distance": 40})
    time_stop_ticks: int = 3000
    max_entries_per_session: int = 3
    cancel_on_bid_drop_ticks: int = 2
    score: float = 0.0
    n_backtests: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PortfolioTrajectory:
    traj_id: str
    allocation_method: str = "equal_weight"
    symbols: list[str] = field(default_factory=list)
    weights: dict[str, float] = field(default_factory=dict)
    lot_sizes: dict[str, int] = field(default_factory=dict)
    max_total_exposure_pct: float = 20.0
    max_correlated_symbols: int = 3
    score: float = 0.0
    n_backtests: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


class TrajectoryPool:
    """Manages three independent trajectory pools with CRUD and scoring."""

    def __init__(self, pool_dir: Path | str = _DEFAULT_POOL_DIR) -> None:
        self.pool_dir = Path(pool_dir)
        self._alphas: dict[str, dict] = {}
        self._execs: dict[str, dict] = {}
        self._portfolios: dict[str, dict] = {}
        self._combinations: list[dict] = []

    # -- CRUD ---------------------------------------------------------------

    def add_alpha(self, traj: AlphaTrajectory) -> None:
        self._alphas[traj.traj_id] = traj.to_dict()

    def add_exec(self, traj: ExecTrajectory) -> None:
        self._execs[traj.traj_id] = traj.to_dict()

    def add_portfolio(self, traj: PortfolioTrajectory) -> None:
        self._portfolios[traj.traj_id] = traj.to_dict()

    def get_alpha(self, traj_id: str) -> dict | None:
        return self._alphas.get(traj_id)

    def get_exec(self, traj_id: str) -> dict | None:
        return self._execs.get(traj_id)

    def get_portfolio(self, traj_id: str) -> dict | None:
        return self._portfolios.get(traj_id)

    def list_alphas(self) -> list[dict]:
        return list(self._alphas.values())

    def list_execs(self) -> list[dict]:
        return list(self._execs.values())

    def list_portfolios(self) -> list[dict]:
        return list(self._portfolios.values())

    # -- Scoring ------------------------------------------------------------

    def update_score(self, axis: str, traj_id: str, score: float) -> None:
        pool = self._get_pool(axis)
        if traj_id in pool:
            pool[traj_id]["score"] = score
            pool[traj_id]["n_backtests"] = pool[traj_id].get("n_backtests", 0) + 1

    def top_n(self, axis: str, n: int = 3) -> list[dict]:
        pool = self._get_pool(axis)
        return sorted(pool.values(), key=lambda x: x.get("score", 0), reverse=True)[:n]

    # -- Crossover ----------------------------------------------------------

    def crossover(self, alpha_id: str, exec_id: str, port_id: str) -> dict:
        combo = {
            "alpha": self._alphas.get(alpha_id, {}),
            "exec": self._execs.get(exec_id, {}),
            "portfolio": self._portfolios.get(port_id, {}),
        }
        self._combinations.append({
            "alpha_id": alpha_id,
            "exec_id": exec_id,
            "port_id": port_id,
        })
        return combo

    # -- Persistence --------------------------------------------------------

    def save(self) -> None:
        self.pool_dir.mkdir(parents=True, exist_ok=True)
        (self.pool_dir / "alpha_pool.json").write_text(
            json.dumps(list(self._alphas.values()), indent=2, ensure_ascii=False))
        (self.pool_dir / "exec_pool.json").write_text(
            json.dumps(list(self._execs.values()), indent=2, ensure_ascii=False))
        (self.pool_dir / "port_pool.json").write_text(
            json.dumps(list(self._portfolios.values()), indent=2, ensure_ascii=False))
        (self.pool_dir / "combinations.json").write_text(
            json.dumps(self._combinations, indent=2, ensure_ascii=False))

    def load(self) -> None:
        for fname, store, key in [
            ("alpha_pool.json", self._alphas, "traj_id"),
            ("exec_pool.json", self._execs, "traj_id"),
            ("port_pool.json", self._portfolios, "traj_id"),
        ]:
            path = self.pool_dir / fname
            if path.exists():
                items = json.loads(path.read_text())
                for item in items:
                    store[item[key]] = item
        cpath = self.pool_dir / "combinations.json"
        if cpath.exists():
            self._combinations = json.loads(cpath.read_text())

    # -- Pruning ------------------------------------------------------------

    def prune(self, axis: str, keep_top: int = 10) -> int:
        pool = self._get_pool(axis)
        if len(pool) <= keep_top:
            return 0
        sorted_ids = sorted(pool.keys(), key=lambda k: pool[k].get("score", 0), reverse=True)
        to_remove = sorted_ids[keep_top:]
        for tid in to_remove:
            del pool[tid]
        return len(to_remove)

    # -- Helpers ------------------------------------------------------------

    def _get_pool(self, axis: str) -> dict:
        if axis == "alpha":
            return self._alphas
        elif axis in ("exec", "execution"):
            return self._execs
        elif axis in ("port", "portfolio"):
            return self._portfolios
        raise ValueError(f"Unknown axis: {axis}")

    def summary(self) -> dict:
        return {
            "alpha_count": len(self._alphas),
            "exec_count": len(self._execs),
            "portfolio_count": len(self._portfolios),
            "combinations_count": len(self._combinations),
        }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _seed_from_briefs(pool: TrajectoryPool, briefs_dir: str, fee_bps: float) -> None:
    """Seed alpha pool from signal briefs -- one alpha trajectory per viable signal."""
    briefs_path = Path(briefs_dir)
    alpha_counter = 0
    for brief_file in sorted(briefs_path.glob("*.json")):
        brief = json.loads(brief_file.read_text())
        symbol = brief["symbol"]
        for sig in brief.get("top_signals", []):
            if not sig.get("viable"):
                continue
            alpha_counter += 1
            traj = AlphaTrajectory(
                traj_id=f"alpha_{alpha_counter:03d}",
                symbol=symbol,
                signal=sig["signal"],
                threshold=sig["threshold"],
                horizon=sig["horizon"],
                signal_brief_rank=sig["rank"],
                ic=0.0,
                q5_bps=sig.get("q5_mean_bps", sig.get("ev_bps", 0)),
            )
            pool.add_alpha(traj)
    print(f"Seeded {alpha_counter} alpha trajectories from {briefs_path}")


def _seed_default_execs(pool: TrajectoryPool) -> None:
    """Seed execution pool with proven parameter sets from prior iterations."""
    templates = [
        ExecTrajectory(traj_id="exec_001", entry_mode="passive_maker",
                       profit_target_bps=80, stop_loss_bps=80, sl_reference="bid_px",
                       trailing={"activation": 60, "distance": 40}, time_stop_ticks=3000),
        ExecTrajectory(traj_id="exec_002", entry_mode="passive_maker",
                       profit_target_bps=80, stop_loss_bps=50, sl_reference="bid_px",
                       trailing={"activation": 50, "distance": 30}, time_stop_ticks=3000),
        ExecTrajectory(traj_id="exec_003", entry_mode="taker",
                       entry_price="ask", profit_target_bps=60, stop_loss_bps=30,
                       sl_reference="bid_px", trailing={"activation": 30, "distance": 15},
                       time_stop_ticks=1000, ttl_ticks=0, cancel_on_bid_drop_ticks=0),
    ]
    for t in templates:
        pool.add_exec(t)
    print(f"Seeded {len(templates)} execution trajectories")


def main():
    import argparse
    ap = argparse.ArgumentParser(description="Trajectory Pool Manager")
    sub = ap.add_subparsers(dest="cmd")

    sub.add_parser("summary", help="Show pool summary")
    p_list = sub.add_parser("list", help="List all trajectories")
    p_list.add_argument("--axis", required=True,
                        choices=["alpha", "exec", "portfolio"])

    p_seed = sub.add_parser("seed", help="Seed pools from signal briefs")
    p_seed.add_argument("--briefs-dir", default="data/signal_briefs")
    p_seed.add_argument("--fee", type=float, default=21.0)

    p_top = sub.add_parser("top", help="Show top-N trajectories")
    p_top.add_argument("--axis", required=True, choices=["alpha", "exec", "portfolio"])
    p_top.add_argument("--n", type=int, default=5)

    args = ap.parse_args()
    pool = TrajectoryPool()
    pool.load()

    if args.cmd == "summary":
        s = pool.summary()
        print(json.dumps(s, indent=2))
    elif args.cmd == "list":
        items = pool.top_n(args.axis, n=100)
        for item in items:
            print(f"  {item['traj_id']:>12s}  score={item.get('score', 0):+.4f}  "
                  f"{json.dumps({k: v for k, v in item.items() if k not in ('traj_id', 'score', 'n_backtests')}, ensure_ascii=False)[:80]}")
    elif args.cmd == "seed":
        _seed_from_briefs(pool, args.briefs_dir, args.fee)
        _seed_default_execs(pool)
        pool.save()
        s = pool.summary()
        print(f"Pool after seeding: {json.dumps(s)}")
    elif args.cmd == "top":
        items = pool.top_n(args.axis, n=args.n)
        for i, item in enumerate(items):
            print(f"  #{i+1} {item['traj_id']}  score={item.get('score', 0):+.4f}")
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
