"""Condizioni SRD e i loro effetti meccanici (§8), codificati a partire dal
testo estratto in data/srd/conditions.json (Glossario delle regole).

Ogni voce copre gli effetti rilevanti per il codice (vantaggio/svantaggio,
velocità, tiri salvezza, incapacità); le sfumature puramente narrative
(es. "non può attaccare chi lo ha affascinato") restano nel testo SRD e
sono arbitrate dall'AI, non dal motore di regole.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ConditionEffect:
    attacks_against_advantage: bool = False
    attacks_against_disadvantage: bool = False
    attacks_by_self_advantage: bool = False
    attacks_by_self_disadvantage: bool = False
    ability_checks_disadvantage: bool = False
    speed_zero: bool = False
    incapacitated: bool = False
    auto_fail_str_dex_saves: bool = False
    dex_save_disadvantage: bool = False
    melee_crit_within_reach: bool = False
    initiative_advantage: bool = False
    initiative_disadvantage: bool = False
    damage_resistance_all: bool = False
    blind: bool = False
    deaf: bool = False
    implies: tuple[str, ...] = field(default_factory=tuple)
    immune_to: tuple[str, ...] = field(default_factory=tuple)


CONDITIONS: dict[str, ConditionEffect] = {
    "accecato": ConditionEffect(
        attacks_against_advantage=True, attacks_by_self_disadvantage=True, blind=True
    ),
    "affascinato": ConditionEffect(),
    "afferrato": ConditionEffect(speed_zero=True),
    "assordato": ConditionEffect(deaf=True),
    "avvelenato": ConditionEffect(attacks_by_self_disadvantage=True, ability_checks_disadvantage=True),
    "incapacitato": ConditionEffect(incapacitated=True, initiative_disadvantage=True),
    "indebolimento": ConditionEffect(),  # cumulativo a livelli: vedi exhaustion_* più sotto
    "invisibile": ConditionEffect(
        attacks_against_disadvantage=True, attacks_by_self_advantage=True, initiative_advantage=True
    ),
    # "Prono" dipende dalla distanza dell'attaccante: vedi attack_against_prone().
    "prono": ConditionEffect(attacks_by_self_disadvantage=True),
    "paralizzato": ConditionEffect(
        incapacitated=True, speed_zero=True, auto_fail_str_dex_saves=True,
        attacks_against_advantage=True, melee_crit_within_reach=True, implies=("incapacitato",),
    ),
    "pietrificato": ConditionEffect(
        incapacitated=True, speed_zero=True, auto_fail_str_dex_saves=True,
        attacks_against_advantage=True, damage_resistance_all=True,
        implies=("incapacitato",), immune_to=("avvelenato",),
    ),
    "privo_di_sensi": ConditionEffect(
        incapacitated=True, speed_zero=True, auto_fail_str_dex_saves=True,
        attacks_against_advantage=True, melee_crit_within_reach=True,
        implies=("incapacitato", "prono"),
    ),
    "spaventato": ConditionEffect(attacks_by_self_disadvantage=True, ability_checks_disadvantage=True),
    "stordito": ConditionEffect(
        incapacitated=True, auto_fail_str_dex_saves=True, attacks_against_advantage=True,
        implies=("incapacitato",),
    ),
    "trattenuto": ConditionEffect(
        speed_zero=True, attacks_against_advantage=True, attacks_by_self_disadvantage=True,
        dex_save_disadvantage=True,
    ),
}

# "Prono" (§Glossario): dipende dalla distanza dell'attaccante, non è un flag fisso.
PRONE_ID = "prono"


def attack_against_prone(attacker_is_within_melee_reach: bool) -> str:
    """Restituisce 'advantage' o 'disadvantage' per un attacco contro un
    bersaglio prono, a seconda che l'attaccante sia in mischia o a distanza."""
    return "advantage" if attacker_is_within_melee_reach else "disadvantage"


def get_effect(condition_id: str) -> ConditionEffect:
    try:
        return CONDITIONS[condition_id]
    except KeyError as exc:
        raise ValueError(f"condizione sconosciuta: {condition_id!r}") from exc


def resolve_conditions(condition_ids: set[str]) -> set[str]:
    """Espande le condizioni implicite (es. paralizzato implica incapacitato)."""
    resolved = set(condition_ids)
    changed = True
    while changed:
        changed = False
        for cid in list(resolved):
            for implied in CONDITIONS[cid].implies:
                if implied not in resolved:
                    resolved.add(implied)
                    changed = True
    return resolved


# --------------------------------------------------------------------------- indebolimento (livelli)
EXHAUSTION_LETHAL_LEVEL = 6


def exhaustion_d20_penalty(level: int) -> int:
    """Ogni prova con d20 è ridotta del doppio del livello di indebolimento."""
    return level * 2


def exhaustion_speed_reduction_m(level: int) -> float:
    """La velocità è ridotta di 1,5 metri per livello di indebolimento."""
    return level * 1.5


def exhaustion_is_lethal(level: int) -> bool:
    return level >= EXHAUSTION_LETHAL_LEVEL
