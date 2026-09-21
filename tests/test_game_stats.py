from __future__ import annotations

from app.game.schema import new_game_save_data
from app.game.stats import compute_stats


def test_compute_stats_on_fresh_save():
    save = new_game_save_data()
    assert compute_stats(save) == {
        "turns": 0, "rolls": 0, "natural_20": 0, "natural_1": 0, "hp_lost": 0, "items_used": 0,
    }


def test_compute_stats_counts_turns_rolls_and_naturals():
    save = new_game_save_data()
    save["turn_log"] = [
        {"turn_id": "t1", "roll": None},
        {"turn_id": "t2", "roll": {"d20": 20, "natural_20": True, "natural_1": False}},
        {"turn_id": "t3", "roll": {"d20": 1, "natural_20": False, "natural_1": True}},
        {"turn_id": "t4", "roll": {"d20": 10, "natural_20": False, "natural_1": False}},
    ]
    save["stats"] = {"hp_lost": 7, "items_used": 2}
    stats = compute_stats(save)
    assert stats["turns"] == 4
    assert stats["rolls"] == 3
    assert stats["natural_20"] == 1
    assert stats["natural_1"] == 1
    assert stats["hp_lost"] == 7
    assert stats["items_used"] == 2
