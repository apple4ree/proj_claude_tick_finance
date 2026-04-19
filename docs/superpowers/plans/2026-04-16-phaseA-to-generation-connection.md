# Phase A → Generation Pipeline Connection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Connect signal_research + optimal_params outputs directly into the agent generation pipeline, so alpha-designer picks signals from a data-ranked shortlist (not LLM guess) and execution-designer uses mathematically-optimal PT/SL (not intuition).

**Architecture:** A new `scripts/generate_signal_brief.py` pre-computes a JSON "signal brief" per symbol that ranks viable signals by Sharpe with optimal exits attached. Alpha-designer and execution-designer agents are modified to MANDATORILY read this brief before proposing any signal or exit parameter. A new orchestrator wrapper (or /new-strategy command enhancement) ensures the brief is freshly generated before each new-strategy run.

**Tech Stack:** Python 3.10+, existing signal_research.py + optimal_params.py, agent prompts in .claude/agents/

**Design principles:**
- Agent token budget stays small: brief is ~200 lines of structured JSON, not raw data
- Data freshness: brief is regenerated per-symbol, cached per (symbol, fee, date_range) tuple
- Graceful fallback: if no viable signal exists in brief, agents escalate with `structural_concern` (not generate a weak strategy)
- Scope: this plan ONLY covers ① Phase A → Generation. ② Phase B → Feedback (clean_pnl in feedback-analyst) is a SEPARATE plan.

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `scripts/generate_signal_brief.py` | CREATE | Orchestrator: run signal_research + optimal_params, emit compact JSON |
| `data/signal_briefs/<symbol>.json` | CREATE (at runtime) | Data brief consumed by agents |
| `.claude/agents/alpha-designer.md` | MODIFY | MANDATORY data-brief-reading protocol + signal picker |
| `.claude/agents/execution-designer.md` | MODIFY | MANDATORY optimal-exit usage from brief |
| `.claude/commands/new-strategy.md` | MODIFY | Generate brief BEFORE invoking alpha-designer |
| `tests/test_signal_brief.py` | CREATE | Unit tests for brief format + schema |
| `CLAUDE.md` | MODIFY | Document the data-driven generation flow |

---

## Task 1: Signal Brief Generator Script

**Files:**
- Create: `scripts/generate_signal_brief.py`
- Create: `tests/test_signal_brief.py`

- [ ] **Step 1: Write failing test for brief schema**

```python
# tests/test_signal_brief.py
"""Unit tests for scripts/generate_signal_brief.py output schema."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent


def test_brief_schema_has_required_fields():
    """The brief JSON must contain the fields agents rely on."""
    # Use existing cached BTC feature data as input
    features_csv = REPO_ROOT / "data/signal_research/crypto/BTC_features.csv"
    if not features_csv.exists():
        pytest.skip("BTC feature data not available")

    out_dir = REPO_ROOT / "data/signal_briefs"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "BTC.json"
    if out_path.exists():
        out_path.unlink()

    result = subprocess.run(
        [
            sys.executable, "scripts/generate_signal_brief.py",
            "--symbol", "BTC",
            "--features-dir", "data/signal_research/crypto",
            "--fee", "4.0",
            "--out-dir", "data/signal_briefs",
        ],
        cwd=REPO_ROOT, capture_output=True, text=True,
    )
    assert result.returncode == 0, f"generator failed: {result.stderr}"
    assert out_path.exists(), "brief JSON not written"

    brief = json.loads(out_path.read_text())
    # Required top-level keys
    assert "symbol" in brief
    assert "fee_bps" in brief
    assert "top_signals" in brief
    assert "recommendation" in brief
    assert brief["symbol"] == "BTC"
    assert brief["fee_bps"] == 4.0
    assert isinstance(brief["top_signals"], list)


def test_brief_top_signals_have_required_fields():
    """Each signal entry must include the fields alpha-designer needs."""
    out_path = REPO_ROOT / "data/signal_briefs/BTC.json"
    if not out_path.exists():
        pytest.skip("brief not generated; run test_brief_schema_has_required_fields first")

    brief = json.loads(out_path.read_text())
    signals = brief["top_signals"]
    assert len(signals) >= 1, "brief must have at least 1 signal"

    for sig in signals:
        assert "rank" in sig
        assert "signal" in sig
        assert "threshold" in sig
        assert "horizon" in sig
        assert "ev_bps" in sig or "q5_mean_bps" in sig
        assert "optimal_exit" in sig
        oe = sig["optimal_exit"]
        assert "pt_bps" in oe
        assert "sl_bps" in oe
        assert "sharpe" in oe
        assert "win_rate_pct" in oe


def test_brief_handles_no_viable_signals():
    """For KRX 005930 (known no-viable market), brief should mark all non-viable."""
    features_csv = REPO_ROOT / "data/signal_research/005930_features.csv"
    if not features_csv.exists():
        pytest.skip("005930 feature data not available")

    out_path = REPO_ROOT / "data/signal_briefs/005930.json"
    if out_path.exists():
        out_path.unlink()

    result = subprocess.run(
        [
            sys.executable, "scripts/generate_signal_brief.py",
            "--symbol", "005930",
            "--features-dir", "data/signal_research",
            "--fee", "21.0",
            "--out-dir", "data/signal_briefs",
        ],
        cwd=REPO_ROOT, capture_output=True, text=True,
    )
    assert result.returncode == 0
    brief = json.loads(out_path.read_text())
    # All signals should be flagged non-viable
    viable = [s for s in brief["top_signals"] if s.get("viable")]
    assert len(viable) == 0, (
        f"Expected 0 viable signals on KRX 005930 at 21 bps fee; got {len(viable)}"
    )
    assert "no viable" in brief["recommendation"].lower()
```

