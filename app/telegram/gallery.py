"""Comando /galleria (§11/§14): manda su Telegram i contact sheet e, a richiesta,
gli album per categoria, così le immagini generate si vedono subito in chat."""

from __future__ import annotations

from pathlib import Path

from telegram import Bot, InputMediaPhoto

ASSETS_DIR = Path(__file__).resolve().parent.parent.parent / "webapp" / "assets"

CONTACT_SHEETS = [
    ("contact_sheet_1_dadi_icone.png", "Dadi, icone di azione/stato e oggetti"),
    ("contact_sheet_2_classi.png", "Le 12 classi"),
    ("contact_sheet_3_scene_percorsi.png", "Scene, carte percorso e mappa del viaggio"),
    ("contact_sheet_4_png_25.png", "25 PNG di esempio"),
    ("contact_sheet_5_catalogo_strati.png", "Catalogo degli strati dei ritratti"),
    ("contact_sheet_6_specie.png", "Le 9 specie dell'SRD"),
]

CATEGORIES = {
    "dadi": "dice",
    "icone": "icons",
    "oggetti": "items",
    "classi": "classes",
    "scene": "scenes",
    "percorsi": "routes",
    "mappa": "map",
    "png": "npc",
}

MISSING_HINT = (
    "Gli asset non sono ancora stati generati.\n"
    "In locale: `python tools/generate_assets.py && python tools/npc_portraits.py`\n"
    "(nel deploy Docker vengono generati automaticamente in fase di build)."
)


async def send_gallery(bot: Bot, chat_id: int, category: str | None = None) -> None:
    if category:
        await _send_category(bot, chat_id, category)
        return

    media = []
    for filename, caption in CONTACT_SHEETS:
        path = ASSETS_DIR / filename
        if path.exists():
            media.append(InputMediaPhoto(path.read_bytes(), caption=caption))

    if not media:
        await bot.send_message(chat_id, MISSING_HINT, parse_mode="Markdown")
        return

    for i in range(0, len(media), 10):
        await bot.send_media_group(chat_id, media[i : i + 10])


async def _send_category(bot: Bot, chat_id: int, category: str) -> None:
    folder = CATEGORIES.get(category)
    if not folder:
        options = ", ".join(sorted(CATEGORIES))
        await bot.send_message(chat_id, f"Categoria sconosciuta. Scegli tra: {options}")
        return

    files = sorted((ASSETS_DIR / folder).glob("*.png"))[:10]
    if not files:
        await bot.send_message(chat_id, MISSING_HINT, parse_mode="Markdown")
        return

    media = [InputMediaPhoto(f.read_bytes(), caption=f.stem if i == 0 else None) for i, f in enumerate(files)]
    await bot.send_media_group(chat_id, media)
