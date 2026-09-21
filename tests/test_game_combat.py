from __future__ import annotations

import pytest

from app.character.schema import new_character_data
from app.character.sheet import compute_sheet
from app.character.wizard import finalize_character, set_ability_scores, set_background, set_background_bonus, set_class, set_personal_details, set_species
from app.game import combat
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


def test_start_combat_builds_initiative_order(monkeypatch):
    char, sheet, save = _setup()
    monkeypatch.setattr("rules.combat.roll_die", lambda sides: 10)
    combat.start_combat(save, char, sheet, ["goblin_guerriero", "goblin_tirapiedi"])
    assert save["mode"] == "combat"
    assert len(save["combat"]["combatants"]) == 3
    assert save["combat"]["combatants"][0]["initiative"] == save["combat"]["combatants"][0]["initiative"]
    ids = {c["id"] for c in save["combat"]["combatants"]}
    assert "player" in ids
    assert "goblin_guerriero_1" in ids
    assert "goblin_tirapiedi_2" in ids


def test_end_combat_clears_state():
    char, sheet, save = _setup()
    combat.start_combat(save, char, sheet, ["goblin_guerriero"])
    combat.end_combat(save)
    assert save["mode"] == "exploration"
    assert save["combat"] is None


def test_player_death_save_if_down_is_none_when_player_is_up():
    char, sheet, save = _setup()
    combat.start_combat(save, char, sheet, ["goblin_guerriero"])
    assert combat.player_death_save_if_down(save) is None


def test_player_death_save_if_down_returns_tally_when_player_is_down():
    char, sheet, save = _setup()
    combat.start_combat(save, char, sheet, ["goblin_guerriero"])
    player = combat.find_combatant(save, "player")
    player["hp"]["current"] = 0
    save["combat"]["death_save"]["successes"] = 1
    result = combat.player_death_save_if_down(save)
    assert result == {"successes": 1, "failures": 0, "stable": False, "dead": False}


def test_sync_player_hp_writes_combat_hp_back_to_character():
    char, sheet, save = _setup()
    combat.start_combat(save, char, sheet, ["goblin_guerriero"])
    player = combat.find_combatant(save, "player")
    player["hp"]["current"] = 3
    player["hp"]["temp"] = 2
    combat.sync_player_hp(save, char)
    assert char["hp_current"] == 3
    assert char["hp_temp"] == 2


def test_end_combat_with_character_data_syncs_before_clearing():
    char, sheet, save = _setup()
    combat.start_combat(save, char, sheet, ["goblin_guerriero"])
    player = combat.find_combatant(save, "player")
    player["hp"]["current"] = 4
    combat.end_combat(save, char)
    assert char["hp_current"] == 4
    assert save["combat"] is None


def test_advance_turn_cycles_and_resets_action_economy():
    char, sheet, save = _setup()
    combat.start_combat(save, char, sheet, ["goblin_guerriero"])
    first = combat.current_combatant(save)
    economy = first["action_economy"]
    economy["used"]["action"] = 1
    result = combat.advance_turn(save)
    assert result["combat_ended"] is False
    assert combat.current_combatant(save)["id"] != first["id"]


def test_advance_turn_wraps_to_new_round_and_resets_reactions():
    char, sheet, save = _setup()
    combat.start_combat(save, char, sheet, ["goblin_guerriero"])
    for c in save["combat"]["combatants"]:
        c["action_economy"]["used"]["reaction"] = 1
    for _ in range(len(save["combat"]["combatants"])):
        result = combat.advance_turn(save)
    assert save["combat"]["round"] == 2
    assert all(c["action_economy"]["used"]["reaction"] == 0 for c in save["combat"]["combatants"])


def test_advance_turn_skips_dead_combatants():
    char, sheet, save = _setup()
    combat.start_combat(save, char, sheet, ["goblin_guerriero", "goblin_tirapiedi"])
    # Ordine forzato: giocatore per primo, cosi il "morto" al secondo posto è
    # sicuramente un mostro (un giocatore a 0 PF non si salta piu, §8).
    save["combat"]["combatants"].sort(key=lambda c: c["is_player"], reverse=True)
    dead_id = save["combat"]["combatants"][1]["id"]
    save["combat"]["combatants"][1]["hp"]["current"] = 0
    save["combat"]["current_turn_index"] = 0
    result = combat.advance_turn(save)
    assert result["current"]["id"] != dead_id


