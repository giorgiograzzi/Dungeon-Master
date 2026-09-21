from __future__ import annotations

import pytest

from rules.action_economy import ActionEconomy
from rules.items import ItemUseError, UseCost, use_item


def test_use_item_action_cost_consumes_action():
    econ = ActionEconomy()
    use_item(econ, UseCost.ACTION)
    assert not econ.can_use("action")


def test_use_item_bonus_action_cost():
    econ = ActionEconomy()
    use_item(econ, UseCost.BONUS_ACTION)
    assert not econ.can_use("bonus_action")


def test_use_item_free_cost_uses_free_object_interaction():
    econ = ActionEconomy()
    use_item(econ, UseCost.FREE)
    assert not econ.can_use("free_object_interaction")


def test_use_item_none_cost_consumes_nothing():
    econ = ActionEconomy()
    use_item(econ, UseCost.NONE)
    assert econ.can_use("action")
    assert econ.can_use("bonus_action")
    assert econ.can_use("free_object_interaction")


def test_use_item_blocked_when_resource_exhausted():
    econ = ActionEconomy()
    use_item(econ, UseCost.FREE)
    with pytest.raises(ItemUseError):
        use_item(econ, UseCost.FREE)
