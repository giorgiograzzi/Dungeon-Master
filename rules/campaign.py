"""Validazione del Piano di Campagna generato dall'AI (§5): il codice
verifica la struttura a grafo prima di darla in pasto al gioco. Se un
controllo fallisce, l'errore indica quale parte rigenerare (il chiamante
decide se rigenerare tutto o solo la sezione indicata)."""

from __future__ import annotations

DURATION_TOLERANCE = 0.15  # ±15% (§5)
MIN_GATE_SOLUTIONS = 3
EXPECTED_ROUTES = 3
EXPECTED_CROSSROADS = 2
EXPECTED_NPCS = 25
MIN_BEATS, MAX_BEATS = 6, 10
MIN_SIDE_QUESTS, MAX_SIDE_QUESTS = 2, 4
MIN_ENDINGS, MAX_ENDINGS = 2, 3


def validate_campaign_plan(plan: dict) -> list[str]:
    """Restituisce la lista di errori trovati (vuota se il piano è valido)."""
    errors: list[str] = []
    errors += _validate_shape(plan)
    errors += _validate_gates(plan)
    errors += _validate_scenes_linked(plan)
    errors += _validate_routes_reach_final_and_no_dead_ends(plan)
    errors += _validate_route_duration_balance(plan)
    errors += _validate_clues_redundant(plan)
    errors += _validate_side_quests(plan)
    return errors


def _validate_shape(plan: dict) -> list[str]:
    errors = []
    routes = plan.get("routes", [])
    if len(routes) != EXPECTED_ROUTES:
        errors.append(f"servono esattamente {EXPECTED_ROUTES} percorsi, trovati {len(routes)}")
    if len(plan.get("crossroads", [])) != EXPECTED_CROSSROADS:
        errors.append(f"servono esattamente {EXPECTED_CROSSROADS} bivi, trovati {len(plan.get('crossroads', []))}")
    if len(plan.get("npcs", [])) != EXPECTED_NPCS:
        errors.append(f"servono esattamente {EXPECTED_NPCS} PNG, trovati {len(plan.get('npcs', []))}")
    n_beats = len(plan.get("beats", []))
    if not (MIN_BEATS <= n_beats <= MAX_BEATS):
        errors.append(f"servono {MIN_BEATS}-{MAX_BEATS} beat, trovati {n_beats}")
    n_sq = len(plan.get("side_quests", []))
    if not (MIN_SIDE_QUESTS <= n_sq <= MAX_SIDE_QUESTS):
        errors.append(f"servono {MIN_SIDE_QUESTS}-{MAX_SIDE_QUESTS} quest secondarie, trovate {n_sq}")
    n_end = len(plan.get("endings", []))
    if not (MIN_ENDINGS <= n_end <= MAX_ENDINGS):
        errors.append(f"servono {MIN_ENDINGS}-{MAX_ENDINGS} finali, trovati {n_end}")
    return errors


def _validate_gates(plan: dict) -> list[str]:
    errors = []
    for gate in plan.get("gates", []):
        n = len(gate.get("solutions", []))
        if n < MIN_GATE_SOLUTIONS:
            errors.append(f"gate {gate.get('id')!r} ha solo {n} soluzioni (minimo {MIN_GATE_SOLUTIONS})")
    return errors


def _validate_scenes_linked(plan: dict) -> list[str]:
    errors = []
    beat_ids = {b["id"] for b in plan.get("beats", [])}
    quest_ids = {q["id"] for q in plan.get("side_quests", [])}
    for scene in plan.get("scenes", []):
        beat_id = scene.get("beat_id")
        quest_id = scene.get("side_quest_id")
        if not beat_id and not quest_id:
            errors.append(f"scena {scene.get('id')!r} non è collegata a nessun beat né quest secondaria")
            continue
        if beat_id and beat_id not in beat_ids:
            errors.append(f"scena {scene.get('id')!r} referenzia un beat inesistente: {beat_id!r}")
        if quest_id and quest_id not in quest_ids:
            errors.append(f"scena {scene.get('id')!r} referenzia una quest inesistente: {quest_id!r}")
    return errors


def _beats_for_route(plan: dict, route_id: str) -> list[dict]:
    return [b for b in plan.get("beats", []) if b.get("route") in (None, route_id)]


def _validate_routes_reach_final_and_no_dead_ends(plan: dict) -> list[str]:
    errors = []
    beats = plan.get("beats", [])
    if not beats:
        return ["nessun beat definito"]
    acts = sorted({b["act"] for b in beats})
    final_act = max(acts)
    hinge_final = [b for b in beats if b["act"] == final_act and b.get("route") is None]
    if not hinge_final:
        errors.append("nessun beat cardine nell'ultimo atto: nessun percorso può raggiungere il finale")
        return errors

    pre_final_acts = [a for a in acts if a != final_act]
    for route in plan.get("routes", []):
        route_id = route["id"]
        # Ogni atto prima del finale deve avere contenuto proprio del percorso
        # (non basta un beat cardine condiviso): altrimenti è un vicolo cieco.
        own_beats = [b for b in beats if b.get("route") == route_id]
        own_acts = {b["act"] for b in own_beats}
        missing_acts = set(pre_final_acts) - own_acts
        if missing_acts:
            errors.append(f"il percorso {route_id!r} non ha beat propri negli atti {sorted(missing_acts)} (vicolo cieco)")
    return errors


def _validate_route_duration_balance(plan: dict) -> list[str]:
    errors = []
    weights: dict[str, int] = {}
    for route in plan.get("routes", []):
        route_id = route["id"]
        weight = len(_beats_for_route(plan, route_id))
        weight += sum(1 for g in plan.get("gates", []) if g.get("route") in (None, route_id))
        weight += sum(1 for q in plan.get("side_quests", []) if q.get("route_id") in (None, route_id))
        weights[route_id] = weight
    if not weights:
        return errors
    lo, hi = min(weights.values()), max(weights.values())
    if lo == 0:
        errors.append("un percorso non ha alcun contenuto stimabile")
    elif (hi - lo) / lo > DURATION_TOLERANCE:
        errors.append(
            f"durate dei percorsi sbilanciate oltre il {int(DURATION_TOLERANCE * 100)}%: {weights}"
        )
    return errors


def _validate_clues_redundant(plan: dict) -> list[str]:
    errors = []
    for clue in plan.get("clues", []):
        if len(clue.get("sources", [])) < 2:
            errors.append(f"indizio {clue.get('fact')!r} ha meno di 2 fonti (non ridondante)")
    return errors


def _validate_side_quests(plan: dict) -> list[str]:
    errors = []
    for quest in plan.get("side_quests", []):
        if not quest.get("reward"):
            errors.append(f"quest secondaria {quest.get('id')!r} senza reward")
        if not quest.get("unlocks"):
            errors.append(f"quest secondaria {quest.get('id')!r} senza unlocks")
        if len(quest.get("solutions", [])) < 2:
            errors.append(f"quest secondaria {quest.get('id')!r} ha meno di 2 modi di risolverla")
    return errors
