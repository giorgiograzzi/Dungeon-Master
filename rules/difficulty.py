"""Tabella delle fasce di Classe Difficoltà (§3): l'AI propone la fascia in
base alla fiction, il codice converte nella CD numerica esatta."""

from __future__ import annotations

DC_BANDS: dict[str, int] = {
    "molto_facile": 5,
    "facile": 10,
    "media": 15,
    "difficile": 20,
    "molto_difficile": 25,
    "quasi_impossibile": 30,
}

DC_BAND_LABELS_IT: dict[str, str] = {
    "molto_facile": "Molto facile",
    "facile": "Facile",
    "media": "Media",
    "difficile": "Difficile",
    "molto_difficile": "Molto difficile",
    "quasi_impossibile": "Quasi impossibile",
}


def dc_for_band(band: str) -> int:
    try:
        return DC_BANDS[band]
    except KeyError as exc:
        raise ValueError(f"fascia di difficoltà sconosciuta: {band!r}") from exc


def check_result(total: int, dc: int) -> bool:
    """Una prova ha successo se il totale è >= alla CD (SRD)."""
    return total >= dc
