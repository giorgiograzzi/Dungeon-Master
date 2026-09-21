"""Calcola la scheda completa del personaggio (§4 punto 7) a partire dal
documento della creazione guidata. Sola lettura: non modifica `data`."""

from __future__ import annotations

import re

from app import srd_data
from rules.ability import ability_modifier, proficiency_bonus
from rules.derived_stats import compute_armor_ac, parse_hit_die, parse_speed_m

_ABILITY_NAME_TO_ID = {
    "forza": "for", "destrezza": "des", "costituzione": "cos",
    "intelligenza": "int", "saggezza": "sag", "carisma": "car",
}


def _parse_ability_list(text: str) -> list[str]:
    cleaned = text.replace(" e ", ", ")
    names = [n.strip().lower() for n in cleaned.split(",") if n.strip()]
    return [_ABILITY_NAME_TO_ID[n] for n in names if n in _ABILITY_NAME_TO_ID]


def _split_equipment_options(text: str) -> dict[str, str]:
    parts = re.split(r"\(([A-C])\)", text)
    options: dict[str, str] = {}
    for i in range(1, len(parts), 2):
        letter, body = parts[i], parts[i + 1]
        body = body.strip()
        body = re.sub(r";?\s+o$", "", body)  # "...15 mo; o" -> "...15 mo" (congiunzione residua)
        options[letter] = body.strip()
    return options


def _find_equipped_armor(option_text: str) -> dict | None:
    text_lower = option_text.lower()
    for armor in sorted(srd_data.armor().values(), key=lambda a: -len(a["name_it"])):
        if armor["category"] != "scudo" and armor["name_it"].lower() in text_lower:
            return armor
    return None


def _has_shield(option_text: str) -> bool:
    return "scudo" in option_text.lower()


def _extract_gold(option_text: str) -> int:
    matches = re.findall(r"(\d+)\s*mo\b", option_text)
    return int(matches[-1]) if matches else 0


def is_complete_for_summary(data: dict) -> list[str]:
    """Elenca cosa manca per poter calcolare una scheda completa."""
    missing = []
    if not data.get("species_id"):
        missing.append("species")
    if not data.get("class_id"):
        missing.append("class")
    if not data.get("background_id"):
        missing.append("background")
    if not data.get("ability_scores"):
        missing.append("ability_scores")
    if not data.get("background_bonus"):
        missing.append("background_bonus")
    if not data.get("name"):
        missing.append("details")
    return missing


def compute_sheet(data: dict) -> dict:
    missing = is_complete_for_summary(data)
    if missing:
        raise ValueError(f"dati mancanti per calcolare la scheda: {missing}")

    species = srd_data.species()[data["species_id"]]
    cls = srd_data.classes()[data["class_id"]]
    background = srd_data.backgrounds()[data["background_id"]]
    level = data.get("level", 1)

    final_scores = dict(data["ability_scores"])
    for ability, bonus in data["background_bonus"].items():
        final_scores[ability] += bonus
    modifiers = {a: ability_modifier(v) for a, v in final_scores.items()}
    prof_bonus = proficiency_bonus(level)

    save_proficiencies = set(_parse_ability_list(cls["saving_throw_proficiencies"]))
    saving_throws = {
        a: modifiers[a] + (prof_bonus if a in save_proficiencies else 0) for a in modifiers
    }

    proficient_skills = set(data["class_skill_choices"]) | set(data["background_skills"])
    all_skills = srd_data.skills()
    skills = {
        skill_id: {
            "name_it": skill["name_it"],
            "ability": skill["ability"],
            "proficient": skill_id in proficient_skills,
            "bonus": modifiers[skill["ability"]] + (prof_bonus if skill_id in proficient_skills else 0),
        }
        for skill_id, skill in all_skills.items()
    }
    passive_perception = 10 + skills["percezione"]["bonus"]

    hit_die = parse_hit_die(cls["hit_die"])
    con_mod = modifiers["cos"]
    hp_max = data.get("hp_max") or (hit_die + con_mod)  # 1° livello: HP massimi (2024)
    hp_current = data.get("hp_current") if data.get("hp_current") is not None else hp_max

    equipment_options = _split_equipment_options(cls["starting_equipment"])
    chosen_equipment = equipment_options.get(data["equipment_choice"], "")
    armor = _find_equipped_armor(chosen_equipment)
    dex_mod = modifiers["des"]
    if armor:
        ac = compute_armor_ac(armor["base_ac"], dex_mod)
    else:
        ac = 10 + dex_mod
    if _has_shield(chosen_equipment):
        ac += 2

    return {
        "name": data["name"],
        "level": level,
        "species": species["name_it"],
        "class_": cls["name_it"],
        "background": background["name_it"],
        "feat": srd_data.feats().get(data["feat_id"], {}).get("name_it") if data.get("feat_id") else None,
        "ability_scores": final_scores,
        "ability_modifiers": modifiers,
        "proficiency_bonus": prof_bonus,
        "armor_class": ac,
        "hit_points": {"current": hp_current, "maximum": hp_max, "temp": data.get("hp_temp", 0)},
        "initiative": dex_mod,
        "speed_m": parse_speed_m(species["speed"]),
        "saving_throws": saving_throws,
        "save_proficiencies": sorted(save_proficiencies),
        "skills": skills,
        "passive_perception": passive_perception,
        "senses": species["creature_type"],
        "species_traits": [t["name"] for t in species["traits"] if t["name"]],
        "equipment": chosen_equipment,
        "inventory": data.get("inventory", []),
        "gold": _extract_gold(chosen_equipment) + data.get("gold_adjustment", 0),
        "inspiration": data.get("inspiration", False),
        "conditions": data.get("conditions", []),
        "personal_details": data["personal_details"],
        "subclass_at_level": cls["subclass_level"],
        "spellcasting": cls["spellcasting"],
    }
