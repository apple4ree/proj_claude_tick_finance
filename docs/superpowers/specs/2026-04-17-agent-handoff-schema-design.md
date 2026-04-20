# Agent Handoff Schema — Design Spec

**Date**: 2026-04-17
**Author**: Brainstorming session (Claude + Minseok)
**Status**: Draft, pending user review
**Scope**: Tick strategy framework agent pipeline (`/experiment`, `/iterate`, `/new-strategy`)

---

## 1. Problem Statement

Realized returns across 24 recent strategies are all negative or ≤+0.01% (best: `pilot_s1_042700_obi10` at +0.0076%). The working hypothesis — "agents produce guessing-like output" — was only partially supported by evidence. The actual diagnosis after auditing `pilot_s3_034020_spread` (a representative loss case):

**Three compounding gaps:**

1. **Brief-vs-execution assumption gap.** `alpha-designer` correctly cites `signal_brief_rank=1`, `ev_bps=1.538`, and reads `optimal_exit` from the brief. But no stage verifies that the brief's **measurement conditions** (mid-to-mid fills, 3000-tick horizon, regime-agnostic historical average) match the **actual strategy conditions** (MARKET BUY crossing the spread, 42-second hold, possibly into a -6.6% downtrend). `pilot_s3` inherited `ev_bps=1.538` and produced WR=0%.

2. **Variant-sweep guessing.** 15 of 24 strategies (`v_thr_*`, `v_sl_sub`, `v_lot_hi`, …) skip `alpha-designer` and `execution-designer` entirely — only `idea.json` is written. These are ad-hoc parameter perturbations with no analytical justification recorded.

3. **Feedback-seed extension without validation.** `feedback-analyst.next_idea_seed` proposes actions like "add 50-tick EMA slope filter" without having validated that slope would have separated WIN/LOSS outcomes in the actual data. Seeds compound iteration-over-iteration.

**Root cause (confirmed from codebase inspection):** agent-to-agent contracts are defined only as markdown prose inside `.claude/agents/*.md`. `grep -r "pydantic\|TypedDict\|BaseModel"` returns 0 matches. `scripts/verify_outputs.py` checks file presence only; it does not validate field values or cross-field consistency. `scripts/audit_handoff.py` is deliberately measurement-only and does not intervene. Consequence: **missing required computations are invisible** — prose can contain eloquent rationale while omitting the key consistency check, and the pipeline proceeds regardless.

The markdown format itself is not the cause. It is the amplifier: narrative rewards completeness-feel over completeness-fact, and missing fields leave no trace.

## 2. Goal

Add a programmatic schema layer at the three highest-leverage handoff boundaries (`alpha → exec`, `exec → spec-writer`, `critic → feedback`) that **hard-fails** when required analytical computations are missing or internally inconsistent, without regressing the rich prose rationale that current agents already produce.

Non-goals for this spec:
- End-to-end schema at every boundary (option 3 from brainstorming — rejected as negative-marginal-value)
- Removing or replacing markdown drafts (they remain as human-readable rationale)
- Retroactive validation of past 24 strategies
- Replacing `audit_handoff.py` (stays as measurement-only tool)

## 3. Solution Architecture

### 3.1 File layout

```
engine/schemas/
  __init__.py
  base.py            # HandoffBase (strategy_id, timestamp, agent_name, model_version)
  alpha.py           # AlphaHandoff, BriefRealismCheck
  execution.py       # ExecutionHandoff, DeviationFromBrief
  feedback.py        # FeedbackOutput
```

### 3.2 New dependencies

- `pydantic >= 2.0` — likely already installed (check `requirements.txt`; add if missing)
- `instructor` — for LLM-output structured extraction with retry. Added to requirements.

### 3.3 Files modified

