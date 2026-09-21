from __future__ import annotations

import copy

from app.ai.fake_data import build_fake_campaign_plan
from rules.campaign import validate_campaign_plan


def test_fake_plan_is_valid():
    plan = build_fake_campaign_plan()
    assert validate_campaign_plan(plan) == []


def test_route_missing_act_content_is_a_dead_end():
    plan = build_fake_campaign_plan()
    plan["beats"] = [b for b in plan["beats"] if b["id"] != "parola_atto1"]
    errors = validate_campaign_plan(plan)
    assert any("vicolo cieco" in e and "parola" in e for e in errors)


def test_gate_with_too_few_solutions():
    plan = build_fake_campaign_plan()
    plan["gates"][0]["solutions"] = plan["gates"][0]["solutions"][:2]
    errors = validate_campaign_plan(plan)
    assert any("soluzioni" in e for e in errors)


def test_scene_not_linked_to_beat_or_quest():
    plan = build_fake_campaign_plan()
    plan["scenes"].append({"id": "scena_orfana", "beat_id": None, "side_quest_id": None, "route_id": None})
    errors = validate_campaign_plan(plan)
    assert any("scena_orfana" in e for e in errors)


def test_scene_referencing_unknown_beat():
    plan = build_fake_campaign_plan()
    plan["scenes"][0]["beat_id"] = "beat_che_non_esiste"
    errors = validate_campaign_plan(plan)
    assert any("inesistente" in e for e in errors)


def test_unbalanced_route_durations():
    plan = build_fake_campaign_plan()
    for _ in range(5):
        plan["beats"].append({"id": f"extra_{_}", "title": "x", "objective": "x", "act": 1, "route": "acciaio", "is_hinge": False})
    errors = validate_campaign_plan(plan)
    assert any("sbilanciate" in e for e in errors)


def test_clue_without_redundant_sources():
    plan = build_fake_campaign_plan()
    plan["clues"][0]["sources"] = ["solo_una_fonte"]
    errors = validate_campaign_plan(plan)
    assert any("ridondante" in e or "meno di 2 fonti" in e for e in errors)


def test_side_quest_missing_reward():
    plan = build_fake_campaign_plan()
    plan["side_quests"][0]["reward"] = None
    errors = validate_campaign_plan(plan)
    assert any("senza reward" in e for e in errors)


def test_wrong_counts_are_reported():
    plan = build_fake_campaign_plan()
    plan["npcs"] = plan["npcs"][:5]
    plan["routes"] = plan["routes"][:2]
    errors = validate_campaign_plan(plan)
    assert any("25 PNG" in e for e in errors)
    assert any("3 percorsi" in e for e in errors)


def test_deep_copy_does_not_share_mutable_state():
    plan_a = build_fake_campaign_plan()
    plan_b = copy.deepcopy(plan_a)
    plan_b["beats"].pop()
    assert len(plan_a["beats"]) != len(plan_b["beats"])
