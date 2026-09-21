"""Statistiche di fine partita (§5): turni, tiri, 20 e 1 naturali, PF persi,
oggetti usati. Derivate dal `turn_log` e dai contatori di `save_data["stats"]`,
mai da uno stato separato da tenere sincronizzato a mano."""

from __future__ import annotations


def compute_stats(save_data: dict) -> dict:
    turn_log = save_data.get("turn_log", [])
    rolls = [t["roll"] for t in turn_log if t.get("roll")]
    stats = save_data.get("stats", {})
    return {
        "turns": len(turn_log),
        "rolls": len(rolls),
        "natural_20": sum(1 for r in rolls if r.get("natural_20")),
        "natural_1": sum(1 for r in rolls if r.get("natural_1")),
        "hp_lost": stats.get("hp_lost", 0),
        "items_used": stats.get("items_used", 0),
    }
