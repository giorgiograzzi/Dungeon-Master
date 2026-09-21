"""Stato di combattimento (§8): iniziativa, round e turni, con un tracker
dell'economia delle azioni per ogni combattente. Il posizionamento usa il
*teatro della mente* semplificato (§8): niente griglia, solo "vicino"/"via"."""

from __future__ import annotations

import re

from app import srd_data
from rules.action_economy import ActionEconomy
from rules.combat import DeathSaveState, apply_damage_at_zero_hp, resolve_attack_roll, roll_damage, roll_death_save, roll_initiative
from rules.hit_points import HitPoints
from rules.items import UseCost, use_item
from rules.weapon import swap_weapon

_DICE_PATTERN = re.compile(r"\d*d\d+")


def find_weapon_in_equipment(equipment_text: str) -> dict | None:
    """Cerca nel testo dell'equipaggiamento la prima arma nota dell'SRD.

    Semplificazione documentata (vedi DECISIONS.md): senza un cambio arma
    esplicito (vedi `swap_active_weapon`), l'arma "impugnata" di default è
    sempre la prima citata nel testo dell'equipaggiamento iniziale.
    """
    text_lower = equipment_text.lower()
    matches = []
    for weapon in srd_data.weapons().values():
        index = text_lower.find(weapon["name_it"].lower())
        if index != -1:
            matches.append((index, -len(weapon["name_it"]), weapon))
    if not matches:
        return None
    # La prima arma citata nel testo vince; a parità di posizione, il nome
    # più lungo e specifico (es. "Ascia bipenne" prima di "Ascia").
    matches.sort(key=lambda m: (m[0], m[1]))
    return matches[0][2]


def list_available_weapons(character_sheet: dict) -> list[dict]:
    """Tutte le armi note dell'SRD citate nell'equipaggiamento o
    nell'inventario del personaggio -- usato dalla UI per proporre un cambio
    arma tra quelle effettivamente possedute.

    Semplificazione: confronto per sottostringa sul solo singolare (una
    voce come "8 giavellotti" al plurale non viene riconosciuta); si scarta
    un nome che è solo sottostringa di un altro nome trovato (es. "Mazza"
    dentro "Mazzafrusto") per evitare falsi positivi."""
    equipment_text = character_sheet.get("equipment", "").lower()
    inventory = [str(i).lower() for i in character_sheet.get("inventory", [])]
    matched_names = [
        weapon["name_it"].lower()
        for weapon in srd_data.weapons().values()
        if weapon["name_it"].lower() in equipment_text or any(weapon["name_it"].lower() in i for i in inventory)
    ]
    found = []
    for weapon in srd_data.weapons().values():
        name_lower = weapon["name_it"].lower()
        if name_lower not in matched_names:
            continue
        if any(name_lower != other and name_lower in other for other in matched_names):
            continue
        found.append({"id": weapon["id"], "name_it": weapon["name_it"]})
    return found


def resolve_active_weapon(character_sheet: dict, save_data: dict) -> dict | None:
    """Arma attualmente impugnata: quella scelta con un cambio arma in questo
    combattimento, altrimenti la prima trovata nell'equipaggiamento (vedi
    `find_weapon_in_equipment`)."""
    combat = save_data.get("combat") or {}
    equipped_id = combat.get("equipped_weapon_id")
    if equipped_id:
        weapon = srd_data.weapons().get(equipped_id)
        if weapon is not None:
            return weapon
    return find_weapon_in_equipment(character_sheet.get("equipment", ""))


class WeaponSwapError(ValueError):
    pass