| File | Change | Approx. LOC |
|---|---|---|
| `.claude/agents/alpha-designer.md` | Replace `## Schema` prose with `AlphaHandoff` pydantic reference + 1 usage example. Retain all workflow/rationale prose. | +30 / -20 |
| `.claude/agents/execution-designer.md` | Same treatment with `ExecutionHandoff`. | +30 / -20 |
| `.claude/agents/feedback-analyst.md` | Same treatment with `FeedbackOutput`. | +30 / -20 |
| `scripts/verify_outputs.py` | Extend per-agent checkers to also run `pydantic.parse_obj()`; failures go into `failures` list. | +80 |
| `.claude/commands/experiment.md` | In the `design-mode=agent` path (Phase 2 branch), insert validator step after each of the three agents. | +40 |
| `requirements.txt` (or `pyproject.toml`) | Add `pydantic>=2.0`, `instructor`. | +2 |

### 3.4 Files NOT touched

- `_drafts/<name>_*.md` — human-readable rationale, stays as-is
- `.claude/agents/*.md` workflow/data-driven-protocol prose — preserved in full (only `## Output` subsection replaced)
- `scripts/audit_handoff.py` — separation of concerns (measurement vs intervention)
- `.claude/agents/spec-writer.md`, `strategy-coder.md`, `alpha-critic.md`, `execution-critic.md` — agent prompts not modified
- Existing 24 strategies — no retroactive validation

**Adapter note:** `spec-writer` expects a flat JSON with `entry_execution`, `exit_execution`, `position` keys. The new `ExecutionHandoff` nests `alpha: AlphaHandoff`. The `/experiment` orchestrator (not the spec-writer prompt) will flatten `ExecutionHandoff` into the legacy shape before invoking spec-writer. This adapter lives in the orchestrator command, not in the agent.

## 4. Schema Definitions

### 4.1 `HandoffBase`

```python
class HandoffBase(BaseModel):
    model_config = ConfigDict(extra="forbid")
    strategy_id: Optional[str]  # None at alpha-designer time; assigned by spec-writer
    timestamp: datetime
    agent_name: Literal["alpha-designer", "execution-designer", "feedback-analyst"]
    model_version: str  # e.g., "claude-sonnet-4-6"
    draft_md_path: str  # path to human-readable rationale MD
```

### 4.2 `BriefRealismCheck` — the key new contract

This is the field that would have caught `pilot_s3`. It makes the "brief measurement conditions vs actual execution conditions" gap **explicit and enforceable**.

```python
class BriefRealismCheck(BaseModel):
    """Required computation: reconcile brief's measurement assumptions with this strategy's execution reality."""
    model_config = ConfigDict(extra="forbid")

    brief_ev_bps_raw: float  # as-reported in signal_brief_v2.json

    # Entry cost adjustment — does strategy cross the spread at entry?
    entry_order_type: Literal["MARKET", "LIMIT_AT_BID", "LIMIT_AT_ASK", "LIMIT_MID"]
    spread_cross_cost_bps: float = Field(
        description=(
            "Signed cost vs mid at entry, in bps. MARKET BUY = +half_spread (positive cost). "
            "LIMIT at bid, if fills, is a negative cost (fill is inside mid) — but must be adjusted "
            "for adverse-selection expectation (i.e., typical post-fill reversion). "
            "Sign convention: positive = cost subtracted from raw EV."
        )
    )

    # Horizon adjustment — does planned hold match brief's horizon?
    brief_horizon_ticks: int
    planned_holding_ticks_estimate: int
    horizon_scale_factor: float = Field(
        gt=0, le=2.0,
        description="planned / brief. If < 0.1 or > 2.0, EV extrapolation is unreliable — must justify or reject."
    )

    # Regime compatibility — does the brief's averaged regime match this strategy's target regime?
    symbol_trend_pct_during_target_window: Optional[float]  # e.g., -6.6 for pilot_s3's 034020
    regime_compatibility: Literal["match", "partial", "mismatch", "unknown"]
    regime_adjustment_bps: float = Field(
        description="Subtractive. Downtrend vs mean-reversion premise = large positive (adverse)."
    )

    # Final adjusted expected value
    adjusted_ev_bps: float
    decision: Literal["proceed", "proceed_with_caveat", "reject"]
    rationale: str  # 1-3 sentences; free text but required

    @model_validator(mode="after")
    def validate_consistency(self):
        # adjusted_ev_bps must equal brief_ev_bps_raw - spread_cross_cost_bps - regime_adjustment_bps
        # (within 0.5 bps tolerance for rounding; horizon_scale_factor acts multiplicatively on the raw)
        expected = (self.brief_ev_bps_raw * self.horizon_scale_factor
                    - self.spread_cross_cost_bps
                    - self.regime_adjustment_bps)
        if abs(self.adjusted_ev_bps - expected) > 0.5:
            raise ValueError(
                f"adjusted_ev_bps ({self.adjusted_ev_bps}) inconsistent with components "
                f"(expected ≈ {expected:.2f})"
            )
        # If adjusted_ev < 0 and decision is 'proceed', that's a contradiction — must be 'reject' or have caveat
        if self.adjusted_ev_bps < 0 and self.decision == "proceed":
            raise ValueError("adjusted_ev_bps < 0 but decision='proceed' — inconsistent")
        return self
```

