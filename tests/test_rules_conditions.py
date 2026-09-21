from __future__ import annotations

import json
from pathlib import Path

import pytest

from rules.conditions import (
    CONDITIONS,
    attack_against_prone,
    exhaustion_d20_penalty,
    exhaustion_is_lethal,
    exhaustion_speed_reduction_m,
    get_effect,
    resolve_conditions,
)

CONDITIONS_JSON = Path(__file__).resolve().parent.parent / "data" / "srd" / "conditions.json"


def test_all_extracted_conditions_have_a_mechanical_entry():
    extracted = json.loads(CONDITIONS_JSON.read_text(encoding="utf-8"))
    ids = {c["id"] for c in extracted}
    assert ids == set(CONDITIONS)


def test_paralizzato_effects():
    e = get_effect("paralizzato")
    assert e.incapacitated
    assert e.speed_zero
    assert e.auto_fail_str_dex_saves
    assert e.attacks_against_advantage
    assert e.melee_crit_within_reach


def test_invisibile_effects():
    e = get_effect("invisibile")
    assert e.attacks_against_disadvantage
    assert e.attacks_by_self_advantage
    assert e.initiative_advantage


def test_unknown_condition():
    with pytest.raises(ValueError):
        get_effect("congelato")


def test_resolve_conditions_expands_implied():
    assert resolve_conditions({"paralizzato"}) == {"paralizzato", "incapacitato"}
    assert resolve_conditions({"privo_di_sensi"}) == {"privo_di_sensi", "incapacitato", "prono"}


def test_attack_against_prone_depends_on_distance():
    assert attack_against_prone(attacker_is_within_melee_reach=True) == "advantage"
    assert attack_against_prone(attacker_is_within_melee_reach=False) == "disadvantage"


def test_exhaustion_scaling():
    assert exhaustion_d20_penalty(2) == 4
    assert exhaustion_speed_reduction_m(2) == 3.0
    assert not exhaustion_is_lethal(5)
    assert exhaustion_is_lethal(6)
