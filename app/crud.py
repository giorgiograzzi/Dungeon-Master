from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User


async def get_or_create_user(
    session: AsyncSession,
    telegram_user_id: int,
    username: str | None,
    first_name: str | None,
) -> User:
    result = await session.execute(select(User).where(User.telegram_user_id == telegram_user_id))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(telegram_user_id=telegram_user_id, username=username, first_name=first_name)
        session.add(user)
    else:
        user.username = username
        user.first_name = first_name
    await session.commit()
    await session.refresh(user)
    return user
