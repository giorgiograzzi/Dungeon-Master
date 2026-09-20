#!/usr/bin/env python3
"""Imposta (o aggiorna) il webhook del bot Telegram sull'URL pubblico dell'app.

Legge BOT_TOKEN, WEBAPP_URL e WEBHOOK_SECRET dall'ambiente (o da .env).
Uso:
    python tools/set_webhook.py
    python tools/set_webhook.py --url https://altro-host.example --drop-pending
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys

from dotenv import load_dotenv
from telegram import Bot

load_dotenv()


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", help="URL pubblico dell'app (default: $WEBAPP_URL)")
    parser.add_argument(
        "--drop-pending", action="store_true", help="scarta gli aggiornamenti in sospeso"
    )
    args = parser.parse_args()

    token = os.environ.get("BOT_TOKEN")
    if not token:
        sys.exit("BOT_TOKEN non impostato")

    base_url = args.url or os.environ.get("WEBAPP_URL")
    if not base_url:
        sys.exit("WEBAPP_URL non impostato (oppure passa --url)")

    secret = os.environ.get("WEBHOOK_SECRET") or None
    webhook_url = base_url.rstrip("/") + "/telegram/webhook"

    bot = Bot(token=token)
    async with bot:
        await bot.set_webhook(
            url=webhook_url,
            secret_token=secret,
            drop_pending_updates=args.drop_pending,
        )
        info = await bot.get_webhook_info()
        print(f"Webhook impostato su: {info.url}")
        if info.last_error_message:
            print(f"Attenzione, ultimo errore riportato da Telegram: {info.last_error_message}")


if __name__ == "__main__":
    asyncio.run(main())
