"""Risoluzione degli attacchi, colpi critici, iniziativa e tiri salvezza
contro la morte (§8), verificati contro il testo dell'SRD ("Colpi critici",
"Scendere a 0 punti ferita", "Tiri salvezza contro morte")."""

from __future__ import annotations

from dataclasses import dataclass

from rules.dice import parse_dice_expression, roll_d20, roll_dice, roll_die
from rules.hit_points import HitPoints

DEATH_SAVE_DC = 10
DEATH_SAVES_TO_STABILIZE = 3
DEATH_SAVES_TO_DIE = 3


@dataclass(frozen=True)
class AttackResult:
    d20: int
    total: int
    target_ac: int
    hit: bool
    critical_hit: bool
    critical_miss: bool


def resolve_attack_roll(*, to_hit_bonus: int, target_ac: int, advantage: bool = False, disadvantage: bool = False) -> AttackResult:
    d20 = roll_d20(advantage=advantage, disadvantage=disadvantage)
    total = d20.kept + to_hit_bonus
    critical_hit = d20.natural_20
    critical_miss = d20.natural_1
    hit = critical_hit or (not critical_miss and total >= target_ac)
    return AttackResult(d20=d20.kept, total=total, target_ac=target_ac, hit=hit, critical_hit=critical_hit, critical_miss=critical_miss)


def roll_damage(expression: str, critical: bool = False) -> int:
    """Un colpo critico raddoppia i dadi di danno, non il modificatore (SRD)."""
    count, sides, modifier = parse_dice_expression(expression)
    if critical:
        count *= 2
    return sum(roll_dice(count, sides)) + modifier


def roll_initiative(dex_modifier: int) -> int:
    return roll_die(20) + dex_modifier


@dataclass
class DeathSaveState:
    successes: int = 0
    failures: int = 0
    stable: bool = False
    dead: bool = False


def roll_death_save(state: DeathSaveState, hp: HitPoints) -> dict:
    """Un tiro salvezza contro la morte a inizio turno (a 0 PF): 1d20 puro,
    CD 10, senza modificatori. 3 successi = stabile, 3 fallimenti = morto."""
    if state.stable or state.dead:
        raise ValueError("il personaggio è già stabile o morto: nessun tiro da fare")
    d20 = roll_die(20)
    if d20 == 20:
        hp.heal(1)
        state.successes = state.failures = 0
        return {"d20": d20, "result": "critico: recupera 1 PF e riprende conoscenza"}
    if d20 == 1:
        state.failures += 2
    elif d20 >= DEATH_SAVE_DC:
        state.successes += 1
    else:
        state.failures += 1

    if state.successes >= DEATH_SAVES_TO_STABILIZE:
        state.stable = True
        return {"d20": d20, "result": "stabile"}
    if state.failures >= DEATH_SAVES_TO_DIE:
        state.dead = True
        return {"d20": d20, "result": "morto"}
    return {"d20": d20, "result": "in bilico", "successes": state.successes, "failures": state.failures}


def apply_damage_at_zero_hp(state: DeathSaveState, hp: HitPoints, damage: int, critical: bool = False) -> dict:
    """Danno subito a 0 PF: conta come tiro salvezza fallito (2 se critico);
    se il danno residuo è pari o superiore ai PF massimi, morte istantanea."""
    if damage >= hp.maximum:
        state.dead = True
        return {"result": "morto (danno massiccio)"}
    state.failures += 2 if critical else 1
    if state.failures >= DEATH_SAVES_TO_DIE:
        state.dead = True
        return {"result": "morto"}
    return {"result": "un tiro salvezza fallito", "failures": state.failures}