**Why this catches `pilot_s3`:** the strategy would have been forced to write:
- `brief_ev_bps_raw = 1.538`
- `entry_order_type = "MARKET"`, `spread_cross_cost_bps ≈ 4.75` (half of 9.5 spread)
- `horizon_scale_factor` — brief's 3000 ticks vs planned ~14 ticks (42s at tick rate) → **0.005, below the `gt=0` allowed but fails the `le=2.0` assumption** — forces a justification or rejection
- `regime_compatibility = "mismatch"` (long-only mean-reversion into -6.6% downtrend)
- `adjusted_ev_bps` would land deeply negative → `decision = "reject"` required

Either way, `pilot_s3` never reaches backtest — or is logged with explicit caveat understanding the expected loss.

### 4.3 `AlphaHandoff`

```python
class AlphaHandoff(HandoffBase):
    agent_name: Literal["alpha-designer"]

    # Core fields (migrated from existing agent schema)
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

    # Brief-grounded
    signal_brief_rank: int = Field(ge=1, le=10)
    universe_rationale: str
    escape_route: Optional[str]

    # The new mandatory check
    brief_realism: BriefRealismCheck
```

### 4.4 `ExecutionHandoff`

```python
class DeviationFromBrief(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pt_pct: float  # (actual - brief) / brief; range ±0.20 per protocol
    sl_pct: float
    rationale: str

    @field_validator("pt_pct", "sl_pct")
    @classmethod
    def within_band(cls, v):
        if abs(v) > 0.20:
            raise ValueError(f"Deviation |{v}| > 0.20 requires structural_concern escalation, not proceed")
        return v


class EntryExecution(BaseModel):
    price: Literal["bid", "bid_minus_1tick", "mid", "ask"]
    ttl_ticks: Optional[int]
    cancel_on_bid_drop_ticks: Optional[int]


class ExitExecution(BaseModel):
    profit_target_bps: float = Field(gt=0)
    stop_loss_bps: float = Field(gt=0)
    trailing_stop: bool
    trailing_activation_bps: Optional[float]
    trailing_distance_bps: Optional[float]


class PositionConfig(BaseModel):
    lot_size: int = Field(ge=1)
    max_entries_per_session: int = Field(ge=1)


class ExecutionHandoff(HandoffBase):
    agent_name: Literal["execution-designer"]

    # All alpha fields carry-over preserved
    alpha: AlphaHandoff

    entry_execution: EntryExecution
    exit_execution: ExitExecution
    position: PositionConfig
    deviation_from_brief: DeviationFromBrief
```

### 4.5 `FeedbackOutput`

```python
class AttributionExtension(BaseModel):
    result: Literal["GATE_A", "GATE_B", "GATE_C"]  # existing semantics
    clean_pnl: float
    bug_pnl: float
    clean_pct_of_total: float
    explanation: str


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
    extensions: dict[str, Any]  # includes clean_pnl_gate, invariant_classification, etc.
```

