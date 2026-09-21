"""Punteggi di caratteristica, modificatori e bonus di competenza (SRD,
"Creazione del personaggio"): (score-10)//2, competenza 2 + (livello-1)//4
(verificato contro le tabelle per livello estratte in data/srd/classes.json)."""

from __future__ import annotations

ABILITIES = ("for", "des", "cos", "int", "sag", "car")


def ability_modifier(score: int) -> int:
    return (score - 10) // 2


def proficiency_bonus(level: int) -> int:
    if not 1 <= level <= 20:
        raise ValueError("il livello deve essere tra 1 e 20")
    return 2 + (level - 1) // 4
