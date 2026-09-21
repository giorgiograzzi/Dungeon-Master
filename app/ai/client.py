"""Client AI (§3, §6): tool use con schema forzato e prompt caching sul
system prompt. `DEV_FAKE_AI=1` sostituisce le chiamate reali con risposte
finte ma valide, per sviluppare/testare senza consumare credito API (§14)."""

from __future__ import annotations

from typing import Protocol

from app.ai import fake_data
from app.ai.tools import (
    EXPORT_STORY_TOOL,
    GENERATE_CAMPAIGN_PLAN_TOOL,
    NARRATE_OUTCOME_TOOL,
    PRESENT_CROSSROADS_TOOL,
    REQUEST_CHECK_TOOL,
    SUMMARIZE_STORY_TOOL,
)


class AIClient(Protocol):
    async def call_tool(
        self, *, model: str, system: str, messages: list[dict], tool: dict, max_tokens: int = 1536
    ) -> dict: ...


class AnthropicAIClient:
    """Wrapper sottile sull'SDK ufficiale `anthropic` (async)."""

    def __init__(self, api_key: str) -> None:
        import anthropic

        self._client = anthropic.AsyncAnthropic(api_key=api_key)

    async def call_tool(
        self, *, model: str, system: str, messages: list[dict], tool: dict, max_tokens: int = 1536
    ) -> dict:
        response = await self._client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            messages=messages,
            tools=[tool],
            tool_choice={"type": "tool", "name": tool["name"]},
        )
        for block in response.content:
            if block.type == "tool_use":
                return block.input
        raise RuntimeError(f"l'AI non ha usato lo strumento atteso: {tool['name']}")


class FakeAIClient:
    """DEV_FAKE_AI=1: risposte deterministiche e strutturalmente valide."""

    async def call_tool(
        self, *, model: str, system: str, messages: list[dict], tool: dict, max_tokens: int = 1536
    ) -> dict:
        handler = {
            REQUEST_CHECK_TOOL["name"]: self._fake_request_check,
            NARRATE_OUTCOME_TOOL["name"]: self._fake_narrate_outcome,
            GENERATE_CAMPAIGN_PLAN_TOOL["name"]: self._fake_campaign_plan,
            PRESENT_CROSSROADS_TOOL["name"]: self._fake_crossroads,
            SUMMARIZE_STORY_TOOL["name"]: self._fake_summarize,
            EXPORT_STORY_TOOL["name"]: self._fake_export,
        }.get(tool["name"])
        if handler is None:
            raise ValueError(f"FakeAIClient non sa rispondere per lo strumento {tool['name']!r}")
        return handler(messages)

    def _last_user_text(self, messages: list[dict]) -> str:
        for message in reversed(messages):
            if message.get("role") == "user":
                content = message.get("content", "")
                return content if isinstance(content, str) else str(content)
        return ""

    def _fake_request_check(self, messages: list[dict]) -> dict:
        text = self._last_user_text(messages).lower()
        if any(word in text for word in ("scasso", "furtiv", "combatt", "attacc", "persuad", "conving")):
            return {
                "needs_roll": True,
                "check_type": "ability",
                "ability": "des",
                "skill_id": "furtivita",
                "dc_band": "media",
                "advantage": False,
                "disadvantage": False,
                "advantage_reason": "",
            }
        return {"needs_roll": False, "narration": "Procedi senza intoppi verso il tuo obiettivo."}

    def _fake_narrate_outcome(self, messages: list[dict]) -> dict:
        return {
            "narration": "L'azione va a segno e la scena si evolve di conseguenza. (narrazione di prova, DEV_FAKE_AI)",
            "options": [
                {"label": "Avanza con cautela", "action_cost": "action"},
                {"label": "Parla con chi hai di fronte", "action_cost": "action"},
                {"label": "Osserva l'ambiente", "action_cost": "free"},
            ],
            "effects": [],
        }

    def _fake_campaign_plan(self, messages: list[dict]) -> dict:
        text = self._last_user_text(messages)
        setting = "fantasy classico"
        duration = "media"
        for s in ("fantasy classico", "noir", "fantascienza", "horror comico"):
            if s in text.lower():
                setting = s
        for d in ("breve", "media", "lunga"):
            if d in text.lower():
                duration = d
        return fake_data.build_fake_campaign_plan(setting=setting, duration=duration)

    def _fake_crossroads(self, messages: list[dict]) -> dict:
        return {
            "routes": [
                {"id": rid, "title": name, "promise": tagline, "risk": "medio", "style": tagline, "duration_effect": "media"}
                for rid, (name, tagline) in fake_data.ROUTE_NAMES.items()
            ]
        }

    def _fake_summarize(self, messages: list[dict]) -> dict:
        return {"summary": "Riassunto di prova generato in modalità DEV_FAKE_AI."}

    def _fake_export(self, messages: list[dict]) -> dict:
        return {"story_text": "Racconto di prova generato in modalità DEV_FAKE_AI."}


_client_cache: dict[str, AIClient] = {}


def get_ai_client(*, dev_fake_ai: bool, api_key: str) -> AIClient:
    key = "fake" if dev_fake_ai else f"real:{api_key}"
    if key not in _client_cache:
        _client_cache[key] = FakeAIClient() if dev_fake_ai else AnthropicAIClient(api_key)
    return _client_cache[key]
