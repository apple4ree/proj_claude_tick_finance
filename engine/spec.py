"""Strategy spec loader.

Specs are declarative YAML files that the engine interprets. Phase 2 only
uses `name`, `universe.symbols`, `universe.dates`. Later phases will consume
`signals`, `entry`, `exit`, `risk` via the DSL evaluator.

Universe shorthands in the symbols list:
  "*"     — all symbols that have CSV data in any of the bar-data directories
  "top3"  — crypto standard 3-symbol universe (BTCUSDT, ETHUSDT, SOLUSDT)

Note: 2026-04-19 crypto-only pivot completed. KRX legacy + Qlib equity
(CSI500/SP500) paths have been fully removed. Supported markets: crypto
bar (Binance OHLCV) and crypto LOB (Binance L2 snapshot archive —
collected forward-going via scripts/binance_lob_collector.py).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

# Bar-data roots searched for "*" expansion. Resolved at call-time.
_BAR_DATA_ROOTS = (
    Path("data/binance_daily"),
    Path("data/binance_multi/1h"),
    Path("data/binance_multi/15m"),
    Path("data/binance_multi/5m"),
)

# Standard crypto universe — Binance top-3 by liquidity for cross-symbol robustness.
TOP3_SYMBOLS: list[str] = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

# Universe presets (2026-04-19 multi-market extension).
# Concrete symbol lists for the equity presets are populated at export time
# by scripts/qlib_export.py --top-n, which picks top-N by average daily
# trading value inside the index-membership snapshot. These literal fallbacks
# only matter if a spec references the preset before qlib_export has run;
# normally the exporter writes CSVs and the universe is taken from the CSV
# directory at runtime.
UNIVERSE_PRESETS: dict[str, list[str]] = {
    "top3": TOP3_SYMBOLS,
}


def _expand_symbols(symbols: list[str], dates: list[str]) -> list[str]:
    """Expand wildcards in the symbols list.

    "top3" → TOP3_SYMBOLS (BTC/ETH/SOL)
    "*"    → union of symbols with CSVs under any bar-data root
    """
    if "top3" not in symbols and "*" not in symbols:
        return symbols

    result: list[str] = []
    seen: set[str] = set()

    for s in symbols:
        if s == "top3":
            for sym in TOP3_SYMBOLS:
                if sym not in seen:
                    result.append(sym)
                    seen.add(sym)
        elif s == "*":
            for root in _BAR_DATA_ROOTS:
                if not root.exists():
                    continue
                for f in sorted(root.glob("*.csv")):
                    sym = f.stem
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
