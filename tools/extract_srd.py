#!/usr/bin/env python3
"""Estrae dati strutturati dall'SRD 5.2.1 (italiano) in data/srd/*.json (§0.2).

Fonte: docs/srd/IT_SRD_CC_v5.2.1.pdf. Script ripetibile: si può rilanciare
ogni volta che il PDF cambia; non modifica il PDF, sovrascrive solo i JSON.

Uso: python tools/extract_srd.py [percorso_pdf] [cartella_output]
Richiede pypdf e pdfplumber (requisiti di sviluppo, vedi requirements-dev.txt).
"""
from __future__ import annotations

import json
import os
import re
import sys
import unicodedata

import pdfplumber
from pypdf import PdfReader

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_PDF = os.path.join(HERE, "..", "docs", "srd", "IT_SRD_CC_v5.2.1.pdf")
DEFAULT_OUT = os.path.join(HERE, "..", "data", "srd")

SIZES = ["Minuscola", "Piccola", "Media", "Grande", "Enorme", "Mastodontica"]
# Le schede dei mostri concordano la taglia in genere col tipo di creatura
# (es. "Folletto Piccolo" ma "Melma Piccola"): normalizziamo alla forma femminile.
SIZE_WORDS = SIZES + ["Minuscolo", "Piccolo", "Medio", "Mastodontico"]
SIZE_CANON = {
    "Minuscolo": "Minuscola", "Piccolo": "Piccola", "Medio": "Media", "Mastodontico": "Mastodontica",
}


# --------------------------------------------------------------------------- utilità generiche
def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^\w]+", "_", text.strip().lower())
    return re.sub(r"_+", "_", text).strip("_")


def clean_line(line: str) -> str:
    # "−" (U+2212, segno meno) è usato al posto di "-" per i modificatori negativi.
    return line.replace("\xad", "").replace("−", "-").strip()


def load_page_texts(pdf_path: str) -> list[str]:
    reader = PdfReader(pdf_path)
    return [page.extract_text() or "" for page in reader.pages]


HYPHEN_LINEBREAK_RE = re.compile(r"(\w+) -\n(\w+)")


def strip_header(text: str) -> str:
    """Rimuove l'intestazione ripetuta 'System Reference Document 5.2.1' + numero
    pagina, e riunisce le parole spezzate a fine riga (es. 'elen -\\nlencati')."""
    lines = [clean_line(line) for line in text.split("\n")]
    out = []
    for line in lines:
        if line.startswith("System Reference Document"):
            continue
        if re.fullmatch(r"\d{1,3}", line):
            continue
        out.append(line)
    return HYPHEN_LINEBREAK_RE.sub(r"\1\2", "\n".join(out))


def pages_text(pages: list[str], start_idx: int, end_idx: int) -> str:
    """Testo (senza intestazioni) delle pagine [start_idx, end_idx) (indici 0-based)."""
    return "\n".join(strip_header(pages[i]) for i in range(start_idx, end_idx))


# --------------------------------------------------------------------------- indice (TOC)
def parse_toc(pages: list[str]) -> dict[str, int]:
    """Legge l'indice (pagine 2-3) e restituisce {titolo_sezione: numero_pagina}."""
    toc_text = "\n".join(pages[1:3])
    entries: dict[str, int] = {}
    for line in toc_text.split("\n"):
        m = re.match(r"^(.+?)\s*\.{2,}\s*(\d+)\s*$", clean_line(line))
        if m:
            title = re.sub(r"\s+", " ", m.group(1)).strip()
            # Alcuni nomi di classe (es. "Mago", "Druido") ricompaiono nell'indice dei
            # mostri: teniamo la prima occorrenza, quella del vero indice dei capitoli.
            entries.setdefault(title, int(m.group(2)))
    return entries


CLASS_NAMES_IT = [
    "Barbaro", "Bardo", "Chierico", "Druido", "Guerriero", "Ladro",
    "Mago", "Monaco", "Paladino", "Ranger", "Stregone", "Warlock",
]


# --------------------------------------------------------------------------- specie
SPECIES_FIELD_RE = re.compile(r"^(Tipo di creatura|Taglia|Velocità):\s*(.*)$")


