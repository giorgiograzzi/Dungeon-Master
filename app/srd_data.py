"""Carica in memoria i dati SRD estratti (data/srd/*.json) e li espone
indicizzati per id, come base dati di sola lettura per la creazione del
personaggio e, più avanti, per il narratore AI."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "srd"


def _load(name: str) -> list[dict]:
    path = DATA_DIR / f"{name}.json"
    with path.open(encoding="utf-8") as f:
        return json.load(f)


@lru_cache
def species() -> dict[str, dict]:
    return {s["id"]: s for s in _load("species")}


@lru_cache
def classes() -> dict[str, dict]:
    return {c["id"]: c for c in _load("classes")}


@lru_cache
def backgrounds() -> dict[str, dict]:
    return {b["id"]: b for b in _load("backgrounds")}


@lru_cache
def feats() -> dict[str, dict]:
    return {f["id"]: f for f in _load("feats")}


@lru_cache
def skills() -> dict[str, dict]:
    return {s["id"]: s for s in _load("skills")}


@lru_cache
def weapons() -> dict[str, dict]:
    return {w["id"]: w for w in _load("weapons")}


@lru_cache
def armor() -> dict[str, dict]:
    return {a["id"]: a for a in _load("armor")}


@lru_cache
def conditions() -> dict[str, dict]:
    return {c["id"]: c for c in _load("conditions")}


@lru_cache
def spells() -> dict[str, dict]:
    return {s["id"]: s for s in _load("spells")}


@lru_cache
def monsters() -> dict[str, dict]:
    return {m["id"]: m for m in _load("monsters")}
