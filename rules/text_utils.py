"""Utilità di testo condivise da runtime e strumenti di estrazione (nessuna
dipendenza pesante, a differenza di tools/extract_srd.py)."""

from __future__ import annotations

import re
import unicodedata


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^\w]+", "_", text.strip().lower())
    return re.sub(r"_+", "_", text).strip("_")
