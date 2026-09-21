"""Schemi JSON degli strumenti del narratore (§10): tool use con schema
forzato (`tool_choice`), mai testo libero da interpretare."""

from __future__ import annotations

EFFECT_TYPES = [
    "hp_delta", "temp_hp", "item_add", "item_remove", "condition_add", "condition_remove",
    "gold", "fact_add", "quest_update", "start_combat", "end_combat", "beat_progress",
    "side_quest_start", "side_quest_update", "side_quest_complete", "route_chosen",
    "gate_solved", "npc_attitude", "npc_learned", "npc_status", "ending_reached",
]

EFFECT_SCHEMA = {
    "type": "object",
    "properties": {
        "type": {"type": "string", "enum": EFFECT_TYPES},
        "target": {"type": "string", "description": "id di riferimento (npc, oggetto, quest, gate...), se pertinente"},
        "value": {"description": "valore dell'effetto: numero, stringa o oggetto a seconda del tipo"},
        "reason": {"type": "string", "description": "motivazione narrativa breve"},
    },
    "required": ["type"],
}

REQUEST_CHECK_TOOL = {
    "name": "request_check",
    "description": "Indica se il turno richiede un tiro con d20 e con quali parametri, oppure narra "
    "direttamente l'esito se non serve alcun tiro.",
    "input_schema": {
        "type": "object",
        "properties": {
            "needs_roll": {"type": "boolean"},
            "check_type": {"type": "string", "enum": ["ability", "save", "attack"]},
            "ability": {"type": "string", "enum": ["for", "des", "cos", "int", "sag", "car"]},
            "skill_id": {"type": "string", "description": "id dell'abilità SRD, se la prova ne usa una"},
            "dc_band": {
                "type": "string",
                "enum": ["molto_facile", "facile", "media", "difficile", "molto_difficile", "quasi_impossibile"],
            },
            "advantage": {"type": "boolean"},
            "disadvantage": {"type": "boolean"},
            "advantage_reason": {"type": "string"},
            "narration": {"type": "string", "description": "narrazione diretta, solo se needs_roll è falso"},
        },
        "required": ["needs_roll"],
    },
}

NARRATE_OUTCOME_TOOL = {
    "name": "narrate_outcome",
    "description": "Narra le conseguenze di un'azione (con o senza tiro) e propone le opzioni successive.",
    "input_schema": {
        "type": "object",
        "properties": {
            "narration": {"type": "string"},
            "options": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "label": {"type": "string"},
                        "action_cost": {"type": "string", "enum": ["action", "bonus_action", "reaction", "free"]},
                        "dc_band": {"type": "string"},
                    },
                    "required": ["label"],
                },
            },
            "effects": {"type": "array", "items": EFFECT_SCHEMA},
        },
        "required": ["narration"],
    },
}

GENERATE_CAMPAIGN_PLAN_TOOL = {
    "name": "generate_campaign_plan",
    "description": "Genera il Piano di Campagna a grafo: atti, beat, percorsi, bivi, gate, quest secondarie, "
    "cast di PNG, indizi ridondanti, finali possibili.",
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "premise": {"type": "string"},
            "antagonist": {
                "type": "object",
                "properties": {"name": {"type": "string"}, "motive": {"type": "string"}},
                "required": ["name", "motive"],
            },
            "setting": {"type": "string"},
            "duration_target": {"type": "string", "enum": ["breve", "media", "lunga"]},
            "acts": {"type": "array", "items": {"type": "object"}},
            "beats": {"type": "array", "items": {"type": "object"}},
            "routes": {"type": "array", "items": {"type": "object"}},
            "crossroads": {"type": "array", "items": {"type": "object"}},
            "gates": {"type": "array", "items": {"type": "object"}},
            "side_quests": {"type": "array", "items": {"type": "object"}},
            "npcs": {"type": "array", "items": {"type": "object"}},
            "endings": {"type": "array", "items": {"type": "object"}},
            "clues": {"type": "array", "items": {"type": "object"}},
            "scenes": {"type": "array", "items": {"type": "object"}},
        },
        "required": ["title", "premise", "antagonist", "beats", "routes", "crossroads", "gates", "side_quests", "npcs"],
    },
}

PRESENT_CROSSROADS_TOOL = {
    "name": "present_crossroads",
    "description": "Presenta i 3 percorsi disponibili a un bivio, senza spoiler e senza sceglierne uno.",
    "input_schema": {
        "type": "object",
        "properties": {
            "routes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "title": {"type": "string"},
                        "promise": {"type": "string"},
                        "risk": {"type": "string"},
                        "style": {"type": "string"},
                        "duration_effect": {"type": "string"},
                    },
                    "required": ["id", "title", "promise", "risk", "style"],
                },
            }
        },
        "required": ["routes"],
    },
}

SUMMARIZE_STORY_TOOL = {
    "name": "summarize_story",
    "description": "Aggiorna il riassunto progressivo della storia (story_summary) con l'ultima scena.",
    "input_schema": {
        "type": "object",
        "properties": {"summary": {"type": "string"}},
        "required": ["summary"],
    },
}

EXPORT_STORY_TOOL = {
    "name": "export_story",
    "description": "Esporta l'intera avventura come racconto in prosa, in italiano.",
    "input_schema": {
        "type": "object",
        "properties": {"story_text": {"type": "string"}},
        "required": ["story_text"],
    },
}
