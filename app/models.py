from __future__ import annotations

import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, JSON, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class User(Base):
    """Un giocatore Telegram. Una partita = un utente = un personaggio (§0)."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Character(Base):
    """Il personaggio di un utente (§0: una partita = un utente = un personaggio).

    Le scelte della creazione guidata (§4) vivono in `data`, un documento JSON
    con `schema_version` — lo stesso approccio dei salvataggi di partita (§6),
    più adatto di uno schema relazionale rigido a una bozza che cresce a step.
    """

    __tablename__ = "characters"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(16), default="draft")  # draft | complete
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class GameSave(Base):
    """Stato di partita (§6): documento JSON con `schema_version` + log dei
    turni. `slot` = 'autosave' oppure 'slot_1'..'slot_5' (salvataggi manuali
    con nome); nessuno stato di gioco vive solo in memoria."""

    __tablename__ = "game_saves"
    __table_args__ = (UniqueConstraint("user_id", "slot", name="uq_game_saves_user_slot"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    slot: Mapped[str] = mapped_column(String(32))
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
