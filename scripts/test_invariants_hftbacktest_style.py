#!/usr/bin/env python3
"""POC: apply our invariant checker to HFTBacktest-style fill records.

This script does NOT run HFTBacktest (that requires .npz data + numba strategy).
Instead, it simulates what HFTBacktest's Recorder would produce and proves:

  1. HFTBacktest fill records can be trivially converted to our GenericFill shape
  2. The engine-agnostic invariant checker produces the same violations on those
  3. Therefore the measurement layer is portable across engines

We construct synthetic fills that mirror real HFTBacktest output fields:
  - hft_fill.local_ts (ns), hft_fill.exch_ts (ns)
  - hft_fill.side (BUY_EVENT=1 / SELL_EVENT=2 in HFTBacktest consts)
  - hft_fill.exec_price
  - hft_fill.leaves_qty, hft_fill.exec_qty
  - hft_fill.order_id, hft_fill.order_type (LIMIT=0, MARKET=1)

Then we convert and verify the checker detects injected violations correctly.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.check_invariants_from_fills import GenericFill, run_checker


HFT_BUY_EVENT = 1
HFT_SELL_EVENT = 2
HFT_LIMIT = 0
HFT_MARKET = 1


_KST = timezone(timedelta(hours=9))


def kst_ts_ns(date: str, hms: str) -> int:
    """date='20260320', hms='10:30:00' -> epoch ns in KST."""
    y, m, d = int(date[:4]), int(date[4:6]), int(date[6:8])
    h, mi, s = [int(x) for x in hms.split(":")]
    dt = datetime(y, m, d, h, mi, s, tzinfo=_KST)
    return int(dt.timestamp() * 1e9)


def make_hft_fills() -> list[dict]:
    """Mock output as if produced by HFTBacktest Recorder.

    This fills array contains 4 roundtrips on symbol 005930 (deliberately chosen
    to trigger specific invariants), with timestamps and sides using
    HFTBacktest constants.
    """
    # Scenario:
    #   - spec says entry_end_time_seconds=46800 (13:00 KST), max_position=2, lot_size=1
    #   - spec says stop_loss_bps=30 (tolerance 10 -> threshold 40)
    #   - spec says profit_target_bps=80
    # We'll inject fills that:
    #   (A) Roundtrip entering at 10:00 with clean SL at -35bps  (clean, no violation)
    #   (B) Roundtrip entering at 13:15 -> entry_gate_end_bypass violation (SELL doesn't matter)
    #   (C) Roundtrip entering at 11:00 with SL at -60bps -> sl_overshoot violation
    #   (D) Roundtrip entering at 12:00 with clean PT at +80bps (no violation; all prior
    #       positions closed, so max_position is not touched — scenario exists purely to
    #       demonstrate a benign control case alongside violation-triggering cases)

    dt = "20260320"
    hft_fills: list[dict] = []

    # (A) clean roundtrip
    hft_fills.append({
        "local_ts": kst_ts_ns(dt, "10:00:00"),
        "exch_ts": kst_ts_ns(dt, "10:00:00"),
        "side": HFT_BUY_EVENT, "exec_price": 80000.0, "exec_qty": 1,
        "order_id": 1, "order_type": HFT_LIMIT, "symbol": "005930",
        "tag": "entry_obi",
    })
    hft_fills.append({
        "local_ts": kst_ts_ns(dt, "10:05:00"),
        "exch_ts": kst_ts_ns(dt, "10:05:00"),
        "side": HFT_SELL_EVENT, "exec_price": 79720.0, "exec_qty": 1,
        "order_id": 2, "order_type": HFT_MARKET, "symbol": "005930",
        "tag": "stop_loss",  # -35 bps, within tolerance
    })

    # (B) entry after gate close -> entry_gate_end_bypass on BUY
    hft_fills.append({
        "local_ts": kst_ts_ns(dt, "13:15:00"),
        "exch_ts": kst_ts_ns(dt, "13:15:00"),
        "side": HFT_BUY_EVENT, "exec_price": 81000.0, "exec_qty": 1,
        "order_id": 3, "order_type": HFT_LIMIT, "symbol": "005930",
        "tag": "entry_obi",
    })
    hft_fills.append({
        "local_ts": kst_ts_ns(dt, "13:20:00"),
        "exch_ts": kst_ts_ns(dt, "13:20:00"),
        "side": HFT_SELL_EVENT, "exec_price": 81500.0, "exec_qty": 1,
        "order_id": 4, "order_type": HFT_LIMIT, "symbol": "005930",
        "tag": "profit_target",
    })

    # (C) sl_overshoot at -60bps
    hft_fills.append({
        "local_ts": kst_ts_ns(dt, "11:00:00"),
        "exch_ts": kst_ts_ns(dt, "11:00:00"),
        "side": HFT_BUY_EVENT, "exec_price": 80000.0, "exec_qty": 1,
        "order_id": 5, "order_type": HFT_LIMIT, "symbol": "005930",
        "tag": "entry_obi",
    })
    hft_fills.append({
        "local_ts": kst_ts_ns(dt, "11:10:00"),
        "exch_ts": kst_ts_ns(dt, "11:10:00"),
        "side": HFT_SELL_EVENT, "exec_price": 79520.0, "exec_qty": 1,
        "order_id": 6, "order_type": HFT_MARKET, "symbol": "005930",
        "tag": "stop_loss",  # -60 bps, over threshold+tolerance (40) -> violation
    })

    # (D) clean roundtrip to complete the list
    hft_fills.append({
        "local_ts": kst_ts_ns(dt, "12:00:00"),
        "exch_ts": kst_ts_ns(dt, "12:00:00"),
        "side": HFT_BUY_EVENT, "exec_price": 80000.0, "exec_qty": 1,
        "order_id": 7, "order_type": HFT_LIMIT, "symbol": "005930",
        "tag": "entry_obi",
    })
    hft_fills.append({
        "local_ts": kst_ts_ns(dt, "12:05:00"),
        "exch_ts": kst_ts_ns(dt, "12:05:00"),
        "side": HFT_SELL_EVENT, "exec_price": 80640.0, "exec_qty": 1,
        "order_id": 8, "order_type": HFT_LIMIT, "symbol": "005930",
        "tag": "profit_target",  # +80 bps, exactly at PT threshold
    })

    return hft_fills


def hft_to_generic(hft_fills: list[dict], lot_size: int = 1) -> list[GenericFill]:
    """Adapter: HFTBacktest-style fill dict -> our GenericFill.

    This is the only integration code needed — everything else is reused.
    For a real HFTBacktest run, the Recorder emits similar dicts via
    state.fills or equivalent; same conversion applies.
    """
    out: list[GenericFill] = []
    position_per_symbol: dict[str, int] = {}
    for f in hft_fills:
        sym = f["symbol"]
        side_code = f["side"]
        side_str = "BUY" if side_code == HFT_BUY_EVENT else "SELL"
        qty = int(f.get("exec_qty", 1))

        if side_str == "BUY":
            position_per_symbol[sym] = position_per_symbol.get(sym, 0) + qty
        else:
            position_per_symbol[sym] = position_per_symbol.get(sym, 0) - qty

        ts_ns = int(f.get("exch_ts") if f.get("exch_ts") is not None else f["local_ts"])
        out.append(GenericFill(
            ts_ns=ts_ns,  # prefer exch_ts; fallback to local_ts if absent
            symbol=sym,
            side=side_str,
            qty=qty,
            price=float(f["exec_price"]),
            tag=str(f.get("tag", "exit_other")),
            position_after=position_per_symbol[sym],
            lot_size=lot_size,
            context={
                "order_id": int(f.get("order_id", 0)),
                "order_type_hft": int(f.get("order_type", 0)),
            },
        ))
    return out


def build_mock_spec() -> dict:
    return {
        "params": {
            "entry_start_time_seconds": 34200,  # 09:30
            "entry_end_time_seconds": 46800,    # 13:00
            "stop_loss_bps": 30.0,              # tolerance +10 -> threshold 40
            "profit_target_bps": 80.0,          # tolerance +20
            "max_position_per_symbol": 2,
            "max_entries_per_session": 4,
            "lot_size": 1,
        }
    }


def main() -> None:
    spec = build_mock_spec()
    hft_fills = make_hft_fills()
    generic = hft_to_generic(hft_fills, lot_size=1)

    print(f"Synthetic HFTBacktest-style fills: {len(hft_fills)}")
    print(f"Converted to GenericFill: {len(generic)}")
    print()

    violations = run_checker(spec, generic)
    print(f"Violations detected: {len(violations)}")
    by_type: dict[str, int] = {}
    for v in violations:
        by_type[v.invariant_type] = by_type.get(v.invariant_type, 0) + 1
    print(f"By type: {by_type}")
    print()

    expected = {
        "entry_gate_end_bypass": 1,  # roundtrip B entered at 13:15 > 13:00
        "sl_overshoot": 1,           # roundtrip C exited at -60bps > 40bps threshold
    }
    print("Expected:", expected)
    print()

    ok = by_type == expected
    if ok:
        print("PASS: engine-agnostic checker correctly detected the injected violations on "
              "HFTBacktest-style fill stream. Measurement layer is portable.")
    else:
        print("FAIL: mismatch between expected and detected violations.")
        print("  Detected detail:")
        for v in violations:
            print(f"    - {v.invariant_type}: expected={v.expected} actual={v.actual} idx={v.fill_index}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
