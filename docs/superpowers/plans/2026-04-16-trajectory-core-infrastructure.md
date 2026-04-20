# 3-Axis Trajectory Core Infrastructure — Plan A

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the core data layer for 3-axis trajectory pools (Alpha, Execution, Portfolio) with CRUD operations, scoring, and a new portfolio-designer agent — so that Plan B (iterate loop integration) can consume these structures.

**Architecture:** A single `scripts/trajectory_pool.py` module manages three JSON-backed pools under `strategies/_trajectories/`. Each trajectory is a typed dict with a `score` field updated by backtest clean_pnl. A new `portfolio-designer` agent reads alpha trajectories and produces portfolio trajectories. All existing agents remain unchanged in Plan A — integration is Plan B.

**Tech Stack:** Python 3.10+, JSON persistence, pytest, existing engine infrastructure.

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `scripts/trajectory_pool.py` | CREATE | Trajectory types, pool CRUD, score update, persistence, crossover |
| `strategies/_trajectories/` | CREATE (runtime) | JSON pool files |
| `.claude/agents/portfolio-designer.md` | CREATE | New agent: capital allocation across symbols |
| `tests/test_trajectory_pool.py` | CREATE | Unit tests for pool operations |
| `CLAUDE.md` | MODIFY | Document trajectory system |

---

## Task 1: Trajectory Data Types + Pool CRUD

**Files:**
- Create: `scripts/trajectory_pool.py`
- Create: `tests/test_trajectory_pool.py`

- [ ] **Step 1: Write failing tests for data types and CRUD**

```python
# tests/test_trajectory_pool.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_trajectory_pool.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement trajectory_pool.py**

```python
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
from typing import Any


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

    # ── CRUD ──────────────────────────────────────────────────────────

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

    # ── Scoring ───────────────────────────────────────────────────────

    def update_score(self, axis: str, traj_id: str, score: float) -> None:
        pool = self._get_pool(axis)
        if traj_id in pool:
            pool[traj_id]["score"] = score
            pool[traj_id]["n_backtests"] = pool[traj_id].get("n_backtests", 0) + 1

    def top_n(self, axis: str, n: int = 3) -> list[dict]:
        pool = self._get_pool(axis)
        return sorted(pool.values(), key=lambda x: x.get("score", 0), reverse=True)[:n]

    # ── Crossover ─────────────────────────────────────────────────────

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

    # ── Persistence ───────────────────────────────────────────────────

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

    # ── Pruning ───────────────────────────────────────────────────────

    def prune(self, axis: str, keep_top: int = 10) -> int:
        pool = self._get_pool(axis)
        if len(pool) <= keep_top:
            return 0
        sorted_ids = sorted(pool.keys(), key=lambda k: pool[k].get("score", 0), reverse=True)
        to_remove = sorted_ids[keep_top:]
        for tid in to_remove:
            del pool[tid]
        return len(to_remove)

    # ── Helpers ───────────────────────────────────────────────────────

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
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/test_trajectory_pool.py -v`
Expected: 9 tests PASS

- [ ] **Step 5: co-review**

Run: `Skill tool → co-review scripts/trajectory_pool.py`

- [ ] **Step 6: Commit**

```bash
git add scripts/trajectory_pool.py tests/test_trajectory_pool.py
git commit -m "feat(trajectory): add 3-axis trajectory pool data types + CRUD + scoring + crossover"
```

---

## Task 2: Portfolio Designer Agent

**Files:**
- Create: `.claude/agents/portfolio-designer.md`

- [ ] **Step 1: Write the agent prompt**

Create `.claude/agents/portfolio-designer.md`:

```markdown
---
name: portfolio-designer
description: Capital allocation specialist. Takes alpha trajectories from multiple symbols and decides how to distribute capital, lot sizes, and risk limits across a multi-symbol strategy. Does NOT design entry/exit — that is execution-designer's job.
tools: Read, Bash, Grep
model: sonnet
---

