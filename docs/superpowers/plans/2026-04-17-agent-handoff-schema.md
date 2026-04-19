# Agent Handoff Schema Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a pydantic-based schema validation layer at three handoff boundaries (`alpha-designer → execution-designer`, `execution-designer → spec-writer`, `feedback-analyst → next iteration`) so that missing required analytical computations — specifically the brief-vs-execution assumption reconciliation — hard-fail the pipeline before reaching backtest.

**Architecture:** New `engine/schemas/` package with pydantic models for each handoff. Existing `scripts/verify_outputs.py` is extended with per-agent pydantic checkers (preserves existing file-presence checks). `.claude/commands/experiment.md` gets validator blocks in the `design-mode=agent` path only. Agent prompt `## Output` subsections are replaced with pydantic schema references; all other workflow/rationale prose stays intact.

**Tech Stack:** Python 3.10+, pydantic 2.12 (already installed), pytest. `instructor` library is *not* required — agents return raw JSON, we parse.

---

## Pre-Flight Checks

Before starting any task, confirm the environment:

- [ ] **Verify pydantic 2.x is available**

Run: `python3 -c "import pydantic; print(pydantic.VERSION)"`
Expected output: `2.12.5` (or >= 2.0)

- [ ] **Verify tests directory and pattern**

Run: `ls tests/ && python3 -m pytest tests/test_signal_brief.py -x --collect-only | head -5`
Expected: test files listed, pytest discovers existing tests.

- [ ] **Verify pilot_s3 sample exists for integration test**

Run: `ls strategies/strat_20260417_0005_pilot_s3_034020_spread/idea.json`
Expected: file exists.

---

## Task 1: HandoffBase schema

**Files:**
- Create: `engine/schemas/__init__.py`
- Create: `engine/schemas/base.py`
- Create: `tests/test_handoff_base.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_handoff_base.py`:

```python
"""Unit tests for engine.schemas.base."""
from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError


def test_handoff_base_accepts_minimal_valid():
    from engine.schemas.base import HandoffBase
    model = HandoffBase(
        strategy_id=None,
        timestamp=datetime(2026, 4, 17, 12, 0, 0),
        agent_name="alpha-designer",
        model_version="claude-sonnet-4-6",
        draft_md_path="strategies/_drafts/foo_alpha.md",
    )
    assert model.strategy_id is None
    assert model.agent_name == "alpha-designer"


def test_handoff_base_rejects_unknown_agent_name():
    from engine.schemas.base import HandoffBase
    with pytest.raises(ValidationError):
        HandoffBase(
            strategy_id="x",
            timestamp=datetime.now(),
            agent_name="random-agent",
            model_version="v1",
            draft_md_path="p.md",
        )


def test_handoff_base_forbids_extra_fields():
    from engine.schemas.base import HandoffBase
    with pytest.raises(ValidationError):
        HandoffBase(
            strategy_id="x",
            timestamp=datetime.now(),
            agent_name="alpha-designer",
            model_version="v1",
            draft_md_path="p.md",
            unexpected_field="foo",
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_handoff_base.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'engine.schemas'`

- [ ] **Step 3: Write minimal implementation**

Create `engine/schemas/__init__.py`:

```python
"""Pydantic schemas for agent-to-agent handoff validation."""
```

Create `engine/schemas/base.py`:

```python
"""Base class for all handoff schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict


class HandoffBase(BaseModel):
    """Common fields every agent handoff must carry."""

    model_config = ConfigDict(extra="forbid")

    strategy_id: Optional[str]
    timestamp: datetime
    agent_name: Literal["alpha-designer", "execution-designer", "feedback-analyst"]
    model_version: str
    draft_md_path: str
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_handoff_base.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add engine/schemas/__init__.py engine/schemas/base.py tests/test_handoff_base.py
git commit -m "feat(schemas): add HandoffBase pydantic model for agent handoffs"
```

---

## Task 2: AlphaHandoff + BriefRealismCheck

**Files:**
- Create: `engine/schemas/alpha.py`
- Create: `tests/test_handoff_alpha.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_handoff_alpha.py`:

```python
"""Unit tests for engine.schemas.alpha."""
from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError


def _valid_realism(**overrides):
    """Build a valid BriefRealismCheck dict; overrides replace fields."""
    base = dict(
        brief_ev_bps_raw=1.5,
        entry_order_type="MARKET",
        spread_cross_cost_bps=5.0,
        brief_horizon_ticks=3000,
        planned_holding_ticks_estimate=3000,
        horizon_scale_factor=1.0,
        symbol_trend_pct_during_target_window=0.5,
        regime_compatibility="match",
        regime_adjustment_bps=0.0,
        adjusted_ev_bps=-3.5,  # 1.5 * 1.0 - 5.0 - 0.0
        decision="reject",
        rationale="entry cost exceeds raw EV",
    )
    base.update(overrides)
    return base


def _valid_alpha(**overrides):
    base = dict(
        strategy_id=None,
        timestamp=datetime(2026, 4, 17),
        agent_name="alpha-designer",
        model_version="claude-sonnet-4-6",
        draft_md_path="strategies/_drafts/foo_alpha.md",
        name="foo",
        hypothesis="h",
        entry_condition="c",
        market_context="m",
        signals_needed=["obi_5"],
        missing_primitive=None,
        needs_python=False,
        paradigm="mean_reversion",
        multi_date=True,
        parent_lesson=None,
        signal_brief_rank=1,
        universe_rationale="u",
        escape_route=None,
        brief_realism=_valid_realism(),
    )
    base.update(overrides)
    return base


def test_alpha_handoff_accepts_valid():
    from engine.schemas.alpha import AlphaHandoff
    AlphaHandoff(**_valid_alpha())


def test_brief_realism_rejects_inconsistent_adjusted_ev():
    """adjusted_ev must equal raw * scale - spread_cross - regime within 0.5 bps."""
    from engine.schemas.alpha import BriefRealismCheck
    with pytest.raises(ValidationError, match="inconsistent with components"):
        BriefRealismCheck(**_valid_realism(adjusted_ev_bps=100.0))  # wildly wrong


def test_brief_realism_rejects_negative_ev_with_proceed():
    """adjusted_ev_bps < 0 and decision='proceed' is contradictory."""
    from engine.schemas.alpha import BriefRealismCheck
    with pytest.raises(ValidationError, match="decision='proceed'"):
        BriefRealismCheck(**_valid_realism(decision="proceed"))


def test_brief_realism_horizon_scale_upper_bound():
    """horizon_scale_factor > 2.0 must fail."""
    from engine.schemas.alpha import BriefRealismCheck
    with pytest.raises(ValidationError):
        BriefRealismCheck(**_valid_realism(horizon_scale_factor=3.0))


def test_brief_realism_horizon_scale_must_be_positive():
    """horizon_scale_factor <= 0 must fail."""
    from engine.schemas.alpha import BriefRealismCheck
    with pytest.raises(ValidationError):
        BriefRealismCheck(**_valid_realism(horizon_scale_factor=0.0))


def test_alpha_handoff_rank_out_of_range():
    from engine.schemas.alpha import AlphaHandoff
    with pytest.raises(ValidationError):
        AlphaHandoff(**_valid_alpha(signal_brief_rank=11))
    with pytest.raises(ValidationError):
        AlphaHandoff(**_valid_alpha(signal_brief_rank=0))


def test_alpha_handoff_spread_cross_can_be_negative_for_limit_bid():
    """LIMIT_AT_BID fills are inside mid — spread_cross_cost can be negative."""
    from engine.schemas.alpha import AlphaHandoff
    realism = _valid_realism(
        entry_order_type="LIMIT_AT_BID",
        spread_cross_cost_bps=-2.0,
        adjusted_ev_bps=3.5,  # 1.5 * 1.0 - (-2.0) - 0.0
        decision="proceed",
        rationale="passive maker captures spread",
    )
    AlphaHandoff(**_valid_alpha(brief_realism=realism))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_handoff_alpha.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'engine.schemas.alpha'`

