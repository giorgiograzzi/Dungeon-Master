"""Riposo breve e lungo (§8, Glossario delle regole "Riposo breve"/"Dadi Vita").

La gestione del pool di Dadi Vita di un personaggio (quanti ne ha, quanti ne
ha spesi) vive nel modello Character (Fase 2): qui ci sono solo le funzioni
pure per tirare il recupero e per resettare ciò che scade al riposo lungo."""

from __future__ import annotations

from rules.dice import roll_die
from rules.hit_points import HitPoints


def spend_hit_die(hit_die_sides: int, con_modifier: int) -> int:
    """Tira un Dado Vita per recuperare PF in un riposo breve: dado + mod
    Costituzione, minimo 0 (non può ridurre i PF)."""
    return max(0, roll_die(hit_die_sides) + con_modifier)


def apply_long_rest(hp: HitPoints) -> None:
    """Riposo lungo: i PF temporanei scadono e i PF tornano al massimo."""
    hp.clear_temp_hp()
    hp.heal(hp.maximum)
