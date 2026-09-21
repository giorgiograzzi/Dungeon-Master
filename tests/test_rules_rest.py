from __future__ import annotations

from rules.hit_points import HitPoints
from rules.rest import apply_long_rest, spend_hit_die


def test_spend_hit_die_within_bounds():
    for _ in range(100):
        healed = spend_hit_die(hit_die_sides=8, con_modifier=2)
        assert 3 <= healed <= 10


def test_spend_hit_die_never_negative(monkeypatch):
    monkeypatch.setattr("rules.rest.roll_die", lambda sides: 1)
    assert spend_hit_die(hit_die_sides=6, con_modifier=-5) == 0


def test_apply_long_rest_heals_and_clears_temp_hp():
    hp = HitPoints(current=2, maximum=20, temp=5)
    apply_long_rest(hp)
    assert hp.current == 20
    assert hp.temp == 0
