"""Punti ferita e PF temporanei (§8): il danno consuma prima i PF
temporanei; non si sommano tra loro (si tiene il valore più alto); non si
curano; scadono al riposo lungo."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class HitPoints:
    current: int
    maximum: int
    temp: int = 0

    def apply_damage(self, amount: int) -> int:
        """Applica danno (prima ai PF temp, poi ai PF reali). Restituisce il
        danno effettivamente sottratto ai PF reali (0 se assorbito del tutto)."""
        if amount < 0:
            raise ValueError("il danno non può essere negativo")
        absorbed = min(self.temp, amount)
        self.temp -= absorbed
        remaining = amount - absorbed
        real_damage = min(self.current, remaining)
        self.current -= real_damage
        return real_damage

    def heal(self, amount: int) -> None:
        if amount < 0:
            raise ValueError("la cura non può essere negativa")
        self.current = min(self.maximum, self.current + amount)

    def add_temp_hp(self, amount: int) -> None:
        """I PF temporanei non si sommano: si tiene il valore più alto."""
        if amount < 0:
            raise ValueError("i PF temporanei non possono essere negativi")
        self.temp = max(self.temp, amount)

    def clear_temp_hp(self) -> None:
        self.temp = 0

    @property
    def is_down(self) -> bool:
        return self.current <= 0
