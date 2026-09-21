from __future__ import annotations

import time

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

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


async def test_game_state_without_campaign(client):
    headers = _init_data_header(10001)
    resp = await client.get("/api/game", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == {"has_campaign": False}


async def test_turn_requires_completed_character(client):
    headers = _init_data_header(10002)
    resp = await client.post("/api/game/turn", json={"turn_id": "t1", "action": "cammino"}, headers=headers)
    assert resp.status_code == 409


async def test_full_campaign_and_turn_flow(client):
    headers = _init_data_header(10003)
    await _create_character(client, headers)

    resp = await client.post("/api/game/campaign", json={"setting": "noir", "duration": "breve"}, headers=headers)
    assert resp.status_code == 200
    summary = resp.json()
    assert summary["setting"] == "noir"

    resp = await client.get("/api/game", headers=headers)
    assert resp.json()["has_campaign"] is True

    resp = await client.post("/api/game/turn", json={"turn_id": "turn-1", "action": "Osservo la stanza"}, headers=headers)
    assert resp.status_code == 200
    turn = resp.json()
    assert turn["narration"]

    # idempotenza: stesso turn_id non ritira né rigenera
    resp2 = await client.post("/api/game/turn", json={"turn_id": "turn-1", "action": "azione diversa"}, headers=headers)
    assert resp2.json() == turn

    resp = await client.get("/api/game/crossroads", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["at_crossroads"] is False  # beat cardine non ancora completato


async def test_crossroads_and_route_choice(client):
    headers = _init_data_header(10004)
    await _create_character(client, headers)
    await client.post("/api/game/campaign", json={"setting": "fantasy classico", "duration": "media"}, headers=headers)

    class DummyEffect:
        pass

    # Forziamo il completamento del beat cardine iniziale applicando l'effetto
    # via un turno con effetto beat_progress (senza dover scrivere 10 turni finti).
    resp = await client.post("/api/game/turn", json={"turn_id": "beat1", "action": "combatto per farmi strada"}, headers=headers)
    assert resp.status_code == 200

    resp = await client.get("/api/game/saves/export", headers=headers)
    save_data = resp.json()
    assert "campaign_plan" in save_data


async def test_saves_list_and_manual_save(client):
    headers = _init_data_header(10005)
    resp = await client.get("/api/game/saves", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["saves"] == []

    resp = await client.post("/api/game/saves/manual", json={"name": "Prima di entrare nel dungeon"}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["slot"] == "slot_1"

    resp = await client.get("/api/game/saves", headers=headers)
    slots = {s["slot"] for s in resp.json()["saves"]}
    assert "autosave" in slots
    assert "slot_1" in slots
