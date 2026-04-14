"""Strategy spec loader.

Specs are declarative YAML files that the engine interprets. Phase 2 only
uses `name`, `universe.symbols`, `universe.dates`. Later phases will consume
`signals`, `entry`, `exit`, `risk` via the DSL evaluator.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class Universe:
    symbols: list[str] = field(default_factory=list)
    dates: list[str] = field(default_factory=list)


@dataclass
class StrategySpec:
    name: str
    description: str = ""
    universe: Universe = field(default_factory=Universe)
    signals: dict[str, Any] = field(default_factory=dict)
    entry: dict[str, Any] = field(default_factory=dict)
    exit: dict[str, Any] = field(default_factory=dict)
    risk: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)


def load_spec(path: Path | str) -> StrategySpec:
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    uni = raw.get("universe", {}) or {}
    return StrategySpec(
        name=raw.get("name", Path(path).stem),
        description=raw.get("description", ""),
        universe=Universe(
            symbols=[str(s).zfill(6) for s in uni.get("symbols", [])],
            dates=[str(d) for d in uni.get("dates", [])],
        ),
        signals=raw.get("signals", {}) or {},
        entry=raw.get("entry", {}) or {},
        exit=raw.get("exit", {}) or {},
        risk=raw.get("risk", {}) or {},
        raw=raw,
    )
