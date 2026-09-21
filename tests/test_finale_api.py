from __future__ import annotations

import time

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.ai.client import FakeAIClient
from app.config import settings
from app.db import Base, get_session
from app.main import app
from tests._helpers import BOT_TOKEN, build_init_data


def _init_data_header(telegram_id: int) -> dict:
    fields = {"auth_date": str(int(time.time())), "user": f'{{"id": {telegram_id}, "first_name": "Prova"}}'}
    return {"X-Telegram-Init-Data": build_init_data(fields, BOT_TOKEN)}


@pytest_asyncio.fixture
async def client(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "bot_token", BOT_TOKEN)
    monkeypatch.setattr(settings, "dev_fake_ai", True)

    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/test.db")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_session():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
    await engine.dispose()


async def _create_character(client, headers):
    await client.post("/api/character/species", json={"species_id": "umano"}, headers=headers)
    await client.post(
        "/api/character/class",
        json={"class_id": "ladro", "skill_choices": ["furtivita", "percezione", "atletica", "intuizione"], "equipment_choice": "A"},
        headers=headers,
    )
    await client.post("/api/character/background", json={"background_id": "criminale"}, headers=headers)
    await client.post(
        "/api/character/ability-scores",
        json={"method": "standard_array", "scores": {"for": 10, "des": 15, "cos": 14, "int": 13, "sag": 12, "car": 8}},
        headers=headers,
    )
    await client.post("/api/character/background-bonus", json={"bonus": {"des": 2, "cos": 1}}, headers=headers)
    resp = await client.post("/api/character/details", json={"name": "Ombra", "details": {}}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "complete"


def _patch_narrate_with_effects(monkeypatch, effects: list[dict]) -> None:
    def fake_narrate(self, messages):
        return {"narration": "Un evento scriptato per il test.", "options": [], "effects": effects}

    monkeypatch.setattr(FakeAIClient, "_fake_narrate_outcome", fake_narrate)


async def test_finale_requires_ended_campaign(client):
    headers = _init_data_header(30001)
    await _create_character(client, headers)
    await client.post("/api/game/campaign", json={"setting": "noir", "duration": "breve"}, headers=headers)
    resp = await client.get("/api/game/finale", headers=headers)
    assert resp.status_code == 409


async def test_finale_returns_ending_stats_and_rewards(client, monkeypatch):
    headers = _init_data_header(30002)
    await _create_character(client, headers)
    await client.post("/api/game/campaign", json={"setting": "noir", "duration": "breve"}, headers=headers)

    _patch_narrate_with_effects(monkeypatch, [
        {"type": "hp_delta", "value": -3},
        {"type": "side_quest_complete", "target": "secondaria_1"},
        {"type": "ending_reached", "target": "finale_vittoria"},
    ])
    resp = await client.post("/api/game/turn", json={"turn_id": "climax", "action": "affronto l'antagonista"}, headers=headers)
    assert resp.status_code == 200

    resp = await client.get("/api/game/finale", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["ending"]["id"] == "finale_vittoria"
    assert body["epilogue"]
    assert body["stats"]["turns"] == 1
    assert body["stats"]["hp_lost"] == 3
    assert len(body["rewards_obtained"]) == 1
    assert body["rewards_obtained"][0]["quest_id"] == "secondaria_1"


async def test_diary_shows_only_encountered_side_quests(client, monkeypatch):
    headers = _init_data_header(30003)
    await _create_character(client, headers)
    await client.post("/api/game/campaign", json={"setting": "noir", "duration": "breve"}, headers=headers)

    resp = await client.get("/api/game/diary", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["side_quests"] == []

    _patch_narrate_with_effects(monkeypatch, [{"type": "side_quest_start", "target": "secondaria_1"}])
    await client.post("/api/game/turn", json={"turn_id": "sq1", "action": "parlo con il locandiere"}, headers=headers)

    resp = await client.get("/api/game/diary", headers=headers)
    side_quests = resp.json()["side_quests"]
    assert len(side_quests) == 1
    assert side_quests[0]["id"] == "secondaria_1"
    assert side_quests[0]["status"] == "aperta"


async def test_story_export_endpoint_returns_text(client):
    headers = _init_data_header(30004)
    await _create_character(client, headers)
    await client.post("/api/game/campaign", json={"setting": "noir", "duration": "breve"}, headers=headers)
    resp = await client.get("/api/game/story", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["story_text"]


async def test_rewind_endpoint_restores_pre_crossroad_state(client, monkeypatch):
    headers = _init_data_header(30005)
    await _create_character(client, headers)
    await client.post("/api/game/campaign", json={"setting": "noir", "duration": "breve"}, headers=headers)
    _patch_narrate_with_effects(monkeypatch, [{"type": "beat_progress", "target": "incidente_scatenante"}])
    await client.post("/api/game/turn", json={"turn_id": "beat1", "action": "combatto per farmi strada"}, headers=headers)

    resp = await client.post("/api/game/crossroads/choose", json={"route_id": "ombra"}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["current_act"] == 2

    resp = await client.post("/api/game/rewind", json={"crossroad_index": 0}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["current_act"] == 1

    resp = await client.post("/api/game/crossroads/choose", json={"route_id": "acciaio"}, headers=headers)
    assert resp.status_code == 200


async def test_load_save_endpoint_restores_a_manual_slot(client, monkeypatch):
    headers = _init_data_header(30006)
    await _create_character(client, headers)
    await client.post("/api/game/campaign", json={"setting": "noir", "duration": "breve"}, headers=headers)

    resp = await client.post("/api/game/saves/manual", json={"name": "Prima del covo"}, headers=headers)
    assert resp.status_code == 200
    slot = resp.json()["slot"]

    _patch_narrate_with_effects(monkeypatch, [{"type": "hp_delta", "value": -100}])
    await client.post("/api/game/turn", json={"turn_id": "danno-fatale", "action": "vengo colpito"}, headers=headers)

    resp = await client.post("/api/game/saves/load", json={"slot": slot}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["has_campaign"] is True

    resp = await client.get("/api/game", headers=headers)
    assert resp.json()["turn_count"] == 0  # tornato allo stato salvato prima del danno


async def test_load_save_endpoint_rejects_unknown_slot(client):
    headers = _init_data_header(30007)
    resp = await client.post("/api/game/saves/load", json={"slot": "slot_3"}, headers=headers)
    assert resp.status_code == 400
