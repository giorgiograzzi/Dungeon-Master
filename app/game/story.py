"""Esportazione della storia come racconto in prosa (§5, comando `/diario`)."""

from __future__ import annotations

from app.ai.client import AIClient
from app.ai.tools import EXPORT_STORY_TOOL


def _story_context(character_sheet: dict, save_data: dict) -> str:
    plan = save_data.get("campaign_plan") or {}
    turns = "\n".join(f"- {t['action']} -> {t['narration']}" for t in save_data.get("turn_log", []))
    return (
        f"Personaggio: {character_sheet.get('name')}, {character_sheet.get('species')} {character_sheet.get('class_')}.\n"
        f"Campagna: {plan.get('title', '')} — {plan.get('premise', '')}\n"
        f"Fatti noti: {', '.join(save_data.get('facts', []))}\n"
        f"Cronologia dei turni:\n{turns}"
    )


async def export_story(*, ai_client: AIClient, model: str, system_prompt: str, character_sheet: dict, save_data: dict) -> str:
    messages = [{"role": "user", "content": _story_context(character_sheet, save_data)}]
    result = await ai_client.call_tool(model=model, system=system_prompt, messages=messages, tool=EXPORT_STORY_TOOL)
    return result["story_text"]