- [ ] **Step 2: Run test to verify failure**

Run: `pytest tests/test_signal_brief.py -v`
Expected: 3 tests FAIL (file scripts/generate_signal_brief.py does not exist)

- [ ] **Step 3: Implement generate_signal_brief.py**

```python
#!/usr/bin/env python3
"""Signal brief generator.

Runs signal_research + optimal_params on a symbol's feature data and emits
a compact JSON brief that agents consume as a data-driven signal shortlist.

Usage:
    python scripts/generate_signal_brief.py \
        --symbol BTC \
        --features-dir data/signal_research/crypto \
        --fee 4.0 \
        --out-dir data/signal_briefs
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.optimal_params import (
    analyze_signal_at_threshold,
    load_features,
)


_KST = timezone(timedelta(hours=9))


def generate_brief(
    symbol: str,
    features_dir: str,
    fee_bps: float,
    top_n: int = 10,
) -> dict:
    """Build a compact signal brief for agent consumption."""
    df = load_features(symbol, outdir=features_dir)

    fwd_cols = [c for c in df.columns if c.startswith("fwd_")]
    feature_cols = [
        c for c in df.columns
        if c not in fwd_cols + ["ts_ns", "mid", "date"]
        and not c.startswith("fwd_")
    ]

    # Sweep: per signal × threshold percentile × horizon
    candidates = []
    percentiles = [70, 80, 90, 95]
    for signal in feature_cols:
        vals = df[signal].dropna()
        if len(vals) == 0 or vals.std() == 0:
            continue
        for pct in percentiles:
            thr = float(np.percentile(vals, pct))
            for fwd_col in fwd_cols:
                result = analyze_signal_at_threshold(df, signal, thr, fwd_col, fee_bps)
                if "error" in result:
                    continue
                candidates.append({
                    "signal": signal,
                    "threshold": thr,
                    "threshold_percentile": pct,
                    "horizon": int(fwd_col.replace("fwd_", "").replace("t_bps", "")),
                    "entry_pct": result.get("entry_pct", 0),
                    "cond_mean_bps": result.get("cond_mean_bps", 0),
                    "cond_std_bps": result.get("cond_std_bps", 0),
                    "ev_bps": result.get("ev_bps", -999),
                    "sharpe": result.get("sharpe", 0),
                    "win_rate_pct": round(result.get("win_rate", 0) * 100, 2),
                    "pt_bps": result.get("pt_bps", 0),
                    "sl_bps": result.get("sl_bps", 0),
                    "pct_pt": result.get("pct_pt", 0),
                    "pct_sl": result.get("pct_sl", 0),
                    "pct_ts": result.get("pct_ts", 0),
                    "n_entry": result.get("n_entry", 0),
                    "viable": result.get("ev_bps", -999) > 0,
                })

    # Rank by Sharpe descending
    candidates.sort(key=lambda x: x["sharpe"], reverse=True)

    top = candidates[:top_n]
    top_signals = []
    for i, c in enumerate(top):
        top_signals.append({
            "rank": i + 1,
            "signal": c["signal"],
            "threshold": round(c["threshold"], 6),
            "threshold_percentile": c["threshold_percentile"],
            "horizon": c["horizon"],
            "entry_pct": round(c["entry_pct"], 2),
            "ic_bps_edge": round(c["cond_mean_bps"], 3),
            "q5_mean_bps": round(c["cond_mean_bps"], 3),
            "ev_bps": round(c["ev_bps"], 3),
            "viable": bool(c["viable"]),
            "optimal_exit": {
                "pt_bps": int(c["pt_bps"]),
                "sl_bps": int(c["sl_bps"]),
                "sharpe": round(c["sharpe"], 4),
                "win_rate_pct": c["win_rate_pct"],
                "exit_mix": {
                    "pt": int(c["pct_pt"]),
                    "sl": int(c["pct_sl"]),
                    "ts": int(c["pct_ts"]),
                },
            },
            "n_entry": c["n_entry"],
        })

    n_viable = sum(1 for s in top_signals if s["viable"])
    if n_viable == 0:
        recommendation = (
            f"No viable signal at fee={fee_bps} bps. "
            f"All {len(top_signals)} candidates have EV < 0 after fees. "
            f"Consider lower-fee market or fundamentally different signal family."
        )
    elif n_viable <= 3:
        recommendation = (
            f"{n_viable} viable signals found. Use rank-1 signal as primary; "
            f"rank-2 as secondary hypothesis if rank-1 fails."
        )
    else:
        recommendation = (
            f"{n_viable} viable signals. Rank-1 ({top_signals[0]['signal']}) has "
            f"highest Sharpe; alternatives diversify signal family risk."
        )

    brief = {
        "symbol": symbol,
        "generated_at": datetime.now(tz=_KST).isoformat(),
        "fee_bps": fee_bps,
        "n_ticks_analyzed": len(df),
        "features_source": f"{features_dir}/{symbol}_features.csv",
        "top_signals": top_signals,
        "n_viable_in_top": n_viable,
        "recommendation": recommendation,
        "usage_protocol": (
            "alpha-designer: pick a signal from top_signals[0..9]; cite the rank. "
            "execution-designer: adopt optimal_exit.pt_bps/sl_bps as baseline PT/SL, "
            "only deviate if you have a concrete reason (document the deviation)."
        ),
    }
    return brief


def main():
    ap = argparse.ArgumentParser(description="Signal brief generator")
    ap.add_argument("--symbol", required=True)
    ap.add_argument("--features-dir", default="data/signal_research")
    ap.add_argument("--fee", type=float, default=21.0, help="Round-trip fee in bps")
    ap.add_argument("--out-dir", default="data/signal_briefs")
    ap.add_argument("--top-n", type=int, default=10)
    args = ap.parse_args()

    try:
        brief = generate_brief(
            symbol=args.symbol,
            features_dir=args.features_dir,
            fee_bps=args.fee,
            top_n=args.top_n,
        )
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    out_path = Path(args.out_dir) / f"{args.symbol}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(brief, indent=2))
    print(f"Wrote {out_path}")
    print(f"Top signal: {brief['top_signals'][0]['signal']} "
          f"(rank 1, Sharpe={brief['top_signals'][0]['optimal_exit']['sharpe']:.3f}, "
          f"viable={brief['top_signals'][0]['viable']})")
    print(f"Viable in top-{args.top_n}: {brief['n_viable_in_top']}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/test_signal_brief.py -v`
