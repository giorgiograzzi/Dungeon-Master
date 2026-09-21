from __future__ import annotations

from app.game.diary import build_diary
from app.game.schema import new_game_save_data


def _plan():
    return {
        "title": "L'ombra su Carpi",
        "beats": [{"id": "b1", "objective": "Scopri la minaccia", "act": 1, "route": None}],
        "side_quests": [
            {"id": "sq1", "hook": "Un mercante chiede aiuto"},
            {"id": "sq2", "hook": "Una bambina ha perso il gatto"},
        ],
    }


def test_build_diary_hides_side_quests_not_yet_encountered():
    plan = _plan()
    save = new_game_save_data()
    diary = build_diary(plan, save)
    assert diary["side_quests"] == []
    assert diary["main_quest"]["objective"] == "Scopri la minaccia"


def test_build_diary_shows_encountered_side_quests_with_status():
    plan = _plan()
    save = new_game_save_data()
    save["side_quests_state"] = {"sq1": "aperta"}
    diary = build_diary(plan, save)
    assert len(diary["side_quests"]) == 1
    assert diary["side_quests"][0]["id"] == "sq1"
    assert diary["side_quests"][0]["status"] == "aperta"
    assert "aiutarti" in diary["side_quests"][0]["hint"]


def test_build_diary_includes_quest_notes():
    plan = _plan()
    save = new_game_save_data()
    save["quest_notes"] = ["Il mercante ha un debito col porto"]
    diary = build_diary(plan, save)
    assert diary["notes"] == ["Il mercante ha un debito col porto"]
