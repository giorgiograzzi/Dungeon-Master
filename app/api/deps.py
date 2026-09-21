from __future__ import annotations

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth_helpers import resolve_user_from_init_data
from app.db import get_session
from app.models import User


async def get_current_user(
    x_telegram_init_data: str = Header(alias="X-Telegram-Init-Data"),
    session: AsyncSession = Depends(get_session),
) -> User:
    """Valida initData su ogni chiamata API (§2) e restituisce l'utente."""
    return await resolve_user_from_init_data(x_telegram_init_data, session)
