"""Determinazione dei punteggi di caratteristica (§4): 3 metodi a scelta."""

from __future__ import annotations

from rules.dice import roll_die

STANDARD_ARRAY = [15, 14, 13, 12, 10, 8]

POINT_BUY_BUDGET = 27
POINT_BUY_MIN = 8
POINT_BUY_MAX = 15
POINT_BUY_COST = {8: 0, 9: 1, 10: 2, 11: 3, 12: 4, 13: 5, 14: 7, 15: 9}


def roll_4d6_drop_lowest() -> int:
    rolls = sorted(roll_die(6) for _ in range(4))
    return sum(rolls[1:])


def roll_ability_scores() -> list[int]:
    """Tira i 6 punteggi con il metodo 4d6 (scarta il più basso)."""
    return [roll_4d6_drop_lowest() for _ in range(6)]


def point_buy_cost(scores: dict[str, int]) -> int:
    total = 0
    for value in scores.values():
        if value not in POINT_BUY_COST:
            raise ValueError(f"punteggio {value} fuori dai limiti del point buy (8-15)")
        total += POINT_BUY_COST[value]
    return total


def validate_point_buy(scores: dict[str, int], budget: int = POINT_BUY_BUDGET) -> bool:
    return point_buy_cost(scores) <= budget


def validate_standard_array(scores: list[int]) -> bool:
    return sorted(scores) == sorted(STANDARD_ARRAY)
