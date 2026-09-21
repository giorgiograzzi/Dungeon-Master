"""Economia delle azioni in combattimento (§8): Azione, Azione Bonus,
Reazione (1 per round), Movimento, Interazione gratuita con un oggetto
(1 per turno). Fuori dal combattimento queste risorse non si consumano
(§8): sta al chiamante invocare `use()` solo quando `mode == "combat"`."""

from __future__ import annotations

from dataclasses import dataclass, field

ACTION_KINDS = ("action", "bonus_action", "reaction", "movement", "free_object_interaction")


class ActionEconomyError(RuntimeError):
    """Sollevato quando si prova a usare una risorsa già esaurita nel turno."""


@dataclass
class ActionEconomy:
    used: dict[str, int] = field(default_factory=lambda: dict.fromkeys(ACTION_KINDS, 0))
    available: dict[str, int] = field(default_factory=lambda: dict.fromkeys(ACTION_KINDS, 1))

    def can_use(self, kind: str) -> bool:
        self._check_kind(kind)
        return self.used[kind] < self.available[kind]

    def use(self, kind: str) -> None:
        if not self.can_use(kind):
            raise ActionEconomyError(f"risorsa esaurita per questo turno: {kind}")
        self.used[kind] += 1

    def remaining(self, kind: str) -> int:
        self._check_kind(kind)
        return self.available[kind] - self.used[kind]

    def reset_turn(self) -> None:
        """Azione, Bonus, Movimento e Interazione libera si rinnovano a ogni turno."""
        for kind in ("action", "bonus_action", "movement", "free_object_interaction"):
            self.used[kind] = 0

    def reset_round(self) -> None:
        """La Reazione si rinnova a ogni round (non a ogni turno altrui)."""
        self.used["reaction"] = 0

    @staticmethod
    def _check_kind(kind: str) -> None:
        if kind not in ACTION_KINDS:
            raise ValueError(f"tipo di azione sconosciuto: {kind!r}")