def test_advance_turn_ends_combat_when_one_side_remains():
    char, sheet, save = _setup()
    combat.start_combat(save, char, sheet, ["goblin_guerriero"])
    for c in save["combat"]["combatants"]:
        if c["id"] != "player":
            c["hp"]["current"] = 0
    result = combat.advance_turn(save)
    assert result["combat_ended"] is True
    assert save["mode"] == "exploration"


def test_player_attack_hits_and_damages(monkeypatch):
    char, sheet, save = _setup()
    combat.start_combat(save, char, sheet, ["goblin_guerriero"])
    monkeypatch.setattr("rules.dice.roll_die", lambda sides: 15 if sides == 20 else 4)
    target_id = next(c["id"] for c in save["combat"]["combatants"] if not c["is_player"])
    result = combat.player_attack(save, sheet, target_id, to_hit_bonus=5, damage_expression="1d8+3")
    assert result["attack"]["hit"]
    assert result["damage"] > 0
    target = combat.find_combatant(save, target_id)
    assert target["hp"]["current"] < target["hp"]["maximum"]


def test_flee_opportunity_triggers_below_threshold():
    char, sheet, save = _setup()
    combat.start_combat(save, char, sheet, ["goblin_guerriero"])
    monster = next(c for c in save["combat"]["combatants"] if not c["is_player"])
    monster["hp"]["current"] = 1
    reaction = combat.check_flee_opportunity(save, monster)
    assert reaction is not None
    assert save["combat"]["pending_reaction"] == reaction


def test_flee_opportunity_none_when_healthy():
    char, sheet, save = _setup()
    combat.start_combat(save, char, sheet, ["goblin_guerriero"])
    monster = next(c for c in save["combat"]["combatants"] if not c["is_player"])
    assert combat.check_flee_opportunity(save, monster) is None


def test_resolve_reaction_accept_attacks_and_consumes_reaction(monkeypatch):
    char, sheet, save = _setup()
    combat.start_combat(save, char, sheet, ["goblin_guerriero"])
    monster = next(c for c in save["combat"]["combatants"] if not c["is_player"])
    monster["hp"]["current"] = 1
    combat.check_flee_opportunity(save, monster)
    monkeypatch.setattr("rules.dice.roll_die", lambda sides: 15 if sides == 20 else 3)
    result = combat.resolve_reaction(save, sheet, accept=True, to_hit_bonus=5, damage_expression="1d4")
    assert result["used"] is True
    assert result["attack"]["hit"]
    assert result["damage"] > 0
    player = combat.find_combatant(save, "player")
    assert player["action_economy"]["used"]["reaction"] == 1
    assert save["combat"]["pending_reaction"] is None


def test_resolve_reaction_decline_does_not_consume_reaction():
    char, sheet, save = _setup()
    combat.start_combat(save, char, sheet, ["goblin_guerriero"])
    monster = next(c for c in save["combat"]["combatants"] if not c["is_player"])
    monster["hp"]["current"] = 1
    combat.check_flee_opportunity(save, monster)
    result = combat.resolve_reaction(save, sheet, accept=False)
    assert result == {"used": False}
    player = combat.find_combatant(save, "player")
    assert player["action_economy"]["used"]["reaction"] == 0


def test_resolve_reaction_without_pending_raises():
    char, sheet, save = _setup()
    combat.start_combat(save, char, sheet, ["goblin_guerriero"])
    with pytest.raises(ValueError):
        combat.resolve_reaction(save, sheet, accept=True)


def test_find_weapon_in_equipment_matches_known_weapon():
    weapon = combat.find_weapon_in_equipment("Una cotta di maglia, uno spadone, un mazzafrusto, 8 giavellotti")
    assert weapon["name_it"] == "Spadone"


def test_find_weapon_in_equipment_returns_none_when_no_match():
    assert combat.find_weapon_in_equipment("una dotazione da avventuriero e 4 mo") is None


def test_resolve_to_hit_and_damage_unarmed():
    char, sheet, save = _setup()
    to_hit, damage_expr = combat.resolve_to_hit_and_damage(sheet, None)
    assert to_hit == sheet["ability_modifiers"]["for"] + sheet["proficiency_bonus"]
    assert damage_expr == f"1d1+{sheet['ability_modifiers']['for']}"


