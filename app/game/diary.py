"""Diario missione (§5): stato di quest principale e secondarie, senza
spoiler sul Piano di Campagna nascosto -- solo dati già noti al giocatore
(quest incontrate, il loro stato, note libere lasciate dal narratore)."""

from __future__ import annotations

from app.game.campaign import current_objective


def build_diary(plan: dict, save_data: dict) -> dict:
    side_quests_state = save_data.get("side_quests_state", {})
    side_quests = []
    for quest in plan.get("side_quests", []):
        status = side_quests_state.get(quest["id"])
        if status is None:
            continue  # non ancora incontrata: nessuno spoiler
        hint = "Ha già dato il suo aiuto." if status == "completata" else "Potrebbe aiutarti nell'impresa principale."
        side_quests.append({"id": quest["id"], "hook": quest["hook"], "status": status, "hint": hint})

    return {
        "main_quest": {"title": plan.get("title", ""), "objective": current_objective(plan, save_data)},
        "side_quests": side_quests,
        "notes": save_data.get("quest_notes", []),
    }
