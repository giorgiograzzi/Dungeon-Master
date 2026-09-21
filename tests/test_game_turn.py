from __future__ import annotations

import pytest

from app.ai.client import FakeAIClient
from app.character.schema import new_character_data
from app.character.sheet import compute_sheet
from app.character.wizard import finalize_character, set_ability_scores, set_background, set_background_bonus, set_class, set_personal_details, set_species
from app.game.schema import new_game_save_data
from app.game.turn import DailyCapExceeded, play_turn
from rules.ability_scores import STANDARD_ARRAY

ABILITIES = ("for", "des", "cos", "int", "sag", "car")


def _character_data():
    data = new_character_data()
    set_species(data, "umano")
    set_class(data, "ladro", ["furtivita", "percezione", "atletica", "intuizione"], "A")
    set_background(data, "criminale")
    set_ability_scores(data, "standard_array", dict(zip(ABILITIES, STANDARD_ARRAY)))
    set_background_bonus(data, {"des": 2, "cos": 1})
    set_personal_details(data, "Ombra", {})
    finalize_character(data)
    return data


@pytest.fixture
def setup():
    char = _character_data()
    sheet = compute_sheet(char)
    save = new_game_save_data()
    return char, sheet, save


async def test_play_turn_without_roll(setup):
    char, sheet, save = setup
    result = await play_turn(
        character_sheet=sheet, character_data=char, save_data=save,
        action_text="Cammino lungo il corridoio", turn_id="t1",
        ai_client=FakeAIClient(), model="fake", system_prompt="", daily_cap=50,
    )
    assert result["roll"] is None
    assert result["narration"]
    assert save["turn_count"] == 1


async def test_play_turn_with_roll_uses_skill_bonus(setup):
    char, sheet, save = setup
    result = await play_turn(
        character_sheet=sheet, character_data=char, save_data=save,
        action_text="Provo a intrufolarmi con furtività nella stanza", turn_id="t2",
        ai_client=FakeAIClient(), model="fake", system_prompt="", daily_cap=50,
    )
    assert result["roll"] is not None
    expected_bonus = sheet["skills"]["furtivita"]["bonus"]
    assert result["roll"]["bonus"] == expected_bonus
    assert result["roll"]["total"] == result["roll"]["d20"] + expected_bonus


async def test_play_turn_is_idempotent_on_turn_id(setup):
    char, sheet, save = setup
    first = await play_turn(
        character_sheet=sheet, character_data=char, save_data=save,
        action_text="Attacco furtivo", turn_id="dup", ai_client=FakeAIClient(),
        model="fake", system_prompt="", daily_cap=50,
    )
    second = await play_turn(
        character_sheet=sheet, character_data=char, save_data=save,
        action_text="testo diverso stavolta", turn_id="dup", ai_client=FakeAIClient(),
        model="fake", system_prompt="", daily_cap=50,
    )
    assert first is second
    assert save["turn_count"] == 1  # non ritirato/riapplicato


async def test_daily_cap_enforced(setup):
    char, sheet, save = setup
    for i in range(3):
        await play_turn(
            character_sheet=sheet, character_data=char, save_data=save,
            action_text=f"azione {i}", turn_id=f"t{i}", ai_client=FakeAIClient(),
            model="fake", system_prompt="", daily_cap=3,
        )
    with pytest.raises(DailyCapExceeded):
        await play_turn(
            character_sheet=sheet, character_data=char, save_data=save,
            action_text="azione extra", turn_id="t-extra", ai_client=FakeAIClient(),
            model="fake", system_prompt="", daily_cap=3,
        )


async def test_effects_are_applied_to_character(setup):
    char, sheet, save = setup

    class DamageAIClient(FakeAIClient):
        def _fake_narrate_outcome(self, messages):
            return {"narration": "Subisci un colpo.", "options": [], "effects": [{"type": "hp_delta", "value": -3}]}

    hp_before = char["hp_current"]
    await play_turn(
        character_sheet=sheet, character_data=char, save_data=save,
        action_text="Mi butto nella mischia", turn_id="dmg", ai_client=DamageAIClient(),
        model="fake", system_prompt="", daily_cap=50,
    )
    assert char["hp_current"] == hp_before - 3
