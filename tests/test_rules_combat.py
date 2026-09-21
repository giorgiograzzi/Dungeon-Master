from __future__ import annotations

import pytest

from rules.combat import (
    DeathSaveState,
    apply_damage_at_zero_hp,
    resolve_attack_roll,
    roll_damage,
    roll_death_save,
    roll_initiative,
)
from rules.hit_points import HitPoints


def test_attack_roll_hit_when_total_meets_ac(monkeypatch):
    monkeypatch.setattr("rules.dice.roll_die", lambda sides: 10)
    result = resolve_attack_roll(to_hit_bonus=5, target_ac=15)
    assert result.total == 15
    assert result.hit
    assert not result.critical_hit


def test_attack_roll_miss_below_ac(monkeypatch):
    monkeypatch.setattr("rules.dice.roll_die", lambda sides: 5)
    result = resolve_attack_roll(to_hit_bonus=2, target_ac=15)
    assert not result.hit


def test_natural_20_always_hits_even_below_ac(monkeypatch):
    monkeypatch.setattr("rules.dice.roll_die", lambda sides: 20)
    result = resolve_attack_roll(to_hit_bonus=-5, target_ac=30)
    assert result.hit
    assert result.critical_hit


def test_natural_1_always_misses_even_above_ac(monkeypatch):
    monkeypatch.setattr("rules.dice.roll_die", lambda sides: 1)
    result = resolve_attack_roll(to_hit_bonus=20, target_ac=5)
    assert not result.hit
    assert result.critical_miss


def test_critical_hit_doubles_dice_not_modifier(monkeypatch):
    monkeypatch.setattr("rules.dice.roll_die", lambda sides: 4)
    normal = roll_damage("1d6+3", critical=False)
    critical = roll_damage("1d6+3", critical=True)
    assert normal == 4 + 3
    assert critical == 4 + 4 + 3  # due dadi, un solo modificatore


def test_roll_initiative_includes_dex_modifier(monkeypatch):
    monkeypatch.setattr("rules.combat.roll_die", lambda sides: 12)
    assert roll_initiative(dex_modifier=3) == 15


def test_death_save_three_successes_stabilizes(monkeypatch):
    values = iter([15, 12, 18])
    monkeypatch.setattr("rules.combat.roll_die", lambda sides: next(values))
    state = DeathSaveState()
    hp = HitPoints(current=0, maximum=10)
    for _ in range(3):
        result = roll_death_save(state, hp)
    assert state.stable
    assert result["result"] == "stabile"


def test_death_save_three_failures_kills(monkeypatch):
    values = iter([5, 9, 3])
    monkeypatch.setattr("rules.combat.roll_die", lambda sides: next(values))
    state = DeathSaveState()
    hp = HitPoints(current=0, maximum=10)
    for _ in range(3):
        result = roll_death_save(state, hp)
    assert state.dead
    assert result["result"] == "morto"


def test_death_save_natural_1_counts_as_two_failures(monkeypatch):
    monkeypatch.setattr("rules.combat.roll_die", lambda sides: 1)
    state = DeathSaveState()
    hp = HitPoints(current=0, maximum=10)
    result = roll_death_save(state, hp)
    assert state.failures == 2
    assert result["result"] == "in bilico"


def test_death_save_natural_20_heals_1_hp_and_resets(monkeypatch):
    monkeypatch.setattr("rules.combat.roll_die", lambda sides: 20)
    state = DeathSaveState(successes=2, failures=1)
    hp = HitPoints(current=0, maximum=10)
    result = roll_death_save(state, hp)
    assert hp.current == 1
    assert state.successes == 0 and state.failures == 0
    assert "recupera 1 PF" in result["result"]


def test_cannot_roll_death_save_when_already_stable():
    state = DeathSaveState(stable=True)
    hp = HitPoints(current=0, maximum=10)
    with pytest.raises(ValueError):
        roll_death_save(state, hp)


def test_damage_at_zero_hp_counts_as_failure():
    state = DeathSaveState()
    hp = HitPoints(current=0, maximum=20)
    result = apply_damage_at_zero_hp(state, hp, damage=3)
    assert state.failures == 1
    assert result["result"] == "un tiro salvezza fallito"


def test_critical_damage_at_zero_hp_counts_as_two_failures():
    state = DeathSaveState()
    hp = HitPoints(current=0, maximum=20)
    apply_damage_at_zero_hp(state, hp, damage=3, critical=True)
    assert state.failures == 2


def test_massive_damage_at_zero_hp_is_instant_death():
    state = DeathSaveState()
    hp = HitPoints(current=0, maximum=12)
    result = apply_damage_at_zero_hp(state, hp, damage=12)
    assert state.dead
    assert "massiccio" in result["result"]