- [ ] **Step 3: Write minimal implementation**

Create `engine/schemas/alpha.py`:

```python
"""AlphaHandoff + BriefRealismCheck — the contract alpha-designer returns."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from engine.schemas.base import HandoffBase


class BriefRealismCheck(BaseModel):
    """Reconcile brief's measurement assumptions with this strategy's execution reality.

    This field is the primary defense against 'cited brief EV but did not adjust for
    actual execution conditions' — the root cause of pilot_s3-class failures.
    """

    model_config = ConfigDict(extra="forbid")

    brief_ev_bps_raw: float

    entry_order_type: Literal["MARKET", "LIMIT_AT_BID", "LIMIT_AT_ASK", "LIMIT_MID"]
    spread_cross_cost_bps: float = Field(
        description=(
            "Signed cost vs mid at entry, in bps. MARKET BUY = +half_spread (positive cost). "
            "LIMIT at bid, if fills, is a negative cost (fill is inside mid) — but adjust "
            "for adverse-selection expectation. Sign convention: positive = cost subtracted from raw EV."
        )
    )

    brief_horizon_ticks: int
    planned_holding_ticks_estimate: int
    horizon_scale_factor: float = Field(
        gt=0, le=2.0,
        description="planned / brief. Outside (0, 2.0] — EV extrapolation unreliable."
    )

    symbol_trend_pct_during_target_window: Optional[float]
    regime_compatibility: Literal["match", "partial", "mismatch", "unknown"]
    regime_adjustment_bps: float = Field(
        description="Subtractive. Downtrend vs mean-reversion premise = large positive (adverse)."
    )

    adjusted_ev_bps: float
    decision: Literal["proceed", "proceed_with_caveat", "reject"]
    rationale: str

    @model_validator(mode="after")
    def _validate_consistency(self):
        expected = (
            self.brief_ev_bps_raw * self.horizon_scale_factor
            - self.spread_cross_cost_bps
            - self.regime_adjustment_bps
        )
        if abs(self.adjusted_ev_bps - expected) > 0.5:
            raise ValueError(
                f"adjusted_ev_bps ({self.adjusted_ev_bps}) inconsistent with components "
                f"(expected ≈ {expected:.2f})"
            )
        if self.adjusted_ev_bps < 0 and self.decision == "proceed":
            raise ValueError(
                "adjusted_ev_bps < 0 but decision='proceed' — inconsistent; "
                "use 'reject' or 'proceed_with_caveat'"
            )
        return self


class AlphaHandoff(HandoffBase):
    """Output of alpha-designer — consumed by execution-designer."""

    agent_name: Literal["alpha-designer"]

    name: str
    hypothesis: str
    entry_condition: str
    market_context: str
    signals_needed: list[str]
    missing_primitive: Optional[str]
    needs_python: bool
    paradigm: Optional[Literal["mean_reversion", "trend_follow", "passive_maker", "fee_escape"]]
    multi_date: bool
    parent_lesson: Optional[str]

    signal_brief_rank: int = Field(ge=1, le=10)
    universe_rationale: str
    escape_route: Optional[str]

    brief_realism: BriefRealismCheck
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_handoff_alpha.py -v`
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add engine/schemas/alpha.py tests/test_handoff_alpha.py
git commit -m "feat(schemas): add AlphaHandoff with BriefRealismCheck consistency rules"
```

---

## Task 3: ExecutionHandoff + DeviationFromBrief

**Files:**
- Create: `engine/schemas/execution.py`
- Create: `tests/test_handoff_execution.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_handoff_execution.py`:

```python
"""Unit tests for engine.schemas.execution."""
from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from tests.test_handoff_alpha import _valid_alpha


def _valid_exec(**overrides):
    base = dict(
        strategy_id=None,
        timestamp=datetime(2026, 4, 17),
        agent_name="execution-designer",
        model_version="claude-sonnet-4-6",
        draft_md_path="strategies/_drafts/foo_exec.md",
        alpha=_valid_alpha(),
        entry_execution=dict(
            price="ask",
            ttl_ticks=None,
            cancel_on_bid_drop_ticks=None,
        ),
        exit_execution=dict(
            profit_target_bps=30.0,
            stop_loss_bps=15.0,
            trailing_stop=False,
            trailing_activation_bps=None,
            trailing_distance_bps=None,
        ),
        position=dict(lot_size=1, max_entries_per_session=3),
        deviation_from_brief=dict(
            pt_pct=0.10, sl_pct=-0.05, rationale="within band"
        ),
    )
    base.update(overrides)
    return base


def test_execution_handoff_accepts_valid():
    from engine.schemas.execution import ExecutionHandoff
    ExecutionHandoff(**_valid_exec())


def test_deviation_from_brief_rejects_out_of_band():
    from engine.schemas.execution import DeviationFromBrief
    with pytest.raises(ValidationError, match="Deviation"):
        DeviationFromBrief(pt_pct=0.30, sl_pct=0.0, rationale="too wide")


