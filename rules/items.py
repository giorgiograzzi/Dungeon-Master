"""Costo d'uso degli oggetti (§8): ogni oggetto ha `use_cost` tra questi
valori, letto dall'SRD (con fallback documentato dove l'SRD non lo indica
esplicitamente, es. la maggior parte dell'equipaggiamento non da combattimento)."""

from __future__ import annotations

from enum import Enum

from rules.action_economy import ActionEconomy


class UseCost(str, Enum):
    ACTION = "action"
    BONUS_ACTION = "bonus_action"
    REACTION = "reaction"
    FREE = "free"
    NONE = "none"


_COST_TO_ACTION_KIND = {
    UseCost.ACTION: "action",
    UseCost.BONUS_ACTION: "bonus_action",
    UseCost.REACTION: "reaction",
    UseCost.FREE: "free_object_interaction",
}


class ItemUseError(RuntimeError):
    pass


def infer_use_cost(item_name: str) -> UseCost:
    """Fallback quando l'oggetto non ha un `use_cost` esplicito nei dati SRD
    (l'equipaggiamento generico non da combattimento non è stato estratto
    con questo dettaglio in Fase 1). Verificato contro il testo dell'SRD:
    "Bere una pozione [...] richiede un'azione bonus" (cap. Incantesimi,
    "Usare una pozione"); ogni altro oggetto usa la generica "azione di
    Utilizzo" (cap. Equipaggiamento avventura)."""
    if "pozione" in item_name.lower():
        return UseCost.BONUS_ACTION
    return UseCost.ACTION


def use_item(economy: ActionEconomy, cost: UseCost) -> None:
    """Consuma la risorsa dell'economia delle azioni per usare un oggetto.

    Da chiamare solo in modalità combattimento (§8: fuori dal combattimento
    non si consumano risorse). `UseCost.NONE` non consuma nulla.
    """
    kind = _COST_TO_ACTION_KIND.get(cost)
    if kind is None:
        return
    if not economy.can_use(kind):
        label = "azione" if kind == "action" else kind
        raise ItemUseError(f"risorsa esaurita per questo turno: {label}")
    economy.use(kind)
