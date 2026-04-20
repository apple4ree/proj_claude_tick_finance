"""Unit tests for 3-axis trajectory pool."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from scripts.trajectory_pool import (
    AlphaTrajectory,
    ExecTrajectory,
    PortfolioTrajectory,
    TrajectoryPool,
)

POOL_DIR = Path("strategies/_trajectories_test")


@pytest.fixture(autouse=True)
def clean_pool():
    if POOL_DIR.exists():
        shutil.rmtree(POOL_DIR)
    POOL_DIR.mkdir(parents=True, exist_ok=True)
    yield
    if POOL_DIR.exists():
        shutil.rmtree(POOL_DIR)


# --- Data type tests ---

def test_alpha_trajectory_to_dict():
    a = AlphaTrajectory(
        traj_id="alpha_001",
        symbol="005930",
        signal="obi_1",
        threshold=0.3,
        horizon=1000,
        signal_brief_rank=1,
        entry_condition="obi(5) > 0.3 AND spread < 8",
        time_window=[36000, 46800],
    )
    d = a.to_dict()
    assert d["traj_id"] == "alpha_001"
    assert d["symbol"] == "005930"
    assert d["score"] == 0.0


def test_exec_trajectory_to_dict():
    e = ExecTrajectory(
        traj_id="exec_001",
        entry_mode="passive_maker",
        profit_target_bps=80,
        stop_loss_bps=50,
        sl_reference="bid_px",
        trailing={"activation": 60, "distance": 40},
        time_stop_ticks=3000,
    )
    d = e.to_dict()
    assert d["profit_target_bps"] == 80
    assert d["sl_reference"] == "bid_px"


def test_portfolio_trajectory_to_dict():
    p = PortfolioTrajectory(
        traj_id="port_001",
        allocation_method="equal_weight",
        symbols=["005930", "000660"],
        weights={"005930": 0.5, "000660": 0.5},
        lot_sizes={"005930": 5, "000660": 3},
    )
    d = p.to_dict()
    assert d["symbols"] == ["005930", "000660"]
    assert d["weights"]["005930"] == 0.5


# --- Pool CRUD tests ---

def test_pool_add_and_get():
    pool = TrajectoryPool(pool_dir=POOL_DIR)
    a = AlphaTrajectory(traj_id="alpha_001", symbol="005930", signal="obi_1",
                        threshold=0.3, horizon=1000, signal_brief_rank=1)
    pool.add_alpha(a)
    retrieved = pool.get_alpha("alpha_001")
    assert retrieved is not None
    assert retrieved["symbol"] == "005930"


def test_pool_list_alphas():
    pool = TrajectoryPool(pool_dir=POOL_DIR)
    for i in range(3):
        pool.add_alpha(AlphaTrajectory(
            traj_id=f"alpha_{i:03d}", symbol="005930", signal="obi_1",
            threshold=0.3 + i * 0.1, horizon=1000, signal_brief_rank=i + 1,
        ))
    alphas = pool.list_alphas()
    assert len(alphas) == 3


def test_pool_update_score():
    pool = TrajectoryPool(pool_dir=POOL_DIR)
    pool.add_alpha(AlphaTrajectory(
        traj_id="alpha_001", symbol="005930", signal="obi_1",
        threshold=0.3, horizon=1000, signal_brief_rank=1,
    ))
    pool.update_score("alpha", "alpha_001", score=0.45)
    a = pool.get_alpha("alpha_001")
    assert a["score"] == 0.45


def test_pool_persistence():
    pool1 = TrajectoryPool(pool_dir=POOL_DIR)
    pool1.add_alpha(AlphaTrajectory(
        traj_id="alpha_001", symbol="005930", signal="obi_1",
        threshold=0.3, horizon=1000, signal_brief_rank=1,
    ))
    pool1.save()

    pool2 = TrajectoryPool(pool_dir=POOL_DIR)
    pool2.load()
    assert pool2.get_alpha("alpha_001") is not None


def test_pool_top_n():
    pool = TrajectoryPool(pool_dir=POOL_DIR)
    for i in range(5):
        a = AlphaTrajectory(
            traj_id=f"alpha_{i:03d}", symbol="005930", signal="obi_1",
            threshold=0.3, horizon=1000, signal_brief_rank=i + 1,
        )
        pool.add_alpha(a)
        pool.update_score("alpha", f"alpha_{i:03d}", score=float(i) * 0.1)

    top3 = pool.top_n("alpha", n=3)
    assert len(top3) == 3
    assert top3[0]["score"] >= top3[1]["score"]  # sorted descending


def test_pool_crossover():
    pool = TrajectoryPool(pool_dir=POOL_DIR)
    # Add alpha and exec trajectories
    pool.add_alpha(AlphaTrajectory(
        traj_id="alpha_001", symbol="005930", signal="obi_1",
        threshold=0.3, horizon=1000, signal_brief_rank=1,
    ))
    pool.add_exec(ExecTrajectory(
        traj_id="exec_001", entry_mode="passive_maker",
        profit_target_bps=80, stop_loss_bps=50, sl_reference="bid_px",
        trailing={"activation": 60, "distance": 40}, time_stop_ticks=3000,
    ))
    pool.add_portfolio(PortfolioTrajectory(
        traj_id="port_001", allocation_method="equal_weight",
        symbols=["005930"], weights={"005930": 1.0}, lot_sizes={"005930": 5},
    ))

    combo = pool.crossover("alpha_001", "exec_001", "port_001")
    assert combo["alpha"]["traj_id"] == "alpha_001"
    assert combo["exec"]["traj_id"] == "exec_001"
    assert combo["portfolio"]["traj_id"] == "port_001"
