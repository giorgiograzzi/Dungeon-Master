from __future__ import annotations

import pytest

from rules.action_economy import ActionEconomy
from rules.weapon import swap_weapon


def test_swap_weapon_default_costs_action():
    econ = ActionEconomy()
    swap_weapon(econ)
    assert not econ.can_use("action")
    assert econ.can_use("free_object_interaction")


def test_swap_weapon_free_interaction_rule():
    econ = ActionEconomy()
    swap_weapon(econ, rule="free_interaction")
    assert econ.can_use("action")
    assert not econ.can_use("free_object_interaction")


def test_swap_weapon_unknown_rule():
    econ = ActionEconomy()
    with pytest.raises(ValueError):
        swap_weapon(econ, rule="gratis")
