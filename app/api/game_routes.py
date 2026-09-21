"""API del gioco (§3, §5, §6): piano di campagna, turni, bivi, salvataggi.
Il Piano di Campagna resta sul server; le rotte espongono solo riepiloghi
senza spoiler."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.client import get_ai_client
from app.ai.prompts import narrator_system_prompt
from app.api.deps import get_current_user
from app.character.sheet import compute_sheet
from app.config import settings
from app.crud import (
    create_manual_save,
    get_or_create_character,
    get_or_create_save,
    list_saves,
    load_save_into_autosave,
    save_character_data,
    save_game_data,
)
from app.db import get_session
from app.game.campaign import (
    CampaignPlanInvalid,
    choose_route,
    generate_and_validate_campaign_plan,
    is_at_crossroads,
    present_crossroads,
    public_campaign_summary,
    rewind_to_crossroad,
)
from app.game.diary import build_diary
from app.game.milestones import maybe_level_up
from app.game.stats import compute_stats
from app.game.story import export_story
from app.game.turn import DailyCapExceeded, play_turn
from app.models import User

router = APIRouter(prefix="/api/game", tags=["game"])


def _ai_client():
    return get_ai_client(dev_fake_ai=settings.dev_fake_ai, api_key=settings.anthropic_api_key)


class CampaignRequest(BaseModel):
    setting: str
    duration: str


@router.post("/campaign")
async def post_campaign(
    payload: CampaignRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    save = await get_or_create_save(session, user)
    try:
        plan = await generate_and_validate_campaign_plan(
            ai_client=_ai_client(),
            model=settings.model_climax,
            system_prompt=narrator_system_prompt(),
            setting=payload.setting,
            duration=payload.duration,
        )
    except CampaignPlanInvalid as exc:
        raise HTTPException(status_code=502, detail=f"piano non valido: {exc.errors}") from exc

    data = save.data
    data["campaign_plan"] = plan
    save = await save_game_data(session, save, data)
    return public_campaign_summary(plan, save.data)


@router.get("")
async def get_game_state(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    save = await get_or_create_save(session, user)
    plan = save.data.get("campaign_plan")
    if plan is None:
        return {"has_campaign": False}
    return {
        "has_campaign": True,
        **public_campaign_summary(plan, save.data),
        "recent_turns": [
            {"action": t["action"], "narration": t["narration"], "options": t.get("options", [])}
            for t in save.data.get("turn_log", [])[-5:]
        ],
        "facts": save.data.get("facts", []),
    }


class TurnRequest(BaseModel):
    turn_id: str
    action: str


@router.post("/turn")
async def post_turn(
    payload: TurnRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    character = await get_or_create_character(session, user)
    if character.status != "complete":
        raise HTTPException(status_code=409, detail="crea prima il personaggio")
    save = await get_or_create_save(session, user)

    sheet = compute_sheet(character.data)
    try:
        turn_record = await play_turn(
            character_sheet=sheet,
            character_data=character.data,
            save_data=save.data,
            action_text=payload.action,
            turn_id=payload.turn_id,
            ai_client=_ai_client(),
            model=settings.model_narrator,
            system_prompt=narrator_system_prompt(),
            daily_cap=settings.daily_turn_cap,
        )
    except DailyCapExceeded as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc

    await save_character_data(session, character, character.data)
    await save_game_data(session, save, save.data)
    return turn_record


@router.get("/crossroads")
async def get_crossroads(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    save = await get_or_create_save(session, user)
    plan = save.data.get("campaign_plan")
    if plan is None:
        raise HTTPException(status_code=409, detail="nessuna campagna in corso")
    crossroad = is_at_crossroads(plan, save.data)
    if crossroad is None:
        return {"at_crossroads": False}
    presentation = await present_crossroads(
        ai_client=_ai_client(), model=settings.model_climax, system_prompt=narrator_system_prompt(),
        plan=plan, crossroad=crossroad,
    )
    return {"at_crossroads": True, **presentation}


class ChooseRouteRequest(BaseModel):
    route_id: str


@router.post("/crossroads/choose")
async def post_choose_route(
    payload: ChooseRouteRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    save = await get_or_create_save(session, user)
    plan = save.data.get("campaign_plan")
    if plan is None:
        raise HTTPException(status_code=409, detail="nessuna campagna in corso")
    crossroad = is_at_crossroads(plan, save.data)
    if crossroad is None:
        raise HTTPException(status_code=409, detail="non sei a un bivio")
    if payload.route_id not in crossroad["route_ids"]:
        raise HTTPException(status_code=400, detail=f"percorso non disponibile a questo bivio: {payload.route_id!r}")

    choose_route(save.data, payload.route_id)

    character = await get_or_create_character(session, user)
    sheet = compute_sheet(character.data)
    level_up = maybe_level_up(save.data, character.data, sheet)
    if level_up is not None:
        await save_character_data(session, character, character.data)

    save = await save_game_data(session, save, save.data)
    return {**public_campaign_summary(plan, save.data), "level_up": level_up}


@router.get("/saves")
async def get_saves(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    saves = await list_saves(session, user)
    return {
        "saves": [
            {
                "slot": s.slot,
                "name": s.name,
                "turn_count": s.data.get("turn_count", 0),
                "updated_at": s.updated_at.isoformat(),
            }
            for s in saves
        ]
    }


class ManualSaveRequest(BaseModel):
    name: str


@router.post("/saves/manual")
async def post_manual_save(
    payload: ManualSaveRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    autosave = await get_or_create_save(session, user)
    try:
        manual = await create_manual_save(session, user, payload.name, dict(autosave.data))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"slot": manual.slot, "name": manual.name}


@router.get("/saves/export")
async def get_save_export(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    save = await get_or_create_save(session, user)
    return save.data


class LoadSaveRequest(BaseModel):
    slot: str


@router.post("/saves/load")
async def post_load_save(
    payload: LoadSaveRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """'Riavvolgi all'ultimo salvataggio' (§5): copia uno slot manuale
    nell'autosave, che diventa la partita attiva."""
    try:
        save = await load_save_into_autosave(session, user, payload.slot)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    plan = save.data.get("campaign_plan")
    if plan is None:
        return {"has_campaign": False}
    return {"has_campaign": True, **public_campaign_summary(plan, save.data)}