def swap_active_weapon(save_data: dict, character_sheet: dict, weapon_id: str, rule: str = "action") -> dict:
    """Cambia l'arma impugnata (§8): consuma la risorsa configurata in
    RULE_WEAPON_SWAP_COST, valida che l'arma sia effettivamente posseduta."""
    weapon = srd_data.weapons().get(weapon_id)
    if weapon is None:
        raise WeaponSwapError(f"arma sconosciuta: {weapon_id!r}")
    equipment_text = character_sheet.get("equipment", "").lower()
    inventory = [str(i).lower() for i in character_sheet.get("inventory", [])]
    name_lower = weapon["name_it"].lower()
    if name_lower not in equipment_text and not any(name_lower in i for i in inventory):
        raise WeaponSwapError(f"il personaggio non possiede: {weapon['name_it']!r}")

    player = find_combatant(save_data, "player")
    economy = _economy_from_dict(player["action_economy"])
    swap_weapon(economy, rule=rule)
    player["action_economy"] = _economy_to_dict(economy)
    save_data["combat"]["equipped_weapon_id"] = weapon_id
    return weapon


def use_item_in_combat(save_data: dict, cost: UseCost) -> None:
    """Consuma la risorsa dell'economia delle azioni del giocatore per usare
    un oggetto dell'inventario in combattimento (§8). Propaga `ItemUseError`
    se la risorsa è già esaurita per questo turno."""
    player = find_combatant(save_data, "player")
    economy = _economy_from_dict(player["action_economy"])
    use_item(economy, cost)
    player["action_economy"] = _economy_to_dict(economy)


def resolve_to_hit_and_damage(character_sheet: dict, weapon: dict | None) -> tuple[int, str]:
    """Bonus di attacco e dado di danno per un'arma (o pugno nudo).

    Semplificazione: competenza con l'arma sempre assunta (l'equipaggiamento
    iniziale di classe è coerente con le sue competenze nell'SRD)."""
    mods = character_sheet["ability_modifiers"]
    prof = character_sheet["proficiency_bonus"]
    if weapon is None:
        return mods["for"] + prof, f"1d1+{mods['for']}"  # pugno nudo: 1 + mod Forza (SRD)

    if weapon["kind"] == "distanza":
        ability_mod = mods["des"]
    elif "accurata" in weapon["properties"].lower():
        ability_mod = max(mods["for"], mods["des"])
    else:
        ability_mod = mods["for"]

    dice_match = _DICE_PATTERN.search(weapon["damage"])
    dice = dice_match.group(0) if dice_match else "1d1"  # es. Cerbottana: "1 perforante", nessun dado
    return ability_mod + prof, f"{dice}+{ability_mod}"


def _economy_to_dict(economy: ActionEconomy) -> dict:
    return {"used": dict(economy.used), "available": dict(economy.available)}


def _economy_from_dict(data: dict) -> ActionEconomy:
    return ActionEconomy(used=dict(data["used"]), available=dict(data["available"]))


def _death_save_to_dict(state: DeathSaveState) -> dict:
    return {"successes": state.successes, "failures": state.failures, "stable": state.stable, "dead": state.dead}


def _death_save_from_dict(data: dict) -> DeathSaveState:
    return DeathSaveState(successes=data["successes"], failures=data["failures"], stable=data["stable"], dead=data["dead"])


def start_combat(save_data: dict, character_data: dict, character_sheet: dict, monster_ids: list[str]) -> None:
    """Tira l'iniziativa per il PG e per ogni mostro, ordina i turni (§8)."""
    monsters = srd_data.monsters()
    combatants = [
        {
            "id": "player",
            "name": character_sheet["name"],
            "is_player": True,
            "initiative": roll_initiative(character_sheet["ability_modifiers"]["des"]),
            "hp": {"current": character_data["hp_current"], "maximum": character_data["hp_max"], "temp": character_data.get("hp_temp", 0)},
            "ac": character_sheet["armor_class"],
            "action_economy": _economy_to_dict(ActionEconomy()),
        }
    ]
    for i, monster_id in enumerate(monster_ids):
        monster = monsters[monster_id]
        dex_mod = int(monster["abilities"]["dex"]["mod"])
        combatants.append({
            "id": f"{monster_id}_{i + 1}",
            "monster_id": monster_id,
            "name": monster["name_it"],
            "is_player": False,
            "initiative": roll_initiative(dex_mod),
            "hp": {"current": monster["hp"], "maximum": monster["hp"], "temp": 0},
            "ac": monster["ac"],
            "action_economy": _economy_to_dict(ActionEconomy()),
        })
    combatants.sort(key=lambda c: c["initiative"], reverse=True)

    save_data["mode"] = "combat"
    save_data["combat"] = {
        "round": 1,
        "combatants": combatants,
        "current_turn_index": 0,
        "pending_reaction": None,
        "death_save": _death_save_to_dict(DeathSaveState()),
    }


