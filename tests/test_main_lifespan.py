"""Se l'inizializzazione del bot Telegram fallisce (rete assente, token non
valido), l'app deve restare in piedi con API e Mini App attive, non andare
in crash all'avvio."""

from __future__ import annotations

from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from app.config import settings


async def test_app_survives_telegram_init_failure(monkeypatch):
    monkeypatch.setattr(settings, "bot_token", "123456:BAD-TOKEN")

    class FailingApplication:
        async def initialize(self):
            raise RuntimeError("rete non disponibile")

    monkeypatch.setattr("app.main.build_application", lambda: FailingApplication())

    from app.main import app

    async with LifespanManager(app):
        assert app.state.telegram_app is None
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/healthz")
            assert resp.status_code == 200
