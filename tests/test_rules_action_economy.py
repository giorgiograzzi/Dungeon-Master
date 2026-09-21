from __future__ import annotations

import pytest

from rules.action_economy import ActionEconomy, ActionEconomyError


def test_use_and_exhaust_action():
    econ = ActionEconomy()
    assert econ.can_use("action")
    econ.use("action")
    assert not econ.can_use("action")
    with pytest.raises(ActionEconomyError):
        econ.use("action")


def test_reset_turn_restores_action_bonus_movement_and_free_interaction():
    econ = ActionEconomy()
    for kind in ("action", "bonus_action", "movement", "free_object_interaction"):
        econ.use(kind)
    econ.reset_turn()
    for kind in ("action", "bonus_action", "movement", "free_object_interaction"):
        assert econ.can_use(kind)


def test_reset_turn_does_not_restore_reaction():
    econ = ActionEconomy()
    econ.use("reaction")
    econ.reset_turn()
    assert not econ.can_use("reaction")


def test_reset_round_restores_reaction():
    econ = ActionEconomy()
    econ.use("reaction")
    econ.reset_round()
    assert econ.can_use("reaction")


def test_unknown_action_kind():
    econ = ActionEconomy()
    with pytest.raises(ValueError):
        econ.use("volo")


def test_remaining():
    econ = ActionEconomy()
    assert econ.remaining("action") == 1
    econ.use("action")
    assert econ.remaining("action") == 0
