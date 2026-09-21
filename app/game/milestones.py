"""Level-up a milestone (§4): livello = atto corrente (fine Atto I -> 2,
fine Atto II -> 3), agganciato all'avanzamento di `current_act` che avviene
quando il giocatore sceglie un percorso a un bivio (`app.game.campaign.choose_route`)."""

from __future__ import annotations

from app import srd_data
from rules.derived_stats import parse_hit_die
from rules.levelup import roll_hp_gain


def target_level_for_act(current_act: int) -> int:
    return min(3, max(1, current_act))


def maybe_level_up(save_data: dict, character_data: dict, character_sheet: dict) -> dict | None:
    """Applica il level-up se il personaggio è sotto il livello atteso per
    l'atto corrente; restituisce i dettagli (per mostrare il tiro del dado
    vita) o None se non c'è nulla da fare."""
    target_level = target_level_for_act(save_data.get("current_act", 1))
    current_level = character_data.get("level", 1)
    if target_level <= current_level:
        return None

    cls = srd_data.classes()[character_data["class_id"]]
    hit_die_sides = parse_hit_die(cls["hit_die"])
    con_mod = character_sheet["ability_modifiers"]["cos"]
    roll, hp_gain = roll_hp_gain(hit_die_sides, con_mod)

    character_data["level"] = target_level
    character_data["hp_max"] = character_data.get("hp_max", 0) + hp_gain
    character_data["hp_current"] = character_data.get("hp_current", 0) + hp_gain
    return {
        "new_level": target_level,
        "hit_die_sides": hit_die_sides,
        "roll": roll,
        "hp_gain": hp_gain,
        "hp_max": character_data["hp_max"],
        "subclass_unlocked": cls["subclass_name"] if target_level >= cls["subclass_level"] else None,
    }
