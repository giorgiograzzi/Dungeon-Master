"""Dati finti ma strutturalmente validi, usati da `FakeAIClient` (DEV_FAKE_AI=1,
§6/§14) e come fixture nei test di `rules/campaign.py`. Non sono creativi:
servono solo a far girare il gioco e la validazione senza chiamare l'API."""

from __future__ import annotations

ROUTE_IDS = ("parola", "ombra", "acciaio")
ROUTE_NAMES = {
    "parola": ("Via della Parola", "Diplomazia e intrighi"),
    "ombra": ("Via dell'Ombra", "Furtività e indagine"),
    "acciaio": ("Via dell'Acciaio", "Scontri e forza"),
}


def build_fake_campaign_plan(setting: str = "fantasy classico", duration: str = "media") -> dict:
    beats = [
        {"id": "incidente_scatenante", "title": "L'incidente scatenante", "objective": "Scopri la minaccia",
         "act": 1, "route": None, "is_hinge": True},
        {"id": "rivelazione_centrale", "title": "La rivelazione centrale", "objective": "Svela il piano del nemico",
         "act": 2, "route": None, "is_hinge": True},
        {"id": "scontro_finale", "title": "Lo scontro finale", "objective": "Affronta l'antagonista",
         "act": 3, "route": None, "is_hinge": True},
    ]
    gates = []
    side_quests = []
    npcs = []
    scenes = [{"id": f"scena_{b['id']}", "beat_id": b["id"], "side_quest_id": None, "route_id": b["route"]} for b in beats]

    for route_id in ROUTE_IDS:
        name, tagline = ROUTE_NAMES[route_id]
        beats.append({
            "id": f"{route_id}_atto1", "title": f"{name}: primo passo", "objective": "Avanza sul tuo percorso",
            "act": 1, "route": route_id, "is_hinge": False,
        })
        beats.append({
            "id": f"{route_id}_atto2", "title": f"{name}: prova decisiva", "objective": "Supera la prova del percorso",
            "act": 2, "route": route_id, "is_hinge": False,
        })
        scenes.append({"id": f"scena_{route_id}_atto1", "beat_id": f"{route_id}_atto1", "side_quest_id": None, "route_id": route_id})
        scenes.append({"id": f"scena_{route_id}_atto2", "beat_id": f"{route_id}_atto2", "side_quest_id": None, "route_id": route_id})

        gates.append({
            "id": f"gate_{route_id}",
            "beat_id": f"{route_id}_atto1",
            "route": None,
            "description": f"Un ostacolo lungo la {name.lower()}",
            "solutions": [
                {"approach": "combattere", "dc_band": "media", "cost": "PF", "consequence": "rumore, attira attenzione"},
                {"approach": "persuadere", "dc_band": "media", "cost": "tempo", "consequence": "un alleato in più"},
                {"approach": "aggirare", "dc_band": "difficile", "cost": "risorse", "consequence": "via più lenta ma silenziosa"},
            ],
        })

    for i in range(1, 4):
        route_id = ROUTE_IDS[(i - 1) % len(ROUTE_IDS)]
        quest_id = f"secondaria_{i}"
        side_quests.append({
            "id": quest_id,
            "hook": f"Qualcuno chiede aiuto (quest {i})",
            "location": "una locanda",
            "npc_id": f"png_{i}",
            "objective": "Risolvi il problema locale",
            "solutions": ["parlarne con calma", "agire con astuzia"],
            "reward": {"type": "indizio", "effect": "rivela il punto debole dell'antagonista"},
            "unlocks": "un alleato nel finale",
            "route_id": None,
        })
        scenes.append({"id": f"scena_{quest_id}", "beat_id": None, "side_quest_id": quest_id, "route_id": None})

    for i in range(1, 26):
        npcs.append({
            "id": f"png_{i}",
            "name": f"PNG {i}",
            "species": "umano",
            "role": "comprimario",
            "age": "adulto",
            "personality": ["cauto", "curioso"],
            "motivation": "sopravvivere e prosperare",
            "secret": "nasconde un debito di gioco",
            "attitude": 0,
            "knows": ["dove si trova il rifugio del nemico"],
            "offers": ["informazioni"],
            "route_id": None,
        })

    return {
        "title": f"L'ombra su {setting.title()}",
        "premise": "Una minaccia emerge dall'ombra e solo l'eroe può fermarla.",
        "antagonist": {"name": "Il Regista", "motive": "potere assoluto"},
        "setting": setting,
        "duration_target": duration,
        "acts": [
            {"number": 1, "title": "Atto I"},
            {"number": 2, "title": "Atto II"},
            {"number": 3, "title": "Atto III"},
        ],
        "beats": beats,
        "routes": [
            {"id": rid, "name": ROUTE_NAMES[rid][0], "tagline": ROUTE_NAMES[rid][1],
             "risk": "medio", "style": ROUTE_NAMES[rid][1], "duration_effect": "media"}
            for rid in ROUTE_IDS
        ],
        "crossroads": [
            {"after_act": 1, "route_ids": list(ROUTE_IDS)},
            {"after_act": 2, "route_ids": list(ROUTE_IDS)},
        ],
        "gates": gates,
        "side_quests": side_quests,
        "npcs": npcs,
        "endings": [
            {"id": "finale_vittoria", "title": "Vittoria", "condition": "l'antagonista è sconfitto"},
            {"id": "finale_pirrico", "title": "Vittoria amara", "condition": "l'antagonista fugge"},
        ],
        "clues": [
            {"fact": "il covo del nemico è nelle fogne", "sources": ["png_1", "secondaria_1"]},
            {"fact": "l'antagonista teme il fuoco", "sources": ["png_2", "secondaria_2"]},
        ],
        "scenes": scenes,
    }