def extract_species(pages: list[str], toc: dict[str, int]) -> list[dict]:
    start = toc["Background dei personaggi"] - 1
    end = toc["Talenti"] - 1
    text = pages_text(pages, start, end)
    text = text.split("Specie dei personaggi", 1)[1]
    lines = [clean_line(line) for line in text.split("\n") if clean_line(line)]

    names_it = ["Dragonide", "Elfo", "Gnomo", "Goliath", "Halfling", "Nano", "Orco", "Tiefling", "Umano"]
    species: list[dict] = []
    idxs = [i for i, line in enumerate(lines) if line in names_it]
    idxs.append(len(lines))
    for k in range(len(idxs) - 1):
        block = lines[idxs[k] : idxs[k + 1]]
        name_it = block[0]
        creature_type = size = speed = ""
        body_start = 1
        for j in range(1, min(len(block), 6)):
            m = SPECIES_FIELD_RE.match(block[j])
            if m:
                field, value = m.groups()
                if field == "Tipo di creatura":
                    creature_type = value
                elif field == "Taglia":
                    size = value
                elif field == "Velocità":
                    speed = value
                body_start = j + 1
        # salta la frase introduttiva "In quanto X, il personaggio ha i seguenti tratti speciali."
        while body_start < len(block) and not re.match(r"^[A-ZÀ-Ý].{2,45}\.\s+\S", block[body_start]):
            body_start += 1
        traits = _split_bold_entries(block[body_start:])
        species.append(
            {
                "id": slugify(name_it),
                "name_it": name_it,
                "creature_type": creature_type,
                "size": size,
                "speed": speed,
                "traits": traits,
            }
        )
    return species


TRAIT_HEADING_RE = re.compile(r"^([A-ZÀ-Ý][^.]{1,45})\.\s+(.*)$")


def _split_bold_entries(lines: list[str]) -> list[dict]:
    """Euristica: 'Nome tratto. Testo...' a inizio riga introduce una nuova voce;
    le righe successive senza questo pattern proseguono la voce corrente."""
    entries: list[dict] = []
    for line in lines:
        m = TRAIT_HEADING_RE.match(line)
        if m and len(m.group(1)) <= 45:
            entries.append({"name": m.group(1).strip(), "text": m.group(2).strip()})
        elif entries:
            entries[-1]["text"] += " " + line
        else:
            entries.append({"name": "", "text": line})
    return entries


# --------------------------------------------------------------------------- background
BACKGROUND_NAMES_IT = ["Accolito", "Criminale", "Sapiente", "Soldato"]
BG_FIELD_RE = re.compile(
    r"^(Punteggi di caratteristica|Talento|Competenze nelle abilità|"
    r"Competenza negli strumenti|Equipaggiamento):\s*(.*)$"
)


def extract_backgrounds(pages: list[str], toc: dict[str, int]) -> list[dict]:
    start = toc["Background dei personaggi"] - 1
    end = toc["Talenti"] - 1
    text = pages_text(pages, start, end)
    text = text.split("Descrizioni dei background", 1)[1].split("Specie dei personaggi", 1)[0]
    lines = [clean_line(line) for line in text.split("\n") if clean_line(line)]

    idxs = [i for i, line in enumerate(lines) if line in BACKGROUND_NAMES_IT]
    idxs.append(len(lines))
    backgrounds = []
    for k in range(len(idxs) - 1):
        block = lines[idxs[k] : idxs[k + 1]]
        name_it = block[0]
        fields = {
            "ability_scores": "",
            "feat": "",
            "skill_proficiencies": "",
            "tool_proficiency": "",
            "equipment": "",
        }
        key_map = {
            "Punteggi di caratteristica": "ability_scores",
            "Talento": "feat",
            "Competenze nelle abilità": "skill_proficiencies",
            "Competenza negli strumenti": "tool_proficiency",
            "Equipaggiamento": "equipment",
        }
        buf = " ".join(block[1:])
        for label, key in key_map.items():
            m = re.search(rf"{re.escape(label)}:\s*(.*?)(?=(?:{'|'.join(re.escape(x) for x in key_map)}):|$)", buf)
            if m:
                fields[key] = m.group(1).strip()
        backgrounds.append({"id": slugify(name_it), "name_it": name_it, **fields})
    return backgrounds


# --------------------------------------------------------------------------- abilità (skills)
SKILL_ROW_RE = re.compile(
    r"^([A-ZÀ-Ý][\wàèéìòù' ]+?)\s+(Forza|Destrezza|Costituzione|Intelligenza|Saggezza|Carisma)\s+(.+)$"
)
# "Furtività" e "Sopravvivenza" non compaiono come righe autonome nella tabella
# "Abilità" (impaginata su due colonne che l'estrazione lineare mischia), ma la
# loro caratteristica è comunque confermata testualmente altrove nello stesso
# capitolo: "Effettui una prova di Destrezza (Furtività)" (azione Nascondersi)
# e "prova di Saggezza (Intuizione, Medicina, Percezione o Sopravvivenza)"
# (azione Ricerca). Le aggiungiamo qui per completare la lista ufficiale di 18.
SKILLS_FALLBACK = {
    "Furtività": "Destrezza",
    "Sopravvivenza": "Saggezza",
}


