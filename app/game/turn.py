"""Ciclo di un turno (§3): al massimo 2 chiamate AI, il codice tira i dadi e
valida/applica gli effetti. Idempotente per `turn_id`: un refresh non ritira."""

from __future__ import annotations

import datetime

from app.ai.client import AIClient
from app.ai.tools import NARRATE_OUTCOME_TOOL, REQUEST_CHECK_TOOL
from app.game.combat import current_combatant, run_monster_turns_until_player, start_combat
from app.game.effects import apply_effects
from rules.dice import roll_d20
from rules.difficulty import check_result, dc_for_band
from rules.pacing import compute_pacing


class DailyCapExceeded(RuntimeError):
    """Il giocatore ha raggiunto DAILY_TURN_CAP turni AI oggi."""


def _check_daily_cap(save_data: dict, cap: int) -> None:
    today = datetime.date.today().isoformat()
    if save_data.get("daily_turn_date") != today:
        save_data["daily_turn_date"] = today
        save_data["daily_turn_count"] = 0
    if save_data.get("daily_turn_count", 0) >= cap:
        raise DailyCapExceeded(f"limite di {cap} turni al giorno raggiunto")


def _find_cached_turn(save_data: dict, turn_id: str) -> dict | None:
    for turn in save_data.get("turn_log", []):
        if turn.get("turn_id") == turn_id:
            return turn
    return None


def _pacing_message(save_data: dict) -> dict | None:
    plan = save_data.get("campaign_plan")
    if plan is None:
        return None
    return {
        "role": "user",
        "content": f"[ritmo] {compute_pacing(duration_target=plan.get('duration_target', 'media'), turn_count=save_data.get('turn_count', 0), current_act=save_data.get('current_act', 1))}",
    }


def _resolve_bonus(character_sheet: dict, check: dict) -> int:
    ability = check.get("ability", "for")
    if check.get("check_type") == "save":
        return character_sheet["saving_throws"][ability]
    skill_id = check.get("skill_id")
    if skill_id and skill_id in character_sheet["skills"]:
        return character_sheet["skills"][skill_id]["bonus"]
    return character_sheet["ability_modifiers"][ability]


async def play_turn(
    *,
    character_sheet: dict,
    character_data: dict,
    save_data: dict,
    action_text: str,
    turn_id: str,
    ai_client: AIClient,
    model: str,
    system_prompt: str,
    daily_cap: int,
) -> dict:
    cached = _find_cached_turn(save_data, turn_id)
    if cached is not None:
        return cached

    _check_daily_cap(save_data, daily_cap)

    messages: list[dict] = []
    pacing_message = _pacing_message(save_data)
    if pacing_message is not None:
        messages.append(pacing_message)
    messages.append({"role": "user", "content": action_text})
    check = await ai_client.call_tool(model=model, system=system_prompt, messages=messages, tool=REQUEST_CHECK_TOOL)

    roll_result = None
    if check.get("needs_roll"):
        dc = dc_for_band(check["dc_band"])
        d20 = roll_d20(advantage=check.get("advantage", False), disadvantage=check.get("disadvantage", False))
        bonus = _resolve_bonus(character_sheet, check)
        total = d20.kept + bonus
        roll_result = {
            "d20": d20.kept,
            "dropped": d20.dropped,
            "advantage": d20.advantage,
            "disadvantage": d20.disadvantage,
            "bonus": bonus,
            "dc": dc,
            "total": total,
            "success": check_result(total, dc),
            "natural_20": d20.natural_20,
            "natural_1": d20.natural_1,
        }
        messages.append({"role": "assistant", "content": f"[request_check] {check}"})
        messages.append({"role": "user", "content": f"Esito del tiro: {roll_result}"})
    else:
        messages.append({"role": "assistant", "content": check.get("narration", "")})

    outcome = await ai_client.call_tool(model=model, system=system_prompt, messages=messages, tool=NARRATE_OUTCOME_TOOL)
    effects_applied = apply_effects(character_data, save_data, outcome.get("effects", []))

    monster_ids = save_data.pop("_pending_combat_monsters", None)
    if monster_ids:
        start_combat(save_data, character_data, character_sheet, monster_ids)
        # Se un mostro vince l'iniziativa, il suo turno si risolve subito:
        # altrimenti il giocatore non avrebbe nulla da fare per proseguire.
        if not current_combatant(save_data)["is_player"]:
            run_monster_turns_until_player(save_data, character_data)

    save_data["turn_count"] = save_data.get("turn_count", 0) + 1
    save_data["daily_turn_count"] = save_data.get("daily_turn_count", 0) + 1

    turn_record = {
        "turn_id": turn_id,
        "action": action_text,
        "check": check,
        "roll": roll_result,
        "narration": outcome["narration"],
        "options": outcome.get("options", []),
        "effects_applied": effects_applied,
    }
    save_data.setdefault("turn_log", []).append(turn_record)
    return turn_record
