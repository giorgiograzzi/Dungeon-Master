from __future__ import annotations

import pytest

from app.character.schema import new_character_data
from app.character.sheet import compute_sheet, is_complete_for_summary
from app.character.wizard import WizardError, set_ability_scores, set_background, set_background_bonus, set_class, set_personal_details, set_species


def _make_umano_guerriero_soldato() -> dict:
    data = new_character_data()
    set_species(data, "umano")
    set_class(data, "guerriero", ["persuasione", "percezione"], "A")
    set_background(data, "soldato")
    set_ability_scores(
        data,
        "standard_array",
        {"for": 15, "des": 12, "cos": 14, "int": 8, "sag": 10, "car": 13},
    )
    set_background_bonus(data, {"for": 2, "cos": 1})
    set_personal_details(data, "Marco", {"appearance": "Alto e robusto"})
    return data


def test_set_species_rejects_unknown():
    data = new_character_data()
    with pytest.raises(WizardError):
        set_species(data, "marziano")


def test_set_class_validates_skill_count():
    data = new_character_data()
    set_species(data, "umano")
    with pytest.raises(WizardError):
        set_class(data, "guerriero", ["persuasione"], "A")


def test_set_class_rejects_skill_outside_options():
    data = new_character_data()
    with pytest.raises(WizardError):
        # "Arcano" non è tra le opzioni del guerriero
        set_class(data, "guerriero", ["persuasione", "arcano"], "A")


def test_set_class_rejects_unknown_equipment_option():
    data = new_character_data()
    with pytest.raises(WizardError):
        set_class(data, "guerriero", ["persuasione", "percezione"], "Z")


def test_set_class_accepts_third_equipment_option():
    data = new_character_data()
    set_class(data, "guerriero", ["persuasione", "percezione"], "C")
    assert data["equipment_choice"] == "C"


def test_bardo_allows_any_skill():
    data = new_character_data()
    set_class(data, "bardo", ["arcano", "religione", "storia"], "A")
    assert data["class_skill_choices"] == ["arcano", "religione", "storia"]


def test_set_background_resolves_feat_and_skills():
    data = new_character_data()
    set_background(data, "soldato")
    assert data["feat_id"] == "aggressore_selvaggio"
    assert set(data["background_skills"]) == {"atletica", "intimidire"}


def test_ability_scores_standard_array_rejects_wrong_values():
    data = new_character_data()
    with pytest.raises(WizardError):
        set_ability_scores(data, "standard_array", {"for": 16, "des": 14, "cos": 13, "int": 12, "sag": 10, "car": 8})


def test_ability_scores_point_buy_rejects_over_budget():
    data = new_character_data()
    with pytest.raises(WizardError):
        set_ability_scores(data, "point_buy", {"for": 15, "des": 15, "cos": 15, "int": 15, "sag": 15, "car": 15})


def test_ability_scores_point_buy_within_budget():
    data = new_character_data()
    set_ability_scores(data, "point_buy", {"for": 15, "des": 14, "cos": 13, "int": 8, "sag": 10, "car": 8})


def test_ability_scores_4d6_must_match_rolled():
    data = new_character_data()
    data["rolled_scores"] = [15, 14, 13, 12, 10, 8]
    with pytest.raises(WizardError):
        set_ability_scores(data, "4d6", {"for": 10, "des": 10, "cos": 10, "int": 10, "sag": 10, "car": 10})
    set_ability_scores(data, "4d6", {"for": 15, "des": 14, "cos": 13, "int": 12, "sag": 10, "car": 8})


def test_background_bonus_shape():
    data = _make_umano_guerriero_soldato()
    with pytest.raises(WizardError):
        set_background_bonus(data, {"for": 1, "cos": 1})  # somma 2, ma non è né 2/1 né 1/1/1


def test_personal_details_requires_name():
    data = new_character_data()
    with pytest.raises(WizardError):
        set_personal_details(data, "  ", {})


def test_is_complete_for_summary_lists_missing_steps():
    data = new_character_data()
    assert "species" in is_complete_for_summary(data)
    set_species(data, "umano")
    assert "species" not in is_complete_for_summary(data)


def test_compute_sheet_full_character():
    data = _make_umano_guerriero_soldato()
    sheet = compute_sheet(data)

    assert sheet["name"] == "Marco"
    assert sheet["species"] == "Umano"
    assert sheet["class_"] == "Guerriero"
    assert sheet["background"] == "Soldato"
    assert sheet["ability_scores"] == {"for": 17, "des": 12, "cos": 15, "int": 8, "sag": 10, "car": 13}
    assert sheet["ability_modifiers"]["for"] == 3
    assert sheet["proficiency_bonus"] == 2
    # Guerriero: TS Forza e Costituzione
    assert sheet["saving_throws"]["for"] == 3 + 2
    assert sheet["saving_throws"]["des"] == 1  # non competente
    # Competenza da classe (Persuasione, Percezione) e da background (Atletica, Intimidire)
    assert sheet["skills"]["persuasione"]["proficient"]
    assert sheet["skills"]["atletica"]["proficient"]
    assert not sheet["skills"]["furtivita"]["proficient"]
    assert sheet["hit_points"]["maximum"] == 10 + 2  # D10 + mod Cos
    assert sheet["initiative"] == 1
    assert sheet["speed_m"] == 9.0
    # Opzione (A): cotta di maglia (CA 16, no mod Des) + spadone ecc.
    assert sheet["armor_class"] == 16
    assert sheet["gold"] == 4


def test_compute_sheet_raises_when_incomplete():
    data = new_character_data()
    with pytest.raises(ValueError):
        compute_sheet(data)