def extract_skills(pages: list[str], toc: dict[str, int]) -> list[dict]:
    start = toc["Come si gioca"] - 1
    end = toc["Creazione del personaggio"] - 1
    text = pages_text(pages, start, end)
    lines = [clean_line(line) for line in text.split("\n") if clean_line(line)]
    # "Addestrare animali" va a capo su due righe, separate dall'abilità/testo
    # sulla riga successiva: le riunisce in un'unica riga "Nome Abilità testo".
    for i, line in enumerate(lines[:-2]):
        if line == "Addestrare" and lines[i + 1] == "animali":
            lines[i] = f"Addestrare animali {lines[i + 2]}"
            lines[i + 1] = lines[i + 2] = ""
            break
    lines = [line for line in lines if line]

    skills: dict[str, str] = {}
    for line in lines:
        m = SKILL_ROW_RE.match(line)
        # I nomi delle abilità sono corti (max 3 parole): scarta le frasi della
        # tabella "Azioni" agganciate per coincidenza dallo stesso pattern
        # (es. "Influenza Effettui una prova di Carisma...").
        if m and len(m.group(1).split()) <= 3:
            skills[m.group(1).strip()] = m.group(2)
    for name, ability in SKILLS_FALLBACK.items():
        skills.setdefault(name, ability)

    ability_id = {
        "Forza": "for", "Destrezza": "des", "Costituzione": "cos",
        "Intelligenza": "int", "Saggezza": "sag", "Carisma": "car",
    }
    return sorted(
        (
            {"id": slugify(name), "name_it": name, "ability": ability_id[ability]}
            for name, ability in skills.items()
        ),
        key=lambda s: s["name_it"],
    )


# --------------------------------------------------------------------------- classi
CLASS_TABLE_LABELS = [
    "Caratteristiche primarie", "Dado Vita", "Competenze nei tiri salvezza",
    "Competenze nelle abilità", "Competenza nelle armi", "Competenza nelle armature",
    "Equipaggiamento iniziale",
]
CLASS_TABLE_FIELD_RE = re.compile(r"^(" + "|".join(CLASS_TABLE_LABELS) + r")\s*(.*)$")
LEVEL_ROW_RE = re.compile(r"^(\d{1,2})\s+([+-]?\d+)\s+(.*?)(\s+(?:[+-]?\d[\d/ +-]*))?$")


def _merge_two_line_labels(lines: list[str], labels: list[str]) -> list[str]:
    """Nella tabella dei tratti di classe, alcune etichette vanno a capo su due
    righe (es. 'Caratteristiche' / 'primarie'): le riunisce in un'unica riga."""
    merged = []
    i = 0
    while i < len(lines):
        if i + 1 < len(lines) and f"{lines[i]} {lines[i + 1]}" in labels:
            merged.append(f"{lines[i]} {lines[i + 1]}")
            i += 2
        else:
            merged.append(lines[i])
            i += 1
    return merged


def extract_classes(pages: list[str], toc: dict[str, int]) -> list[dict]:
    class_start = {name: toc[name] - 1 for name in CLASS_NAMES_IT if name in toc}
    ordered = sorted(class_start.items(), key=lambda kv: kv[1])
    section_end = toc["Origini dei personaggi"] - 1
    classes = []
    for i, (name_it, start_idx) in enumerate(ordered):
        # +1 pagina di margine: la sezione "Sottoclasse" a volte inizia proprio
        # sulla pagina in cui comincia la classe successiva.
        end_idx = min(ordered[i + 1][1] + 1, section_end) if i + 1 < len(ordered) else section_end
        text = pages_text(pages, start_idx, end_idx)
        classes.append(_parse_one_class(name_it, text))
    return classes


