from __future__ import annotations

from app.telegram import gallery


class FakeBot:
    def __init__(self):
        self.messages: list[tuple[int, str]] = []
        self.media_groups: list[tuple[int, list]] = []

    async def send_message(self, chat_id, text, **kwargs):
        self.messages.append((chat_id, text))

    async def send_media_group(self, chat_id, media, **kwargs):
        self.media_groups.append((chat_id, media))


async def test_unknown_category_lists_options():
    bot = FakeBot()
    await gallery.send_gallery(bot, 1, category="sconosciuta")
    assert bot.messages
    assert "dadi" in bot.messages[0][1]


async def test_missing_assets_sends_hint(tmp_path, monkeypatch):
    monkeypatch.setattr(gallery, "ASSETS_DIR", tmp_path)
    bot = FakeBot()
    await gallery.send_gallery(bot, 1)
    assert bot.messages
    assert "generate_assets" in bot.messages[0][1]


async def test_missing_category_assets_sends_hint(tmp_path, monkeypatch):
    monkeypatch.setattr(gallery, "ASSETS_DIR", tmp_path)
    bot = FakeBot()
    await gallery.send_gallery(bot, 1, category="dadi")
    assert bot.messages
    assert "generate_assets" in bot.messages[0][1]


async def test_sends_contact_sheets_when_present(tmp_path, monkeypatch):
    monkeypatch.setattr(gallery, "ASSETS_DIR", tmp_path)
    (tmp_path / "contact_sheet_1_dadi_icone.png").write_bytes(b"fake-png")

    bot = FakeBot()
    await gallery.send_gallery(bot, 1)
    assert not bot.messages
    assert len(bot.media_groups) == 1
    assert len(bot.media_groups[0][1]) == 1


async def test_sends_category_album_when_present(tmp_path, monkeypatch):
    monkeypatch.setattr(gallery, "ASSETS_DIR", tmp_path)
    dice_dir = tmp_path / "dice"
    dice_dir.mkdir()
    (dice_dir / "dice_d20.png").write_bytes(b"fake-png")

    bot = FakeBot()
    await gallery.send_gallery(bot, 1, category="dadi")
    assert not bot.messages
    assert len(bot.media_groups) == 1
