from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.character.schema import new_character_data
from app.models import Character, User


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


async def get_or_create_character(session: AsyncSession, user: User) -> Character:
    """Una partita = un utente = un personaggio (§0): al massimo una riga per utente."""
    result = await session.execute(select(Character).where(Character.user_id == user.id))
    character = result.scalar_one_or_none()
    if character is None:
        character = Character(user_id=user.id, status="draft", data=new_character_data())
        session.add(character)
        await session.commit()
        await session.refresh(character)
    return character


async def save_character_data(session: AsyncSession, character: Character, data: dict) -> Character:
    character.data = data
    flag_modified(character, "data")  # SQLAlchemy non rileva le mutazioni in-place di un JSON
    await session.commit()
    await session.refresh(character)
    return character