def _parse_one_class(name_it: str, text: str) -> dict:
    lines = [clean_line(line) for line in text.split("\n") if clean_line(line)]
    lines = _merge_two_line_labels(lines, CLASS_TABLE_LABELS)
    # la tabella "Tratti del X" alterna etichetta / valore fino a "Diventare un X..."
    table: dict[str, str] = {}
    i = 0
    # salta fino al nome classe e alla tabella
    while i < len(lines) and lines[i] != name_it:
        i += 1
    i += 1
    if i < len(lines) and lines[i].lower().startswith("tratti del"):
        i += 1
    while i < len(lines) and not lines[i].startswith("Diventare un"):
        m = CLASS_TABLE_FIELD_RE.match(lines[i])
        if m:
            label, rest = m.group(1), m.group(2).strip()
            i += 1
            value_parts = [rest] if rest else []
            while i < len(lines) and not CLASS_TABLE_FIELD_RE.match(lines[i]) and not lines[i].startswith("Diventare un"):
                value_parts.append(lines[i])
                i += 1
            table[label] = " ".join(value_parts).strip()
        else:
            i += 1

    # privilegi di 1° livello: dal titolo "Privilegi di classe del X" (o "Livello 1:") alla tabella dei privilegi
    level1_features = _extract_level1_features(lines, name_it)

    # tabella dei privilegi per livello: righe "N +B testo ... extra"
    levels = []
    seen_levels: set[int] = set()
    for line in lines:
        m = LEVEL_ROW_RE.match(line)
        if m:
            level = int(m.group(1))
            features_text = m.group(3)
            # Scarta le righe "spezzate" che restano solo con la coda numerica
            # della tabella degli slot incantesimo (es. "2 — — — — — — — —"):
            # una riga di privilegi vera contiene sempre del testo.
            if not re.search(r"[A-Za-zÀ-ÿ]{3,}", features_text):
                continue
            # La prima tabella per-livello incontrata è quella dei privilegi di
            # classe; le classi incantatrici ne hanno altre (slot incantesimo)
            # più avanti nel testo, che scartiamo per evitare doppioni.
            if 1 <= level <= 20 and level not in seen_levels:
                seen_levels.add(level)
                levels.append(
                    {
                        "level": level,
                        "proficiency_bonus": m.group(2),
                        "features": [f.strip() for f in m.group(3).split(",") if f.strip()],
                    }
                )

    subclass_level = 3
    subclass_name = ""
    subclass_heading_re = re.compile(rf"^Sottoclasse dell?[oa']? {re.escape(name_it.lower())}:\s*(.*)$", re.I)
    for j, line in enumerate(lines):
        hm = subclass_heading_re.match(line)
        if hm:
            # Il nome della sottoclasse occupa il resto di questa riga più la
            # riga successiva (a volte va a capo a metà, es. "Dominio" / "della Vita").
            rest = hm.group(1).strip()
            next_line = lines[j + 1].strip() if j + 1 < len(lines) else ""
            # Se il nome continua a capo, la riga successiva inizia in minuscolo
            # (es. "Dominio" / "della Vita"); se il nome era già completo, la riga
            # dopo è lo slogan della sottoclasse e inizia con la maiuscola.
            if not rest or (next_line and next_line[0].islower()):
                subclass_name = clean_line(f"{rest} {next_line}".strip())
            else:
                subclass_name = clean_line(rest)
            break

    spellcasting = f"Lista degli incantesimi da {name_it.lower()}" in text

    return {
        "id": slugify(name_it),
        "name_it": name_it,
        "primary_abilities": table.get("Caratteristiche primarie", ""),
        "hit_die": table.get("Dado Vita", ""),
        "saving_throw_proficiencies": table.get("Competenze nei tiri salvezza", ""),
        "skill_proficiencies": table.get("Competenze nelle abilità", ""),
        "weapon_proficiencies": table.get("Competenza nelle armi", ""),
        "armor_proficiencies": table.get("Competenza nelle armature", ""),
        "starting_equipment": table.get("Equipaggiamento iniziale", ""),
        "spellcasting": spellcasting,
        "subclass_name": subclass_name,
        "subclass_level": subclass_level,
        "level1_features": level1_features,
        "levels": levels,
    }


def _extract_level1_features(lines: list[str], name_it: str) -> list[dict]:
    try:
        start = next(i for i, l in enumerate(lines) if l.startswith("Privilegi di classe del"))
    except StopIteration:
        return []
    try:
        end = next(i for i, l in enumerate(lines) if i > start and l.startswith("Privilegi del "))
    except StopIteration:
        end = len(lines)
    body = lines[start + 2 : end]  # salta il titolo + la frase introduttiva
    # isola il blocco "Livello 1: <nomi>" fino a "Livello 2:" (se presente)
    try:
        lvl1 = next(i for i, l in enumerate(body) if re.match(r"^Livello 1:", l))
    except StopIteration:
        return []
    try:
        lvl2 = next(i for i, l in enumerate(body) if i > lvl1 and re.match(r"^Livello \d+:", l))
    except StopIteration:
        lvl2 = len(body)
    feature_names = clean_line(body[lvl1].split(":", 1)[1]).split(", ")
    return _split_bold_entries(body[lvl1 + 1 : lvl2]) or [{"name": n, "text": ""} for n in feature_names]


