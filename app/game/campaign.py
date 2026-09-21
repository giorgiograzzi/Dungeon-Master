"""Generazione e uso del Piano di Campagna (§5): il piano resta nascosto al
giocatore, il codice ne espone solo un riepilogo senza spoiler e i bivi."""

from __future__ import annotations

import copy

from app.ai.client import AIClient
from app.ai.tools import GENERATE_CAMPAIGN_PLAN_TOOL, PRESENT_CROSSROADS_TOOL
from rules.campaign import validate_campaign_plan

MAX_GENERATION_ATTEMPTS = 3


class CampaignPlanInvalid(RuntimeError):
    def __init__(self, errors: list[str]) -> None:
        super().__init__("; ".join(errors))
        self.errors = errors


async def generate_and_validate_campaign_plan(
    *, ai_client: AIClient, model: str, system_prompt: str, setting: str, duration: str
) -> dict:
    last_errors: list[str] = []
    for _ in range(MAX_GENERATION_ATTEMPTS):
        messages = [
            {
                "role": "user",
                "content": f"Genera il Piano di Campagna. Ambientazione: {setting}. Durata target: {duration}.",
            }
        ]
        plan = await ai_client.call_tool(model=model, system=system_prompt, messages=messages, tool=GENERATE_CAMPAIGN_PLAN_TOOL)
        errors = validate_campaign_plan(plan)
        if not errors:
            return plan
        last_errors = errors
    raise CampaignPlanInvalid(last_errors)


def public_campaign_summary(plan: dict, save_data: dict) -> dict:
    """Ciò che il giocatore può vedere: mai il grafo completo (§5)."""
    return {
        "title": plan["title"],
        "premise": plan["premise"],
        "setting": plan["setting"],
        "duration_target": plan["duration_target"],
        "current_objective": current_objective(plan, save_data),
        "turn_count": save_data.get("turn_count", 0),
        "mode": save_data.get("mode", "exploration"),
        "current_act": save_data.get("current_act", 1),
        "ended": save_data.get("ended", False),
    }


def current_objective(plan: dict, save_data: dict) -> str:
    completed = set(save_data.get("completed_beats", []))
    route_id = save_data.get("current_route_id")
    for beat in plan.get("beats", []):
        if beat["id"] not in completed and beat.get("route") in (None, route_id):
            return beat["objective"]
    return "Concludi la tua avventura."


def is_at_crossroads(plan: dict, save_data: dict) -> dict | None:
    """Restituisce il prossimo bivio da presentare, se il giocatore vi è
    arrivato (il beat cardine dell'atto precedente è completato) e non lo ha
    ancora risolto; altrimenti None."""
    crossroads = plan.get("crossroads", [])
    idx = save_data.get("crossroads_resolved_count", 0)
    if idx >= len(crossroads):
        return None
    crossroad = crossroads[idx]
    hinge_beats = {b["act"]: b["id"] for b in plan.get("beats", []) if b.get("route") is None}
    hinge_id = hinge_beats.get(crossroad["after_act"])
    if hinge_id and hinge_id in save_data.get("completed_beats", []):
        return crossroad
    return None


async def present_crossroads(
    *, ai_client: AIClient, model: str, system_prompt: str, plan: dict, crossroad: dict
) -> dict:
    route_details = [r for r in plan["routes"] if r["id"] in crossroad["route_ids"]]
    messages = [
        {
            "role": "user",
            "content": f"Presenta il bivio senza spoiler. Percorsi disponibili: {route_details}",
        }
    ]
    return await ai_client.call_tool(model=model, system=system_prompt, messages=messages, tool=PRESENT_CROSSROADS_TOOL)


def choose_route(save_data: dict, route_id: str) -> None:
    idx = save_data.get("crossroads_resolved_count", 0)
    _snapshot_before_crossroad(save_data, idx)

    save_data["current_route_id"] = route_id
    save_data["crossroads_resolved_count"] = idx + 1
    # Bivio 1 superato -> si entra nell'Atto II, bivio 2 -> Atto III (§4/§5):
    # il livello a milestone si aggancia a questo stesso avanzamento.
    save_data["current_act"] = min(3, idx + 2)


def _snapshot_before_crossroad(save_data: dict, crossroad_index: int) -> None:
    """Salva lo stato subito prima di risolvere il bivio `crossroad_index`,
    per poter poi 'Rigioca da un bivio' (§5) senza dover reimplementare un
    sistema di versioning completo dei salvataggi."""
    snapshot = {k: v for k, v in save_data.items() if k != "crossroad_snapshots"}
    save_data.setdefault("crossroad_snapshots", {})[str(crossroad_index)] = copy.deepcopy(snapshot)


def rewind_to_crossroad(save_data: dict, crossroad_index: int) -> dict:
    """'Rigioca da un bivio': ripristina lo stato salvato subito prima di
    aver risolto il bivio `crossroad_index` (0 = il primo), per provare un
    percorso diverso. Richiede che quel bivio sia già stato risolto almeno
    una volta (altrimenti non esiste alcuno snapshot da cui ripartire)."""
    snapshots = save_data.get("crossroad_snapshots", {})
    key = str(crossroad_index)
    if key not in snapshots:
        raise ValueError(f"nessuno snapshot disponibile per il bivio {crossroad_index}")
    restored = copy.deepcopy(snapshots[key])
    restored["crossroad_snapshots"] = snapshots
    save_data.clear()
    save_data.update(restored)
    return save_data