def player_death_save_if_down(save_data: dict) -> dict | None:
    """Il conteggio dei tiri salvezza contro la morte, solo se il giocatore
    è a 0 PF (altrimenti il contatore azzerato non è informazione utile
    per la UI, vedi `_public_combat_state`)."""
    player = find_combatant(save_data, "player")
    if player["hp"]["current"] > 0:
        return None
    return save_data["combat"]["death_save"]


def sync_player_hp(save_data: dict, character_data: dict) -> None:
    """Riporta i PF di lavoro del giocatore (tenuti nel combattimento) sulla
    scheda persistente del personaggio, cosi la scheda resta accurata anche
    durante un combattimento in corso e dopo che è finito."""
    player = find_combatant(save_data, "player")
    character_data["hp_current"] = player["hp"]["current"]
    character_data["hp_max"] = player["hp"]["maximum"]
    character_data["hp_temp"] = player["hp"]["temp"]


def end_combat(save_data: dict, character_data: dict | None = None) -> None:
    if character_data is not None:
        sync_player_hp(save_data, character_data)
    save_data["mode"] = "exploration"
    save_data["combat"] = None


def current_combatant(save_data: dict) -> dict:
    combat = save_data["combat"]
    return combat["combatants"][combat["current_turn_index"]]


def find_combatant(save_data: dict, combatant_id: str) -> dict:
    for c in save_data["combat"]["combatants"]:
        if c["id"] == combatant_id:
            return c
    raise ValueError(f"combattente sconosciuto: {combatant_id!r}")


def _is_defeated(save_data: dict, combatant: dict) -> bool:
    """Un mostro è sconfitto a 0 PF (SRD: muore); il giocatore resta in gioco
    -- a terra ma non morto -- finché non fallisce 3 tiri salvezza contro la
    morte (§8, "Scendere a 0 punti ferita")."""
    if combatant["is_player"]:
        return save_data["combat"]["death_save"]["dead"]
    return combatant["hp"]["current"] <= 0


def _damage_combatant(save_data: dict, combatant: dict, damage: int, critical: bool = False) -> dict:
    """Applica danno a un combattente. Se il giocatore è già a 0 PF, il danno
    conta come tiro salvezza contro la morte fallito invece di essere solo
    sottratto (§8)."""
    hp = HitPoints(**combatant["hp"])
    result: dict = {}
    if combatant["is_player"] and hp.current <= 0 and not save_data["combat"]["death_save"]["stable"]:
        state = _death_save_from_dict(save_data["combat"]["death_save"])
        outcome = apply_damage_at_zero_hp(state, hp, damage, critical=critical)
        save_data["combat"]["death_save"] = _death_save_to_dict(state)
        result["death_save"] = outcome
    else:
        was_up = hp.current > 0
        hp.apply_damage(damage)
        if combatant["is_player"] and was_up and hp.current <= 0:
            # Sceso a 0 PF ora: si riparte con tiri salvezza puliti.
            save_data["combat"]["death_save"] = _death_save_to_dict(DeathSaveState())
    combatant["hp"] = {"current": hp.current, "maximum": hp.maximum, "temp": hp.temp}
    return result


