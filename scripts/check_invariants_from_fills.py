#!/usr/bin/env python3
"""Engine-agnostic invariant checker.

Takes a spec dict + a list of generic Fill records and produces
InvariantViolation records identical in schema to those in our custom
engine's report.json.

This separates the measurement layer from the simulator, enabling:
- Replay against existing report.json (sanity check)
- Application to third-party engines (HFTBacktest, ABIDES, JAX-LOB, ...)
  whose fill logs can be converted to our generic Fill shape

The paper claim: "invariant checker + counterfactual PnL attribution are an
engine-agnostic measurement layer" — this script is the proof.

Usage:
  # On our report.json (roundtrip-level)
  python scripts/check_invariants_from_fills.py \
      --spec strategies/<id>/spec.yaml \
      --fills-from-report strategies/<id>/report.json

  # On a generic fills JSON array
  python scripts/check_invariants_from_fills.py \
      --spec strategies/<id>/spec.yaml \
      --fills-json path/to/fills.json

  # Compare engine-agnostic output vs embedded violations in report.json
  python scripts/check_invariants_from_fills.py \
      --spec strategies/<id>/spec.yaml \
      --fills-from-report strategies/<id>/report.json \
      --compare
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml  # type: ignore

from engine.invariants import (
    InvariantRunner,
    InvariantViolation,
    infer_invariants,
)

_KST = timezone(timedelta(hours=9))


@dataclass
class GenericFill:
    """Engine-agnostic fill record.

    Any LOB backtest engine that produces fill events can be converted to this
    shape. Our invariant checker then operates purely on a list of these
    records + the spec.

    Required fields:
      ts_ns: int — exchange/fill timestamp in nanoseconds since Unix epoch
      symbol: str
      side: str — "BUY" or "SELL"
      qty: float
      price: float — fill price (positive)
      tag: str — one of
          entry_*              (any string starting with "entry" counts as entry)
          stop_loss            (checked for sl_overshoot)
          profit_target        (checked for pt_overshoot)
          time_stop            (checked for time_stop_overshoot)
          exit_*               (generic exit, no overshoot check)

    Optional fields:
      ticks_held: int — ticks since entry fill (only needed for time_stop checks)
      position_after: int — signed position qty after this fill
                            (only needed for max_position check)
      lot_size: int — per-contract lot size; default 1
      context: dict — arbitrary per-fill context (OBI, spread, etc.)
    """
    ts_ns: int
    symbol: str
    side: str
    qty: float
    price: float
    tag: str
    ticks_held: int | None = None
    position_after: int | None = None
    lot_size: int = 1
    context: dict[str, Any] = field(default_factory=dict)

    @property
    def kst_sec(self) -> int:
        dt = datetime.fromtimestamp(self.ts_ns / 1e9, tz=_KST)
        return dt.hour * 3600 + dt.minute * 60 + dt.second

    @property
    def kst_date(self) -> str:
        dt = datetime.fromtimestamp(self.ts_ns / 1e9, tz=_KST)
        return dt.strftime("%Y%m%d")


def run_checker(spec: dict, fills: list[GenericFill]) -> list[InvariantViolation]:
    """Run invariant checks against a list of generic fills.

    Returns: list of InvariantViolation (same schema as report.json embeds).
    """
    invariants = infer_invariants(spec)
    runner = InvariantRunner(invariants, strict_mode=False)

    for idx, f in enumerate(fills):
        runner.on_fill(
            fill_index=idx,
            side=f.side,
            qty=int(f.qty),
            price=float(f.price),
            tag=f.tag,
            kst_sec=f.kst_sec,
            date_str=f.kst_date,
            symbol=f.symbol,
            ticks_held=f.ticks_held,
        )
        if f.position_after is not None:
            runner.on_position_update(
                symbol=f.symbol,
                qty=int(f.position_after),
                lot_size=int(f.lot_size),
                fill_index=idx,
                date_str=f.kst_date,
            )

    return runner.get_violations()


def fills_from_report_roundtrips(report: dict, lot_size_fallback: int = 1) -> list[GenericFill]:
    """Convert report.json roundtrips (our engine) to GenericFill list.

    Each roundtrip becomes 2 half-fills: a BUY at entry_ts and a SELL at exit_ts.
    We emit ALL BUYs and ALL SELLs together then sort by timestamp so that
    overlapping positions (multi-entry strategies) receive correct
    `position_after` accounting — essential for max_position_exceeded checks.

    Ticks-held is not included because report.json roundtrips don't record it;
    if your engine stores ticks_held per fill, pass a fills array via
    fills_from_json instead.
    """
    events: list[tuple[int, str, str, int, float, str, dict]] = []
    for rt in report.get("roundtrips", []):
        sym = rt["symbol"]
        qty = int(rt.get("qty", 1))
        events.append((
            int(rt["entry_ts_ns"]), sym, "BUY", qty, float(rt["entry_price"]),
            "entry_obi", dict(rt.get("entry_context") or {}),
        ))
        events.append((
            int(rt["exit_ts_ns"]), sym, "SELL", qty, float(rt["exit_price"]),
            str(rt.get("exit_tag", "exit_other")), {},
        ))

    events.sort(key=lambda e: (e[0], 0 if e[2] == "BUY" else 1))

    fills: list[GenericFill] = []
    position_per_symbol: dict[str, int] = {}
    for ts_ns, sym, side, qty, price, tag, ctx in events:
        if side == "BUY":
            position_per_symbol[sym] = position_per_symbol.get(sym, 0) + qty
        else:
            position_per_symbol[sym] = position_per_symbol.get(sym, 0) - qty
        fills.append(GenericFill(
            ts_ns=ts_ns,
            symbol=sym,
            side=side,
            qty=qty,
            price=price,
            tag=tag,
            ticks_held=None,
            position_after=position_per_symbol[sym],
            lot_size=lot_size_fallback,
            context=ctx,
        ))
    return fills


def fills_from_json(json_path: Path) -> list[GenericFill]:
    """Load fills from a JSON array with the GenericFill schema.

    Schema: list of dicts with keys:
      ts_ns, symbol, side, qty, price, tag, (ticks_held), (position_after),
      (lot_size), (context)
    """
    records = json.loads(json_path.read_text())
    out: list[GenericFill] = []
    for r in records:
        out.append(GenericFill(
            ts_ns=int(r["ts_ns"]),
            symbol=str(r["symbol"]),
            side=str(r["side"]),
            qty=float(r["qty"]),
            price=float(r["price"]),
            tag=str(r.get("tag", "exit_other")),
            ticks_held=r.get("ticks_held"),
            position_after=r.get("position_after"),
            lot_size=int(r.get("lot_size", 1)),
            context=r.get("context", {}),
        ))
    return out


def _load_spec(path: Path) -> dict:
    return yaml.safe_load(path.read_text())


def _violations_to_jsonable(vs: list[InvariantViolation]) -> list[dict]:
    return [v.to_dict() for v in vs]


def _embedded_violations(report: dict) -> list[dict]:
    return report.get("invariant_violations") or []


def _compare(ours: list[dict], embedded: list[dict]) -> dict:
    """Compare standalone-checker violations vs embedded (simulator-injected) ones.

    Match by (invariant_type, fill_index) tuple. Note: fill_index semantics may
    differ (our engine increments per fill event; our standalone uses
    GenericFill list index), so we also aggregate by (type, approximate match).
    """
    def key(v):
        return (v["invariant_type"], int(v["fill_index"]))

    ours_keys = {key(v) for v in ours}
    embed_keys = {key(v) for v in embedded}

    by_type_ours: dict[str, int] = {}
    for v in ours:
        by_type_ours[v["invariant_type"]] = by_type_ours.get(v["invariant_type"], 0) + 1
    by_type_embed: dict[str, int] = {}
    for v in embedded:
        by_type_embed[v["invariant_type"]] = by_type_embed.get(v["invariant_type"], 0) + 1

    return {
        "standalone_total": len(ours),
        "embedded_total": len(embedded),
        "by_type_standalone": by_type_ours,
        "by_type_embedded": by_type_embed,
        "tuple_match_intersection": len(ours_keys & embed_keys),
        "only_standalone_tuples": len(ours_keys - embed_keys),
        "only_embedded_tuples": len(embed_keys - ours_keys),
        "by_type_delta": {
            t: by_type_ours.get(t, 0) - by_type_embed.get(t, 0)
            for t in set(by_type_ours) | set(by_type_embed)
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Run engine-agnostic invariant checker on a fill list.")
    ap.add_argument("--spec", required=True, help="Path to spec.yaml")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--fills-from-report", help="Path to our-engine report.json (use roundtrips)")
    src.add_argument("--fills-json", help="Path to a generic-fills JSON file")
    ap.add_argument("--compare", action="store_true",
                    help="If using --fills-from-report, compare against its embedded violations")
    ap.add_argument("--out", help="Write violations JSON to this path")
    args = ap.parse_args()

    spec = _load_spec(Path(args.spec))
    lot_size = int(((spec.get("params") or {}).get("lot_size") or 1))

    if args.fills_from_report:
        report = json.loads(Path(args.fills_from_report).read_text())
        fills = fills_from_report_roundtrips(report, lot_size_fallback=lot_size)
    else:
        fills = fills_from_json(Path(args.fills_json))

    violations = run_checker(spec, fills)
    vs_jsonable = _violations_to_jsonable(violations)

    output: dict[str, Any] = {
        "n_fills": len(fills),
        "violations": vs_jsonable,
        "violation_count": len(vs_jsonable),
        "by_type": {},
    }
    for v in vs_jsonable:
        output["by_type"][v["invariant_type"]] = output["by_type"].get(v["invariant_type"], 0) + 1

    if args.compare and args.fills_from_report:
        report = json.loads(Path(args.fills_from_report).read_text())
        output["comparison"] = _compare(vs_jsonable, _embedded_violations(report))

    text = json.dumps(output, indent=2, ensure_ascii=False)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text)
        print(f"wrote {args.out}")
    else:
        print(text)


if __name__ == "__main__":
    main()