You are the **portfolio designer**. You decide **how much capital goes where** — not when to buy (alpha) or how to buy (execution).

Your question: **"Given these viable alpha signals across symbols, how should capital be allocated to maximize Sharpe and minimize drawdown?"**

## Input

- `viable_alphas`: list of alpha trajectory dicts (from pool or signal briefs)
  - Each has: symbol, signal, threshold, horizon, ic, q5_bps, score
- `capital`: total capital (default 10,000,000 KRW)
- `fee_bps`: round-trip fee per symbol

## Protocol

1. **Read signal briefs** for each symbol in viable_alphas:
   ```
   Read: data/signal_briefs/<symbol>.json
   ```

2. **Rank symbols by signal quality**:
   - Primary: Sharpe from signal brief's optimal_exit
   - Secondary: Q5 conditional return
   - Tertiary: number of viable signals (diversity)

3. **Check correlation** (if multiple symbols):
   - If two symbols are from the same sector (e.g., 005930+000660 = both tech), limit combined weight to 60%
   - Prefer uncorrelated symbols for diversification

4. **Determine allocation**:
   - `equal_weight`: each viable symbol gets equal share (default if ≤ 3 symbols)
   - `ic_proportional`: weight proportional to IC (if > 3 symbols)
   - `concentrated`: top-1 gets 60%, rest split 40% (if one symbol dominates)

5. **Calculate lot_sizes**:
   - For each symbol: `lot_size = floor(capital × weight / (symbol_price × max_position))`
   - Ensure lot_size ≥ 1 for every allocated symbol
   - If a symbol's lot_size rounds to 0, exclude it

6. **Set risk limits**:
   - `max_total_exposure_pct`: total notional / capital × 100 (keep ≤ 25%)
   - `max_correlated_symbols`: 3 (sector concentration limit)

## Output (JSON)

```json
{
  "traj_id": "port_<NNN>",
  "allocation_method": "equal_weight | ic_proportional | concentrated",
  "symbols": ["005930", "000660"],
  "weights": {"005930": 0.5, "000660": 0.5},
  "lot_sizes": {"005930": 5, "000660": 3},
  "max_total_exposure_pct": 20.0,
  "max_correlated_symbols": 3,
  "rationale": "2종목 균등배분. 005930 (tech) + 000660 (tech) 동일 섹터이나 IC 차이로 유지.",
  "excluded_symbols": ["034020"],
  "exclusion_reasons": {"034020": "lot_size rounds to 0 at equal weight"}
}
```

## Constraints