def test_exit_execution_rejects_non_positive_pt():
    from engine.schemas.execution import ExecutionHandoff
    bad = _valid_exec()
    bad["exit_execution"]["profit_target_bps"] = 0.0
    with pytest.raises(ValidationError):
        ExecutionHandoff(**bad)


def test_position_rejects_zero_lot():
    from engine.schemas.execution import ExecutionHandoff
    bad = _valid_exec()
    bad["position"]["lot_size"] = 0
    with pytest.raises(ValidationError):
        ExecutionHandoff(**bad)


def test_execution_carries_alpha_nested():
    from engine.schemas.execution import ExecutionHandoff
    h = ExecutionHandoff(**_valid_exec())
    assert h.alpha.signal_brief_rank == 1
    assert h.alpha.brief_realism.decision == "reject"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_handoff_execution.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'engine.schemas.execution'`

- [ ] **Step 3: Write minimal implementation**

Create `engine/schemas/execution.py`:

```python
"""ExecutionHandoff — output of execution-designer, consumed by spec-writer."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from engine.schemas.alpha import AlphaHandoff
from engine.schemas.base import HandoffBase


class DeviationFromBrief(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pt_pct: float
    sl_pct: float
    rationale: str

    @field_validator("pt_pct", "sl_pct")
    @classmethod
    def _within_band(cls, v: float) -> float:
        if abs(v) > 0.20:
            raise ValueError(
                f"Deviation |{v}| > 0.20 requires structural_concern escalation, not proceed"
            )
        return v


class EntryExecution(BaseModel):
    model_config = ConfigDict(extra="forbid")
    price: Literal["bid", "bid_minus_1tick", "mid", "ask"]
    ttl_ticks: Optional[int]
    cancel_on_bid_drop_ticks: Optional[int]


class ExitExecution(BaseModel):
    model_config = ConfigDict(extra="forbid")
    profit_target_bps: float = Field(gt=0)
    stop_loss_bps: float = Field(gt=0)
    trailing_stop: bool
    trailing_activation_bps: Optional[float]
    trailing_distance_bps: Optional[float]


class PositionConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lot_size: int = Field(ge=1)
    max_entries_per_session: int = Field(ge=1)


class ExecutionHandoff(HandoffBase):
    """Output of execution-designer. Nests AlphaHandoff for full carry-over."""

    agent_name: Literal["execution-designer"]
    alpha: AlphaHandoff
    entry_execution: EntryExecution
    exit_execution: ExitExecution
    position: PositionConfig
    deviation_from_brief: DeviationFromBrief
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_handoff_execution.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add engine/schemas/execution.py tests/test_handoff_execution.py
git commit -m "feat(schemas): add ExecutionHandoff with DeviationFromBrief band check"
```

---

## Task 4: FeedbackOutput

**Files:**
- Create: `engine/schemas/feedback.py`
- Create: `tests/test_handoff_feedback.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_handoff_feedback.py`:

```python
"""Unit tests for engine.schemas.feedback."""
from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError


def _valid_feedback(**overrides):
    base = dict(
        strategy_id="strat_20260417_0005_pilot_s3_034020_spread",
        timestamp=datetime(2026, 4, 17),
        agent_name="feedback-analyst",
        model_version="claude-sonnet-4-6",
        draft_md_path="strategies/<sid>/feedback_notes.md",
        lesson_id=None,
        pattern_id=None,
        primary_finding="f",
        agreement_points=["a"],
        disagreement_points=["d"],
        priority_action="alpha",
        next_idea_seed="s",
        local_seed="l",
        escape_seed="e",
        stop_suggested=False,
        structural_concern=None,
        data_requests=[],
        extensions={},
    )
    base.update(overrides)
    return base


def test_feedback_accepts_valid():
    from engine.schemas.feedback import FeedbackOutput
    FeedbackOutput(**_valid_feedback())


def test_feedback_empty_agreement_points_is_allowed_but_explicit():
    """Empty lists are allowed; the point of the schema is that the FIELD must be present."""
    from engine.schemas.feedback import FeedbackOutput
    FeedbackOutput(**_valid_feedback(agreement_points=[]))


def test_feedback_rejects_invalid_priority():
    from engine.schemas.feedback import FeedbackOutput
    with pytest.raises(ValidationError):
        FeedbackOutput(**_valid_feedback(priority_action="maybe"))


def test_feedback_rejects_missing_required_field():
    from engine.schemas.feedback import FeedbackOutput
    bad = _valid_feedback()
    del bad["primary_finding"]
    with pytest.raises(ValidationError):
        FeedbackOutput(**bad)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_handoff_feedback.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

Create `engine/schemas/feedback.py`:

```python
"""FeedbackOutput — output of feedback-analyst."""
from __future__ import annotations

from typing import Any, Literal, Optional

from engine.schemas.base import HandoffBase


class FeedbackOutput(HandoffBase):
    agent_name: Literal["feedback-analyst"]

    lesson_id: Optional[str]
    pattern_id: Optional[str]
    primary_finding: str
    agreement_points: list[str]
    disagreement_points: list[str]
    priority_action: Literal["alpha", "execution", "both", "neither", "meta"]
    next_idea_seed: str
    local_seed: str
    escape_seed: str
    stop_suggested: bool
    structural_concern: Optional[str]
    data_requests: list[str]
    extensions: dict[str, Any]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_handoff_feedback.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add engine/schemas/feedback.py tests/test_handoff_feedback.py
git commit -m "feat(schemas): add FeedbackOutput pydantic model"
```

---

## Task 5: Extend verify_outputs.py with pydantic checkers

**Files:**
- Modify: `scripts/verify_outputs.py`
- Create: `tests/test_verify_outputs_schema.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_verify_outputs_schema.py`:

```python
"""Integration test for scripts/verify_outputs.py pydantic extensions."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _run_verify(agent: str, output_json: dict) -> dict:
    result = subprocess.run(
        [sys.executable, "scripts/verify_outputs.py",
         "--agent", agent, "--output", json.dumps(output_json)],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    return json.loads(result.stdout)


def test_alpha_designer_rejects_missing_brief_realism():
    malformed = {
        "strategy_id": None,
        "timestamp": "2026-04-17T00:00:00",
        "agent_name": "alpha-designer",
        "model_version": "v1",
        "draft_md_path": "p.md",
        "name": "x", "hypothesis": "h", "entry_condition": "c",
        "market_context": "m", "signals_needed": ["obi_5"],
        "missing_primitive": None, "needs_python": False,
        "paradigm": "mean_reversion", "multi_date": True,
        "parent_lesson": None, "signal_brief_rank": 1,
        "universe_rationale": "u", "escape_route": None,
        # brief_realism intentionally omitted
    }
    out = _run_verify("alpha-designer", malformed)
    assert out["ok"] is False
    assert any("brief_realism" in f for f in out["failures"])


def test_execution_designer_rejects_out_of_band_deviation():
    # Use a minimal valid alpha but bad deviation
    valid_realism = dict(
        brief_ev_bps_raw=1.5, entry_order_type="MARKET",
        spread_cross_cost_bps=5.0, brief_horizon_ticks=3000,
        planned_holding_ticks_estimate=3000, horizon_scale_factor=1.0,
        symbol_trend_pct_during_target_window=0.5,
        regime_compatibility="match", regime_adjustment_bps=0.0,
        adjusted_ev_bps=-3.5, decision="reject",
        rationale="cost dominates",
    )
    valid_alpha = {
        "strategy_id": None, "timestamp": "2026-04-17T00:00:00",
        "agent_name": "alpha-designer", "model_version": "v1",
        "draft_md_path": "p.md",
        "name": "x", "hypothesis": "h", "entry_condition": "c",
        "market_context": "m", "signals_needed": ["obi_5"],
        "missing_primitive": None, "needs_python": False,
        "paradigm": "mean_reversion", "multi_date": True,
        "parent_lesson": None, "signal_brief_rank": 1,
        "universe_rationale": "u", "escape_route": None,
        "brief_realism": valid_realism,
    }
    out_json = {
        "strategy_id": None, "timestamp": "2026-04-17T00:00:00",
        "agent_name": "execution-designer", "model_version": "v1",
        "draft_md_path": "e.md",
        "alpha": valid_alpha,
        "entry_execution": {"price": "ask", "ttl_ticks": None,
                            "cancel_on_bid_drop_ticks": None},
        "exit_execution": {"profit_target_bps": 30.0, "stop_loss_bps": 15.0,
                           "trailing_stop": False,
                           "trailing_activation_bps": None,
                           "trailing_distance_bps": None},
        "position": {"lot_size": 1, "max_entries_per_session": 3},
        "deviation_from_brief": {"pt_pct": 0.30, "sl_pct": 0.0,  # out of band
                                 "rationale": "bad"},
    }
    out = _run_verify("execution-designer", out_json)
    assert out["ok"] is False
    assert any("Deviation" in f for f in out["failures"])


def test_feedback_analyst_rejects_missing_priority():
    fb = {
        "strategy_id": "sid", "timestamp": "2026-04-17T00:00:00",
        "agent_name": "feedback-analyst", "model_version": "v1",
        "draft_md_path": "p.md",
        "lesson_id": None, "pattern_id": None,
        "primary_finding": "f",
        "agreement_points": [], "disagreement_points": [],
        # priority_action missing
        "next_idea_seed": "s", "local_seed": "l", "escape_seed": "e",
        "stop_suggested": False, "structural_concern": None,
        "data_requests": [], "extensions": {},
    }
    out = _run_verify("feedback-analyst", fb)
    assert out["ok"] is False
    assert any("priority_action" in f for f in out["failures"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_verify_outputs_schema.py -v`
Expected: FAIL — `verify_outputs.py` has no `alpha-designer` or `execution-designer` in `AGENT_CHECKERS`.

- [ ] **Step 3: Modify `scripts/verify_outputs.py`**

First, add imports at the top of the file (after existing imports, before `ROOT = …`):

```python
from pydantic import ValidationError

# Lazy import to keep verify_outputs importable even if engine/schemas/ is absent
def _import_schemas():
    from engine.schemas.alpha import AlphaHandoff
    from engine.schemas.execution import ExecutionHandoff
    from engine.schemas.feedback import FeedbackOutput
    return AlphaHandoff, ExecutionHandoff, FeedbackOutput
```

Second, add two new checker functions. Insert them above the `AGENT_CHECKERS` dict (around line 244):

```python
def check_alpha_designer(output: dict, failures: list, warnings: list) -> None:
    """Pydantic validation for alpha-designer output."""
    try:
        AlphaHandoff, _, _ = _import_schemas()
        AlphaHandoff.model_validate(output)
    except ValidationError as e:
        for err in e.errors():
            loc = ".".join(str(x) for x in err["loc"])
            failures.append(f"alpha-designer: {loc} — {err['msg']}")
    except Exception as e:
        failures.append(f"alpha-designer: schema import or unexpected error — {e}")


def check_execution_designer(output: dict, failures: list, warnings: list) -> None:
    """Pydantic validation for execution-designer output."""
    try:
        _, ExecutionHandoff, _ = _import_schemas()
        ExecutionHandoff.model_validate(output)
    except ValidationError as e:
        for err in e.errors():
            loc = ".".join(str(x) for x in err["loc"])
            failures.append(f"execution-designer: {loc} — {err['msg']}")
    except Exception as e:
        failures.append(f"execution-designer: schema import or unexpected error — {e}")
```

Third, add pydantic validation to the existing `check_feedback_analyst`. Locate the existing function (around line 112). At its start (after the docstring), add:

```python
    try:
        _, _, FeedbackOutput = _import_schemas()
        FeedbackOutput.model_validate(output)
    except ValidationError as e:
        for err in e.errors():
            loc = ".".join(str(x) for x in err["loc"])
            failures.append(f"feedback-analyst: {loc} — {err['msg']}")
    except Exception as e:
        failures.append(f"feedback-analyst: schema import or unexpected error — {e}")
    # (continue with existing file-presence checks below)
```

Fourth, update the `AGENT_CHECKERS` dict (line 246) to include the new agents:

```python
AGENT_CHECKERS = {
    "alpha-designer": check_alpha_designer,
    "execution-designer": check_execution_designer,
    "spec-writer": check_spec_writer,
    "feedback-analyst": check_feedback_analyst,
    "backtest-runner": check_backtest_runner,
    "meta-reviewer": check_meta_reviewer,
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_verify_outputs_schema.py -v`
Expected: 3 passed.

Also run the existing verify_outputs callers (regression check):

Run: `python3 -m pytest tests/ -k "verify" -v`
Expected: all pass; no regression.

- [ ] **Step 5: Commit**

```bash
git add scripts/verify_outputs.py tests/test_verify_outputs_schema.py
git commit -m "feat(verify): add pydantic validation for alpha/exec/feedback agents"
```

---

## Task 6: Integration test — replay pilot_s3

**Files:**
- Create: `tests/test_handoff_pilot_s3_replay.py`

Goal: prove the schema would have blocked `pilot_s3` before backtest.

- [ ] **Step 1: Write the failing test**

Create `tests/test_handoff_pilot_s3_replay.py`:

```python
"""Regression / replay test: would the schema have caught pilot_s3?

pilot_s3 was a canonical failure case:
- brief ev_bps = 1.538
- entry = MARKET BUY (crosses ~4.75 bps half-spread on 034020)
- brief horizon 3000 ticks, actual hold ~14 ticks (42s) — horizon_scale ~0.005
- 034020 in -6.6% downtrend during backtest window

Under the schema, either (a) the pilot_s3-style alpha JSON must be authored with
a brief_realism block whose adjusted_ev is correctly negative AND decision='reject',
or (b) the authorship fails validation. This test demonstrates (b) directly.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_pilot_s3_idea_json_without_realism_block_fails_validation():
    """If we submit the existing (schema-less) pilot_s3 idea.json as alpha-designer
    output, the new validator should reject it for missing brief_realism."""
    existing = json.loads(
        (REPO_ROOT
         / "strategies/strat_20260417_0005_pilot_s3_034020_spread/idea.json").read_text()
    )
    # Build a minimal alpha-designer-shaped wrapper around existing content
    wrapper = {
        "strategy_id": "strat_20260417_0005_pilot_s3_034020_spread",
        "timestamp": "2026-04-17T00:00:00",
        "agent_name": "alpha-designer",
        "model_version": "claude-sonnet-4-6",
        "draft_md_path": "strategies/_drafts/pilot_s3_034020_spread_alpha.md",
        "name": existing.get("name", "pilot_s3"),
        "hypothesis": existing.get("hypothesis", ""),
        "entry_condition": existing.get("entry_condition", ""),
        "market_context": existing.get("market_context", ""),
        "signals_needed": existing.get("signals_needed", []),
        "missing_primitive": existing.get("missing_primitive"),
        "needs_python": existing.get("needs_python", False),
        "paradigm": existing.get("paradigm", "mean_reversion"),
        "multi_date": existing.get("multi_date", True),
        "parent_lesson": existing.get("parent_lesson"),
        "signal_brief_rank": existing.get("signal_brief_rank", 1),
        "universe_rationale": existing.get("universe_rationale", ""),
        "escape_route": existing.get("escape_route"),
        # brief_realism is MISSING — the point of this test
    }
    result = subprocess.run(
        [sys.executable, "scripts/verify_outputs.py",
         "--agent", "alpha-designer", "--output", json.dumps(wrapper)],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    out = json.loads(result.stdout)
    assert out["ok"] is False
    assert any("brief_realism" in f for f in out["failures"]), (
        f"Expected brief_realism failure; got: {out['failures']}"
    )


def test_pilot_s3_with_honest_realism_block_is_rejected_by_decision():
    """Even if we hand-fill a truthful brief_realism block for pilot_s3's actual
    conditions, it should fail the 'adjusted_ev < 0 but decision=proceed' rule."""
    realism = {
        "brief_ev_bps_raw": 1.538,
        "entry_order_type": "MARKET",
        "spread_cross_cost_bps": 4.75,  # half of 9.5 bps 1-tick spread on 034020
        "brief_horizon_ticks": 3000,
        "planned_holding_ticks_estimate": 14,  # ~42s / typical tick rate
        "horizon_scale_factor": 0.01,  # 14/3000 rounded
        "symbol_trend_pct_during_target_window": -6.6,
        "regime_compatibility": "mismatch",
        "regime_adjustment_bps": 0.0,
        "adjusted_ev_bps": 1.538 * 0.01 - 4.75 - 0.0,  # ≈ -4.73
        "decision": "proceed",  # contradicts negative adjusted_ev
        "rationale": "attempted to force proceed",
    }
    wrapper = {
        "strategy_id": None, "timestamp": "2026-04-17T00:00:00",
        "agent_name": "alpha-designer", "model_version": "v",
        "draft_md_path": "p.md",
        "name": "pilot_s3_replay", "hypothesis": "h", "entry_condition": "c",
        "market_context": "m", "signals_needed": ["spread_bps", "obi_5"],
        "missing_primitive": None, "needs_python": False,
        "paradigm": "mean_reversion", "multi_date": True,
        "parent_lesson": None, "signal_brief_rank": 1,
        "universe_rationale": "u", "escape_route": None,
        "brief_realism": realism,
    }
    result = subprocess.run(
        [sys.executable, "scripts/verify_outputs.py",
         "--agent", "alpha-designer", "--output", json.dumps(wrapper)],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    out = json.loads(result.stdout)
    assert out["ok"] is False
    assert any("decision='proceed'" in f for f in out["failures"]), (
        f"Expected decision-contradiction failure; got: {out['failures']}"
    )
```

- [ ] **Step 2: Run test to verify it fails first, then passes after verify_outputs.py changes propagate**

Run: `python3 -m pytest tests/test_handoff_pilot_s3_replay.py -v`
Expected: 2 passed (since verify_outputs.py was already extended in Task 5).

If this fails unexpectedly, re-verify Task 5 changes.

- [ ] **Step 3: Commit**

```bash
git add tests/test_handoff_pilot_s3_replay.py
git commit -m "test: pilot_s3 replay — schema would have blocked before backtest"
```

---

## 🛑 Review Checkpoint A (end of Day 1)

Before proceeding to Day 2 (agent prompt edits), pause and verify:

- [ ] All tests pass: `python3 -m pytest tests/test_handoff_*.py tests/test_verify_outputs_schema.py -v`
- [ ] `scripts/verify_outputs.py` still accepts the existing agents it knew before (regression): `python3 -m pytest tests/ -v` — no unexpected failures
- [ ] No changes to `engine/` files outside `engine/schemas/` (run `git diff --stat main... engine/ | grep -v schemas`)
- [ ] Agent `.md` files untouched (`git diff --stat main... .claude/agents/` should be empty)

If any check fails, fix before continuing.

---

## Task 7: Update alpha-designer.md Output section

**Files:**
- Modify: `.claude/agents/alpha-designer.md`

Goal: Replace only the `## Schema` > `### Output (core …)` subsection with a pydantic reference. Keep everything else.

- [ ] **Step 1: Read current Output section**

Run: `python3 -c "p=open('.claude/agents/alpha-designer.md').read(); s=p.find('### Output'); print(p[s:s+1500])"`
Expected: prints the current Output subsection.

- [ ] **Step 2: Replace the Output subsection with pydantic reference**

Using Edit tool, replace the section starting at `### Output (core — 항상 required)` through the end of the Output subsections (before the next `##` or `###` heading that isn't part of Output). Exact old_string and new_string:

`old_string` (starts at line ≈50 of the agent file):
```
### Output (core — 항상 required)
- `name`: string — short slug (lowercase, underscores)
- `hypothesis`: string — 1 sentence: what market inefficiency are you exploiting?
- `entry_condition`: string — plain English: exact conditions that signal an entry opportunity
- `market_context`: string — what state must the market be in? (regime, time of day, volume profile)
- `signals_needed`: array — only the primitives required for the entry signal
- `missing_primitive`: string | null
- `needs_python`: boolean — true if entry logic requires stateful computation across ticks
- `paradigm`: string | null — `mean_reversion` | `trend_follow` | `passive_maker` | `fee_escape`
- `multi_date`: boolean
- `parent_lesson`: string | null
- `alpha_draft_path`: string — path where the .md output was saved

### Output (extensions — 필요시 추가)
- `universe_rationale`: string — why these symbols?
- `escape_route`: string — (ESCAPE 모드) 기존 접근의 한계와 우회 방법

### Input handling
- 모르는 입력 필드는 `extensions`에 보존하고 아이디어 생성 시 참조한다
```

`new_string`:
```
### Output

Return JSON that conforms to `engine.schemas.alpha.AlphaHandoff` (defined in `engine/schemas/alpha.py`). The orchestrator pipes your JSON through `scripts/verify_outputs.py --agent alpha-designer`; any validation failure aborts the iteration.

Mandatory fields (hard-fail if missing or malformed):

- All fields from `HandoffBase`: `strategy_id` (nullable at this stage), `timestamp`, `agent_name="alpha-designer"`, `model_version`, `draft_md_path`
- Alpha core: `name`, `hypothesis`, `entry_condition`, `market_context`, `signals_needed`, `missing_primitive`, `needs_python`, `paradigm`, `multi_date`, `parent_lesson`
- Brief-grounded: `signal_brief_rank` (int 1–10), `universe_rationale`, `escape_route` (nullable)
- **`brief_realism: BriefRealismCheck`** — you MUST compute and report:
  - `brief_ev_bps_raw` — copy from signal brief
  - `entry_order_type` — one of `MARKET | LIMIT_AT_BID | LIMIT_AT_ASK | LIMIT_MID`
  - `spread_cross_cost_bps` — signed; positive = half-spread cost (MARKET BUY); negative allowed for passive LIMIT at bid
  - `brief_horizon_ticks`, `planned_holding_ticks_estimate`
  - `horizon_scale_factor` — `planned / brief`; must be in (0, 2.0]; if outside, you must either re-plan the hold or reject
  - `symbol_trend_pct_during_target_window` — look up buy-hold return over the target backtest window
  - `regime_compatibility` — `match | partial | mismatch | unknown`; set `mismatch` if the symbol trend contradicts the paradigm (e.g., mean-reversion into a >3% directional trend)
  - `regime_adjustment_bps` — subtractive; larger when mismatch
  - `adjusted_ev_bps` = `brief_ev_bps_raw * horizon_scale_factor − spread_cross_cost_bps − regime_adjustment_bps` (validator enforces ±0.5 bps tolerance)
  - `decision` — `proceed | proceed_with_caveat | reject`; must NOT be `proceed` when `adjusted_ev_bps < 0`
  - `rationale` — 1–3 sentences

The `.md` draft at `draft_md_path` remains your human-readable rationale — keep writing it for critics and audit. The pydantic JSON is the machine-readable contract.

Unknown input fields: preserve them in a field named `extensions` (dict) if you add one to your draft; the schema currently forbids extras, so do NOT include them in the returned JSON.
```

- [ ] **Step 3: Verify file still renders well and agent can read its own Schema**

Run: `grep -n "^###" .claude/agents/alpha-designer.md | head -20`
Expected: section headings are still ordered sanely (no duplicates, no orphans).

Run: `python3 -c "from engine.schemas.alpha import AlphaHandoff; print(list(AlphaHandoff.model_fields.keys()))"`
Expected: prints field list matching the prompt description.

- [ ] **Step 4: Commit**

```bash
git add .claude/agents/alpha-designer.md
git commit -m "feat(agent): alpha-designer Output section references AlphaHandoff pydantic schema"
```

---

## Task 8: Update execution-designer.md Output section

**Files:**
- Modify: `.claude/agents/execution-designer.md`

- [ ] **Step 1: Read current Output section**

Run: `python3 -c "p=open('.claude/agents/execution-designer.md').read(); s=p.find('### Output'); print(p[s:s+2000])"`
Expected: prints the current Output subsection.

- [ ] **Step 2: Replace the Output subsection**

Using Edit tool on `.claude/agents/execution-designer.md`:

`old_string`:
```
### Output (core — 항상 required)
모든 alpha 필드를 carry-over하고 아래를 추가:

**entry_execution**:
- `price`: `"bid"` | `"bid_minus_1tick"` | `"mid"` — 진입 주문 가격
- `ttl_ticks`: integer | null — 미체결 시 CANCEL까지 대기 틱 수 (null = 만기 없음)
- `cancel_on_bid_drop_ticks`: integer | null — 제출 시점 bid 대비 N틱 하락 시 CANCEL (null = 비활성)

**exit_execution**:
- `profit_target_bps`: float — LIMIT SELL 목표 bps
- `stop_loss_bps`: float — MARKET SELL stop bps
- `trailing_stop`: boolean — trailing stop 활성화 여부
- `trailing_activation_bps`: float | null — 이 bps 이익 발생 후 trailing 시작 (trailing_stop=true 시 required)
- `trailing_distance_bps`: float | null — 고점 대비 이 bps 하락 시 청산

**position**:
- `lot_size`: integer — 주문 수량
- `max_entries_per_session`: integer — 세션당 최대 진입 횟수

**execution_draft_path**: string — 저장한 .md 파일 경로
```

`new_string`:
```
### Output

Return JSON that conforms to `engine.schemas.execution.ExecutionHandoff` (defined in `engine/schemas/execution.py`). The orchestrator validates via `scripts/verify_outputs.py --agent execution-designer`; failures abort before spec-writer is called.

Top-level fields:

- All `HandoffBase` fields (`strategy_id`, `timestamp`, `agent_name="execution-designer"`, `model_version`, `draft_md_path`)
- `alpha: AlphaHandoff` — full carry-over of alpha-designer's validated JSON (nest the object as-is)
- `entry_execution`:
  - `price` — `bid | bid_minus_1tick | mid | ask`
  - `ttl_ticks` — int or null (null = no expiry)
  - `cancel_on_bid_drop_ticks` — int or null
- `exit_execution`:
  - `profit_target_bps` — float, > 0
  - `stop_loss_bps` — float, > 0
  - `trailing_stop` — bool
  - `trailing_activation_bps` — float or null (required when `trailing_stop` is true)
  - `trailing_distance_bps` — float or null (required when `trailing_stop` is true)
- `position`:
  - `lot_size` — int, ≥ 1
  - `max_entries_per_session` — int, ≥ 1
- `deviation_from_brief`:
  - `pt_pct` — signed fraction relative to brief's `optimal_exit.pt_bps`; absolute value must be ≤ 0.20
  - `sl_pct` — same constraint
  - `rationale` — required; explain any non-zero deviation

If you need deviation > ±20%, do NOT return a handoff — escalate via `structural_concern` in your MD draft and skip JSON return; the orchestrator will treat this as an abort.

The `.md` draft at `draft_md_path` remains your adverse-selection narrative and exit-structure rationale — keep writing it in full.
```

- [ ] **Step 3: Verify**

Run: `grep -n "^###" .claude/agents/execution-designer.md | head -20`
Expected: sections still ordered.

- [ ] **Step 4: Commit**

```bash
git add .claude/agents/execution-designer.md
git commit -m "feat(agent): execution-designer Output section references ExecutionHandoff schema"
```

---

## Task 9: Update feedback-analyst.md Output section

**Files:**
- Modify: `.claude/agents/feedback-analyst.md`

- [ ] **Step 1: Read current Output section**

Run: `python3 -c "p=open('.claude/agents/feedback-analyst.md').read(); s=p.find('### Output'); print(p[s:s+1500])"`

- [ ] **Step 2: Replace the Output subsection**

Using Edit tool on `.claude/agents/feedback-analyst.md`:

`old_string`:
```
### Output (core)
- `strategy_id`, `lesson_id`, `primary_finding`, `next_idea_seed`, `local_seed`, `escape_seed`, `stop_suggested`: same as before
- `agreement_points`: string[] — where both critics agree
- `disagreement_points`: string[] — where they diverge
- `priority_action`: "alpha" | "execution" | "both" — which to fix first

### Output (extensions)
- `pattern_id`: string | null
- `structural_concern`: string | null
- `data_requests`: string[] — aggregated from both critics
```

`new_string`:
```
### Output

Return JSON that conforms to `engine.schemas.feedback.FeedbackOutput` (defined in `engine/schemas/feedback.py`). The orchestrator validates via `scripts/verify_outputs.py --agent feedback-analyst`; failures prevent the lesson from being recorded as canonical.

Required fields:

- All `HandoffBase` fields (`strategy_id`, `timestamp`, `agent_name="feedback-analyst"`, `model_version`, `draft_md_path`)
- `lesson_id` — string or null (null if this iteration produced no new durable lesson)
- `pattern_id` — string or null
- `primary_finding` — 1–3 sentences, the bottom line
- `agreement_points` — list of strings (may be empty, but the field is required)
- `disagreement_points` — list of strings
- `priority_action` — one of `alpha | execution | both | neither | meta`
- `next_idea_seed`, `local_seed`, `escape_seed` — required strings
- `stop_suggested` — bool
- `structural_concern` — string or null
- `data_requests` — list of strings
- `extensions` — dict (carries `clean_pnl_gate`, `invariant_classification`, etc., per the existing post-backtest protocol in this document)

Seeds that cite specific evidence from the critiques (WIN/LOSS deltas, fill-time OBI, regime trend) are preferred — the schema does not enforce evidence citation but critics and meta-reviewer may flag empty-evidence seeds.
```

- [ ] **Step 3: Verify**

Run: `grep -n "^###" .claude/agents/feedback-analyst.md | head -20`
Expected: sections still ordered.

- [ ] **Step 4: Commit**

```bash
git add .claude/agents/feedback-analyst.md
git commit -m "feat(agent): feedback-analyst Output section references FeedbackOutput schema"
```

---

## Task 10: Integrate validators into `/experiment` command

**Files:**
- Modify: `.claude/commands/experiment.md`

Goal: In the `design-mode=agent` path, insert a `verify_outputs.py` call after each of alpha-designer, execution-designer, and feedback-analyst.

- [ ] **Step 1: Locate the agent-mode invocation block**

Run: `grep -n "alpha-designer\|execution-designer\|feedback-analyst\|verify_outputs" .claude/commands/experiment.md`
Expected: shows the current call sites (lines ~83, 84, 150, 153).

- [ ] **Step 2: Insert validator after alpha-designer**

Using Edit tool, locate:

`old_string`:
```
1. `Agent(subagent_type="alpha-designer", prompt="... see below ...")`
2. `Agent(subagent_type="execution-designer", prompt="…")`
```

`new_string`:
```
1. `Agent(subagent_type="alpha-designer", prompt="... see below ...")`

   Validate immediately:
   ```
   python scripts/verify_outputs.py --agent alpha-designer --output '<alpha_json>'
   ```
   If `ok=false`: log `failures` to `strategies/_iterate_context.md` as `"<iter>: alpha-designer schema fail — <first failure>"`, SKIP execution-designer, advance to next seed (or abort run).

2. `Agent(subagent_type="execution-designer", prompt="…")`

   Validate immediately:
   ```
   python scripts/verify_outputs.py --agent execution-designer --output '<execution_json>'
   ```
   If `ok=false`: log failure, SKIP spec-writer and all downstream steps, advance.

   **Adapter (before invoking spec-writer):** The returned `ExecutionHandoff` nests `alpha: AlphaHandoff`. Spec-writer expects a flat shape with `entry_execution`, `exit_execution`, `position`, and alpha fields at the top level. The orchestrator flattens before calling spec-writer:
   ```
   flat = {**execution_json["alpha"], **{k: v for k, v in execution_json.items() if k != "alpha"}}
   Agent(subagent_type="spec-writer", prompt=f"... input={json.dumps(flat)} ...")
   ```
```

- [ ] **Step 3: Insert validator after feedback-analyst**

Using Edit tool, locate:

`old_string`:
```
4. `Agent(subagent_type="feedback-analyst", prompt="Reconcile strategies/<sid>/alpha_critique.md and execution_critique.md. Write knowledge/lessons/<date>_<slug>.md and update strategies/_iterate_context.md. Set stop_suggested=true if this family has exhausted its edge.")`
```

`new_string`:
```
4. `Agent(subagent_type="feedback-analyst", prompt="Reconcile strategies/<sid>/alpha_critique.md and execution_critique.md. Write knowledge/lessons/<date>_<slug>.md and update strategies/_iterate_context.md. Set stop_suggested=true if this family has exhausted its edge.")`

   Validate immediately:
   ```
   python scripts/verify_outputs.py --agent feedback-analyst --output '<feedback_json>'
   ```
   If `ok=false`: do NOT finalize `knowledge/lessons/<date>_<slug>.md`. Log failure, continue loop (feedback was advisory, not blocking).
```

- [ ] **Step 4: Verify command file still parses as Markdown and points are coherent**

Run: `grep -n "verify_outputs" .claude/commands/experiment.md`
Expected: 4–5 references now (1 existing for feedback-analyst may already exist; confirm dedup).

- [ ] **Step 5: Commit**

```bash
git add .claude/commands/experiment.md
git commit -m "feat(experiment): validator checkpoints in design-mode=agent path"
```

---

## 🛑 Review Checkpoint B (end of Day 2)

Before running the smoke test, verify:

- [ ] All unit + integration tests still pass: `python3 -m pytest tests/ -v`
- [ ] Agent `.md` files only changed in their `### Output` subsection: `git diff HEAD~3 -- .claude/agents/` — prose above and below Output should be unchanged
- [ ] `experiment.md` still has both `design-mode=auto` and `design-mode=agent` branches intact
- [ ] `AGENT_CHECKERS` dict now has 6 entries (alpha-designer, execution-designer, spec-writer, feedback-analyst, backtest-runner, meta-reviewer)

If any check fails, fix before proceeding.

---

## Task 11: End-to-end smoke test

**Files:**
- Create: `docs/superpowers/plans/2026-04-17-agent-handoff-schema-smoketest-notes.md` (human notes, not committed unless useful)

Goal: Exercise the `/experiment --design-mode=agent` path once. This is a manual step — the agents invoke LLMs that we cannot fully automate in this plan.

- [ ] **Step 1: Ensure prerequisites**

Run: `ls data/signal_briefs/*.json | head -3`
Expected: at least one brief exists.

Run: `python3 scripts/verify_outputs.py --agent alpha-designer --output '{"foo":"bar"}'` 
Expected: `ok: false`, explicit validation errors naming missing required fields.

- [ ] **Step 2: Kick off a single iteration**

This is user-driven (not automatable inside the plan). Invoke:

```
/experiment --market krx --symbols 042700 --is-start 20260316 --oos-start 20260323 \
            --design-mode agent --feedback-mode programmatic --n-iterations 1
```

Watch for:

- `verify_outputs.py --agent alpha-designer` runs and passes (proof: the iteration continues past alpha → exec)
- `verify_outputs.py --agent execution-designer` runs and passes (proof: spec-writer is invoked)
- Strategy backtests
- Feedback-analyst validator runs (may pass or warn)

If alpha-designer's first output fails validation, EXPECTED for first run — the agent prompt update may need a tweak. Iterate on prompt wording (see Task 7 new_string) until a valid AlphaHandoff is produced on a known-good seed.

- [ ] **Step 3: Capture outcome in a short note**

Write observations (pass/fail per stage, any prompt tweaks needed) under this file:

`docs/superpowers/plans/2026-04-17-agent-handoff-schema-smoketest-notes.md`

Content template:

```markdown
# Smoke Test Log — 2026-04-17

## Setup
- Command: `/experiment --market krx --symbols 042700 ...`
- Brief used: `data/signal_briefs/042700.json`
- First-pass alpha-designer output: [path to returned JSON / first failure]

## Observed
- alpha-designer validation: PASS/FAIL
- execution-designer validation: PASS/FAIL
- feedback-analyst validation: PASS/FAIL
- Any prompt updates needed: [list]

## Next actions
- [list of any follow-ups]
```

- [ ] **Step 4: Commit (if notes are useful)**

```bash
git add docs/superpowers/plans/2026-04-17-agent-handoff-schema-smoketest-notes.md
git commit -m "docs: smoke test log for agent handoff schema rollout"
```

---

## 🛑 Review Checkpoint C (end of Day 3)

Final acceptance checklist against spec §10 (Success Criteria):

- [ ] **Criterion 1** — A new `/experiment --design-mode=agent` run produces JSON that validates against `AlphaHandoff + ExecutionHandoff`. Evidence: smoke test log shows PASS.
- [ ] **Criterion 2** — A pilot_s3-like scenario is blocked before backtest. Evidence: `tests/test_handoff_pilot_s3_replay.py` passes.
- [ ] **Criterion 3** — The currently-best strategy (`pilot_s1`) can be regenerated and passes validation. If reproduction is impractical, note deferred.
- [ ] **Criterion 4** — `scripts/verify_outputs.py --agent alpha-designer` returns `ok=false` with non-empty failures on malformed input. Evidence: `tests/test_verify_outputs_schema.py::test_alpha_designer_rejects_missing_brief_realism` passes.

If all four check out, the rollout is complete.

---

## Self-Review Summary (inline check against spec)

1. **Spec §3.1 file layout** — covered by Tasks 1–4.
2. **Spec §3.3 files modified** — `verify_outputs.py` (Task 5), 3 agent files (Tasks 7–9), `experiment.md` (Task 10).
3. **Spec §4.2 BriefRealismCheck consistency rules** — Task 2 tests both rules (component equality, decision coherence).
4. **Spec §5.1 verify_outputs extension** — Task 5.
5. **Spec §5.2 /experiment integration** — Task 10.
6. **Spec §5.3 agent Output replacement** — Tasks 7–9 replace ONLY the Output subsection, preserving all other prose per the spec's "minimal surgery" directive.
7. **Spec §6.2 pilot_s3 integration test** — Task 6.
8. **Spec §6.3 end-to-end smoke** — Task 11.
9. **Spec §7 migration path** — Days 1/2/3 pacing respected.
10. **Spec §8 risks (narrative regression)** — Review Checkpoint B explicitly compares agent `.md` diff outside Output subsection.
11. **Spec §9 out-of-scope** — no tasks touch `spec-writer`, `strategy-coder`, critics, `audit_handoff.py`, or legacy strategies.
12. **Dependency note** — `instructor` omitted per spec's fallback; pure pydantic is used throughout. No `pip install` step required.
13. **Adapter** — explicitly spelled out in Task 10 as part of the orchestrator flatten step, per spec §3.4.