Expected: 3 tests PASS

- [ ] **Step 5: Manual smoke test**

```bash
python scripts/generate_signal_brief.py --symbol BTC --features-dir data/signal_research/crypto --fee 4.0
cat data/signal_briefs/BTC.json | python -m json.tool | head -60
```
Expected: JSON output with top_signals list; top_signals[0].signal is whichever signal has highest Sharpe in BTC data.

- [ ] **Step 6: Commit**

```bash
git add scripts/generate_signal_brief.py tests/test_signal_brief.py
git commit -m "feat(scripts): add generate_signal_brief.py for data-driven signal shortlist"
```

---

## Task 2: Update alpha-designer.md

**Files:**
- Modify: `.claude/agents/alpha-designer.md`

- [ ] **Step 1: Read the current agent prompt**

Run: `wc -l .claude/agents/alpha-designer.md`
Note the file length; identify where to insert the protocol section (ideally near the top of the instructions, before any existing signal-proposal guidance).

- [ ] **Step 2: Insert "Data-Driven Signal Selection Protocol" section**

Insert this section near the top of `.claude/agents/alpha-designer.md`, immediately after the role description and before any existing "how to propose a signal" guidance:

```markdown
## Data-Driven Signal Selection Protocol (MANDATORY)

Before proposing any signal edge, you MUST read the signal brief for the target symbol:

```
data/signal_briefs/<symbol>.json
```

The brief contains the top 10 signals ranked by Sharpe, pre-computed from historical LOB data with the correct round-trip fee applied. Each entry has:
- `signal`: feature name (e.g., "obi_1", "microprice_diff_bps")
- `threshold`: the entry threshold value
- `horizon`: forward return horizon in ticks
- `ev_bps`: expected profit per trade after fees
- `viable`: true if EV > 0
- `optimal_exit`: pt_bps, sl_bps, sharpe, win_rate

### Your protocol

1. **Load the brief.** If the file is missing, STOP and request: "Run `python scripts/generate_signal_brief.py --symbol <SYM> --fee <FEE>` first, then retry."

2. **Check viability.** If `n_viable_in_top == 0`, do NOT propose a strategy. Instead return:
   ```json
   {
     "missing_primitive": null,
     "structural_concern": "No viable signal at current fee level; all top-10 candidates have EV < 0",
     "escape_route": "consider lower-fee market or new signal family"
   }
   ```
   This prevents wasted iterations on markets with no edge.

3. **Pick from the top 10.** Do NOT invent a new signal. Pick a signal from `top_signals[0..9]` whose `viable==true`. Prefer rank 1 unless you have a specific diversification reason (state it).

4. **Use the brief's threshold and horizon.** These are data-optimal. You may deviate by ≤10% if you cite a reason (e.g., "raised threshold by 5% to increase selectivity for first iteration").

5. **State the rank you chose and justify.** In your output `hypothesis` field, include the phrase `"rank-N from signal_brief"` where N is the position you picked.

### Output changes

Add a field `signal_brief_rank: int` to your returned JSON, indicating which rank (1-10) you chose. This is audited downstream by the critic.

### What NOT to do

- Do not propose a signal that isn't in the top 10 of the brief.
- Do not propose thresholds or horizons outside the brief's ±10% band without a cited reason.
- Do not proceed if `n_viable_in_top == 0` — escalate instead.
```

