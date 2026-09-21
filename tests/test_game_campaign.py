from __future__ import annotations

import pytest

from app.ai.client import FakeAIClient
from app.game.campaign import (
    CampaignPlanInvalid,
    choose_route,
    generate_and_validate_campaign_plan,
    is_at_crossroads,
    present_crossroads,
    public_campaign_summary,
    rewind_to_crossroad,
)
from app.game.schema import new_game_save_data


async def test_generate_and_validate_campaign_plan_succeeds_with_fake_client():
    plan = await generate_and_validate_campaign_plan(
        ai_client=FakeAIClient(), model="fake", system_prompt="", setting="noir", duration="breve"
    )
    assert plan["setting"] == "noir"


async def test_generate_and_validate_raises_after_max_attempts():
    class AlwaysInvalidClient(FakeAIClient):
        def _fake_campaign_plan(self, messages):
            plan = super()._fake_campaign_plan(messages)
            plan["npcs"] = plan["npcs"][:3]  # meno dei 25 richiesti: sempre non valido
            return plan

    with pytest.raises(CampaignPlanInvalid):
        await generate_and_validate_campaign_plan(
            ai_client=AlwaysInvalidClient(), model="fake", system_prompt="", setting="fantasy classico", duration="media"
        )


async def test_public_campaign_summary_has_no_graph_details():
    from app.ai.fake_data import build_fake_campaign_plan

    plan = build_fake_campaign_plan()
    save = new_game_save_data()
    summary = public_campaign_summary(plan, save)
    assert "gates" not in summary
    assert "npcs" not in summary
    assert summary["current_objective"] == "Scopri la minaccia"


async def test_crossroads_flow():
    from app.ai.fake_data import build_fake_campaign_plan

    plan = build_fake_campaign_plan()
    save = new_game_save_data()

    assert is_at_crossroads(plan, save) is None  # incidente_scatenante non ancora completato

    save["completed_beats"].append("incidente_scatenante")
    crossroad = is_at_crossroads(plan, save)
    assert crossroad is not None
    assert crossroad["after_act"] == 1

    result = await present_crossroads(ai_client=FakeAIClient(), model="fake", system_prompt="", plan=plan, crossroad=crossroad)
    assert len(result["routes"]) == 3

    choose_route(save, "ombra")
    assert save["current_route_id"] == "ombra"
    assert is_at_crossroads(plan, save) is None  # risolto, il prossimo richiede l'atto 2
    assert save["current_act"] == 2  # bivio 1 superato -> si entra nell'Atto II (§4)

    save["completed_beats"].append("rivelazione_centrale")
    choose_route(save, "acciaio")
    assert save["current_act"] == 3


async def test_rewind_to_crossroad_restores_pre_choice_state():
    plan = await generate_and_validate_campaign_plan(
        ai_client=FakeAIClient(), model="fake", system_prompt="", setting="noir", duration="breve"
    )
    save = new_game_save_data()
    save["campaign_plan"] = plan
    save["completed_beats"].append("incidente_scatenante")

    choose_route(save, "ombra")
    assert save["current_route_id"] == "ombra"
    save["facts"].append("un fatto scoperto sulla via dell'ombra")

    rewind_to_crossroad(save, 0)
    assert save["current_route_id"] is None
    assert save["current_act"] == 1
    assert save["facts"] == []
    # Il bivio torna risolvibile: si può scegliere un percorso diverso.
    assert is_at_crossroads(plan, save) is not None

    choose_route(save, "acciaio")
    assert save["current_route_id"] == "acciaio"


def test_rewind_to_crossroad_without_snapshot_raises():
    save = new_game_save_data()
    with pytest.raises(ValueError):
        rewind_to_crossroad(save, 0)
