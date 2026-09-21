"""Tiri di dado lato server (§0.1, §3, §7): l'AI non tira mai, propone;
il codice tira con `secrets` (non `random`) e persiste l'esito."""

from __future__ import annotations

import secrets
from dataclasses import dataclass


def roll_die(sides: int) -> int:
    if sides < 1:
        raise ValueError("un dado deve avere almeno 1 faccia")
    return secrets.randbelow(sides) + 1


def roll_dice(count: int, sides: int) -> list[int]:
    return [roll_die(sides) for _ in range(count)]


@dataclass(frozen=True)
class D20Roll:
    """Risultato di una prova con d20, con eventuale vantaggio/svantaggio.

    Più fonti di vantaggio (o svantaggio) non si sommano: si tira sempre un
    solo d20 in più. Vantaggio e svantaggio insieme si annullano (SRD, §3).
    """

    kept: int
    dropped: int | None
    advantage: bool
    disadvantage: bool

    @property
    def natural_20(self) -> bool:
        return self.kept == 20

    @property
    def natural_1(self) -> bool:
        return self.kept == 1


def roll_d20(advantage: bool = False, disadvantage: bool = False) -> D20Roll:
    if advantage and disadvantage:
        advantage = disadvantage = False
    if not (advantage or disadvantage):
        return D20Roll(kept=roll_die(20), dropped=None, advantage=False, disadvantage=False)
    a, b = roll_die(20), roll_die(20)
    kept = max(a, b) if advantage else min(a, b)
    dropped = min(a, b) if advantage else max(a, b)
    return D20Roll(kept=kept, dropped=dropped, advantage=advantage, disadvantage=disadvantage)


def parse_dice_expression(expr: str) -> tuple[int, int, int]:
    """Analizza espressioni come '1d6', '2d8+3', '1d10-1' -> (numero, facce, modificatore)."""
    import re

    m = re.fullmatch(r"\s*(\d+)\s*d\s*(\d+)\s*(?:([+-])\s*(\d+))?\s*", expr, re.IGNORECASE)
    if not m:
        raise ValueError(f"espressione di dado non valida: {expr!r}")
    count, sides, sign, mod = m.groups()
    modifier = int(mod) if mod else 0
    if sign == "-":
        modifier = -modifier
    return int(count), int(sides), modifier


def roll_expression(expr: str) -> int:
    """Tira un'espressione di dadi (es. '2d6+3') e restituisce il totale."""
    count, sides, modifier = parse_dice_expression(expr)
    return sum(roll_dice(count, sides)) + modifier
