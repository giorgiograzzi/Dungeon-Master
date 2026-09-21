"""Cambio arma (§8, regola della casa): consuma un'Azione di default,
configurabile con RULE_WEAPON_SWAP_COST=free_interaction."""

from __future__ import annotations

from rules.action_economy import ActionEconomy


def swap_weapon(economy: ActionEconomy, rule: str = "action") -> None:
    if rule == "action":
        economy.use("action")
    elif rule == "free_interaction":
        economy.use("free_object_interaction")
    else:
        raise ValueError(f"RULE_WEAPON_SWAP_COST sconosciuta: {rule!r}")
