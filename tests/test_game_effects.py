from __future__ import annotations

from app.character.schema import new_character_data
from app.game.effects import apply_effects
from app.game.schema import new_game_save_data


def _char():
    data = new_character_data()
    data["hp_current"] = 10
    data["hp_max"] = 10
    data["hp_temp"] = 0
    return data


def test_hp_delta_damage_and_heal():
    char = _char()
    save = new_game_save_data()
    apply_effects(char, save, [{"type": "hp_delta", "value": -4}])
    assert char["hp_current"] == 6
    apply_effects(char, save, [{"type": "hp_delta", "value": 2}])
    assert char["hp_current"] == 8


def test_temp_hp():
    char = _char()
    save = new_game_save_data()
    apply_effects(char, save, [{"type": "temp_hp", "value": 5}])
    assert char["hp_temp"] == 5


def test_item_add_and_remove():
    char = _char()
    save = new_game_save_data()
    apply_effects(char, save, [{"type": "item_add", "target": "torcia"}])
    assert "torcia" in char["inventory"]
    apply_effects(char, save, [{"type": "item_remove", "target": "torcia"}])
    assert "torcia" not in char["inventory"]


def test_condition_add_remove_deduplicated():
    char = _char()
    save = new_game_save_data()
    apply_effects(char, save, [{"type": "condition_add", "target": "prono"}, {"type": "condition_add", "target": "prono"}])
    assert char["conditions"] == ["prono"]
    apply_effects(char, save, [{"type": "condition_remove", "target": "prono"}])
    assert "prono" not in char["conditions"]


def test_gold_accumulates():
    char = _char()
    save = new_game_save_data()
    apply_effects(char, save, [{"type": "gold", "value": 10}, {"type": "gold", "value": -3}])
    assert char["gold_adjustment"] == 7


def test_fact_add_deduplicated():
    char = _char()
    save = new_game_save_data()
    apply_effects(char, save, [{"type": "fact_add", "value": "il ponte è crollato"}] * 2)
    assert save["facts"] == ["il ponte è crollato"]


def test_start_combat_stashes_monster_ids_for_the_caller():
    # L'effetto segna solo l'intenzione: il vero avvio (iniziativa, stat
    # block) lo fa app.game.combat.start_combat, che ha bisogno della scheda.
    char = _char()
    save = new_game_save_data()
    apply_effects(char, save, [{"type": "start_combat", "value": ["goblin_guerriero"]}])
    assert save["_pending_combat_monsters"] == ["goblin_guerriero"]


def test_end_combat_resets_mode_and_state():
    char = _char()
    save = new_game_save_data()
    save["mode"] = "combat"
    save["combat"] = {"round": 2}
    apply_effects(char, save, [{"type": "end_combat"}])
    assert save["mode"] == "exploration"
    assert save["combat"] is None


def test_beat_progress_and_gate_solved():
    char = _char()
    save = new_game_save_data()
    apply_effects(char, save, [{"type": "beat_progress", "target": "incidente_scatenante"}])
    assert save["completed_beats"] == ["incidente_scatenante"]
    apply_effects(char, save, [{"type": "gate_solved", "target": "gate_parola"}])
    assert save["solved_gates"] == ["gate_parola"]


def test_side_quest_lifecycle():
    char = _char()
    save = new_game_save_data()
    apply_effects(char, save, [{"type": "side_quest_start", "target": "sq1"}])
    assert save["side_quests_state"]["sq1"] == "aperta"
    apply_effects(char, save, [{"type": "side_quest_complete", "target": "sq1"}])
    assert save["side_quests_state"]["sq1"] == "completata"


def test_side_quest_complete_registers_reward_from_campaign_plan():
    char = _char()
    save = new_game_save_data()
    save["campaign_plan"] = {
        "side_quests": [{"id": "sq1", "reward": {"type": "indizio", "effect": "svela il covo"}, "unlocks": "un alleato"}]
    }
    apply_effects(char, save, [{"type": "side_quest_complete", "target": "sq1"}] * 2)  # deduplicato
    assert save["rewards_obtained"] == [{"quest_id": "sq1", "reward": {"type": "indizio", "effect": "svela il covo"}, "unlocks": "un alleato"}]


def test_side_quest_complete_without_campaign_plan_does_not_crash():
    char = _char()
    save = new_game_save_data()
    apply_effects(char, save, [{"type": "side_quest_complete", "target": "sq1"}])
    assert save["side_quests_state"]["sq1"] == "completata"
    assert save["rewards_obtained"] == []


def test_ending_reached_valid_id():
    char = _char()
    save = new_game_save_data()
    save["campaign_plan"] = {"endings": [{"id": "finale_vittoria", "title": "Vittoria"}]}
    apply_effects(char, save, [{"type": "ending_reached", "target": "finale_vittoria"}])
    assert save["ended"] is True
    assert save["ending_id"] == "finale_vittoria"


def test_ending_reached_unknown_id_is_rejected():
    char = _char()
    save = new_game_save_data()
    save["campaign_plan"] = {"endings": [{"id": "finale_vittoria", "title": "Vittoria"}]}
    apply_effects(char, save, [{"type": "ending_reached", "target": "finale_inventato"}])
    assert save["ended"] is False
    assert save["ending_id"] is None


def test_hp_delta_damage_tracks_hp_lost_stat():
    char = _char()
    save = new_game_save_data()
    apply_effects(char, save, [{"type": "hp_delta", "value": -4}])
    assert save["stats"]["hp_lost"] == 4
    apply_effects(char, save, [{"type": "hp_delta", "value": 2}])  # curare non conta come "perso"
    assert save["stats"]["hp_lost"] == 4


def test_item_remove_tracks_items_used_stat():
    char = _char()
    save = new_game_save_data()
    apply_effects(char, save, [{"type": "item_add", "target": "pozione"}])
    apply_effects(char, save, [{"type": "item_remove", "target": "pozione"}])
    assert save["stats"]["items_used"] == 1


def test_route_chosen():
    char = _char()
    save = new_game_save_data()
    apply_effects(char, save, [{"type": "route_chosen", "value": "ombra"}])
    assert save["current_route_id"] == "ombra"


def test_npc_attitude_learned_status():
    char = _char()
    save = new_game_save_data()
    apply_effects(
        char, save,
        [
            {"type": "npc_attitude", "target": "png_1", "value": 2},
            {"type": "npc_learned", "target": "png_1", "value": "conosce il covo"},
            {"type": "npc_status", "target": "png_1", "value": "alleato"},
        ],
    )
    npc = save["npc_state"]["png_1"]
    assert npc["attitude"] == 2
    assert npc["known"] == ["conosce il covo"]
    assert npc["status"] == "alleato"


def test_unknown_effect_type_is_skipped_not_crashing():
    char = _char()
    save = new_game_save_data()
    applied = apply_effects(char, save, [{"type": "teletrasporto_magico", "value": 1}])
    assert applied == []
