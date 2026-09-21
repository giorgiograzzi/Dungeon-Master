"""Forma del documento JSON di un salvataggio di partita (§6)."""

from __future__ import annotations

SCHEMA_VERSION = 1


def new_game_save_data() -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "campaign_plan": None,
        "current_route_id": None,
        "current_act": 1,
        "completed_beats": [],
        "solved_gates": [],
        "side_quests_state": {},
        "npc_state": {},
        "facts": [],
        "quest_notes": [],
        "story_summary": "",
        "turn_log": [],
        "mode": "exploration",
        "turn_count": 0,
        "daily_turn_count": 0,
        "daily_turn_date": None,
        "ended": False,
        "ending_id": None,
        "rewards_obtained": [],
        "stats": {"hp_lost": 0, "items_used": 0},
    }
