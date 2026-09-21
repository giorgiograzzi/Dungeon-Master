"""Forma del documento JSON di un personaggio (§4, §6: stesso approccio a
documento JSON con schema_version usato per i salvataggi di partita)."""

from __future__ import annotations

SCHEMA_VERSION = 1

STEPS = ("species", "class", "background", "ability_scores", "skills", "details", "summary")


def new_character_data() -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "step": STEPS[0],
        "level": 1,
        "species_id": None,
        "class_id": None,
        "background_id": None,
        "feat_id": None,
        "ability_score_method": None,
        "ability_scores": None,
        "rolled_scores": None,
        "background_bonus": None,
        "class_skill_choices": [],
        "background_skills": [],
        "equipment_choice": None,
        "name": None,
        "personal_details": {
            "appearance": "",
            "traits": "",
            "ideals": "",
            "bonds": "",
            "flaws": "",
            "backstory": "",
        },
        "hp_current": None,
        "hp_max": None,
        "hp_temp": 0,
        "inspiration": False,
    }
