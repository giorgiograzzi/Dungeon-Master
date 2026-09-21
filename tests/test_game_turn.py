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


async def test_start_combat_effect_resolves_monster_turn_first_if_it_wins_initiative(setup, monkeypatch):
    char, sheet, save = setup

    class AmbushAIClient(FakeAIClient):
        def _fake_narrate_outcome(self, messages):
            return {"narration": "Un goblin ti tende un'imboscata.", "options": [], "effects": [{"type": "start_combat", "value": ["goblin_guerriero"]}]}

    # Il giocatore tira basso, il goblin alto: l'iniziativa del goblin vince
    # (start_combat tira prima per il giocatore, poi per ogni mostro).
    rolls = iter([1, 20])
    monkeypatch.setattr("rules.combat.roll_die", lambda sides: next(rolls))
    hp_before = char["hp_current"]
    await play_turn(
        character_sheet=sheet, character_data=char, save_data=save,
        action_text="avanzo nel corridoio", turn_id="ambush", ai_client=AmbushAIClient(),
        model="fake", system_prompt="", daily_cap=50,
    )
    assert save["mode"] == "combat"
    # Il turno del goblin (iniziativa piu alta) e gia stato risolto: tocca al
    # giocatore, che altrimenti non avrebbe nessuna azione da compiere.
    assert save["combat"]["combatants"][save["combat"]["current_turn_index"]]["is_player"] is True
    assert char["hp_current"] <= hp_before  # il goblin ha potuto attaccare per primo


async def test_pacing_context_is_sent_to_the_ai_when_a_campaign_is_active(setup):
    char, sheet, save = setup
    save["campaign_plan"] = {"duration_target": "breve"}
    save["current_act"] = 1

    captured_messages = []

    class RecordingAIClient(FakeAIClient):
        async def call_tool(self, *, model, system, messages, tool, max_tokens=1536):
            captured_messages.append(list(messages))
            return await super().call_tool(model=model, system=system, messages=messages, tool=tool, max_tokens=max_tokens)

    await play_turn(
        character_sheet=sheet, character_data=char, save_data=save,
        action_text="Osservo la stanza", turn_id="pacing1", ai_client=RecordingAIClient(),
        model="fake", system_prompt="", daily_cap=50,
    )
    first_call_messages = captured_messages[0]
    assert len(first_call_messages) == 2
    assert "[ritmo]" in first_call_messages[0]["content"]
    assert first_call_messages[-1]["content"] == "Osservo la stanza"


async def test_no_pacing_context_without_an_active_campaign(setup):
    char, sheet, save = setup
    captured_messages = []

    class RecordingAIClient(FakeAIClient):
        async def call_tool(self, *, model, system, messages, tool, max_tokens=1536):
            captured_messages.append(list(messages))
            return await super().call_tool(model=model, system=system, messages=messages, tool=tool, max_tokens=max_tokens)

    await play_turn(
        character_sheet=sheet, character_data=char, save_data=save,
        action_text="Osservo la stanza", turn_id="nopacing", ai_client=RecordingAIClient(),
        model="fake", system_prompt="", daily_cap=50,
    )
    assert captured_messages[0] == [{"role": "user", "content": "Osservo la stanza"}]


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
