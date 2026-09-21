from __future__ import annotations

from rules.levelup import roll_hp_gain


def test_roll_hp_gain_adds_con_modifier(monkeypatch):
    monkeypatch.setattr("rules.levelup.roll_die", lambda sides: 6)
    assert roll_hp_gain(hit_die_sides=10, con_modifier=2) == (6, 8)


def test_roll_hp_gain_never_below_one(monkeypatch):
    monkeypatch.setattr("rules.levelup.roll_die", lambda sides: 1)
    assert roll_hp_gain(hit_die_sides=6, con_modifier=-3) == (1, 1)
