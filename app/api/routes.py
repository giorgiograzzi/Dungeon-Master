from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.crud import get_or_create_user
from app.db import get_session
from app.security.telegram_auth import InitDataError, validate_init_data

router = APIRouter()


@router.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok"}


class AuthVerifyRequest(BaseModel):
    init_data: str


class AuthVerifyResponse(BaseModel):
    user_id: int
    telegram_user_id: int
    username: str | None
    first_name: str | None


@router.post("/api/auth/verify", response_model=AuthVerifyResponse)
async def auth_verify(
    payload: AuthVerifyRequest,
    session: AsyncSession = Depends(get_session),
) -> AuthVerifyResponse:
    try:
        data = validate_init_data(payload.init_data, settings.bot_token)
    except InitDataError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    user_data = data.get("user")
    if not isinstance(user_data, dict) or "id" not in user_data:
        raise HTTPException(status_code=401, detail="initData senza utente")

    telegram_user_id = int(user_data["id"])
    allowed = settings.allowed_user_ids_set
    if allowed and telegram_user_id not in allowed:
        raise HTTPException(status_code=403, detail="utente non autorizzato")

    user = await get_or_create_user(
        session,
        telegram_user_id,
        user_data.get("username"),
        user_data.get("first_name"),
    )
    return AuthVerifyResponse(
        user_id=user.id,
        telegram_user_id=user.telegram_user_id,
        username=user.username,
        first_name=user.first_name,
    )
