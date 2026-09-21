from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configurazione da variabili d'ambiente (vedi .env.example)."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", protected_namespaces=()
    )

    bot_token: str = ""
    anthropic_api_key: str = ""
    database_url: str = "sqlite+aiosqlite:///./dungeon_master.db"
    webapp_url: str = ""
    webhook_secret: str = ""
    allowed_user_ids: str = ""
    daily_turn_cap: int = 50
    model_narrator: str = "claude-haiku-4-5-20251001"
    model_climax: str = "claude-sonnet-5"
    rule_weapon_swap_cost: Literal["action", "free_interaction"] = "action"
    port: int = 8000
    dev_fake_ai: bool = False

    @property
    def allowed_user_ids_set(self) -> frozenset[int]:
        return frozenset(int(v) for v in self.allowed_user_ids.split(",") if v.strip())


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
