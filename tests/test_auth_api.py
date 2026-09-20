from __future__ import annotations

import time

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import settings
from app.db import Base, get_session
from app.main import app
from tests._helpers import BOT_TOKEN, build_init_data


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


async def test_auth_verify_creates_and_reuses_user(client):
    fields = {
        "auth_date": str(int(time.time())),
        "user": '{"id": 555, "first_name": "Prova", "username": "prova"}',
    }
    init_data = build_init_data(fields, BOT_TOKEN)

    resp = await client.post("/api/auth/verify", json={"init_data": init_data})
    assert resp.status_code == 200
    body = resp.json()
    assert body["telegram_user_id"] == 555
    assert body["first_name"] == "Prova"

    # Una seconda verifica per lo stesso utente Telegram riusa la stessa riga.
    resp2 = await client.post("/api/auth/verify", json={"init_data": init_data})
    assert resp2.status_code == 200
    assert resp2.json()["user_id"] == body["user_id"]


async def test_auth_verify_rejects_bad_signature(client):
    resp = await client.post("/api/auth/verify", json={"init_data": "hash=deadbeef&auth_date=1"})
    assert resp.status_code == 401


async def test_auth_verify_rejects_not_allowed_user(client, monkeypatch):
    monkeypatch.setattr(settings, "allowed_user_ids", "999")
    fields = {"auth_date": str(int(time.time())), "user": '{"id": 555}'}
    init_data = build_init_data(fields, BOT_TOKEN)

    resp = await client.post("/api/auth/verify", json={"init_data": init_data})
    assert resp.status_code == 403
