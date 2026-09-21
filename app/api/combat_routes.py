"""API di combattimento (§8): attacchi, reazioni, avanzamento turno, uso
oggetti e cambio arma. Lo stato vive in GameSave.data["combat"]; il codice
tira i dadi e applica le regole, l'IA non interviene mai qui."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.character.sheet import compute_sheet
from app.crud import get_or_create_character, get_or_create_save, save_character_data, save_game_data
from app.db import get_session
from app.game import combat
from app.models import User
from rules.action_economy import ActionEconomyError
from rules.items import ItemUseError, infer_use_cost

router = APIRouter(prefix="/api/game/combat", tags=["combat"])


def _public_combat_state(save_data: dict, character_sheet: dict | None = None) -> dict:
    combat_state = save_data.get("combat")
    if combat_state is None:
        return {"in_combat": False}
    state = {
        "in_combat": True,
        "round": combat_state["round"],
        "combatants": [
            {
                "id": c["id"],
                "name": c["name"],
                "is_player": c["is_player"],
                "hp": c["hp"],
                "ac": c["ac"],
                "used": c["action_economy"]["used"],
            }
            for c in combat_state["combatants"]
        ],
        "current_turn_id": combat.current_combatant(save_data)["id"],
        "pending_reaction": combat_state.get("pending_reaction"),
        "death_save": combat.player_death_save_if_down(save_data),
    }
    if character_sheet is not None:
        active_weapon = combat.resolve_active_weapon(character_sheet, save_data)
        state["active_weapon"] = active_weapon["name_it"] if active_weapon else "a mani nude"
        state["available_weapons"] = combat.list_available_weapons(character_sheet)
        state["inventory"] = character_sheet.get("inventory", [])
    return state


async def _require_combat(session: AsyncSession, user: User):
    character = await get_or_create_character(session, user)
    save = await get_or_create_save(session, user)
    if save.data.get("combat") is None:
        raise HTTPException(status_code=409, detail="nessun combattimento in corso")
    return character, save


@router.get("")
async def get_combat_state(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    character = await get_or_create_character(session, user)
    save = await get_or_create_save(session, user)
    if save.data.get("combat") is None:
        return {"in_combat": False}
    return _public_combat_state(save.data, compute_sheet(character.data))


class AttackRequest(BaseModel):
    target_id: str


@router.post("/attack")
async def post_attack(
    payload: AttackRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    character, save = await _require_combat(session, user)
    sheet = compute_sheet(character.data)
    weapon = combat.resolve_active_weapon(sheet, save.data)
    to_hit, damage_expr = combat.resolve_to_hit_and_damage(sheet, weapon)
    try:
        result = combat.player_attack(save.data, sheet, payload.target_id, to_hit, damage_expr)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ActionEconomyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    target = combat.find_combatant(save.data, payload.target_id)
    flee_reaction = None
    if not target["is_player"] and target["hp"]["current"] > 0:
        flee_reaction = combat.check_flee_opportunity(save.data, target)

    await save_character_data(session, character, character.data)
    await save_game_data(session, save, save.data)
    return {
        "weapon": weapon["name_it"] if weapon else "a mani nude",
        "result": result,
        "flee_reaction": flee_reaction,
        "state": _public_combat_state(save.data, sheet),
    }


class ReactionRequest(BaseModel):
    accept: bool


@router.post("/reaction")
async def post_reaction(
    payload: ReactionRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    character, save = await _require_combat(session, user)
    sheet = compute_sheet(character.data)
    weapon = combat.resolve_active_weapon(sheet, save.data)
    to_hit, damage_expr = combat.resolve_to_hit_and_damage(sheet, weapon)
    try:
        result = combat.resolve_reaction(save.data, sheet, payload.accept, to_hit, damage_expr)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ActionEconomyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    await save_character_data(session, character, character.data)
    await save_game_data(session, save, save.data)
    return {"result": result, "state": _public_combat_state(save.data, sheet)}


@router.post("/advance")
async def post_advance(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    character, save = await _require_combat(session, user)
    sheet = compute_sheet(character.data)
    advance_result = combat.advance_turn(save.data, character.data)
    monster_phase = None
    if not advance_result["combat_ended"] and not advance_result["current"]["is_player"]:
        monster_phase = combat.run_monster_turns_until_player(save.data, character.data)

    await save_character_data(session, character, character.data)
    await save_game_data(session, save, save.data)
    state = _public_combat_state(save.data, sheet) if save.data.get("combat") is not None else {"in_combat": False}
    return {"advance": advance_result, "monster_phase": monster_phase, "state": state}


class WeaponSwapRequest(BaseModel):
    weapon_id: str


@router.post("/weapon-swap")
async def post_weapon_swap(
    payload: WeaponSwapRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    character, save = await _require_combat(session, user)
    sheet = compute_sheet(character.data)
    try:
        weapon = combat.swap_active_weapon(save.data, sheet, payload.weapon_id)
    except combat.WeaponSwapError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ActionEconomyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    await save_game_data(session, save, save.data)
    return {"weapon": weapon["name_it"], "state": _public_combat_state(save.data, sheet)}


class ItemUseRequest(BaseModel):
    item: str


@router.post("/item-use")
async def post_item_use(
    payload: ItemUseRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Consuma la risorsa dell'economia delle azioni per usare un oggetto
    dell'inventario. Nessun effetto meccanico automatico oltre al consumo
    della risorsa: gli oggetti generici non hanno dati SRD estratti per un
    effetto strutturato (semplificazione documentata in DECISIONS.md); un
    eventuale effetto (es. cura) va narrato dall'IA come `hp_delta` nel
    turno successivo, non da questa rotta."""
    character, save = await _require_combat(session, user)
    if payload.item not in character.data.get("inventory", []):
        raise HTTPException(status_code=400, detail=f"oggetto non nell'inventario: {payload.item!r}")

    cost = infer_use_cost(payload.item)
    try:
        combat.use_item_in_combat(save.data, cost)
    except ItemUseError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    character.data["inventory"].remove(payload.item)

    await save_character_data(session, character, character.data)
    await save_game_data(session, save, save.data)
    return {"used": payload.item, "cost": cost.value, "state": _public_combat_state(save.data, compute_sheet(character.data))}