# --------------------------------------------------------------------------- talenti
FEAT_CATEGORY_RE = re.compile(r"^Talenti (Origini|Generali|Stile di combattimento|Dono epico)$")
FEAT_TAG_RE = re.compile(r"^Talento (Origini|Generale|Stile di combattimento|Dono epico)(?:\s*\((.+)\))?$")


def _merge_wrapped_parens(lines: list[str], prefix: str = "") -> list[str]:
    """Unisce una riga che inizia con `prefix` (o qualunque riga, se non dato)
    e ha parentesi non bilanciate con le righe successive, finché non si
    richiude (il testo va a capo)."""
    merged = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith(prefix):
            j = i + 1
            while line.count("(") > line.count(")") and j < len(lines):
                line = line + " " + lines[j]
                j += 1
            merged.append(line)
            i = j
        else:
            merged.append(line)
            i += 1
    return merged


def extract_feats(pages: list[str], toc: dict[str, int]) -> list[dict]:
    start = toc["Descrizioni dei talenti"] - 1
    end = toc["Equipaggiamento"] - 1
    text = pages_text(pages, start, end)
    lines = [clean_line(line) for line in text.split("\n") if clean_line(line)]
    lines = _merge_wrapped_parens(lines, "Talento ")

    feats = []
    category = ""
    i = 0
    while i < len(lines):
        cat_m = FEAT_CATEGORY_RE.match(lines[i])
        if cat_m:
            category = cat_m.group(1)
            i += 1
            continue
        if i + 1 < len(lines):
            tag_m = FEAT_TAG_RE.match(lines[i + 1])
            if tag_m:
                name = lines[i]
                prerequisite = tag_m.group(2) or ""
                j = i + 2
                body = []
                while j < len(lines) and not FEAT_TAG_RE.match(lines[j + 1] if j + 1 < len(lines) else "") \
                        and not FEAT_CATEGORY_RE.match(lines[j]):
                    body.append(lines[j])
                    j += 1
                feats.append(
                    {
                        "id": slugify(name),
                        "name_it": name,
                        "category": category,
                        "prerequisite": prerequisite,
                        "text": " ".join(body).strip(),
                    }
                )
                i = j
                continue
        i += 1
    return feats


# --------------------------------------------------------------------------- condizioni (glossario)
CONDITION_HEADING_RE = re.compile(r"^([A-ZÀ-Ý][\wàèéìòùÀ-Ý' -]{1,40})\s*\[condizione\]$")


def extract_conditions(pages: list[str], toc: dict[str, int]) -> list[dict]:
    start = toc["Glossario delle regole"] - 1
    end = toc["Strumenti di gioco"] - 1
    text = pages_text(pages, start, end)
    lines = [clean_line(line) for line in text.split("\n")]

    conditions = []
    for i, line in enumerate(lines):
        m = CONDITION_HEADING_RE.match(line)
        if not m:
            continue
        name = m.group(1).strip()
        j = i + 1
        body = []
        while j < len(lines) and not _looks_like_glossary_heading(lines[j]):
            if lines[j]:
                body.append(lines[j])
            j += 1
        conditions.append({"id": slugify(name), "name_it": name, "text": " ".join(body).strip()})
    return conditions


def _looks_like_glossary_heading(line: str) -> bool:
    if not line or len(line) > 45:
        return False
    if line.endswith("."):
        return False
    return bool(re.match(r"^[A-ZÀ-Ý][\wàèéìòùÀ-Ý' -]*(\s*\[[a-zàèéìòù ]+\])?$", line))


# --------------------------------------------------------------------------- equipaggiamento (armi/armature)
WEAPON_DAMAGE_RE = re.compile(r"^\d*d?\d*\s*(contundenti|perforanti|taglienti)$|^\d+\s*(contundenti|perforanti|taglienti)$")
ARMOR_AC_RE = re.compile(r"modificatore di Des|^\+?\d+$")


WEAPON_LINE_RE = re.compile(
    r"^(?P<name>[A-ZÀ-Ý][\wàèéìòù' ]*?)\s+"
    r"(?P<damage>\d*d?\d+ (?:contundenti|perforanti|taglienti)|\d+ (?:contundente|perforante|tagliente))\s+"
    r"(?P<properties>.+?)\s+"
    r"(?P<mastery>[A-ZÀ-Ý][\wàèéìòù]+(?:\s[a-zàèéìòù]+)?)\s+"
    r"(?P<weight>[\d,]+\s*kg)\s+(?P<cost>[\d.,]+\s*(?:mo|ma|mr|me|mp))$"
)
ARMOR_LINE_RE = re.compile(
    r"^(?P<name>[A-ZÀ-Ý][\wàèéìòù' ]+?)\s+"
    r"(?P<ac>\d+\s*\+\s*modificatore di Des(?:\s*\(max \d+\))?|\+\d+|\d+)\s+"
    r"(?P<str_req>—|For \d+)\s+(?P<stealth>—|Svantaggio)\s+"
    r"(?P<weight>[\d,]+\s*kg)\s+(?P<cost>[\d.,]+\s*mo)$"
)
CONTINUATION_WORD_RE = re.compile(r"^[a-zàèéìòù]+$")


