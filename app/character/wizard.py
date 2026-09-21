"""Funzioni pure per ogni step della creazione guidata (§4): prendono il
documento del personaggio e l'input del giocatore, validano contro i dati
SRD (`app.srd_data`) e restituiscono il documento aggiornato. Nessuno stato
nascosto: la persistenza è compito del chiamante (routes)."""

from __future__ import annotations

from app import srd_data
from rules.ability_scores import (
    POINT_BUY_BUDGET,
    STANDARD_ARRAY,
    validate_point_buy,
    validate_standard_array,
)
from rules.text_choices import parse_choice
from rules.text_utils import slugify

ABILITIES = ("for", "des", "cos", "int", "sag", "car")


class WizardError(ValueError):
    """Scelta non valida in uno step della creazione del personaggio."""


def set_species(data: dict, species_id: str) -> dict:
    if species_id not in srd_data.species():
        raise WizardError(f"specie sconosciuta: {species_id!r}")
    data["species_id"] = species_id
    return data


def set_background(data: dict, background_id: str) -> dict:
    backgrounds = srd_data.backgrounds()
    if background_id not in backgrounds:
        raise WizardError(f"background sconosciuto: {background_id!r}")
    bg = backgrounds[background_id]
    data["background_id"] = background_id
    data["feat_id"] = _match_feat_id(bg["feat"])
    data["background_skills"] = _resolve_skill_names(bg["skill_proficiencies"])
    return data


def _match_feat_id(feat_text: str) -> str | None:
    """Il campo 'Talento' del background cita il nome e a volte una nota tra
    parentesi (es. 'Iniziato alla magia (chierico)'): confrontiamo solo il nome."""
    name = feat_text.split("(")[0].strip()
    target = slugify(name)
    for feat_id, feat in srd_data.feats().items():
        if slugify(feat["name_it"]) == target:
            return feat_id
    return None


def _resolve_skill_names(text: str) -> list[str]:
    """'Intuizione e Religione' -> ['intuizione', 'religione'] (id da skills.json)."""
    cleaned = text.replace(" e ", ", ")
    names = [n.strip() for n in cleaned.split(",") if n.strip()]
    return [_skill_id_for_name(n) for n in names]


def _skill_id_for_name(name: str) -> str:
    target = slugify(name)
    for skill_id, skill in srd_data.skills().items():
        if slugify(skill["name_it"]) == target:
            return skill_id
    raise WizardError(f"abilità sconosciuta nel testo SRD: {name!r}")


def set_class(data: dict, class_id: str, skill_choices: list[str], equipment_choice: str) -> dict:
    classes = srd_data.classes()
    if class_id not in classes:
        raise WizardError(f"classe sconosciuta: {class_id!r}")
    cls = classes[class_id]

    choice = parse_choice(cls["skill_proficiencies"])
    if len(skill_choices) != choice.count:
        raise WizardError(f"servono esattamente {choice.count} abilità, ricevute {len(skill_choices)}")
    if len(set(skill_choices)) != len(skill_choices):
        raise WizardError("abilità duplicate nella scelta")
    all_skills = srd_data.skills()
    for skill_id in skill_choices:
        if skill_id not in all_skills:
            raise WizardError(f"abilità sconosciuta: {skill_id!r}")
    if choice.options is not None:
        allowed = {_skill_id_for_name(o) for o in choice.options}
        invalid = set(skill_choices) - allowed
        if invalid:
            raise WizardError(f"abilità non tra le opzioni di classe: {sorted(invalid)}")

    valid_letters = _equipment_options(cls["starting_equipment"])
    if equipment_choice not in valid_letters:
        raise WizardError(f"opzione equipaggiamento non valida: {equipment_choice!r} (valide: {sorted(valid_letters)})")

    data["class_id"] = class_id
    data["class_skill_choices"] = skill_choices
    data["equipment_choice"] = equipment_choice
    return data


def _equipment_options(text: str) -> set[str]:
    import re

    return set(re.findall(r"\(([A-C])\)", text))


def set_ability_scores(data: dict, method: str, scores: dict[str, int]) -> dict:
    if set(scores) != set(ABILITIES):
        raise WizardError(f"servono tutte le 6 caratteristiche: {ABILITIES}")

    if method == "standard_array":
        if not validate_standard_array(list(scores.values())):
            raise WizardError(f"i valori devono essere l'array standard {STANDARD_ARRAY}, permutato")
    elif method == "point_buy":
        if not validate_point_buy(scores):
            raise WizardError(f"il costo supera il budget di {POINT_BUY_BUDGET} punti")
    elif method == "4d6":
        rolled = data.get("rolled_scores")
        if not rolled or sorted(rolled) != sorted(scores.values()):
            raise WizardError("i valori assegnati devono corrispondere ai punteggi tirati")
    else:
        raise WizardError(f"metodo sconosciuto: {method!r} (standard_array | point_buy | 4d6)")

    data["ability_score_method"] = method
    data["ability_scores"] = scores
    return data


def set_background_bonus(data: dict, bonus: dict[str, int]) -> dict:
    """+2/+1 su due caratteristiche, oppure +1/+1/+1 su tre (§4)."""
    if not data.get("background_id"):
        raise WizardError("scegli prima il background")
    if any(a not in ABILITIES for a in bonus):
        raise WizardError("caratteristica sconosciuta nel bonus")
    values = sorted(bonus.values(), reverse=True)
    if values not in ([2, 1], [1, 1, 1]):
        raise WizardError("il bonus deve essere +2/+1 su due caratteristiche o +1/+1/+1 su tre")
    scores = data.get("ability_scores")
    if scores:
        for ability, increment in bonus.items():
            if scores[ability] + increment > 20:
                raise WizardError(f"il bonus porterebbe {ability} oltre 20")
    data["background_bonus"] = bonus
    return data


def set_personal_details(data: dict, name: str, details: dict[str, str]) -> dict:
    if not name or not name.strip():
        raise WizardError("il nome del personaggio non può essere vuoto")
    allowed_keys = {"appearance", "traits", "ideals", "bonds", "flaws", "backstory"}
    unknown = set(details) - allowed_keys
    if unknown:
        raise WizardError(f"campi sconosciuti: {sorted(unknown)}")
    data["name"] = name.strip()
    data["personal_details"].update(details)
    return data
