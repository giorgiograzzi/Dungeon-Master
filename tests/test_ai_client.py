from __future__ import annotations

import pytest

from app.ai.client import FakeAIClient, get_ai_client
from app.ai.tools import (
    EXPORT_STORY_TOOL,
    GENERATE_CAMPAIGN_PLAN_TOOL,
    NARRATE_OUTCOME_TOOL,
    PRESENT_CROSSROADS_TOOL,
    REQUEST_CHECK_TOOL,
    SUMMARIZE_STORY_TOOL,
)
from rules.campaign import validate_campaign_plan


@pytest.fixture
def fake_client():
    return FakeAIClient()


async def test_request_check_no_roll_needed(fake_client):
    result = await fake_client.call_tool(
        model="x", system="x", messages=[{"role": "user", "content": "Cammino verso la porta"}], tool=REQUEST_CHECK_TOOL
    )
    assert result["needs_roll"] is False
    assert result["narration"]


async def test_request_check_roll_needed(fake_client):
    result = await fake_client.call_tool(
        model="x", system="x", messages=[{"role": "user", "content": "Provo a intrufolarmi con furtività"}], tool=REQUEST_CHECK_TOOL
    )
    assert result["needs_roll"] is True
    assert result["dc_band"] in ("molto_facile", "facile", "media", "difficile", "molto_difficile", "quasi_impossibile")


async def test_narrate_outcome_has_options(fake_client):
    result = await fake_client.call_tool(model="x", system="x", messages=[{"role": "user", "content": "esito"}], tool=NARRATE_OUTCOME_TOOL)
    assert result["narration"]
    assert len(result["options"]) >= 1


async def test_generate_campaign_plan_is_valid(fake_client):
    plan = await fake_client.call_tool(
        model="x", system="x", messages=[{"role": "user", "content": "ambientazione: noir, durata: lunga"}],
        tool=GENERATE_CAMPAIGN_PLAN_TOOL,
    )
    assert plan["setting"] == "noir"
    assert plan["duration_target"] == "lunga"
    assert validate_campaign_plan(plan) == []


async def test_present_crossroads_has_three_routes(fake_client):
    result = await fake_client.call_tool(model="x", system="x", messages=[{"role": "user", "content": "bivio"}], tool=PRESENT_CROSSROADS_TOOL)
    assert len(result["routes"]) == 3


async def test_summarize_and_export(fake_client):
    summary = await fake_client.call_tool(model="x", system="x", messages=[{"role": "user", "content": "riassumi"}], tool=SUMMARIZE_STORY_TOOL)
    assert summary["summary"]
    export = await fake_client.call_tool(model="x", system="x", messages=[{"role": "user", "content": "esporta"}], tool=EXPORT_STORY_TOOL)
    assert export["story_text"]


async def test_unknown_tool_raises(fake_client):
    with pytest.raises(ValueError):
        await fake_client.call_tool(model="x", system="x", messages=[], tool={"name": "boh"})


def test_get_ai_client_returns_fake_when_dev_flag_set():
    client = get_ai_client(dev_fake_ai=True, api_key="")
    assert isinstance(client, FakeAIClient)


def test_get_ai_client_returns_real_client_when_flag_off():
    from app.ai.client import AnthropicAIClient

    client = get_ai_client(dev_fake_ai=False, api_key="sk-fake-for-construction-only")
    assert isinstance(client, AnthropicAIClient)
