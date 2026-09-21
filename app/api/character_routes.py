"""API della creazione guidata del personaggio (§4) e della scheda (§4.7)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app import srd_data
from app.api.deps import get_current_user
from app.character import wizard
from app.character.sheet import compute_sheet, is_complete_for_summary
from app.crud import get_or_create_character, save_character_data
from app.db import get_session
from app.models import User
from rules.ability_scores import STANDARD_ARRAY, roll_ability_scores
from rules.text_choices import parse_choice

router = APIRouter(prefix="/api/character", tags=["character"])


def _apply(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except wizard.WizardError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("")
async def get_character(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    character = await get_or_create_character(session, user)
    return {"status": character.status, "data": character.data, "missing": is_complete_for_summary(character.data)}


@router.get("/sheet")
async def get_character_sheet(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    character = await get_or_create_character(session, user)
    try:
        return compute_sheet(character.data)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


class SpeciesRequest(BaseModel):
    species_id: str


@router.post("/species")
async def post_species(
    payload: SpeciesRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    character = await get_or_create_character(session, user)
    data = _apply(wizard.set_species, character.data, payload.species_id)
    data["step"] = "class"
    character = await save_character_data(session, character, data)
    return {"data": character.data}


class ClassRequest(BaseModel):
    class_id: str
    skill_choices: list[str]
    equipment_choice: str


@router.post("/class")
async def post_class(
    payload: ClassRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    character = await get_or_create_character(session, user)
    data = _apply(
        wizard.set_class, character.data, payload.class_id, payload.skill_choices, payload.equipment_choice
    )
    data["step"] = "background"
    character = await save_character_data(session, character, data)
    return {"data": character.data}


class BackgroundRequest(BaseModel):
    background_id: str


@router.post("/background")
async def post_background(
    payload: BackgroundRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    character = await get_or_create_character(session, user)
    data = _apply(wizard.set_background, character.data, payload.background_id)
    data["step"] = "ability_scores"
    character = await save_character_data(session, character, data)
    return {"data": character.data}


@router.post("/ability-scores/roll")
async def post_roll_ability_scores(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    character = await get_or_create_character(session, user)
    data = character.data
    data["rolled_scores"] = roll_ability_scores()
    character = await save_character_data(session, character, data)
    return {"rolled_scores": character.data["rolled_scores"]}


class AbilityScoresRequest(BaseModel):
    method: str
    scores: dict[str, int]


@router.post("/ability-scores")
async def post_ability_scores(
    payload: AbilityScoresRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    character = await get_or_create_character(session, user)
    data = _apply(wizard.set_ability_scores, character.data, payload.method, payload.scores)
    data["step"] = "skills"
    character = await save_character_data(session, character, data)
    return {"data": character.data}


class BackgroundBonusRequest(BaseModel):
    bonus: dict[str, int]


@router.post("/background-bonus")
async def post_background_bonus(
    payload: BackgroundBonusRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    character = await get_or_create_character(session, user)
    data = _apply(wizard.set_background_bonus, character.data, payload.bonus)
    data["step"] = "details"
    character = await save_character_data(session, character, data)
    return {"data": character.data}


class PersonalDetailsRequest(BaseModel):
    name: str
    details: dict[str, str] = {}


@router.post("/details")
async def post_details(
    payload: PersonalDetailsRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    character = await get_or_create_character(session, user)
    data = _apply(wizard.set_personal_details, character.data, payload.name, payload.details)
    data["step"] = "summary"
    if not is_complete_for_summary(data):
        character.status = "complete"
        data = wizard.finalize_character(data)
    character = await save_character_data(session, character, data)
    return {"data": character.data, "status": character.status}


@router.get("/options")
async def get_character_options() -> dict:
    """Opzioni per la UI della creazione guidata: niente dati di gioco a
    memoria nel frontend, tutto viene da qui (§0.2)."""

    def _class_summary(c: dict) -> dict:
        choice = parse_choice(c["skill_proficiencies"])
        return {
            "id": c["id"],
            "name_it": c["name_it"],
            "hit_die": c["hit_die"],
            "primary_abilities": c["primary_abilities"],
            "spellcasting": c["spellcasting"],
            "starting_equipment": c["starting_equipment"],
            "skill_choice_count": choice.count,
            "skill_choice_options": list(choice.options) if choice.options else None,
        }

    return {
        "species": [
            {"id": s["id"], "name_it": s["name_it"], "size": s["size"], "speed": s["speed"]}
            for s in srd_data.species().values()
        ],
        "classes": [_class_summary(c) for c in srd_data.classes().values()],
        "backgrounds": [
            {"id": b["id"], "name_it": b["name_it"], "ability_scores": b["ability_scores"], "feat": b["feat"]}
            for b in srd_data.backgrounds().values()
        ],
        "skills": [
            {"id": s["id"], "name_it": s["name_it"], "ability": s["ability"]} for s in srd_data.skills().values()
        ],
        "standard_array": STANDARD_ARRAY,
    }
