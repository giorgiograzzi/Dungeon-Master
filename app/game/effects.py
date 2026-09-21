"""Applica gli `effects` proposti dall'AI (§10): il codice valida e applica,
l'AI non cambia mai lo stato da sola (§0.1). Un effetto sconosciuto o mal
formato viene scartato con un avviso, mai applicato alla cieca."""

from __future__ import annotations

import logging

from app.ai.tools import EFFECT_TYPES
from rules.hit_points import HitPoints

logger = logging.getLogger(__name__)


def _hp_wrapper(character_data: dict) -> HitPoints:
    return HitPoints(
        current=character_data.get("hp_current") or 0,
        maximum=character_data.get("hp_max") or 0,
        temp=character_data.get("hp_temp", 0),
    )


def _sync_hp(character_data: dict, hp: HitPoints) -> None:
    character_data["hp_current"] = hp.current
    character_data["hp_max"] = hp.maximum
    character_data["hp_temp"] = hp.temp


def apply_effects(character_data: dict, save_data: dict, effects: list[dict]) -> list[str]:
    """Applica in sequenza gli effetti; restituisce un log testuale di ciò
    che è stato fatto (utile per il registro dei tiri/eventi)."""
    applied: list[str] = []
    for effect in effects:
        etype = effect.get("type")
        if etype not in EFFECT_TYPES:
            logger.warning("effetto sconosciuto scartato: %r", etype)
            continue
        handler = _HANDLERS.get(etype)
        if handler is None:
            logger.warning("nessun handler per l'effetto %r, scartato", etype)
            continue
        applied.append(handler(character_data, save_data, effect))
    return applied


def _hp_delta(character_data: dict, save_data: dict, effect: dict) -> str:
    hp = _hp_wrapper(character_data)
    delta = int(effect.get("value", 0))
    if delta >= 0:
        hp.heal(delta)
    else:
        hp.apply_damage(-delta)
    _sync_hp(character_data, hp)
    return f"PF: {delta:+d} (ora {hp.current}/{hp.maximum})"


def _temp_hp(character_data: dict, save_data: dict, effect: dict) -> str:
    hp = _hp_wrapper(character_data)
    hp.add_temp_hp(int(effect.get("value", 0)))
    _sync_hp(character_data, hp)
    return f"PF temporanei: {hp.temp}"


def _item_add(character_data: dict, save_data: dict, effect: dict) -> str:
    character_data.setdefault("inventory", []).append(effect.get("target", "oggetto"))
    return f"Aggiunto all'inventario: {effect.get('target')}"


def _item_remove(character_data: dict, save_data: dict, effect: dict) -> str:
    inventory = character_data.setdefault("inventory", [])
    target = effect.get("target")
    if target in inventory:
        inventory.remove(target)
    return f"Rimosso dall'inventario: {target}"


def _condition_add(character_data: dict, save_data: dict, effect: dict) -> str:
    conditions = character_data.setdefault("conditions", [])
    target = effect.get("target")
    if target and target not in conditions:
        conditions.append(target)
    return f"Condizione applicata: {target}"


def _condition_remove(character_data: dict, save_data: dict, effect: dict) -> str:
    conditions = character_data.setdefault("conditions", [])
    target = effect.get("target")
    if target in conditions:
        conditions.remove(target)
    return f"Condizione rimossa: {target}"


def _gold(character_data: dict, save_data: dict, effect: dict) -> str:
    delta = int(effect.get("value", 0))
    character_data["gold_adjustment"] = character_data.get("gold_adjustment", 0) + delta
    return f"Monete: {delta:+d}"


def _fact_add(character_data: dict, save_data: dict, effect: dict) -> str:
    facts = save_data.setdefault("facts", [])
    value = effect.get("value")
    if value and value not in facts:
        facts.append(value)
    return f"Fatto registrato: {value}"


def _quest_update(character_data: dict, save_data: dict, effect: dict) -> str:
    save_data.setdefault("quest_notes", []).append(effect.get("value", ""))
    return f"Nota missione: {effect.get('value')}"


def _start_combat(character_data: dict, save_data: dict, effect: dict) -> str:
    # L'avvio vero e proprio (iniziativa, stat block dei mostri) richiede la
    # scheda del personaggio: lo fa app.game.combat.start_combat, chiamato
    # dal chiamante di apply_effects quando trova questo marcatore (§8).
    monster_ids = effect.get("value") or []
    save_data["_pending_combat_monsters"] = monster_ids if isinstance(monster_ids, list) else [monster_ids]
    return f"Combattimento in arrivo: {monster_ids}"


def _end_combat(character_data: dict, save_data: dict, effect: dict) -> str:
    save_data["mode"] = "exploration"
    save_data["combat"] = None
    return "Combattimento terminato"


def _beat_progress(character_data: dict, save_data: dict, effect: dict) -> str:
    beats = save_data.setdefault("completed_beats", [])
    target = effect.get("target")
    if target and target not in beats:
        beats.append(target)
    return f"Beat avanzato: {target}"


def _side_quest(status: str):
    def handler(character_data: dict, save_data: dict, effect: dict) -> str:
        target = effect.get("target")
        save_data.setdefault("side_quests_state", {})[target] = status
        return f"Quest secondaria {target}: {status}"

    return handler


def _route_chosen(character_data: dict, save_data: dict, effect: dict) -> str:
    save_data["current_route_id"] = effect.get("value")
    return f"Percorso scelto: {effect.get('value')}"


def _gate_solved(character_data: dict, save_data: dict, effect: dict) -> str:
    gates = save_data.setdefault("solved_gates", [])
    target = effect.get("target")
    if target and target not in gates:
        gates.append(target)
    return f"Gate risolto: {target}"


def _npc_state(target_key: str):
    def get_npc(save_data: dict, target: str) -> dict:
        return save_data.setdefault("npc_state", {}).setdefault(
            target, {"attitude": 0, "known": [], "status": "sconosciuto"}
        )

    def handler(character_data: dict, save_data: dict, effect: dict) -> str:
        npc = get_npc(save_data, effect.get("target"))
        if target_key == "attitude":
            npc["attitude"] += int(effect.get("value", 0))
        elif target_key == "known":
            fact = effect.get("value")
            if fact and fact not in npc["known"]:
                npc["known"].append(fact)
        elif target_key == "status":
            npc["status"] = effect.get("value")
        return f"PNG {effect.get('target')}: {target_key} aggiornato"

    return handler


_HANDLERS = {
    "hp_delta": _hp_delta,
    "temp_hp": _temp_hp,
    "item_add": _item_add,
    "item_remove": _item_remove,
    "condition_add": _condition_add,
    "condition_remove": _condition_remove,
    "gold": _gold,
    "fact_add": _fact_add,
    "quest_update": _quest_update,
    "start_combat": _start_combat,
    "end_combat": _end_combat,
    "beat_progress": _beat_progress,
    "side_quest_start": _side_quest("aperta"),
    "side_quest_update": _side_quest("aggiornata"),
    "side_quest_complete": _side_quest("completata"),
    "route_chosen": _route_chosen,
    "gate_solved": _gate_solved,
    "npc_attitude": _npc_state("attitude"),
    "npc_learned": _npc_state("known"),
    "npc_status": _npc_state("status"),
}