@router.get("/diary")
async def get_diary(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    save = await get_or_create_save(session, user)
    plan = save.data.get("campaign_plan")
    if plan is None:
        raise HTTPException(status_code=409, detail="nessuna campagna in corso")
    return build_diary(plan, save.data)


@router.get("/story")
async def get_story_export(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    character = await get_or_create_character(session, user)
    save = await get_or_create_save(session, user)
    if save.data.get("campaign_plan") is None:
        raise HTTPException(status_code=409, detail="nessuna campagna in corso")
    sheet = compute_sheet(character.data)
    story_text = await export_story(
        ai_client=_ai_client(), model=settings.model_climax, system_prompt=narrator_system_prompt(),
        character_sheet=sheet, save_data=save.data,
    )
    return {"story_text": story_text}


@router.get("/finale")
async def get_finale(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    save = await get_or_create_save(session, user)
    plan = save.data.get("campaign_plan")
    if plan is None or not save.data.get("ended"):
        raise HTTPException(status_code=409, detail="l'avventura non è ancora conclusa")
    ending_id = save.data.get("ending_id")
    ending = next((e for e in plan.get("endings", []) if e["id"] == ending_id), None)
    last_turn = save.data.get("turn_log", [])[-1] if save.data.get("turn_log") else None
    return {
        "ending": ending,
        "epilogue": last_turn["narration"] if last_turn else "",
        "stats": compute_stats(save.data),
        "rewards_obtained": save.data.get("rewards_obtained", []),
    }


class RewindRequest(BaseModel):
    crossroad_index: int


@router.post("/rewind")
async def post_rewind(
    payload: RewindRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """'Rigioca da un bivio' (§5): ripristina lo stato subito prima di aver
    scelto un percorso a quel bivio, per provarne un altro."""
    save = await get_or_create_save(session, user)
    plan = save.data.get("campaign_plan")
    if plan is None:
        raise HTTPException(status_code=409, detail="nessuna campagna in corso")
    try:
        rewind_to_crossroad(save.data, payload.crossroad_index)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    save = await save_game_data(session, save, save.data)
    return public_campaign_summary(plan, save.data)
