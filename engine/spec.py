"""Strategy spec loader.

Specs are declarative YAML files that the engine interprets. Phase 2 only
uses `name`, `universe.symbols`, `universe.dates`. Later phases will consume
`signals`, `entry`, `exit`, `risk` via the DSL evaluator.

Universe shorthands in the symbols list:
  "*"     — all symbols that have data for at least one of the specified dates
  "top10" — top-10 symbols by tick count (liquidity) on the IS universe;
             fixed list for reproducibility (measured on 20260316)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

_DATA_ROOT = Path("/home/dgu/tick/open-trading-api/data/realtime/H0STASP0")

# Top-10 KRX symbols by tick count on 20260316 (IS reference date).
# Order: descending liquidity. Fixed for reproducibility across runs.
TOP10_SYMBOLS: list[str] = [
    "005930",  # 삼성전자      71,497 ticks  184,750 KRW  반도체
    "000660",  # SK하이닉스    66,914 ticks  934,500 KRW  반도체
    "005380",  # 현대자동차    63,742 ticks  501,500 KRW  자동차
    "034020",  # 두산에너빌    59,228 ticks  106,150 KRW  중공업
    "010140",  # 삼성중공업    51,261 ticks   28,825 KRW  조선
    "006800",  # 미래에셋증권  45,600 ticks   69,850 KRW  금융
    "272210",  # HD현대        43,133 ticks  145,650 KRW  중공업
    "042700",  # 한미반도체    42,590 ticks  294,250 KRW  반도체 장비
    "015760",  # 한국전력      42,174 ticks   46,775 KRW  유틸리티
    "035420",  # NAVER         38,680 ticks  217,250 KRW  IT
]


def _expand_symbols(symbols: list[str], dates: list[str]) -> list[str]:
    """Expand wildcards in the symbols list.

    "top10" → TOP10_SYMBOLS (fixed list, reproducible)
    "*"     → all symbols present for any of the given dates
    """
    if "top10" not in symbols and "*" not in symbols:
        return symbols

    result: list[str] = []
    seen: set[str] = set()

    for s in symbols:
        if s == "top10":
            for sym in TOP10_SYMBOLS:
                if sym not in seen:
                    result.append(sym)
                    seen.add(sym)
        elif s == "*":
            for d in dates:
                day_dir = _DATA_ROOT / d
                if day_dir.exists():
                    for f in sorted(day_dir.glob("*.csv")):
                        sym = f.stem.zfill(6)
                        if sym not in seen:
                            result.append(sym)
                            seen.add(sym)
        else:
            if s not in seen:
                result.append(s)
                seen.add(s)

    return result


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
    dates = [str(d) for d in uni.get("dates", [])]
    raw_symbols = [str(s) for s in uni.get("symbols", [])]
    _WILDCARDS = {"*", "top10"}
    symbols = _expand_symbols(
        [s if s in _WILDCARDS else s.zfill(6) for s in raw_symbols],
        dates,
    )
    return StrategySpec(
        name=raw.get("name", Path(path).stem),
        description=raw.get("description", ""),
        universe=Universe(symbols=symbols, dates=dates),
        signals=raw.get("signals", {}) or {},
        entry=raw.get("entry", {}) or {},
        exit=raw.get("exit", {}) or {},
        risk=raw.get("risk", {}) or {},
        raw=raw,
    )
