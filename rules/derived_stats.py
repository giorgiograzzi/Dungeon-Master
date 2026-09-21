"""Parsing di piccoli formati testuali dell'SRD verso numeri utilizzabili
dal motore di regole (dado vita, velocità, CA base di un'armatura)."""

from __future__ import annotations

import re


def parse_hit_die(text: str) -> int:
    """'D12 per ogni livello da barbaro' -> 12."""
    m = re.search(r"D(\d+)", text)
    if not m:
        raise ValueError(f"dado vita non riconosciuto: {text!r}")
    return int(m.group(1))


def parse_speed_m(text: str) -> float:
    """'9 metri' / '10,5 metri' -> 9.0 / 10.5."""
    m = re.search(r"([\d,.]+)\s*metri", text)
    if not m:
        raise ValueError(f"velocità non riconosciuta: {text!r}")
    return float(m.group(1).replace(",", "."))


def compute_armor_ac(base_ac_text: str, dex_modifier: int) -> int:
    """Converte il campo `base_ac` di data/srd/armor.json in una CA numerica."""
    text = base_ac_text.strip()
    if text.lstrip("+-").isdigit():
        return int(text)
    m = re.match(r"(\d+)\s*\+\s*modificatore di Des(?:\s*\(max\s*(\d+)\))?", text)
    if m:
        base = int(m.group(1))
        cap = int(m.group(2)) if m.group(2) else None
        applied = min(dex_modifier, cap) if cap is not None else dex_modifier
        return base + applied
    raise ValueError(f"formula CA non riconosciuta: {base_ac_text!r}")
