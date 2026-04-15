"""Roundtrip trace analyzer.

Reads trace_per_symbol.json (or trace.json) for a strategy, FIFO-matches
BUY/SELL fills into roundtrips, and enriches each roundtrip with the full
10-level LOB snapshot from the original CSV at both entry and exit timestamps.

Outputs:
  strategies/<id>/analysis_trace.json   — full data with raw LOB arrays (for programmatic use)
  strategies/<id>/analysis_trace.md     — human+LLM-readable summary (for feedback-analyst)
  stdout (--pretty)                     — human-readable roundtrip table

Usage:
  python scripts/analyze_trace.py --strategy <strategy_id>
  python scripts/analyze_trace.py --strategy <strategy_id> --pretty
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
STRATEGIES_DIR = ROOT / "strategies"
DATA_ROOT = ROOT.parent / "open-trading-api" / "data" / "realtime" / "H0STASP0"

KST = timezone(timedelta(hours=9))

ASK_PX_COLS  = [f"ASKP{i}"      for i in range(1, 11)]
BID_PX_COLS  = [f"BIDP{i}"      for i in range(1, 11)]
ASK_QTY_COLS = [f"ASKP_RSQN{i}" for i in range(1, 11)]
BID_QTY_COLS = [f"BIDP_RSQN{i}" for i in range(1, 11)]

_STR_COLS = ("MKSC_SHRN_ISCD", "HOUR_CLS_CODE", "tr_id")


# ---------------------------------------------------------------------------
# CSV loading & caching
# ---------------------------------------------------------------------------

def _load_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype={c: "string" for c in _STR_COLS}, low_memory=False)
    df["ts_ns"] = pd.to_datetime(df["recv_ts_kst"], utc=False).astype("int64")
    df["HOUR_CLS_CODE"] = df["HOUR_CLS_CODE"].fillna("0").astype("string")
    return df


def _get_df(symbol: str, date_str: str, cache: dict) -> pd.DataFrame | None:
    key = (symbol, date_str)
    if key not in cache:
        path = DATA_ROOT / date_str / f"{symbol}.csv"
        if not path.exists():
            cache[key] = None
            return None
        df = _load_csv(path)
        df = df[df["HOUR_CLS_CODE"] == "0"].reset_index(drop=True)
        cache[key] = df
    return cache[key]


# ---------------------------------------------------------------------------
# LOB snapshot extraction
# ---------------------------------------------------------------------------

def _extract_lob(row: pd.Series) -> dict:
    bid = [[int(row[f"BIDP{i}"]), int(row[f"BIDP_RSQN{i}"])] for i in range(1, 11)]
    ask = [[int(row[f"ASKP{i}"]), int(row[f"ASKP_RSQN{i}"])] for i in range(1, 11)]

    bid1 = bid[0][0]
    ask1 = ask[0][0]
    total_bid = int(row["TOTAL_BIDP_RSQN"])
    total_ask = int(row["TOTAL_ASKP_RSQN"])
    total     = total_bid + total_ask

    return {
        "bid": bid,
        "ask": ask,
        "spread_bps": round((ask1 - bid1) / bid1 * 1e4, 2) if bid1 > 0 else 0.0,
        "obi":        round((total_bid - total_ask) / total, 4) if total > 0 else 0.0,
        "total_bid_qty": total_bid,
        "total_ask_qty": total_ask,
        "acml_vol":   int(row["ACML_VOL"]),
    }


def _lookup_lob(symbol: str, ts_ns: int, cache: dict) -> dict:
    """Return LOB snapshot at the last tick at or before ts_ns."""
    dt       = datetime.fromtimestamp(ts_ns / 1e9, tz=KST)
    date_str = dt.strftime("%Y%m%d")
    df       = _get_df(symbol, date_str, cache)
    if df is None or df.empty:
        return {}

    # Binary search: last row with ts_ns <= fill_ts_ns
    idx = int(np.searchsorted(df["ts_ns"].to_numpy(), ts_ns, side="right")) - 1
    if idx < 0:
        return {}
    return _extract_lob(df.iloc[idx])


# ---------------------------------------------------------------------------
# FIFO roundtrip matching
# ---------------------------------------------------------------------------

def _fmt_hold(sec: float) -> str:
    sec = int(sec)
    if sec < 60:
        return f"{sec}s"
    if sec < 3600:
        return f"{sec // 60}m {sec % 60}s"
    h, rem = divmod(sec, 3600)
    return f"{h}h {rem // 60}m"


def _match_roundtrips(fills: list[dict], df_cache: dict) -> list[dict]:
    """FIFO-match BUY/SELL fills per symbol; enrich with LOB snapshots."""
    inventory: dict[str, deque] = {}
    roundtrips: list[dict] = []

    for f in fills:
        sym  = f["symbol"]
        side = f["side"]

        if side == "BUY":
            inventory.setdefault(sym, deque()).append(f)
            continue

        # SELL — unwind FIFO
        inv = inventory.get(sym, deque())
        if not inv:
            continue
        buy = inv.popleft()

        buy_ts  = buy["ts_ns"]
        sell_ts = f["ts_ns"]
        qty     = buy["qty"]   # lot_size=1 assumption; handles partial fills gracefully

        buy_px   = float(buy["avg_price"])
        sell_px  = float(f["avg_price"])
        buy_fee  = float(buy["fee"])
        sell_fee = float(f["fee"])
        total_fee = buy_fee + sell_fee

        gross_pnl = (sell_px - buy_px) * qty
        net_pnl   = gross_pnl - total_fee
        net_bps   = round(net_pnl / (buy_px * qty) * 1e4, 2) if buy_px > 0 else 0.0

        hold_sec = (sell_ts - buy_ts) / 1e9

        buy_dt  = datetime.fromtimestamp(buy_ts  / 1e9, tz=KST)
        sell_dt = datetime.fromtimestamp(sell_ts / 1e9, tz=KST)

        roundtrips.append({
            "symbol":    sym,
            "buy_time":  buy_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "buy_px":    int(buy_px),
            "sell_time": sell_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "sell_px":   int(sell_px),
            "hold":      _fmt_hold(hold_sec),
            "hold_sec":  round(hold_sec),
            "exit_tag":  f["tag"],
            "qty":       qty,
            "buy_fee":   round(buy_fee,   2),
            "sell_fee":  round(sell_fee,  2),
            "fee":       round(total_fee, 2),
            "gross_pnl": round(gross_pnl, 2),
            "net_pnl":   round(net_pnl,   2),
            "net_bps":   net_bps,
            "result":    "WIN" if net_pnl > 0 else "LOSS",
            "buy_lob":   _lookup_lob(sym, buy_ts,  df_cache),
            "sell_lob":  _lookup_lob(sym, sell_ts, df_cache),
        })

    return roundtrips


# ---------------------------------------------------------------------------
# Summary stats
# ---------------------------------------------------------------------------

def _compute_summary(roundtrips: list[dict]) -> dict:
    if not roundtrips:
        return {"total_roundtrips": 0}

    wins   = [r for r in roundtrips if r["result"] == "WIN"]
    losses = [r for r in roundtrips if r["result"] == "LOSS"]

    # Exit tag breakdown
    tag_groups: dict[str, list] = defaultdict(list)
    for r in roundtrips:
        tag_groups[r["exit_tag"]].append(r)
    tag_breakdown = {
        tag: {
            "total":  len(rs),
            "wins":   sum(1 for r in rs if r["result"] == "WIN"),
            "losses": sum(1 for r in rs if r["result"] == "LOSS"),
            "avg_net_bps": round(sum(r["net_bps"] for r in rs) / len(rs), 2),
        }
        for tag, rs in sorted(tag_groups.items())
    }

    # Entry hour distribution (KST HH)
    hour_groups: dict[str, list] = defaultdict(list)
    for r in roundtrips:
        hour_groups[r["buy_time"][11:13]].append(r)
    hour_dist = {
        h: {
            "total":  len(rs),
            "wins":   sum(1 for r in rs if r["result"] == "WIN"),
            "losses": sum(1 for r in rs if r["result"] == "LOSS"),
        }
        for h, rs in sorted(hour_groups.items())
    }

    def _avg(seq):
        return round(sum(seq) / len(seq), 2) if seq else None

    return {
        "total_roundtrips":      len(roundtrips),
        "wins":                  len(wins),
        "losses":                len(losses),
        "win_rate_pct":          round(len(wins) / len(roundtrips) * 100, 2),
        "avg_net_pnl":           _avg([r["net_pnl"] for r in roundtrips]),
        "avg_net_bps":           _avg([r["net_bps"] for r in roundtrips]),
        "avg_net_bps_wins":      _avg([r["net_bps"] for r in wins]),
        "avg_net_bps_losses":    _avg([r["net_bps"] for r in losses]),
        "avg_hold_sec_wins":     _avg([r["hold_sec"] for r in wins]),
        "avg_hold_sec_losses":   _avg([r["hold_sec"] for r in losses]),
        "exit_tag_breakdown":    tag_breakdown,
        "entry_hour_distribution": hour_dist,
    }


# ---------------------------------------------------------------------------
# Pretty printer
# ---------------------------------------------------------------------------

def _print_pretty(roundtrips: list[dict], summary: dict) -> None:
    # Roundtrip table (without full LOB — too wide; show key derived fields)
    cols = [
        ("symbol",       8,  "symbol"),
        ("buy_time",    19,  "buy_time"),
        ("buy_px",       9,  "buy_px"),
        ("sell_time",   19,  "sell_time"),
        ("sell_px",      9,  "sell_px"),
        ("hold",        10,  "hold"),
        ("exit_tag",    12,  "exit_tag"),
        ("fee",          8,  "fee"),
        ("net_pnl",     10,  "net_pnl"),
        ("net_bps",      9,  "net_bps"),
        ("result",       6,  "result"),
        # BUY LOB summary
        ("buy_spr",      8,  None),
        ("buy_obi",      8,  None),
        ("buy_bidQ",     9,  None),
        ("buy_askQ",     9,  None),
        # SELL LOB summary
        ("sel_spr",      8,  None),
        ("sel_obi",      8,  None),
        ("sel_bidQ",     9,  None),
        ("sel_askQ",     9,  None),
    ]

    header = "  ".join(f"{name:<{w}}" for name, w, _ in cols)
    sep    = "  ".join("-" * w for _, w, _ in cols)
    print(header)
    print(sep)

    for r in roundtrips:
        bl = r.get("buy_lob",  {})
        sl = r.get("sell_lob", {})
        result_str = ("WIN ✓" if r["result"] == "WIN" else "LOSS ✗")
        row_vals = [
            str(r["symbol"]),
            str(r["buy_time"]),
            f'{r["buy_px"]:,}',
            str(r["sell_time"]),
            f'{r["sell_px"]:,}',
            str(r["hold"]),
            str(r["exit_tag"]),
            f'{r["fee"]:,.0f}',
            f'{r["net_pnl"]:+,.0f}',
            f'{r["net_bps"]:+.1f}',
            result_str,
            f'{bl.get("spread_bps", 0):.1f}',
            f'{bl.get("obi", 0):+.3f}',
            f'{bl.get("total_bid_qty", 0):,}',
            f'{bl.get("total_ask_qty", 0):,}',
            f'{sl.get("spread_bps", 0):.1f}',
            f'{sl.get("obi", 0):+.3f}',
            f'{sl.get("total_bid_qty", 0):,}',
            f'{sl.get("total_ask_qty", 0):,}',
        ]
        line = "  ".join(f"{v:<{w}}" for v, (_, w, _) in zip(row_vals, cols))
        print(line)

    print()
    print("=== Summary ===")
    print(f"Total roundtrips : {summary['total_roundtrips']}")
    print(f"WIN / LOSS       : {summary['wins']} / {summary['losses']}  "
          f"({summary['win_rate_pct']:.1f}% win rate)")
    print(f"Avg net bps      : {summary.get('avg_net_bps', 0):+.1f} bps  "
          f"(wins: {summary.get('avg_net_bps_wins') or 0:+.1f}  "
          f"losses: {summary.get('avg_net_bps_losses') or 0:+.1f})")
    avg_hold_w = summary.get("avg_hold_sec_wins")
    avg_hold_l = summary.get("avg_hold_sec_losses")
    print(f"Avg hold         : "
          f"WIN {_fmt_hold(avg_hold_w) if avg_hold_w else '-'}  "
          f"LOSS {_fmt_hold(avg_hold_l) if avg_hold_l else '-'}")

    print()
    print("Exit tag breakdown:")
    for tag, info in summary.get("exit_tag_breakdown", {}).items():
        bar = "█" * info["wins"] + "░" * info["losses"]
        print(f"  {tag:<14} total={info['total']}  "
              f"WIN={info['wins']} LOSS={info['losses']}  "
              f"avg_bps={info['avg_net_bps']:+.1f}  {bar}")

    print()
    print("Entry hour distribution (KST):")
    for hour, info in summary.get("entry_hour_distribution", {}).items():
        bar = "■" * info["wins"] + "□" * info["losses"]
        print(f"  {hour}시  {bar}  ({info['wins']}W / {info['losses']}L)")


# ---------------------------------------------------------------------------
# Markdown report writer
# ---------------------------------------------------------------------------

def _write_md(strategy_id: str, roundtrips: list[dict], summary: dict, out_path: Path) -> None:
    """Write a human+LLM-readable analysis_trace.md for feedback-analyst."""
    from datetime import datetime as _dt

    def _avg(vals):
        return round(sum(vals) / len(vals), 2) if vals else None

    wins   = [r for r in roundtrips if r["result"] == "WIN"]
    losses = [r for r in roundtrips if r["result"] == "LOSS"]

    lines: list[str] = []

    # --- Header ---
    lines += [
        f"# Trace Analysis: {strategy_id}",
        f"",
        f"Generated: {_dt.now().strftime('%Y-%m-%d %H:%M')} | "
        f"total_roundtrips: {summary['total_roundtrips']}",
        "",
    ]

    if summary["total_roundtrips"] == 0:
        lines.append("_No roundtrips — 0-trade run._")
        out_path.write_text("\n".join(lines))
        return

    # --- Summary table ---
    lines += [
        "## Summary",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Total roundtrips | {summary['total_roundtrips']} |",
        f"| WIN / LOSS | {summary['wins']} / {summary['losses']} "
        f"({summary['win_rate_pct']:.1f}%) |",
        f"| Avg net bps | {summary.get('avg_net_bps', 0):+.2f} bps |",
        f"| Avg net bps (WIN) | {summary.get('avg_net_bps_wins') or 0:+.2f} bps |",
        f"| Avg net bps (LOSS) | {summary.get('avg_net_bps_losses') or 0:+.2f} bps |",
        f"| Avg hold WIN | {_fmt_hold(summary['avg_hold_sec_wins']) if summary.get('avg_hold_sec_wins') else '-'} |",
        f"| Avg hold LOSS | {_fmt_hold(summary['avg_hold_sec_losses']) if summary.get('avg_hold_sec_losses') else '-'} |",
        "",
    ]

    # --- Exit tag breakdown ---
    lines += [
        "## Exit Tag Breakdown",
        "",
        "| exit_tag | total | WIN | LOSS | avg_net_bps |",
        "|----------|-------|-----|------|-------------|",
    ]
    for tag, info in summary.get("exit_tag_breakdown", {}).items():
        lines.append(
            f"| {tag} | {info['total']} | {info['wins']} | {info['losses']} "
            f"| {info['avg_net_bps']:+.2f} |"
        )
    lines.append("")

    # --- Entry hour distribution ---
    lines += [
        "## Entry Hour Distribution (KST)",
        "",
        "| hour | total | WIN | LOSS |",
        "|------|-------|-----|------|",
    ]
    for hour, info in summary.get("entry_hour_distribution", {}).items():
        lines.append(f"| {hour}시 | {info['total']} | {info['wins']} | {info['losses']} |")
    lines.append("")

    # --- Roundtrips table ---
    lines += [
        "## Roundtrips",
        "",
        "| # | sym | buy_time | sell_time | hold | exit_tag | net_bps | result"
        " | buy_spr | buy_obi | buy_bidQ | buy_askQ | buy_vol"
        " | sell_spr | sell_obi | sell_bidQ | sell_askQ |",
        "|---|-----|----------|-----------|------|----------|---------|-------"
        "|---------|---------|----------|----------|--------"
        "|----------|----------|-----------|-----------|",
    ]
    for i, r in enumerate(roundtrips, 1):
        bl = r.get("buy_lob",  {})
        sl = r.get("sell_lob", {})
        lines.append(
            f"| {i} | {r['symbol']} | {r['buy_time'][11:]} | {r['sell_time'][11:]} "
            f"| {r['hold']} | {r['exit_tag']} | {r['net_bps']:+.1f} | {r['result']} "
            f"| {bl.get('spread_bps', 0):.1f} | {bl.get('obi', 0):+.3f} "
            f"| {bl.get('total_bid_qty', 0):,} | {bl.get('total_ask_qty', 0):,} "
            f"| {bl.get('acml_vol', 0):,} "
            f"| {sl.get('spread_bps', 0):.1f} | {sl.get('obi', 0):+.3f} "
            f"| {sl.get('total_bid_qty', 0):,} | {sl.get('total_ask_qty', 0):,} |"
        )
    lines.append("")

    # --- Pre-computed observations ---
    lines += ["## Pre-computed Observations", ""]

    def _lob_avg(rts, lob_key, field):
        vals = [r.get(lob_key, {}).get(field) for r in rts]
        vals = [v for v in vals if v is not None]
        return _avg(vals)

    w_spr  = _lob_avg(wins,   "buy_lob", "spread_bps")
    l_spr  = _lob_avg(losses, "buy_lob", "spread_bps")
    w_obi  = _lob_avg(wins,   "buy_lob", "obi")
    l_obi  = _lob_avg(losses, "buy_lob", "obi")
    w_vol  = _lob_avg(wins,   "buy_lob", "acml_vol")
    l_vol  = _lob_avg(losses, "buy_lob", "acml_vol")
    w_sobi = _lob_avg(wins,   "sell_lob", "obi")
    l_sobi = _lob_avg(losses, "sell_lob", "obi")

    if w_spr is not None and l_spr is not None:
        flag = " ← LOSS wider" if l_spr > w_spr else ""
        lines.append(f"- Entry spread (bps): WIN avg={w_spr:.1f} | LOSS avg={l_spr:.1f}{flag}")
    if w_obi is not None and l_obi is not None:
        flag = " ← LOSS weaker OBI at entry" if l_obi < w_obi else ""
        lines.append(f"- Entry OBI: WIN avg={w_obi:+.3f} | LOSS avg={l_obi:+.3f}{flag}")
    if w_vol is not None and l_vol is not None:
        lines.append(f"- Entry acml_vol: WIN avg={w_vol:,.0f} | LOSS avg={l_vol:,.0f}")
    if w_sobi is not None and l_sobi is not None:
        flag = " ← LOSS exits into weaker bid" if l_sobi < w_sobi else ""
        lines.append(f"- Exit OBI: WIN avg={w_sobi:+.3f} | LOSS avg={l_sobi:+.3f}{flag}")

    # Most problematic hour
    hour_dist = summary.get("entry_hour_distribution", {})
    worst_hour = max(
        hour_dist.items(),
        key=lambda kv: kv[1]["losses"] / max(kv[1]["total"], 1),
        default=None,
    )
    if worst_hour:
        h, hi = worst_hour
        loss_rate = hi["losses"] / max(hi["total"], 1) * 100
        if loss_rate > 60:
            lines.append(f"- Worst entry hour: {h}시 loss_rate={loss_rate:.0f}% "
                         f"({hi['wins']}W/{hi['losses']}L) — consider time filter")

    lines.append("")
    out_path.write_text("\n".join(lines))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run(strategy_id: str, pretty: bool = False) -> dict:
    strategy_dir = STRATEGIES_DIR / strategy_id

    # Detect trace file
    trace_ps = strategy_dir / "trace_per_symbol.json"
    trace_s  = strategy_dir / "trace.json"

    if trace_ps.exists():
        raw = json.loads(trace_ps.read_text())
        # Merge all symbols' fills into a single chronological list
        all_fills: list[dict] = []
        for sym_trace in raw.values():
            all_fills.extend(sym_trace.get("fills", []))
        all_fills.sort(key=lambda f: f["ts_ns"])
        mode = "per_symbol"
    elif trace_s.exists():
        raw  = json.loads(trace_s.read_text())
        all_fills = sorted(raw.get("fills", []), key=lambda f: f["ts_ns"])
        mode = "single"
    else:
        raise FileNotFoundError(
            f"No trace file found in {strategy_dir}. "
            "Run the backtest first to generate trace.json or trace_per_symbol.json."
        )

    df_cache: dict = {}
    roundtrips = _match_roundtrips(all_fills, df_cache)
    summary    = _compute_summary(roundtrips)

    output = {
        "strategy_id": strategy_id,
        "trace_mode":  mode,
        "summary":     summary,
        "roundtrips":  roundtrips,   # full — includes buy_lob/sell_lob with 10-level arrays
    }

    # Always write full JSON (programmatic access / ML feature extraction)
    json_path = strategy_dir / "analysis_trace.json"
    json_path.write_text(json.dumps(output, ensure_ascii=False, indent=2))

    # Always write analysis_trace.md (trace-only; also used as building block for backtest_analysis.md)
    md_path = strategy_dir / "analysis_trace.md"
    _write_md(strategy_id, roundtrips, summary, md_path)

    # Always write backtest_analysis.md — consolidated report_summary.md + analysis_trace.md.
    # This is the single file feedback-analyst reads; no need to open two files.
    report_md_path = strategy_dir / "report_summary.md"
    ba_path = strategy_dir / "backtest_analysis.md"
    parts: list[str] = []
    if report_md_path.exists():
        parts.append(report_md_path.read_text().rstrip())
        parts.append("\n\n---\n")
    parts.append(md_path.read_text().rstrip())
    ba_path.write_text("\n".join(parts) + "\n")

    if pretty:
        _print_pretty(roundtrips, summary)
    else:
        print(f"written: {json_path.relative_to(ROOT)}")
        print(f"written: {ba_path.relative_to(ROOT)}")
        print(f"roundtrips: {summary['total_roundtrips']}  "
              f"WIN {summary.get('wins', 0)} / LOSS {summary.get('losses', 0)}")

    return output


def main() -> None:
    ap = argparse.ArgumentParser(description="Analyze backtest trace into roundtrip table with LOB snapshots")
    ap.add_argument("--strategy", required=True, help="strategy directory name under strategies/")
    ap.add_argument("--pretty",   action="store_true", help="print human-readable roundtrip table to stdout")
    args = ap.parse_args()
    run(args.strategy, pretty=args.pretty)


if __name__ == "__main__":
    main()