def _maybe_roll_player_death_save(save_data: dict, next_combatant: dict) -> dict | None:
    """A inizio turno, un giocatore a 0 PF non ancora stabile/morto tira
    automaticamente il tiro salvezza contro la morte (§8: non è una scelta)."""
    if not next_combatant["is_player"] or next_combatant["hp"]["current"] > 0:
        return None
    state = _death_save_from_dict(save_data["combat"]["death_save"])
    if state.stable or state.dead:
        return None
    hp = HitPoints(**next_combatant["hp"])
    outcome = roll_death_save(state, hp)
    next_combatant["hp"] = {"current": hp.current, "maximum": hp.maximum, "temp": hp.temp}
    save_data["combat"]["death_save"] = _death_save_to_dict(state)
    return outcome


def advance_turn(save_data: dict, character_data: dict | None = None) -> dict:
    """Passa al prossimo combattente vivo; a un nuovo round si rinnovano le
    Reazioni di tutti (§8: 1 Reazione per round)."""
    combat = save_data["combat"]
    living = [c for c in combat["combatants"] if not _is_defeated(save_data, c)]
    if len(living) <= 1:
        end_combat(save_data, character_data)
        return {"combat_ended": True}

    combat["current_turn_index"] += 1
    new_round = False
    if combat["current_turn_index"] >= len(combat["combatants"]):
        combat["current_turn_index"] = 0
        combat["round"] += 1
        new_round = True
        for c in combat["combatants"]:
            economy = _economy_from_dict(c["action_economy"])
            economy.reset_round()
            c["action_economy"] = _economy_to_dict(economy)

    next_combatant = combat["combatants"][combat["current_turn_index"]]
    if not next_combatant["is_player"] and next_combatant["hp"]["current"] <= 0:
        return advance_turn(save_data, character_data)

    economy = _economy_from_dict(next_combatant["action_economy"])
    economy.reset_turn()
    next_combatant["action_economy"] = _economy_to_dict(economy)

    death_save = _maybe_roll_player_death_save(save_data, next_combatant)
    return {"combat_ended": False, "new_round": new_round, "current": next_combatant, "death_save": death_save}


def player_attack(save_data: dict, character_sheet: dict, target_id: str, to_hit_bonus: int, damage_expression: str) -> dict:
    player = find_combatant(save_data, "player")
    if player["hp"]["current"] <= 0:
        raise ValueError("il personaggio è a 0 PF: non può agire")
    target = find_combatant(save_data, target_id)
    economy = _economy_from_dict(player["action_economy"])
    economy.use("action")
    player["action_economy"] = _economy_to_dict(economy)

    attack = resolve_attack_roll(to_hit_bonus=to_hit_bonus, target_ac=target["ac"])
    result = {"attack": attack.__dict__, "damage": 0}
    if attack.hit:
        damage = roll_damage(damage_expression, critical=attack.critical_hit)
        damage_result = _damage_combatant(save_data, target, damage, critical=attack.critical_hit)
        result["damage"] = damage
        result.update(damage_result)
    return result


MONSTER_FLEE_HP_FRACTION = 0.25


def check_flee_opportunity(save_data: dict, monster_combatant: dict) -> dict | None:
    """Un mostro sotto un quarto dei PF tenta di ritirarsi: se il giocatore
    ha una Reazione disponibile e un'arma da mischia, gli si chiede se vuole
    tentare un attacco di opportunità (§8, Glossario "Attacchi di opportunità")."""
    if monster_combatant["hp"]["current"] > monster_combatant["hp"]["maximum"] * MONSTER_FLEE_HP_FRACTION:
        return None
    player = find_combatant(save_data, "player")
    economy = _economy_from_dict(player["action_economy"])
    if not economy.can_use("reaction"):
        return None
    reaction = {
        "combatant_id": "player",
        "trigger": "opportunity_attack",
        "target_id": monster_combatant["id"],
        "description": f"{monster_combatant['name']} cerca di ritirarsi: vuoi tentare un attacco di opportunità?",
    }
    save_data["combat"]["pending_reaction"] = reaction
    return reaction