def _maybe_join_continuation(lines: list[str], i: int, name: str) -> str:
    if i + 1 < len(lines) and CONTINUATION_WORD_RE.match(lines[i + 1]):
        return f"{name} {lines[i + 1]}"
    return name


def extract_equipment(pdf_path: str, toc: dict[str, int]) -> dict:
    start_page = toc["Armi"] - 1
    end_page = toc["Strumenti"] - 1
    with pdfplumber.open(pdf_path) as pdf:
        text = "\n".join(strip_header(pdf.pages[i].extract_text() or "") for i in range(start_page, end_page))
    lines = [clean_line(line) for line in text.split("\n")]

    weapons: list[dict] = []
    armor: list[dict] = []
    seen_weapons: set[tuple] = set()
    seen_armor: set[str] = set()
    category = kind = ""

    for i, line in enumerate(lines):
        if "Armi da mischia" in line:
            kind = "mischia"
        elif "Armi a distanza" in line:
            kind = "distanza"
        if "semplici" in line.lower() and "Armi" in line:
            category = "semplice"
        elif "da guerra" in line.lower() and "Armi" in line:
            category = "guerra"
        elif line.startswith("Armatura leggera"):
            category = "leggera"
        elif line.startswith("Armatura media"):
            category = "media"
        elif line.startswith("Armatura pesante"):
            category = "pesante"

        wm = WEAPON_LINE_RE.match(line)
        if wm:
            name = wm.group("name")
            key = (name, wm.group("damage"))
            if key not in seen_weapons:
                seen_weapons.add(key)
                weapons.append(
                    {
                        "id": slugify(name),
                        "name_it": name,
                        "category": category,
                        "kind": kind,
                        "damage": wm.group("damage"),
                        "properties": wm.group("properties"),
                        "mastery": _maybe_join_continuation(lines, i, wm.group("mastery")),
                        "weight": wm.group("weight"),
                        "cost": wm.group("cost"),
                    }
                )
            continue

        am = ARMOR_LINE_RE.match(line)
        if am:
            name = _maybe_join_continuation(lines, i, am.group("name"))
            armor_category = "scudo" if name == "Scudo" else category
            if name not in seen_armor:
                seen_armor.add(name)
                armor.append(
                    {
                        "id": slugify(name),
                        "name_it": name,
                        "category": armor_category,
                        "base_ac": am.group("ac"),
                        "strength_requirement": am.group("str_req"),
                        "stealth": am.group("stealth"),
                        "weight": am.group("weight"),
                        "cost": am.group("cost"),
                    }
                )
    return {"weapons": weapons, "armor": armor}


# --------------------------------------------------------------------------- incantesimi
SPELL_CANTRIP_RE = re.compile(r"^Trucchetto di (?P<school>\w+)\s*\((?P<classes>[^)]+)\)$")
SPELL_LEVELED_RE = re.compile(r"^(?P<school>\w+) di (?P<level>\d+)º livello\s*\((?P<classes>[^)]+)\)$")
SPELL_STAT_RE = re.compile(r"^(Tempo di lancio|Gittata|Componenti|Durata):\s*(.*)$")
SPELL_HEADER_START_RE = re.compile(r"^(Trucchetto di \w+|.+ di \d+º livello)\s*\(")


def _merge_spell_header_parens(lines: list[str]) -> list[str]:
    """La lista delle classi nell'intestazione di un incantesimo (es.
    '(bardo, chierico,\nparadino)') a volte va a capo: la riunisce."""
    merged = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if SPELL_HEADER_START_RE.match(line):
            j = i + 1
            while line.count("(") > line.count(")") and j < len(lines) and j - i <= 3:
                line = line + " " + lines[j]
                j += 1
            merged.append(line)
            i = j
        else:
            merged.append(line)
            i += 1
    return merged


