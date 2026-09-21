from __future__ import annotations

from functools import lru_cache
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent.parent.parent / "prompts"


@lru_cache
def narrator_system_prompt() -> str:
    return (PROMPTS_DIR / "narrator_system_it.md").read_text(encoding="utf-8")
