"""Chain 2 cost model — fees, spreads, slippage per market.

Single source of truth for per-trade fee decomposition used by
`chain2/execution_runner.py`. See CLAUDE.md §Chain 2 Backtest Engine (4)
for the authoritative fee table.
"""
from __future__ import annotations

from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Fee tables (fixed, 2026-04-21 policy)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FeeConfig:
    """Round-trip fee components for one market, in bps.

    Attributes:
        maker_fee_bps: Per-fill fee if we are the maker.
        taker_fee_bps: Per-fill fee if we cross.
        sell_tax_bps:  Tax applied only on the SELL side (e.g., KRX 20 bps on long exit).
    """
    market: str
    maker_fee_bps: float
    taker_fee_bps: float
    sell_tax_bps: float


# Canonical fee table (per CLAUDE.md §Chain 2 (4))
FEE_TABLE: dict[str, FeeConfig] = {
    "krx_cash": FeeConfig(
        market="krx_cash",
        maker_fee_bps=1.5,
        taker_fee_bps=1.5,
        sell_tax_bps=20.0,   # applied only on the exit side of long positions
    ),
}


def get_fee_config(market: str) -> FeeConfig:
    if market not in FEE_TABLE:
        raise ValueError(f"Unknown fee market: {market}. Available: {list(FEE_TABLE)}")
    return FEE_TABLE[market]


# ---------------------------------------------------------------------------
# Per-round-trip cost calculation
# ---------------------------------------------------------------------------


def compute_roundtrip_costs(
    *,
    fee: FeeConfig,
    entry_is_maker: bool,
    exit_is_maker: bool,
    entry_spread_bps: float,
    exit_spread_bps: float,
    position_is_long: bool,
    slippage_bps: float = 0.0,
) -> dict[str, float]:
    """Decompose round-trip execution cost into 5 labelled components (bps).

    - `entry_spread_bps` / `exit_spread_bps`: half-spread crossed at entry/exit
      respectively. Caller passes `spread/2` when cross is needed, 0 when posted.
    - `position_is_long`: determines whether sell_tax applies (KRX cash-equity:
      long exit pays sell_tax; short entry would pay it, but Phase 2.0 is long-only).

    All components are non-negative (they are COSTS — subtract from gross PnL).
    `adverse_selection_cost_bps` is computed separately (signed) by the runner.
    """
    maker_fee = 0.0
    taker_fee = 0.0
    if entry_is_maker:
        maker_fee += fee.maker_fee_bps
    else:
        taker_fee += fee.taker_fee_bps
    if exit_is_maker:
        maker_fee += fee.maker_fee_bps
    else:
        taker_fee += fee.taker_fee_bps

    sell_tax = fee.sell_tax_bps if position_is_long else 0.0

    return {
        "spread_cost_bps": float(entry_spread_bps + exit_spread_bps),
        "maker_fee_cost_bps": float(maker_fee),
        "taker_fee_cost_bps": float(taker_fee),
        "sell_tax_cost_bps": float(sell_tax),
        "slippage_cost_bps": float(slippage_bps),
    }


def sum_costs(cb: dict[str, float]) -> float:
    """Total deductible cost (bps) for a round-trip. adverse_selection not included —
    that is a *signed* quantity tracked separately and already embedded in realized PnL.
    """
    return (
        cb["spread_cost_bps"]
        + cb["maker_fee_cost_bps"]
        + cb["taker_fee_cost_bps"]
        + cb["sell_tax_cost_bps"]
        + cb.get("slippage_cost_bps", 0.0)
    )