def extract_spells(pages: list[str], toc: dict[str, int]) -> list[dict]:
    start = toc["Descrizioni degli incantesimi"] - 1
    end = toc["Glossario delle regole"] - 1
    text = pages_text(pages, start, end)
    lines = [clean_line(line) for line in text.split("\n") if clean_line(line)]
    lines = _merge_spell_header_parens(lines)

    anchors = []
    for i, line in enumerate(lines):
        m = SPELL_CANTRIP_RE.match(line) or SPELL_LEVELED_RE.match(line)
        if m and i > 0:
            anchors.append((i, m))

    spells = []
    for k, (i, m) in enumerate(anchors):
        name = lines[i - 1]
        level = 0 if "level" not in m.groupdict() or m.groupdict().get("level") is None else int(m.group("level"))
        school = m.group("school")
        classes = [c.strip() for c in m.group("classes").split(",")]
        body_end = anchors[k + 1][0] - 1 if k + 1 < len(anchors) else len(lines)
        stats: dict[str, str] = {}
        required = {"Tempo di lancio", "Gittata", "Componenti", "Durata"}
        current_key = None
        j = i + 1
        while j < body_end and not required.issubset(stats):
            sm = SPELL_STAT_RE.match(lines[j])
            if sm:
                current_key = sm.group(1)
                stats[current_key] = sm.group(2)
            elif current_key:
                # Un valore lungo (es. il componente materiale) può andare a capo.
                stats[current_key] += " " + lines[j]
            else:
                break
            j += 1
        description = " ".join(lines[j:body_end]).strip()
        spells.append(
            {
                "id": slugify(name),
                "name_it": name,
                "level": level,
                "school": school,
                "classes": classes,
                "casting_time": stats.get("Tempo di lancio", ""),
                "range": stats.get("Gittata", ""),
                "components": stats.get("Componenti", ""),
                "duration": stats.get("Durata", ""),
                "description": description,
            }
        )
    return spells


# --------------------------------------------------------------------------- mostri
MONSTER_TYPE_LINE_RE = re.compile(
    r"^(?P<type>[\wÀ-Ý][\wÀ-Ýàèéìòù]*(?:\s[\wÀ-Ýàèéìòù]+)?)\s+"
    r"(?P<size>" + "|".join(SIZE_WORDS) + r")"
    r"(?:\s*\((?P<subtype>[^)]+)\))?,\s*(?P<alignment>[a-zàèéìòù ]+)$"
)
MONSTER_AC_RE = re.compile(r"CA\s+(\d+)(?:\s*\(([^)]+)\))?\s+Iniziativa\s+([+-]\d+)\s*\((\d+)\)")
MONSTER_HP_RE = re.compile(r"PF\s+(\d+)\s*\(([^)]+)\)")
MONSTER_SPEED_RE = re.compile(r"Velocità\s+(.+)")
MONSTER_ABILITY_RE = re.compile(r"[A-Za-z]{3}\s+(\d+)\s+([+-]\d+)\s+([+-]\d+)")
MONSTER_CR_RE = re.compile(r"GS\s+([\d/]+)\s*\(PE\s+([\d.]+);\s*BC\s*([+-]\d+)\)")
MONSTER_EXTRA_FIELDS = ["Abilità", "Attrezzatura", "Resistenze ai danni", "Vulnerabilità ai danni",
                        "Immunità ai danni", "Immunità alle condizioni", "Sensi", "Lingue"]
MONSTER_EXTRA_RE = re.compile("^(" + "|".join(re.escape(f) for f in MONSTER_EXTRA_FIELDS) + r")\s+(.*)$")
MONSTER_SECTION_RE = re.compile(r"^(Azioni|Azioni bonus|Reazioni|Azioni leggendarie|Tratti)$")
ATTACK_RE = re.compile(
    r"Tiro per colpire (?:in mischia|a distanza|in mischia o a distanza):\s*([+-]\d+),.*?"
    r"Colpito:\s*(\d+)\s*\(([^)]+)\)\s*danni\s+(\w+)"
)


def extract_monsters(pages: list[str], toc: dict[str, int]) -> list[dict]:
    start = toc["Mostri A–Z"] - 1
    text = pages_text(pages, start, len(pages))
    lines = [clean_line(line) for line in text.split("\n")]

    anchors = [i for i, line in enumerate(lines) if MONSTER_TYPE_LINE_RE.match(line) and i > 0]
    monsters = []
    for k, i in enumerate(anchors):
        end = anchors[k + 1] - 1 if k + 1 < len(anchors) else len(lines)
        name = lines[i - 1].strip()
        if not name:
            continue
        block = lines[i:end]
        monster = _parse_one_monster(name, block)
        if monster:
            monsters.append(monster)
    return monsters