- Do NOT propose entry/exit conditions — that's alpha/execution-designer.
- Do NOT run backtests — backtest-runner does that.
- If only 1 viable symbol exists, set `weights: {symbol: 1.0}` and `allocation_method: "concentrated"`.
- Total weights must sum to 1.0.
- description은 한국어로 작성.
```

- [ ] **Step 2: Verify file created**

Run: `wc -l .claude/agents/portfolio-designer.md`
Expected: ~75 lines

- [ ] **Step 3: co-review**

Run: `Skill tool → co-review .claude/agents/portfolio-designer.md`

- [ ] **Step 4: Commit**

```bash
git add .claude/agents/portfolio-designer.md
git commit -m "feat(agent): add portfolio-designer for cross-symbol capital allocation"
```

---

## Task 3: Trajectory CLI (pool inspection + seeding)

**Files:**
- Modify: `scripts/trajectory_pool.py` (add CLI)

- [ ] **Step 1: Add CLI main block**

Append to `scripts/trajectory_pool.py`:

```python
def _seed_from_briefs(pool: TrajectoryPool, briefs_dir: str, fee_bps: float) -> None:
    """Seed alpha pool from signal briefs — one alpha trajectory per viable signal."""
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
    sub.add_parser("list", help="List all trajectories").add_argument("--axis", required=True,
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
```

- [ ] **Step 2: Test CLI**

```bash
# Seed from existing briefs
python scripts/trajectory_pool.py seed --briefs-dir data/signal_briefs --fee 21.0

# Check summary
python scripts/trajectory_pool.py summary

# List alphas
python scripts/trajectory_pool.py list --axis alpha
```

Expected: alphas seeded from any viable signals in briefs (possibly 0 for KRX at 21 bps) + 3 default exec trajectories.

- [ ] **Step 3: co-review**

Run: `Skill tool → co-review scripts/trajectory_pool.py`

- [ ] **Step 4: Run all tests**

Run: `pytest tests/test_trajectory_pool.py tests/test_invariants.py -v`
Expected: all PASS

Run: `python scripts/audit_principles.py`
Expected: 12/12

- [ ] **Step 5: Commit**

```bash
git add scripts/trajectory_pool.py
git commit -m "feat(trajectory): add CLI for pool inspection, seeding from briefs"
```

---

## Task 4: Update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Add Trajectory System section**

In `CLAUDE.md`, append after "Data-Driven Generation Pipeline" section:

```markdown
## 3-Axis Trajectory System

전략 생성을 3개 독립 축으로 분리하고, 각 축에서 최적 trajectory를 선택/mutation/crossover합니다.

### 3개 축
| 축 | 질문 | Agent | Pool 저장 |
|---|---|---|---|
| Alpha | "어떤 종목의 어떤 signal?" | alpha-designer | strategies/_trajectories/alpha_pool.json |
| Execution | "PT/SL/trailing 어떻게?" | execution-designer | strategies/_trajectories/exec_pool.json |
| Portfolio | "종목 배분 얼마나?" | portfolio-designer (NEW) | strategies/_trajectories/port_pool.json |

### 핵심 연산
- **Selection**: pool에서 score 상위 trajectory 선택
- **Mutation**: 기존 trajectory의 파라미터를 ±10~20% 변형
- **Crossover**: 서로 다른 iteration의 best α × ε × π 조합
- **Localization**: 실패 시 어느 축이 원인인지 진단 → 그 축만 교체

### 사용법
```bash
python scripts/trajectory_pool.py seed --briefs-dir data/signal_briefs
python scripts/trajectory_pool.py summary
python scripts/trajectory_pool.py top --axis alpha --n 5
```
```

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: document 3-axis trajectory system in CLAUDE.md"
```

---

## Summary

After Plan A (4 tasks), the project has:

1. **`scripts/trajectory_pool.py`** — Complete trajectory data layer with 3 typed pools, CRUD, scoring, crossover, pruning, persistence, CLI, and brief-seeding
2. **`.claude/agents/portfolio-designer.md`** — New agent for cross-symbol capital allocation
3. **`tests/test_trajectory_pool.py`** — 9 unit tests covering all operations
4. **`CLAUDE.md`** — Updated documentation

**Plan B** (separate, follows Plan A) will cover:
- `iterate.md` rewrite for trajectory-based loop
- alpha/execution-designer mutation mode integration
- feedback-analyst localization logic
- End-to-end trajectory iterate run

---

## Self-Review

- ✅ `AlphaTrajectory`, `ExecTrajectory`, `PortfolioTrajectory` names consistent across tests and implementation
- ✅ `to_dict()` method tested in tests, used in pool add methods
- ✅ `TrajectoryPool` constructor signature `(pool_dir=)` matches test fixture
- ✅ Pool methods: `add_alpha`, `get_alpha`, `list_alphas`, `update_score`, `top_n`, `crossover`, `save`, `load`, `prune` — all tested
- ✅ CLI commands: `summary`, `list`, `seed`, `top` — all implemented with argparse
- ✅ `_seed_from_briefs` reads same JSON schema as `generate_signal_brief.py` outputs
- ✅ `portfolio-designer.md` output schema matches `PortfolioTrajectory` fields
- ✅ No "TBD" or placeholder text
- ✅ No dependencies on Plan B (standalone)