(Feedback gets a lighter schema because the primary quality lever there is "does this seed reference specific evidence from the critiques?" — enforced by `agreement_points` and `disagreement_points` being non-empty, not by structural typing.)

## 5. Integration Points

### 5.1 `scripts/verify_outputs.py` extension

```python
# Add per-agent pydantic check after existing file-presence checks
def check_alpha_designer(output: dict, failures: list, warnings: list) -> None:
    try:
        AlphaHandoff.model_validate(output)
    except ValidationError as e:
        failures.append(f"alpha-designer: pydantic validation failed — {e}")
```

Return `ok=false` on any validation failure. The calling orchestrator (`/experiment`) MUST abort the iteration — no backtest, no spec-writer invocation.

Register new checkers in `AGENT_CHECKERS` dict.

### 5.2 `.claude/commands/experiment.md` — design-mode=agent path

Insert a validator block after each of the three agents within Phase 2 agent branch. Example for alpha-designer:

```markdown
After `alpha-designer`:
  vfy = Bash("python scripts/verify_outputs.py --agent alpha-designer --output '<alpha_json>'")
  if not vfy.ok:
    log failures, DO NOT invoke execution-designer, abort iteration
    append to strategies/_iterate_context.md: "<iter>: alpha-designer schema fail — <first failure>"
```

Same pattern for `execution-designer` (before `spec-writer`) and `feedback-analyst` (before writing lesson).

No changes needed for `design-mode=auto` path — that goes through `scripts/gen_strategy_from_brief.py` (rule-template, deterministic).

### 5.3 Agent prompt updates — minimal surgery

In each of the three agent `.md` files, replace the `## Schema` section's **Output** subsection with:

```markdown
## Output

Return JSON that conforms to `engine.schemas.alpha.AlphaHandoff`. Use the `instructor` library if available; otherwise structure your JSON to match the pydantic model.

Mandatory fields (will hard-fail if missing):
- All fields listed in `AlphaHandoff` (see `engine/schemas/alpha.py`)
- `brief_realism: BriefRealismCheck` — you MUST compute and report:
  - Estimated `spread_cross_cost_bps` based on your chosen entry order type
  - `horizon_scale_factor` = planned_hold / brief_horizon
  - `regime_compatibility` — look up the target symbol's buy-hold return over the target backtest window; if mean-reversion premise contradicts a >3% directional trend, set to "mismatch"
  - `adjusted_ev_bps` = brief_ev * horizon_scale_factor - spread_cross_cost - regime_adjustment
  - `decision = "reject"` if adjusted_ev_bps < 0 and you have no caveat justification

(MD draft path remains required; the pydantic JSON is the machine-readable contract, the MD is the human rationale.)
```

Keep all other prose (workflow, data-driven-protocol, knowledge-search steps) **untouched**. This is the key design choice: we constrain outputs, not reasoning.

## 6. Testing Plan

1. **Unit tests for schemas** — `tests/test_schemas.py`:
   - `BriefRealismCheck` fails when `adjusted_ev_bps` inconsistent with components (> 0.5 bps delta)
   - Fails when `adjusted_ev_bps < 0` and `decision == "proceed"`
   - `DeviationFromBrief` fails when `|pt_pct| > 0.20`
   - `AlphaHandoff` fails when `signal_brief_rank` outside [1, 10]

2. **Integration test** — replay `pilot_s3_034020_spread`'s `idea.json` through the new validator. Should fail with a specific error indicating missing `brief_realism` block. After manually adding a realistic `brief_realism` with the actual (-6.6% trend) regime data, should fail with `adjusted_ev_bps < 0` contradicting `decision="proceed"`.

3. **End-to-end smoke** — run one iteration of `/experiment --design-mode=agent --n-iterations=1` on a symbol with known viable signal (e.g., `005930` crypto pivot if applicable) to confirm the happy path does not break.

## 7. Migration Path

