from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.character_routes import router as character_router
from app.api.routes import router as api_router
from app.config import settings
from app.db import init_db
from app.telegram.bot import build_application, configure_bot
from app.telegram.webhook import router as webhook_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

WEBAPP_DIR = Path(__file__).resolve().parent.parent / "webapp"


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()

    app.state.telegram_app = None
    if settings.bot_token:
        application = build_application()
        await application.initialize()
        await application.start()
        await configure_bot(application)
        app.state.telegram_app = application
    else:
        logger.warning("BOT_TOKEN non impostato: bot Telegram disabilitato (solo API/Mini App attive).")

    yield

    application = app.state.telegram_app
    if application is not None:
        await application.stop()
        await application.shutdown()


app = FastAPI(title="Dungeon Master Tascabile", lifespan=lifespan)
app.include_router(api_router)
app.include_router(character_router)
app.include_router(webhook_router)
app.mount("/", StaticFiles(directory=str(WEBAPP_DIR), html=True), name="webapp")