def _parse_one_monster(name: str, block: list[str]) -> dict | None:
    type_m = MONSTER_TYPE_LINE_RE.match(block[0])
    if not type_m:
        return None
    data = {
        "id": slugify(name),
        "name_it": name,
        "type": type_m.group("type"),
        "size": SIZE_CANON.get(type_m.group("size"), type_m.group("size")),
        "subtype": type_m.group("subtype") or "",
        "alignment": type_m.group("alignment"),
        "abilities": {},
        "extra": {},
        "traits": [],
        "actions": [],
        "bonus_actions": [],
        "reactions": [],
        "legendary_actions": [],
    }
    body = " ".join(block[1:])
    ac_m = MONSTER_AC_RE.search(body)
    if ac_m:
        data["ac"] = int(ac_m.group(1))
        data["ac_note"] = ac_m.group(2) or ""
        data["initiative"] = ac_m.group(3)
    hp_m = MONSTER_HP_RE.search(body)
    if hp_m:
        data["hp"] = int(hp_m.group(1))
        data["hit_dice"] = hp_m.group(2)
    speed_m = MONSTER_SPEED_RE.search(body)
    if speed_m:
        data["speed"] = re.split(r"\s+MOD\s+SALV", speed_m.group(1))[0].strip()
    ab_matches = MONSTER_ABILITY_RE.findall(body)[:6]
    for idx, ability in enumerate(("str", "dex", "con", "int", "wis", "cha")):
        if idx < len(ab_matches):
            score, mod, save = ab_matches[idx]
            data["abilities"][ability] = {"score": int(score), "mod": mod, "save": save}
    cr_m = MONSTER_CR_RE.search(body)
    if cr_m:
        data["challenge_rating"] = cr_m.group(1)
        data["xp"] = cr_m.group(2)
        data["proficiency_bonus"] = cr_m.group(3)
    for line in block:
        em = MONSTER_EXTRA_RE.match(line)
        if em:
            data["extra"][em.group(1)] = em.group(2)

    section = None
    for line in block:
        sec_m = MONSTER_SECTION_RE.match(line)
        if sec_m:
            section = sec_m.group(1)
            continue
        if section is None:
            continue
        entry_m = None if line.startswith("Colpito:") else TRAIT_HEADING_RE.match(line)
        target = {
            "Tratti": data["traits"],
            "Azioni": data["actions"],
            "Azioni bonus": data["bonus_actions"],
            "Reazioni": data["reactions"],
            "Azioni leggendarie": data["legendary_actions"],
        }.get(section)
        if target is None:
            continue
        if entry_m:
            target.append({"name": entry_m.group(1).strip(), "text": entry_m.group(2).strip()})
        elif target:
            target[-1]["text"] += " " + line

    for entries in (data["traits"], data["actions"], data["bonus_actions"], data["reactions"], data["legendary_actions"]):
        for entry in entries:
            attack_m = ATTACK_RE.search(entry["text"])
            if attack_m:
                entry["attack"] = {
                    "to_hit": attack_m.group(1),
                    "avg_damage": int(attack_m.group(2)),
                    "damage_dice": attack_m.group(3),
                    "damage_type": attack_m.group(4),
                }

    if "ac" not in data or "hp" not in data or not data["abilities"]:
        return None
    return data


# --------------------------------------------------------------------------- glossario IT (id inglese -> nome IT)
def build_it_glossary(classes: list[dict], species: list[dict]) -> dict[str, str]:
    glossary = {c["id"]: c["name_it"] for c in classes}
    glossary.update({s["id"]: s["name_it"] for s in species})
    return glossary


# --------------------------------------------------------------------------- main
def main(pdf_path: str, out_dir: str) -> None:
    os.makedirs(out_dir, exist_ok=True)
    pages = load_page_texts(pdf_path)
    toc = parse_toc(pages)

    datasets = {
        "species": extract_species(pages, toc),
        "backgrounds": extract_backgrounds(pages, toc),
        "classes": extract_classes(pages, toc),
        "feats": extract_feats(pages, toc),
        "conditions": extract_conditions(pages, toc),
        "spells": extract_spells(pages, toc),
        "skills": extract_skills(pages, toc),
        "monsters": extract_monsters(pages, toc),
    }
    equipment = extract_equipment(pdf_path, toc)
    datasets["weapons"] = equipment["weapons"]
    datasets["armor"] = equipment["armor"]
    datasets["it_glossary"] = build_it_glossary(datasets["classes"], datasets["species"])

    for name, data in datasets.items():
        path = os.path.join(out_dir, f"{name}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        count = len(data) if isinstance(data, list) else len(data)
        print(f"{name}.json: {count} voci")


if __name__ == "__main__":
    pdf_arg = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PDF
    out_arg = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_OUT
    main(pdf_arg, out_arg)
