from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth_helpers import resolve_user_from_init_data
from app.db import get_session

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
    user = await resolve_user_from_init_data(payload.init_data, session)
    return AuthVerifyResponse(
        user_id=user.id,
        telegram_user_id=user.telegram_user_id,
        username=user.username,
        first_name=user.first_name,
    )
