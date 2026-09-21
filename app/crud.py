from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.character.schema import new_character_data
from app.game.schema import new_game_save_data
from app.models import Character, GameSave, User


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


AUTOSAVE_SLOT = "autosave"
MANUAL_SLOTS = [f"slot_{i}" for i in range(1, 6)]  # 5 slot manuali (§6)


async def get_or_create_save(session: AsyncSession, user: User, slot: str = AUTOSAVE_SLOT) -> GameSave:
    result = await session.execute(
        select(GameSave).where(GameSave.user_id == user.id, GameSave.slot == slot)
    )
    save = result.scalar_one_or_none()
    if save is None:
        save = GameSave(user_id=user.id, slot=slot, data=new_game_save_data())
        session.add(save)
        await session.commit()
        await session.refresh(save)
    return save


async def save_game_data(session: AsyncSession, save: GameSave, data: dict) -> GameSave:
    save.data = data
    flag_modified(save, "data")
    await session.commit()
    await session.refresh(save)
    return save


async def list_saves(session: AsyncSession, user: User) -> list[GameSave]:
    result = await session.execute(
        select(GameSave).where(GameSave.user_id == user.id).order_by(GameSave.slot)
    )
    return list(result.scalars().all())


async def create_manual_save(session: AsyncSession, user: User, name: str, data: dict) -> GameSave:
    """Copia lo stato attuale (di solito l'autosave) in un nuovo slot manuale
    con nome, scegliendo il primo libero tra i 5 disponibili (§6)."""
    existing = {s.slot for s in await list_saves(session, user)}
    free_slot = next((slot for slot in MANUAL_SLOTS if slot not in existing), None)
    if free_slot is None:
        raise ValueError("tutti i 5 slot di salvataggio manuale sono occupati")
    save = GameSave(user_id=user.id, slot=free_slot, name=name, data=data)
    session.add(save)
    await session.commit()
    await session.refresh(save)
    return save


async def load_save_into_autosave(session: AsyncSession, user: User, slot: str) -> GameSave:
    """'Riavvolgi all'ultimo salvataggio' (§5): copia uno slot (di solito
    manuale) nell'autosave, che diventa così la partita attiva."""
    if slot == AUTOSAVE_SLOT:
        raise ValueError("l'autosave è già la partita attiva")
    result = await session.execute(select(GameSave).where(GameSave.user_id == user.id, GameSave.slot == slot))
    source = result.scalar_one_or_none()
    if source is None:
        raise ValueError(f"nessun salvataggio nello slot {slot!r}")
    autosave = await get_or_create_save(session, user)
    return await save_game_data(session, autosave, dict(source.data))
