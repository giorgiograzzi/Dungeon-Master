"""Test di fumo per gli script di generazione asset (§0/§11): confermano che
girino senza errori e producano i file attesi, prima che il bot li usi in /galleria."""

from __future__ import annotations

from pathlib import Path

from tools import generate_assets, npc_portraits


def test_generate_assets_smoke(tmp_path: Path):
    generate_assets.main(str(tmp_path))
    assert (tmp_path / "contact_sheet_1_dadi_icone.png").exists()
    assert (tmp_path / "contact_sheet_2_classi.png").exists()
    assert (tmp_path / "contact_sheet_3_scene_percorsi.png").exists()
    assert (tmp_path / "dice" / "dice_d20.png").exists()
    assert (tmp_path / "classes" / "class_wizard.png").exists()


def test_npc_portraits_smoke(tmp_path: Path):
    npc_portraits.main(str(tmp_path))
    assert (tmp_path / "contact_sheet_4_png_25.png").exists()
    assert (tmp_path / "contact_sheet_5_catalogo_strati.png").exists()
    assert (tmp_path / "contact_sheet_6_specie.png").exists()
    assert len(list((tmp_path / "npc").glob("*.png"))) == 25


def test_npc_portrait_same_seed_same_face(tmp_path: Path):
    traits_a = npc_portraits.roll(12345, species="dwarf")
    traits_b = npc_portraits.roll(12345, species="dwarf")
    assert traits_a == traits_b
    img_a = npc_portraits.render(traits_a, size=64)
    img_b = npc_portraits.render(traits_b, size=64)
    assert img_a.tobytes() == img_b.tobytes()
