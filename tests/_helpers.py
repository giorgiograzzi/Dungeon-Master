"""Utilità condivise dai test (non è un modulo di test)."""

from __future__ import annotations

import hashlib
import hmac
from urllib.parse import urlencode

BOT_TOKEN = "123456:TEST-TOKEN"


def build_init_data(fields: dict, bot_token: str = BOT_TOKEN) -> str:
    """Costruisce una stringa initData valida firmandola come farebbe Telegram."""
    check_string = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    digest = hmac.new(secret_key, check_string.encode("utf-8"), hashlib.sha256).hexdigest()
    return urlencode({**fields, "hash": digest})