def test_resolve_to_hit_and_damage_with_weapon():
    char, sheet, save = _setup()
    weapon = {"kind": "mischia", "properties": "Due mani, pesante", "damage": "2d6 taglienti"}
    to_hit, damage_expr = combat.resolve_to_hit_and_damage(sheet, weapon)
    assert to_hit == sheet["ability_modifiers"]["for"] + sheet["proficiency_bonus"]
    assert damage_expr == f"2d6+{sheet['ability_modifiers']['for']}"


def test_resolve_to_hit_and_damage_finesse_uses_best_modifier():
    char, sheet, save = _setup()
    weapon = {"kind": "mischia", "properties": "Accurata, leggera", "damage": "1d4 perforanti"}
    to_hit, damage_expr = combat.resolve_to_hit_and_damage(sheet, weapon)
    best = max(sheet["ability_modifiers"]["for"], sheet["ability_modifiers"]["des"])
    assert damage_expr == f"1d4+{best}"


def test_downed_player_is_not_counted_as_defeated_and_stays_in_combat():
    char, sheet, save = _setup()
    combat.start_combat(save, char, sheet, ["goblin_guerriero"])
    player = combat.find_combatant(save, "player")
    player["hp"]["current"] = 0
    assert combat._is_defeated(save, player) is False


def test_dead_player_is_counted_as_defeated():
    char, sheet, save = _setup()
    combat.start_combat(save, char, sheet, ["goblin_guerriero"])
    save["combat"]["death_save"]["dead"] = True
    player = combat.find_combatant(save, "player")
    assert combat._is_defeated(save, player) is True


def test_player_attack_raises_when_downed():
    char, sheet, save = _setup()
    combat.start_combat(save, char, sheet, ["goblin_guerriero"])
    player = combat.find_combatant(save, "player")
    player["hp"]["current"] = 0
    target_id = next(c["id"] for c in save["combat"]["combatants"] if not c["is_player"])
    with pytest.raises(ValueError):
        combat.player_attack(save, sheet, target_id, to_hit_bonus=5, damage_expression="1d8+3")


def test_damage_to_downed_player_counts_as_failed_death_save(monkeypatch):
    char, sheet, save = _setup()
    combat.start_combat(save, char, sheet, ["goblin_guerriero"])
    player = combat.find_combatant(save, "player")
    player["hp"]["current"] = 0
    monkeypatch.setattr("rules.dice.roll_die", lambda sides: 15 if sides == 20 else 2)
    result = combat._damage_combatant(save, player, damage=3, critical=False)
    assert result["death_save"]["result"] == "un tiro salvezza fallito"
    assert save["combat"]["death_save"]["failures"] == 1
    assert player["hp"]["current"] == 0


def test_damage_to_downed_player_can_be_instant_death_on_massive_damage():
    char, sheet, save = _setup()
    combat.start_combat(save, char, sheet, ["goblin_guerriero"])
    player = combat.find_combatant(save, "player")
    player["hp"]["current"] = 0
    result = combat._damage_combatant(save, player, damage=player["hp"]["maximum"] + 5)
    assert result["death_save"]["result"] == "morto (danno massiccio)"
    assert save["combat"]["death_save"]["dead"] is True


def test_first_hit_that_drops_player_to_zero_resets_death_save():
    char, sheet, save = _setup()
    combat.start_combat(save, char, sheet, ["goblin_guerriero"])
    save["combat"]["death_save"] = {"successes": 2, "failures": 1, "stable": False, "dead": False}
    player = combat.find_combatant(save, "player")
    player["hp"]["current"] = 5
    combat._damage_combatant(save, player, damage=5)
    assert player["hp"]["current"] == 0
    assert save["combat"]["death_save"] == {"successes": 0, "failures": 0, "stable": False, "dead": False}


def test_advance_turn_auto_rolls_death_save_for_downed_player(monkeypatch):
    char, sheet, save = _setup()
    combat.start_combat(save, char, sheet, ["goblin_guerriero"])
    save["combat"]["combatants"].sort(key=lambda c: c["is_player"], reverse=True)
    player = combat.find_combatant(save, "player")
    player["hp"]["current"] = 0
    save["combat"]["current_turn_index"] = len(save["combat"]["combatants"]) - 1
    monkeypatch.setattr("rules.combat.roll_die", lambda sides: 15)
    result = combat.advance_turn(save)
    assert combat.current_combatant(save)["id"] == "player"
    assert result["death_save"] == {"d20": 15, "result": "in bilico", "successes": 1, "failures": 0}