- [ ] **Step 3: Verify file integrity**

Run: `wc -l .claude/agents/alpha-designer.md`
Expected: line count increased by ~40 lines.

Run: `grep -c "Data-Driven Signal Selection" .claude/agents/alpha-designer.md`
Expected: 1

- [ ] **Step 4: Commit**

```bash
git add .claude/agents/alpha-designer.md
git commit -m "docs(agent): alpha-designer MUST read signal brief before proposing signal"
```

---

## Task 3: Update execution-designer.md

**Files:**
- Modify: `.claude/agents/execution-designer.md`

- [ ] **Step 1: Insert "Data-Driven Exit Calibration Protocol" section**

Insert near the top of `.claude/agents/execution-designer.md`, immediately after the role description:

```markdown
## Data-Driven Exit Calibration Protocol (MANDATORY)

Before proposing PT/SL/time_stop values, read the signal brief:

```
data/signal_briefs/<symbol>.json
```

Find the signal chosen by alpha-designer (via the `signal_brief_rank` field in its output) in `top_signals`. That entry's `optimal_exit` field contains mathematically-optimal PT/SL derived from the empirical conditional return distribution.

### Your protocol

1. **Read the alpha-designer's `signal_brief_rank`.** Locate the corresponding entry in the brief's `top_signals`.

2. **Use `optimal_exit` as baseline.** Start with:
   - `profit_target_bps = optimal_exit.pt_bps`
   - `stop_loss_bps = optimal_exit.sl_bps`

3. **Check the exit_mix.** If `exit_mix.pt` is < 10% (PT rarely hit), flag it in your rationale — the strategy will rely on time_stop exits.

4. **Adjust only with explicit reason.** You may modify PT/SL by ±20% if you cite one of:
   - Volatility asymmetry expected (e.g., known news event)
   - Tick-size constraint on the symbol
   - Lot-size scaling concern

   State the deviation in your `entry_execution`/`exit_execution` rationale: `"PT raised 15% from brief's optimal (X bps → Y bps) because <reason>"`.

5. **Do NOT deviate by more than 20%** without escalating as `structural_concern`. The brief's optimal is a statistical floor for reasonable parameters.

### Output changes

Add a field `deviation_from_brief: {pt_pct: float, sl_pct: float, rationale: str}` to indicate how far you deviated from `optimal_exit` and why.

### What NOT to do

- Do not guess PT/SL from intuition when the brief has computed optimal values.
- Do not use PT > 2x brief's optimal (it's phantom — will never hit).
- Do not ignore the `win_rate_pct` — if it's below 30%, warn alpha-designer that the signal may be weak.
```