1. **Day 1**: Write schemas + unit tests, extend `verify_outputs.py`, update agent prompts. No `/experiment` integration yet. Run existing agents; confirm they can (with prompt update) produce valid JSON. If not, iterate on agent prompt wording.
2. **Day 2**: Integrate into `/experiment` `design-mode=agent` path. Run smoke test. Fix any downstream issues (spec-writer reading the new JSON — it expects flattened keys; write an adapter).
3. **Day 3**: Replay `pilot_s3` integration test. Confirm hard-fail path works.
4. **No retroactive migration** — existing 24 strategies retain their current schema-less `idea.json`. `audit_handoff.py` continues to measure them as-is.

## 8. Risks & Mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| Agent prompt update causes narrative regression (loss of analytical prose quality) | Medium | Replace only the `## Output` subsection; preserve all workflow/rationale prose. Test on a known-good seed after update. |
| `instructor` dependency conflicts with existing stack | Low | Fallback: pure pydantic without instructor; agent returns raw JSON, we parse. |
| Schema too strict — valid strategies get rejected | Medium | `decision="proceed_with_caveat"` escape hatch allows documented-override of individual checks. |
| `brief_realism` fields themselves can be gamed (agent writes optimistic regime_adjustment) | Medium | Post-hoc `audit_handoff.py` records the claimed values; mismatch against realized backtest metrics becomes a new paper measurement (unenforced but observable). |
| `/experiment` integration breaks existing `design-mode=auto` path | Low | The validator step is inserted only in the `agent` branch. `auto` branch is untouched. |

## 9. Out of Scope (explicit)

- Schemas for `spec-writer`, `strategy-coder`, `alpha-critic`, `execution-critic`, `backtest-runner`, `portfolio-designer`, `meta-reviewer`
- Retroactive validation of past strategies
- Removing/replacing the markdown draft files
- Changes to `audit_handoff.py`
- Variant-sweep strategies (`v_thr_*`) — those skip the designer agents entirely; addressing that is a separate design question
- Refactoring `/iterate` or `/new-strategy` (they are deprecated in favor of `/experiment`)

## 10. Success Criteria

1. A new strategy generation through `/experiment --design-mode=agent` produces an `idea.json` that validates against `AlphaHandoff + ExecutionHandoff`.
2. When a `pilot_s3`-like scenario is constructed (brief ev=+1.5 bps, MARKET entry, symbol in -6% downtrend), the validator blocks it before backtest with a specific error message identifying the offending field.
3. Existing `pilot_s1` (the one weakly profitable case) can be regenerated and passes validation (i.e., the schema is not so strict it rejects the currently-best strategy).
4. `scripts/verify_outputs.py --agent alpha-designer` returns `ok=false` with a non-empty `failures` list when run on malformed output.

---

## Appendix A — Why not option 3 (end-to-end schemas)

Summary of the brainstorming rejection of option 3:

- pilot_s3-class failures are caught by the `BriefRealismCheck` field alone; end-to-end typing adds no further detection.
- End-to-end typing pushes toward JSON-only output, which risks regressing the rich analytical prose currently in `_drafts/*.md` (e.g., `pilot_s3_alpha.md`'s lesson citations and data-derived tick size).
- `CLAUDE.md` was just refactored to designate `/experiment` as the canonical entry point; heavy rewrites of legacy agent prompts risk being re-done as `/experiment` evolves.
- 80% of the fidelity-paper measurement infrastructure is already in `audit_handoff.py` (records presence/absence of mandated artifacts). Option 2 + existing audit covers the paper's needs.

## Appendix B — Relation to existing infrastructure

- `scripts/verify_outputs.py` — this spec extends it (adds pydantic validation on top of file-presence checks).
- `scripts/audit_handoff.py` — unchanged; continues to record measurements for the paper.
- `data/signal_briefs/<symbol>.json` — the schema assumes this file is canonical for `brief_ev_bps_raw` and `brief_horizon_ticks`. Strategies must cite the brief that was loaded.
- `scripts/attribute_pnl.py` + strict mode — unchanged; continues to compute `clean_pnl` retroactively. Long-term, a realized `clean_pnl` vs claimed `adjusted_ev_bps` delta becomes a useful metric but is out of scope for this spec.
