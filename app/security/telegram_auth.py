"""Validazione di `initData` di Telegram (HMAC-SHA256), come richiesto dal §2 del PROMPT:

ogni chiamata API deve identificare l'utente solo tramite questo dato, mai fidandosi
di un ID passato liberamente dal client.

Algoritmo ufficiale Telegram:
    secret_key = HMAC_SHA256(key="WebAppData", msg=bot_token)
    hash_atteso = HEX(HMAC_SHA256(key=secret_key, msg=data_check_string))
dove `data_check_string` è l'elenco `chiave=valore` (esclusa "hash") ordinato
alfabeticamente e unito con "\n".
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl

DEFAULT_MAX_AGE_SECONDS = 24 * 60 * 60  # 24 ore


class InitDataError(ValueError):
    """initData mancante, malformato, con firma non valida o scaduto."""


def validate_init_data(
    init_data: str,
    bot_token: str,
    max_age: int | None = DEFAULT_MAX_AGE_SECONDS,
) -> dict:
    """Verifica `init_data` e restituisce i campi decodificati (con "user" come dict).

    Solleva InitDataError se la verifica fallisce per qualunque motivo.
    """
    if not bot_token:
        raise InitDataError("bot non configurato (BOT_TOKEN mancante)")
    if not init_data:
        raise InitDataError("initData mancante")

    try:
        pairs = parse_qsl(init_data, strict_parsing=True, keep_blank_values=True)
    except ValueError as exc:
        raise InitDataError("initData malformato") from exc

    data = dict(pairs)
    received_hash = data.pop("hash", None)
    if not received_hash:
        raise InitDataError("hash mancante in initData")

    check_string = "\n".join(f"{key}={value}" for key, value in sorted(data.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    computed_hash = hmac.new(secret_key, check_string.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(computed_hash, received_hash):
        raise InitDataError("firma di initData non valida")

    if max_age is not None:
        try:
            auth_date = int(data.get("auth_date", "0"))
        except ValueError as exc:
            raise InitDataError("auth_date non valido") from exc
        if time.time() - auth_date > max_age:
            raise InitDataError("initData scaduto")

    result: dict = dict(data)
    if "user" in result:
        try:
            result["user"] = json.loads(result["user"])
        except json.JSONDecodeError as exc:
            raise InitDataError("campo user non è JSON valido") from exc
    return result
