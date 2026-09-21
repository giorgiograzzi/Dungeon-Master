"""§14: creazione del personaggio per tutte le combinazioni specie×classe×
background (9×12×4 = 432), con una scelta valida di default per ogni step."""

from __future__ import annotations

import pytest

from app import srd_data
from app.character.schema import new_character_data
from app.character.sheet import compute_sheet
from app.character.wizard import set_ability_scores, set_background, set_background_bonus, set_class, set_personal_details, set_species
from rules.ability_scores import STANDARD_ARRAY
from rules.text_choices import parse_choice
from rules.text_utils import slugify

ABILITIES = ("for", "des", "cos", "int", "sag", "car")

ALL_COMBOS = [
    (species_id, class_id, background_id)
    for species_id in srd_data.species()
    for class_id in srd_data.classes()
    for background_id in srd_data.backgrounds()
]


def _default_skill_choices(class_id: str) -> list[str]:
    cls = srd_data.classes()[class_id]
    choice = parse_choice(cls["skill_proficiencies"])
    options = choice.options or tuple(s["name_it"] for s in srd_data.skills().values())
    ids = [slugify(o) for o in options][: choice.count]
    return ids


@pytest.mark.parametrize("species_id,class_id,background_id", ALL_COMBOS)
def test_full_creation_produces_a_valid_sheet(species_id, class_id, background_id):
    data = new_character_data()
    set_species(data, species_id)
    set_class(data, class_id, _default_skill_choices(class_id), "A")
    set_background(data, background_id)
    set_ability_scores(data, "standard_array", dict(zip(ABILITIES, STANDARD_ARRAY)))
    set_background_bonus(data, {"for": 2, "des": 1})
    set_personal_details(data, "Prova", {})

    sheet = compute_sheet(data)
    assert sheet["armor_class"] > 0
    assert sheet["hit_points"]["maximum"] > 0
    assert 1 <= sheet["proficiency_bonus"] <= 6
    assert len(sheet["skills"]) == 18
