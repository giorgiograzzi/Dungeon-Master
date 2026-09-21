"""Risoluzione dell'utente da initData, condivisa tra /api/auth/verify e le
altre rotte API (§2: initData validato a ogni chiamata)."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.crud import get_or_create_user
from app.models import User
from app.security.telegram_auth import InitDataError, validate_init_data


async def resolve_user_from_init_data(init_data: str, session: AsyncSession) -> User:
    try:
        data = validate_init_data(init_data, settings.bot_token)
    except InitDataError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    user_data = data.get("user")
    if not isinstance(user_data, dict) or "id" not in user_data:
        raise HTTPException(status_code=401, detail="initData senza utente")

    telegram_user_id = int(user_data["id"])
    allowed = settings.allowed_user_ids_set
    if allowed and telegram_user_id not in allowed:
        raise HTTPException(status_code=403, detail="utente non autorizzato")

    return await get_or_create_user(
        session, telegram_user_id, user_data.get("username"), user_data.get("first_name")
    )