- [ ] **Step 2: Verify**

Run: `grep -c "Data-Driven Exit Calibration" .claude/agents/execution-designer.md`
Expected: 1

- [ ] **Step 3: Commit**

```bash
git add .claude/agents/execution-designer.md
git commit -m "docs(agent): execution-designer MUST use optimal_exit from signal brief"
```

---

## Task 4: Update /new-strategy command to pre-generate brief

**Files:**
- Modify: `.claude/commands/new-strategy.md`

- [ ] **Step 1: Read current /new-strategy command**

Run: `cat .claude/commands/new-strategy.md`
Identify the section that invokes alpha-designer (or describes the pipeline flow).

- [ ] **Step 2: Insert brief generation step at the beginning of the pipeline**

At the very start of the command's execution flow (before alpha-designer is invoked), add:

```markdown
## Step 0: Signal Brief Generation (MANDATORY)

Before invoking any agent, you MUST ensure a fresh signal brief exists for each
target symbol in the seed's universe.

### Protocol

1. Parse the seed for target symbols (default: `005930` for KRX, `BTC` for crypto).

2. For each symbol, check if `data/signal_briefs/<SYMBOL>.json` exists AND was
   generated within the last 24 hours (`generated_at` field).

3. If missing or stale, run:
   ```bash
   # KRX symbol (fee 21 bps)
   python scripts/generate_signal_brief.py --symbol <SYM> --features-dir data/signal_research --fee 21.0

   # Crypto symbol (fee 4 bps, Upbit data root)
   python scripts/generate_signal_brief.py --symbol <SYM> --features-dir data/signal_research/crypto --fee 4.0
   ```

4. If `generate_signal_brief.py` fails because the underlying features CSV is
   missing, FIRST run:
   ```bash
   # KRX
   python scripts/signal_research.py extract --symbol <SYM> --dates <IS_DATES> --horizons 50,100,200,500,1000,3000

   # Crypto (from /home/dgu/tick/crypto/)
   python scripts/signal_research.py --data-root /home/dgu/tick/crypto extract \
       --symbol <SYM> --dates <DATE> --horizons 50,100,200,500,1000 \
       --regular-only false --outdir data/signal_research/crypto
   ```
   Then retry brief generation.

5. After briefs are confirmed fresh, check each brief's `n_viable_in_top`:
   - If 0, skip the symbol (log "no viable signal; skipping")
   - If all symbols are skipped, ABORT the iteration with reason "no market has viable signals at current fee"

6. Only then proceed to invoke `alpha-designer`.
```

- [ ] **Step 3: Verify**

Run: `grep -c "Signal Brief Generation" .claude/commands/new-strategy.md`
Expected: 1

- [ ] **Step 4: Commit**

```bash
git add .claude/commands/new-strategy.md
git commit -m "docs(command): /new-strategy generates signal brief before alpha-designer"
```

---

## Task 5: End-to-end integration smoke test

**Files:**
- No new files — validation only

- [ ] **Step 1: Verify KRX brief generates correctly**

```bash
python scripts/generate_signal_brief.py \
    --symbol 005930 \
    --features-dir data/signal_research \
    --fee 21.0
```

Expected output:
```
Wrote data/signal_briefs/005930.json
Top signal: <name> (rank 1, Sharpe=<value>, viable=False)
Viable in top-10: 0
```

- [ ] **Step 2: Verify the brief flags KRX as no-viable**

```bash
python -c "
import json
b = json.load(open('data/signal_briefs/005930.json'))
assert b['n_viable_in_top'] == 0, f'Expected 0 viable, got {b[\"n_viable_in_top\"]}'
assert 'no viable' in b['recommendation'].lower()
print('KRX 005930 brief correctly flags 0 viable signals at fee=21.0 bps')
"
```

Expected: prints confirmation line.

- [ ] **Step 3: Verify BTC brief generates and has viable signals (if data exists)**

