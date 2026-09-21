from __future__ import annotations

from app.ai.client import FakeAIClient
from app.game.schema import new_game_save_data
from app.game.story import export_story


async def test_export_story_returns_fake_text_and_includes_context():
    save = new_game_save_data()
    save["campaign_plan"] = {"title": "L'ombra su Carpi", "premise": "Una minaccia emerge dall'ombra."}
    save["facts"] = ["il covo è nelle fogne"]
    save["turn_log"] = [{"action": "Osservo la stanza", "narration": "Non trovi nulla di insolito."}]
    sheet = {"name": "Marco", "species": "Umano", "class_": "Guerriero"}

    story_text = await export_story(
        ai_client=FakeAIClient(), model="fake", system_prompt="", character_sheet=sheet, save_data=save,
    )
    assert isinstance(story_text, str)
    assert story_text
