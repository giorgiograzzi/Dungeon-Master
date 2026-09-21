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
    """Guerriero/Soldato con equipaggiamento (A): cotta di maglia, spadone,
    mazzafrusto, giavellotti -- coerente con tests/test_game_combat.py."""
    await client.post("/api/character/species", json={"species_id": "umano"}, headers=headers)
    await client.post(
        "/api/character/class",
        json={"class_id": "guerriero", "skill_choices": ["percezione", "intimidire"], "equipment_choice": "A"},
        headers=headers,
    )
    await client.post("/api/character/background", json={"background_id": "soldato"}, headers=headers)
    await client.post(
        "/api/character/ability-scores",
        json={"method": "standard_array", "scores": {"for": 15, "des": 14, "cos": 13, "int": 12, "sag": 10, "car": 8}},
        headers=headers,
    )
    await client.post("/api/character/background-bonus", json={"bonus": {"for": 2, "cos": 1}}, headers=headers)
    resp = await client.post("/api/character/details", json={"name": "Marco", "details": {}}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "complete"


def _patch_narrate_with_effects(monkeypatch, effects: list[dict]) -> None:
    def fake_narrate(self, messages):
        return {"narration": "Un evento scriptato per il test.", "options": [], "effects": effects}

    monkeypatch.setattr(FakeAIClient, "_fake_narrate_outcome", fake_narrate)


async def _start_combat_via_turn(client, headers, monkeypatch, extra_effects: list[dict] | None = None) -> None:
    effects = [{"type": "start_combat", "value": ["goblin_guerriero"]}] + (extra_effects or [])
    _patch_narrate_with_effects(monkeypatch, effects)
    resp = await client.post("/api/game/turn", json={"turn_id": "imboscata", "action": "avanzo nel corridoio"}, headers=headers)
    assert resp.status_code == 200


async def test_combat_state_when_not_in_combat(client):
    headers = _init_data_header(20001)
    await _create_character(client, headers)
    resp = await client.get("/api/game/combat", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == {"in_combat": False}


async def test_turn_effect_starts_combat_and_state_reflects_it(client, monkeypatch):
    headers = _init_data_header(20002)
    await _create_character(client, headers)
    await _start_combat_via_turn(client, headers, monkeypatch)

    resp = await client.get("/api/game/combat", headers=headers)
    state = resp.json()
    assert state["in_combat"] is True
    assert len(state["combatants"]) == 2
    assert any(c["is_player"] for c in state["combatants"])
    assert any(not c["is_player"] for c in state["combatants"])
    assert state["active_weapon"] == "Spadone"
    assert {"id": "mazzafrusto", "name_it": "Mazzafrusto"} in state["available_weapons"]


async def test_attack_endpoint_hits_and_reduces_target_hp(client, monkeypatch):
    headers = _init_data_header(20003)
    await _create_character(client, headers)
    await _start_combat_via_turn(client, headers, monkeypatch)

    state = (await client.get("/api/game/combat", headers=headers)).json()
    target_id = next(c["id"] for c in state["combatants"] if not c["is_player"])

    monkeypatch.setattr("rules.dice.roll_die", lambda sides: 15 if sides == 20 else 4)
    resp = await client.post("/api/game/combat/attack", json={"target_id": target_id}, headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["result"]["attack"]["hit"] is True
    assert body["result"]["damage"] > 0
    target = next(c for c in body["state"]["combatants"] if c["id"] == target_id)
    assert target["hp"]["current"] < target["hp"]["maximum"]


async def test_attack_endpoint_rejects_unknown_target(client, monkeypatch):
    headers = _init_data_header(20004)
    await _create_character(client, headers)
    await _start_combat_via_turn(client, headers, monkeypatch)

    resp = await client.post("/api/game/combat/attack", json={"target_id": "non_esiste"}, headers=headers)
    assert resp.status_code == 400


async def test_attack_endpoint_requires_active_combat(client):
    headers = _init_data_header(20005)
    await _create_character(client, headers)
    resp = await client.post("/api/game/combat/attack", json={"target_id": "qualsiasi"}, headers=headers)
    assert resp.status_code == 409


async def test_advance_endpoint_moves_turn_and_may_run_monster_phase(client, monkeypatch):
    headers = _init_data_header(20006)
    await _create_character(client, headers)
    await _start_combat_via_turn(client, headers, monkeypatch)

    monkeypatch.setattr("rules.dice.roll_die", lambda sides: 2 if sides == 20 else 1)
    resp = await client.post("/api/game/combat/advance", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "advance" in body
    # con solo 2 combattenti, dopo l'avanzamento tocca di nuovo al giocatore
    # (l'eventuale turno del mostro viene auto-risolto).
    assert body["state"]["in_combat"] is True
    assert body["state"]["current_turn_id"] == "player"


async def test_weapon_swap_endpoint_switches_active_weapon(client, monkeypatch):
    headers = _init_data_header(20007)
    await _create_character(client, headers)
    await _start_combat_via_turn(client, headers, monkeypatch)

    resp = await client.post("/api/game/combat/weapon-swap", json={"weapon_id": "mazzafrusto"}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["weapon"] == "Mazzafrusto"

    state = resp.json()["state"]
    player = next(c for c in state["combatants"] if c["is_player"])
    assert player["used"]["action"] == 1


async def test_attack_endpoint_returns_conflict_when_action_already_spent(client, monkeypatch):
    headers = _init_data_header(20011)
    await _create_character(client, headers)
    await _start_combat_via_turn(client, headers, monkeypatch)

    state = (await client.get("/api/game/combat", headers=headers)).json()
    target_id = next(c["id"] for c in state["combatants"] if not c["is_player"])

    # Il cambio arma di default consuma l'Azione (RULE_WEAPON_SWAP_COST):
    # un attacco nello stesso turno deve fallire in modo pulito (409), non
    # con un 500 per un'eccezione dell'economia delle azioni non gestita.
    resp = await client.post("/api/game/combat/weapon-swap", json={"weapon_id": "mazzafrusto"}, headers=headers)
    assert resp.status_code == 200

    resp = await client.post("/api/game/combat/attack", json={"target_id": target_id}, headers=headers)
    assert resp.status_code == 409


async def test_weapon_swap_endpoint_rejects_unowned_weapon(client, monkeypatch):
    headers = _init_data_header(20008)
    await _create_character(client, headers)
    await _start_combat_via_turn(client, headers, monkeypatch)

    resp = await client.post("/api/game/combat/weapon-swap", json={"weapon_id": "alabarda"}, headers=headers)
    assert resp.status_code == 400


async def test_item_use_endpoint_consumes_resource_and_removes_item(client, monkeypatch):
    headers = _init_data_header(20009)
    await _create_character(client, headers)
    await _start_combat_via_turn(client, headers, monkeypatch, extra_effects=[{"type": "item_add", "target": "Pozione di cura"}])

    resp = await client.post("/api/game/combat/item-use", json={"item": "Pozione di cura"}, headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["cost"] == "bonus_action"

    state = body["state"]
    player = next(c for c in state["combatants"] if c["is_player"])
    assert player["used"]["bonus_action"] == 1


async def test_item_use_endpoint_rejects_item_not_in_inventory(client, monkeypatch):
    headers = _init_data_header(20010)
    await _create_character(client, headers)
    await _start_combat_via_turn(client, headers, monkeypatch)

    resp = await client.post("/api/game/combat/item-use", json={"item": "spada laser"}, headers=headers)
    assert resp.status_code == 400
