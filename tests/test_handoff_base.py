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