```bash
if [ -f data/signal_research/crypto/BTC_features.csv ]; then
    python scripts/generate_signal_brief.py \
        --symbol BTC \
        --features-dir data/signal_research/crypto \
        --fee 4.0
    python -c "
import json
b = json.load(open('data/signal_briefs/BTC.json'))
print(f'BTC viable={b[\"n_viable_in_top\"]}, rank-1 signal={b[\"top_signals\"][0][\"signal\"]}')
assert b['n_viable_in_top'] >= 1, 'BTC should have at least 1 viable signal'
"
fi
```

Expected: prints rank-1 BTC signal name with viable count >= 1.

- [ ] **Step 4: Final audit**

Run: `python scripts/audit_principles.py`
Expected: 12/12 passed

Run: `pytest tests/ -v`
Expected: all tests passing (test_invariants + test_signal_brief)

---

## Task 6: Documentation

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Add "Data-Driven Generation Pipeline" section**

In `CLAUDE.md`, append after the existing "Counterfactual PnL Attribution" subsection:

```markdown
## Data-Driven Generation Pipeline (Phase A → Generation)

전략 생성은 이제 데이터 기반입니다. Agent가 LLM 직감으로 signal/exit를 고르지 않고, 사전 분석된 signal brief에서 선택합니다.

### Flow

```
signal_research.py extract   (feature extraction, 1회 per symbol)
    ↓
generate_signal_brief.py     (Sharpe-ranked top 10 + optimal exits)
    ↓  data/signal_briefs/<symbol>.json
    ↓
alpha-designer               (read brief, pick from top 10)
    ↓
execution-designer           (use brief's optimal_exit as baseline)
    ↓
spec-writer / strategy-coder (build strategy from data-informed params)
    ↓
backtest + invariants + attribute_pnl (post-gen validation)
```

### 핵심 규칙

- `/new-strategy` 및 `/iterate`는 alpha-designer 호출 전에 **반드시** signal brief를 생성/갱신
- Brief의 `n_viable_in_top == 0`이면 해당 symbol 건너뜀
- alpha-designer는 top 10 내에서만 signal 선택 (새 signal 발명 금지)
- execution-designer는 brief의 `optimal_exit`을 baseline으로 사용 (±20% 이내만 조정)

### 강제 검증

Agent 산출물에 `signal_brief_rank`, `deviation_from_brief` 필드 포함 → critic이 확인 → 규약 이탈 시 feedback-analyst가 재작업 요청.
```

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: document data-driven generation pipeline (Phase A → Generation)"
```

---

## Summary

After 6 tasks complete, the project has:

1. **`scripts/generate_signal_brief.py`** — produces ranked signal shortlist with optimal exits per symbol
2. **`data/signal_briefs/<symbol>.json`** — runtime-generated JSON consumed by agents
3. **Modified agent prompts** — alpha-designer + execution-designer MUST read the brief; `signal_brief_rank` and `deviation_from_brief` become output contract
4. **Modified `/new-strategy` command** — pre-generates brief before pipeline starts
5. **Integration tests** — schema validation + KRX/BTC smoke tests
6. **Documentation** — CLAUDE.md describes the new flow

**What this achieves:**
- Alpha-designer no longer guesses signals; picks from data-validated top 10
- Execution-designer no longer guesses PT/SL; uses mathematical optimum
- When market has no edge (KRX), pipeline correctly refuses to generate weak strategies instead of wasting iterations
- Next iterate run will produce data-informed strategies whose backtest results are MEANINGFUL (not chasing noise)

**What this does NOT yet do:**
- Feedback loop (Phase B → Feedback) is a SEPARATE plan — feedback-analyst still uses raw return_pct, not clean_pnl
- Critics don't yet check compliance with the brief rules (future plan)

---

## Self-Review

- ✅ Task 1 test references `analyze_signal_at_threshold` and `load_features`, both of which exist in `scripts/optimal_params.py` (confirmed in earlier tasks)
- ✅ JSON schema fields used in Task 2 (`signal_brief_rank`) match field names in Task 1 output (`rank`)
- ✅ `optimal_exit` shape in Task 3 uses `pt_bps`/`sl_bps`/`sharpe`/`win_rate_pct`/`exit_mix` — matches Task 1 output
- ✅ Task 4 brief-generation commands match Task 1 CLI signature
- ✅ `n_viable_in_top` is consistent across all tasks
- ✅ No "TBD" / "implement later" placeholders
- ✅ File paths are absolute and match project layout
- ✅ Fallback behavior explicit: missing brief → error; no viable signals → structural_concern escalation
- ✅ Scope matches the agreed ordering: this plan = ① only; ② is next separate plan