def resolve_reaction(save_data: dict, character_sheet: dict, accept: bool, to_hit_bonus: int = 0, damage_expression: str = "1d4") -> dict:
    combat = save_data["combat"]
    reaction = combat.get("pending_reaction")
    if reaction is None:
        raise ValueError("nessuna reazione in sospeso")
    combat["pending_reaction"] = None
    if not accept:
        return {"used": False}

    player = find_combatant(save_data, "player")
    economy = _economy_from_dict(player["action_economy"])
    economy.use("reaction")
    player["action_economy"] = _economy_to_dict(economy)

    if reaction["trigger"] == "opportunity_attack":
        attack_result = player_attack_reaction(save_data, reaction["target_id"], to_hit_bonus, damage_expression)
        return {"used": True, **attack_result}
    return {"used": True}


def player_attack_reaction(save_data: dict, target_id: str, to_hit_bonus: int, damage_expression: str) -> dict:
    """Come player_attack, ma non consuma l'Azione (la Reazione è già stata
    consumata da resolve_reaction) — usata per l'attacco di opportunità."""
    target = find_combatant(save_data, target_id)
    attack = resolve_attack_roll(to_hit_bonus=to_hit_bonus, target_ac=target["ac"])
    result = {"attack": attack.__dict__, "damage": 0}
    if attack.hit:
        damage = roll_damage(damage_expression, critical=attack.critical_hit)
        damage_result = _damage_combatant(save_data, target, damage, critical=attack.critical_hit)
        result["damage"] = damage
        result.update(damage_result)
    return result


def resolve_monster_turn(save_data: dict, monster_combatant: dict) -> dict:
    """Turno automatico di un mostro: usa la prima azione con un attacco
    strutturato dell'SRD contro il giocatore (semplificazione documentata in
    DECISIONS.md: nessuna scelta tattica, sempre bersaglio il giocatore)."""
    monster = srd_data.monsters()[monster_combatant["monster_id"]]
    actions_with_attack = [a for a in monster.get("actions", []) if a.get("attack")]
    if not actions_with_attack:
        return {"action_name": None, "attack": None, "damage": 0}

    action = actions_with_attack[0]
    attack_info = action["attack"]
    to_hit_bonus = int(attack_info["to_hit"])
    damage_expression = attack_info["damage_dice"]

    player = find_combatant(save_data, "player")
    economy = _economy_from_dict(monster_combatant["action_economy"])
    if economy.can_use("action"):
        economy.use("action")
        monster_combatant["action_economy"] = _economy_to_dict(economy)

    attack = resolve_attack_roll(to_hit_bonus=to_hit_bonus, target_ac=player["ac"])
    result = {"action_name": action["name"], "attack": attack.__dict__, "damage": 0}
    if attack.hit:
        damage = roll_damage(damage_expression, critical=attack.critical_hit)
        damage_result = _damage_combatant(save_data, player, damage, critical=attack.critical_hit)
        result["damage"] = damage
        result.update(damage_result)
    return result


def run_monster_turns_until_player(save_data: dict, character_data: dict | None = None) -> dict:
    """Risolve automaticamente i turni di tutti i mostri finché non tocca di
    nuovo al giocatore o il combattimento finisce (§8: l'IA non decide nulla
    qui, sono azioni deterministiche lette dallo statblock)."""
    monster_turns = []
    death_save = None
    while True:
        current = current_combatant(save_data)
        if current["is_player"]:
            return {"combat_ended": False, "monster_turns": monster_turns, "death_save": death_save}
        turn_result = resolve_monster_turn(save_data, current)
        monster_turns.append({"combatant_id": current["id"], "name": current["name"], **turn_result})
        advance_result = advance_turn(save_data, character_data)
        if advance_result["combat_ended"]:
            return {"combat_ended": True, "monster_turns": monster_turns, "death_save": None}
        death_save = advance_result.get("death_save")
