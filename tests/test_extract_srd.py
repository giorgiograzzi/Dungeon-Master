"""Verifica che tools/extract_srd.py produca dati sensati dal PDF reale
(non un mock): conteggi minimi e alcuni valori noti, per intercettare
regressioni nel parsing se il PDF cambia o il regex si rompe."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools import extract_srd as ex

PDF_PATH = Path(__file__).resolve().parent.parent / "docs" / "srd" / "IT_SRD_CC_v5.2.1.pdf"

pytestmark = pytest.mark.skipif(not PDF_PATH.exists(), reason="PDF dell'SRD non presente nel repo")


@pytest.fixture(scope="module")
def pages():
    return ex.load_page_texts(str(PDF_PATH))


@pytest.fixture(scope="module")
def toc(pages):
    return ex.parse_toc(pages)


def test_species_count_and_fields(pages, toc):
    species = ex.extract_species(pages, toc)
    assert len(species) == 9
    umano = next(s for s in species if s["id"] == "umano")
    assert umano["creature_type"] == "umanoide"
    assert "9 m" in umano["speed"] or "9" in umano["speed"]
    assert len(umano["traits"]) >= 2


def test_backgrounds_count(pages, toc):
    backgrounds = ex.extract_backgrounds(pages, toc)
    assert len(backgrounds) == 4
    assert {b["id"] for b in backgrounds} == {"accolito", "criminale", "sapiente", "soldato"}


def test_classes_count_and_key_fields(pages, toc):
    classes = ex.extract_classes(pages, toc)
    assert len(classes) == 12
    by_id = {c["id"]: c for c in classes}
    assert by_id["barbaro"]["hit_die"].startswith("D12")
    assert by_id["mago"]["hit_die"].startswith("D6")
    assert by_id["barbaro"]["subclass_name"] == "Cammino del berserker"
    assert by_id["mago"]["spellcasting"] is True
    assert by_id["barbaro"]["spellcasting"] is False
    # La tabella dei privilegi per livello va a capo su più righe per le classi
    # incantatrici (slot incantesimo): il conteggio esatto non è garantito per
    # loro (vedi DECISIONS.md), ma barbaro/guerriero (senza slot) sono puliti.
    assert len(by_id["barbaro"]["levels"]) == 20
    assert len(by_id["guerriero"]["levels"]) == 20
    for c in classes:
        assert len(c["levels"]) >= 14


def test_feats_have_all_categories(pages, toc):
    feats = ex.extract_feats(pages, toc)
    assert len(feats) >= 15
    categories = {f["category"] for f in feats}
    assert categories == {"Origini", "Generali", "Stile di combattimento", "Dono epico"}


def test_conditions_full_set(pages, toc):
    conditions = ex.extract_conditions(pages, toc)
    assert len(conditions) == 15
    assert {"accecato", "prono", "paralizzato", "invisibile"} <= {c["id"] for c in conditions}


def test_equipment_weapons_and_armor(pages, toc):
    equipment = ex.extract_equipment(str(PDF_PATH), toc)
    weapon_names = {w["name_it"] for w in equipment["weapons"]}
    assert {"Pugnale", "Spada corta", "Arco lungo", "Stocco", "Balestra a mano"} <= weapon_names
    armor_names = {a["name_it"] for a in equipment["armor"]}
    assert {"Armatura di cuoio", "Cotta di maglia", "Armatura a piastre", "Scudo"} <= armor_names


def test_spells_include_known_ones(pages, toc):
    spells = ex.extract_spells(pages, toc)
    assert len(spells) >= 300
    by_name = {s["name_it"]: s for s in spells}
    fireball = by_name["Palla di fuoco"]
    assert fireball["level"] == 3
    assert fireball["duration"] == "istantanea"
    assert "Durata:" not in fireball["description"]


def test_skills_are_the_full_srd_set(pages, toc):
    skills = ex.extract_skills(pages, toc)
    assert len(skills) == 18
    by_name = {s["name_it"]: s["ability"] for s in skills}
    assert by_name["Furtività"] == "des"
    assert by_name["Sopravvivenza"] == "sag"
    assert by_name["Addestrare animali"] == "sag"


def test_monsters_known_stat_block(pages, toc):
    monsters = ex.extract_monsters(pages, toc)
    assert len(monsters) >= 250
    goblin = next(m for m in monsters if m["name_it"] == "Goblin guerriero")
    assert goblin["ac"] == 15
    assert goblin["hp"] == 10
    assert goblin["abilities"]["dex"]["score"] == 15
    assert goblin["abilities"]["str"]["score"] == 8