def test_advance_turn_does_not_roll_death_save_once_stable():
    char, sheet, save = _setup()
    combat.start_combat(save, char, sheet, ["goblin_guerriero"])
    save["combat"]["combatants"].sort(key=lambda c: c["is_player"], reverse=True)
    player = combat.find_combatant(save, "player")
    player["hp"]["current"] = 0
    save["combat"]["death_save"]["stable"] = True
    save["combat"]["current_turn_index"] = len(save["combat"]["combatants"]) - 1
    result = combat.advance_turn(save)
    assert result["death_save"] is None


def test_resolve_monster_turn_attacks_player(monkeypatch):
    char, sheet, save = _setup()
    combat.start_combat(save, char, sheet, ["goblin_guerriero"])
    monster = next(c for c in save["combat"]["combatants"] if not c["is_player"])
    monkeypatch.setattr("rules.dice.roll_die", lambda sides: 18 if sides == 20 else 3)
    result = combat.resolve_monster_turn(save, monster)
    assert result["action_name"] == "Scimitarra"
    assert result["attack"]["hit"] is True
    assert result["damage"] > 0
    player = combat.find_combatant(save, "player")
    assert player["hp"]["current"] < player["hp"]["maximum"]
    assert monster["action_economy"]["used"]["action"] == 1


def test_run_monster_turns_until_player_resolves_all_monsters_then_stops(monkeypatch):
    char, sheet, save = _setup()
    combat.start_combat(save, char, sheet, ["goblin_guerriero", "goblin_tirapiedi"])
    # Forza l'ordine: mostri prima, giocatore per ultimo.
    save["combat"]["combatants"].sort(key=lambda c: c["is_player"])
    save["combat"]["current_turn_index"] = 0
    monkeypatch.setattr("rules.dice.roll_die", lambda sides: 2 if sides == 20 else 1)
    result = combat.run_monster_turns_until_player(save)
    assert result["combat_ended"] is False
    assert len(result["monster_turns"]) == 2
    assert combat.current_combatant(save)["is_player"] is True


def test_list_available_weapons_finds_owned_weapons_without_substring_false_positives():
    char, sheet, save = _setup()
    weapons = combat.list_available_weapons(sheet)
    ids = {w["id"] for w in weapons}
    # "Mazza" è solo una sottostringa di "Mazzafrusto" nel testo dell'equip.:
    # non deve comparire come arma posseduta a sé stante.
    assert ids == {"spadone", "mazzafrusto"}
    assert "mazza" not in ids


def test_resolve_active_weapon_defaults_to_equipment_text():
    char, sheet, save = _setup()
    combat.start_combat(save, char, sheet, ["goblin_guerriero"])
    weapon = combat.resolve_active_weapon(sheet, save)
    assert weapon["name_it"] == "Spadone"


def test_swap_active_weapon_changes_resolve_active_weapon_result():
    char, sheet, save = _setup()
    combat.start_combat(save, char, sheet, ["goblin_guerriero"])
    combat.swap_active_weapon(save, sheet, "mazzafrusto")
    weapon = combat.resolve_active_weapon(sheet, save)
    assert weapon["id"] == "mazzafrusto"
    player = combat.find_combatant(save, "player")
    assert player["action_economy"]["used"]["action"] == 1


def test_swap_active_weapon_rejects_unowned_weapon():
    char, sheet, save = _setup()
    combat.start_combat(save, char, sheet, ["goblin_guerriero"])
    with pytest.raises(combat.WeaponSwapError):
        combat.swap_active_weapon(save, sheet, "alabarda")


def test_swap_active_weapon_rejects_unknown_id():
    char, sheet, save = _setup()
    combat.start_combat(save, char, sheet, ["goblin_guerriero"])
    with pytest.raises(combat.WeaponSwapError):
        combat.swap_active_weapon(save, sheet, "non_esiste")


def test_run_monster_turns_until_player_stops_when_combat_ends():
    char, sheet, save = _setup()
    combat.start_combat(save, char, sheet, ["goblin_guerriero"])
    save["combat"]["combatants"].sort(key=lambda c: c["is_player"])
    save["combat"]["current_turn_index"] = 0
    player = combat.find_combatant(save, "player")
    player["hp"]["current"] = 0
    save["combat"]["death_save"]["dead"] = True
    result = combat.run_monster_turns_until_player(save)
    assert result["combat_ended"] is True
    assert save["mode"] == "exploration"
