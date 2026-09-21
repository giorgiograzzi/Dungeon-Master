"""Level-up a milestone (§4): fine Atto I -> livello 2, fine Atto II ->
livello 3. L'aumento di PF si tira (dado vita + modificatore Costituzione,
minimo 1), coerente con "dadi visibili anche per... dadi vita" (§7)."""

from __future__ import annotations

from rules.dice import roll_die


def roll_hp_gain(hit_die_sides: int, con_modifier: int) -> tuple[int, int]:
    """Restituisce (tiro grezzo del dado vita, PF guadagnati) -- il tiro
    grezzo serve a mostrare il dado (§7: dadi visibili anche per i dadi vita)."""
    roll = roll_die(hit_die_sides)
    return roll, max(1, roll + con_modifier)
