from __future__ import annotations

import time

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import settings
from app.db import Base, get_session
from app.main import app
from tests._helpers import BOT_TOKEN, build_init_data


def _init_data_header(telegram_id: int = 777) -> dict:
    fields = {"auth_date": str(int(time.time())), "user": f'{{"id": {telegram_id}, "first_name": "Prova"}}'}
    return {"X-Telegram-Init-Data": build_init_data(fields, BOT_TOKEN)}


@pytest_asyncio.fixture
async def client(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "bot_token", BOT_TOKEN)

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


async def test_options_endpoint_is_public_and_complete(client):
    resp = await client.get("/api/character/options")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["species"]) == 9
    assert len(body["classes"]) == 12
    assert len(body["backgrounds"]) == 4
    assert len(body["skills"]) == 18


async def test_character_endpoints_require_init_data(client):
    resp = await client.get("/api/character")
    assert resp.status_code == 422  # header mancante


async def test_full_creation_flow_via_api(client):
    headers = _init_data_header()

    resp = await client.get("/api/character", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "draft"

    resp = await client.post("/api/character/species", json={"species_id": "umano"}, headers=headers)
    assert resp.status_code == 200

    resp = await client.post(
        "/api/character/class",
        json={"class_id": "guerriero", "skill_choices": ["persuasione", "percezione"], "equipment_choice": "A"},
        headers=headers,
    )
    assert resp.status_code == 200

    resp = await client.post("/api/character/background", json={"background_id": "soldato"}, headers=headers)
    assert resp.status_code == 200

    resp = await client.post(
        "/api/character/ability-scores",
        json={"method": "standard_array", "scores": {"for": 15, "des": 12, "cos": 14, "int": 8, "sag": 10, "car": 13}},
        headers=headers,
    )
    assert resp.status_code == 200

    resp = await client.post(
        "/api/character/background-bonus", json={"bonus": {"for": 2, "cos": 1}}, headers=headers
    )
    assert resp.status_code == 200

    resp = await client.get("/api/character/sheet", headers=headers)
    assert resp.status_code == 409  # manca ancora il nome

    resp = await client.post(
        "/api/character/details", json={"name": "Marco", "details": {"appearance": "Alto"}}, headers=headers
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "complete"

    resp = await client.get("/api/character/sheet", headers=headers)
    assert resp.status_code == 200
    sheet = resp.json()
    assert sheet["name"] == "Marco"
    assert sheet["armor_class"] == 16


async def test_invalid_species_returns_400(client):
    headers = _init_data_header(telegram_id=888)
    resp = await client.post("/api/character/species", json={"species_id": "marziano"}, headers=headers)
    assert resp.status_code == 400


async def test_roll_ability_scores_endpoint(client):
    headers = _init_data_header(telegram_id=999)
    resp = await client.post("/api/character/ability-scores/roll", headers=headers)
    assert resp.status_code == 200
    rolled = resp.json()["rolled_scores"]
    assert len(rolled) == 6
    assert all(3 <= v <= 18 for v in rolled)

    resp = await client.post(
        "/api/character/ability-scores",
        json={"method": "4d6", "scores": dict(zip(["for", "des", "cos", "int", "sag", "car"], rolled))},
        headers=headers,
    )
    assert resp.status_code == 200
