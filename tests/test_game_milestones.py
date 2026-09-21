from __future__ import annotations

from app.character.schema import new_character_data
from app.character.sheet import compute_sheet
from app.character.wizard import finalize_character, set_ability_scores, set_background, set_background_bonus, set_class, set_personal_details, set_species
from app.game.milestones import maybe_level_up, target_level_for_act
from app.game.schema import new_game_save_data
from rules.ability_scores import STANDARD_ARRAY

ABILITIES = ("for", "des", "cos", "int", "sag", "car")


def _setup():
    char = new_character_data()
    set_species(char, "umano")
    set_class(char, "guerriero", ["percezione", "intimidire"], "A")
    set_background(char, "soldato")
    set_ability_scores(char, "standard_array", dict(zip(ABILITIES, STANDARD_ARRAY)))
    set_background_bonus(char, {"for": 2, "cos": 1})
    set_personal_details(char, "Marco", {})
    finalize_character(char)
    sheet = compute_sheet(char)
    save = new_game_save_data()
    return char, sheet, save


def test_target_level_for_act():
    assert target_level_for_act(1) == 1
    assert target_level_for_act(2) == 2
    assert target_level_for_act(3) == 3
    assert target_level_for_act(4) == 3  # non oltre il livello 3 (§4)


def test_maybe_level_up_does_nothing_when_already_at_target_level():
    char, sheet, save = _setup()
    save["current_act"] = 1
    assert maybe_level_up(save, char, sheet) is None
    assert char["level"] == 1


def test_maybe_level_up_applies_gain_and_updates_hp(monkeypatch):
    char, sheet, save = _setup()
    save["current_act"] = 2
    hp_max_before = char["hp_max"]
    monkeypatch.setattr("rules.levelup.roll_die", lambda sides: 6)
    result = maybe_level_up(save, char, sheet)
    con_mod = sheet["ability_modifiers"]["cos"]
    assert result["new_level"] == 2
    assert result["hp_gain"] == 6 + con_mod
    assert char["level"] == 2
    assert char["hp_max"] == hp_max_before + result["hp_gain"]
    assert char["hp_current"] == sheet["hit_points"]["current"] + result["hp_gain"]


def test_maybe_level_up_reports_subclass_unlock_at_level_3(monkeypatch):
    char, sheet, save = _setup()
    save["current_act"] = 3
    monkeypatch.setattr("rules.levelup.roll_die", lambda sides: 5)
    result = maybe_level_up(save, char, sheet)
    assert result["new_level"] == 3
    assert result["subclass_unlocked"] == "Campione"


def test_maybe_level_up_is_idempotent_once_at_target():
    char, sheet, save = _setup()
    save["current_act"] = 2
    maybe_level_up(save, char, sheet)
    assert maybe_level_up(save, char, sheet) is None
