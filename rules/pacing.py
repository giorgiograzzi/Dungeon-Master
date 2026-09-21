"""Ritmo narrativo (§5): un orologio a turni che dice all'AI se accorciare
le scene (in ritardo) o proporre una quest secondaria (in anticipo).

I budget di turni per durata target non sono specificati dall'SRD né dal
PROMPT (non è una regola di gioco, solo un'euristica di ritmo): sono una
stima ragionevole, documentata in DECISIONS.md, pensata per una sessione
di ~1/2/3 ore con un turno ogni 3-5 minuti di gioco reale."""

from __future__ import annotations

TURN_BUDGETS = {"breve": 12, "media": 24, "lunga": 36}
DEFAULT_BUDGET = TURN_BUDGETS["media"]


def compute_pacing(*, duration_target: str, turn_count: int, current_act: int) -> dict:
    budget = TURN_BUDGETS.get(duration_target, DEFAULT_BUDGET)
    per_act = budget / 3
    expected_act = min(3, max(1, int(turn_count // per_act) + 1))

    if current_act < expected_act:
        status = "in_ritardo"
    elif current_act > expected_act:
        status = "in_anticipo"
    else:
        status = "in_linea"

    return {
        "status": status,
        "current_act": current_act,
        "expected_act": expected_act,
        "turn_count": turn_count,
        "estimated_turns_remaining": max(0, budget - turn_count),
    }
