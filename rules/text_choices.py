"""Analizza le frasi SRD del tipo 'Due a scelta tra: A, B, C o D' (usate per
le competenze nelle abilità di classe) in una scelta strutturata (numero,
opzioni). Se la classe non elenca opzioni (es. "Tre abilità a scelta"),
restituisce `options=None`: qualunque abilità è ammessa."""

from __future__ import annotations

import re
from dataclasses import dataclass

_NUMBER_WORDS_IT = {"una": 1, "due": 2, "tre": 3, "quattro": 4, "cinque": 5}

_WITH_OPTIONS_RE = re.compile(
    r"^(?P<word>Una|Due|Tre|Quattro|Cinque) a scelta tra:\s*(?P<rest>.+)$", re.IGNORECASE
)
_ANY_SKILL_RE = re.compile(r"^(?P<word>Una|Due|Tre|Quattro|Cinque)\s+abilità\s+a\s+scelta", re.IGNORECASE)


@dataclass(frozen=True)
class Choice:
    count: int
    options: tuple[str, ...] | None  # None = qualunque opzione valida


def parse_choice(text: str) -> Choice:
    m = _WITH_OPTIONS_RE.match(text.strip())
    if m:
        count = _NUMBER_WORDS_IT[m.group("word").lower()]
        rest = m.group("rest").strip().rstrip(".")
        # l'ultimo elemento è unito da " o " invece della virgola
        rest = re.sub(r"\s+o\s+(?=[^,]+$)", ", ", rest)
        options = tuple(part.strip() for part in rest.split(",") if part.strip())
        return Choice(count=count, options=options)

    m = _ANY_SKILL_RE.match(text.strip())
    if m:
        count = _NUMBER_WORDS_IT[m.group("word").lower()]
        return Choice(count=count, options=None)

    raise ValueError(f"testo di scelta non riconosciuto: {text!r}")
