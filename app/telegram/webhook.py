from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Request, Response
from telegram import Update

from app.config import settings

router = APIRouter()


@router.post("/telegram/webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> Response:
    application = request.app.state.telegram_app
    if application is None:
        raise HTTPException(status_code=503, detail="bot Telegram non configurato")
    if settings.webhook_secret and x_telegram_bot_api_secret_token != settings.webhook_secret:
        raise HTTPException(status_code=401, detail="secret non valido")

    payload = await request.json()
    update = Update.de_json(payload, application.bot)
    await application.process_update(update)
    return Response(status_code=200)
