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
