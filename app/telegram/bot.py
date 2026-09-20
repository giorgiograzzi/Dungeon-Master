"""Bot Telegram in modalità webhook (§1): /start, /gioca, /aiuto, /galleria."""

from __future__ import annotations

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, MenuButtonWebApp, Update, WebAppInfo
from telegram.ext import Application, CommandHandler, ContextTypes

from app.config import settings
from app.telegram.gallery import send_gallery

logger = logging.getLogger(__name__)

WELCOME = (
    "🎲 Benvenuto nel *Dungeon Master Tascabile*!\n\n"
    "Un'avventura fantasy in solitaria, narrata dall'AI e arbitrata dal codice. "
    "Premi il pulsante qui sotto per aprire la Mini App e iniziare."
)
HELP = (
    "Comandi disponibili:\n"
    "/start – apri il menu iniziale\n"
    "/gioca – apri la Mini App di gioco\n"
    "/galleria – guarda dadi, icone, classi, scene e ritratti dei PNG generati\n"
    "/aiuto – questo messaggio"
)
NOT_ALLOWED = "Non sei autorizzato a usare questo bot."


def _is_allowed(user_id: int) -> bool:
    allowed = settings.allowed_user_ids_set
    return not allowed or user_id in allowed


def _webapp_keyboard() -> InlineKeyboardMarkup | None:
    if not settings.webapp_url:
        return None
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("🎲 Apri il gioco", web_app=WebAppInfo(url=settings.webapp_url))]]
    )


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.effective_user and update.message
    if not _is_allowed(update.effective_user.id):
        await update.message.reply_text(NOT_ALLOWED)
        return
    await update.message.reply_markdown(WELCOME, reply_markup=_webapp_keyboard())


async def cmd_gioca(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.effective_user and update.message
    if not _is_allowed(update.effective_user.id):
        await update.message.reply_text(NOT_ALLOWED)
        return
    keyboard = _webapp_keyboard()
    if keyboard is None:
        await update.message.reply_text("La Mini App non è ancora configurata (WEBAPP_URL mancante).")
        return
    await update.message.reply_text("Apri la Mini App per continuare la tua avventura:", reply_markup=keyboard)


async def cmd_aiuto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.effective_user and update.message
    if not _is_allowed(update.effective_user.id):
        await update.message.reply_text(NOT_ALLOWED)
        return
    await update.message.reply_text(HELP, reply_markup=_webapp_keyboard())


async def cmd_galleria(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.effective_user and update.effective_chat
    if not _is_allowed(update.effective_user.id):
        await update.message.reply_text(NOT_ALLOWED)
        return
    category = context.args[0].lower() if context.args else None
    await send_gallery(context.bot, update.effective_chat.id, category)


def build_application() -> Application:
    application = Application.builder().token(settings.bot_token).updater(None).build()
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("gioca", cmd_gioca))
    application.add_handler(CommandHandler("aiuto", cmd_aiuto))
    application.add_handler(CommandHandler("galleria", cmd_galleria))
    return application


async def configure_bot(application: Application) -> None:
    """Imposta il menu comandi e il Menu Button (chiamato una volta all'avvio, §14)."""
    await application.bot.set_my_commands(
        [
            ("start", "Apri il menu iniziale"),
            ("gioca", "Apri la Mini App di gioco"),
            ("galleria", "Guarda dadi, icone, classi e ritratti dei PNG"),
            ("aiuto", "Mostra i comandi disponibili"),
        ]
    )
    if settings.webapp_url:
        await application.bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(text="Gioca", web_app=WebAppInfo(url=settings.webapp_url))
        )
