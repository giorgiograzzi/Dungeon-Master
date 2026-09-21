from __future__ import annotations

import pytest

from rules.hit_points import HitPoints


def test_damage_reduces_current_hp():
    hp = HitPoints(current=10, maximum=10)
    real = hp.apply_damage(4)
    assert hp.current == 6
    assert real == 4


def test_temp_hp_absorbed_first():
    hp = HitPoints(current=10, maximum=10, temp=5)
    real = hp.apply_damage(3)
    assert hp.temp == 2
    assert hp.current == 10
    assert real == 0


def test_temp_hp_overflow_spills_to_real_hp():
    hp = HitPoints(current=10, maximum=10, temp=5)
    real = hp.apply_damage(8)
    assert hp.temp == 0
    assert hp.current == 7
    assert real == 3


def test_temp_hp_do_not_stack_keeps_higher():
    hp = HitPoints(current=10, maximum=10, temp=5)
    hp.add_temp_hp(3)
    assert hp.temp == 5
    hp.add_temp_hp(8)
    assert hp.temp == 8


def test_heal_cannot_exceed_maximum():
    hp = HitPoints(current=5, maximum=10)
    hp.heal(100)
    assert hp.current == 10


def test_damage_cannot_go_below_zero():
    hp = HitPoints(current=3, maximum=10)
    real = hp.apply_damage(100)
    assert hp.current == 0
    assert real == 3
    assert hp.is_down


def test_negative_damage_rejected():
    hp = HitPoints(current=10, maximum=10)
    with pytest.raises(ValueError):
        hp.apply_damage(-1)


def test_clear_temp_hp_on_long_rest():
    hp = HitPoints(current=10, maximum=10, temp=5)
    hp.clear_temp_hp()
    assert hp.temp == 0
