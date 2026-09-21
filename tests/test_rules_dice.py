from __future__ import annotations

import pytest

from rules.dice import parse_dice_expression, roll_d20, roll_die, roll_expression


def test_roll_die_within_bounds():
    for _ in range(200):
        assert 1 <= roll_die(20) <= 20


def test_roll_die_rejects_zero_sides():
    with pytest.raises(ValueError):
        roll_die(0)


def test_roll_d20_no_advantage_uses_single_die():
    result = roll_d20()
    assert result.dropped is None
    assert not result.advantage and not result.disadvantage


def test_roll_d20_advantage_keeps_higher(monkeypatch):
    values = iter([5, 17])
    monkeypatch.setattr("rules.dice.roll_die", lambda sides: next(values))
    result = roll_d20(advantage=True)
    assert result.kept == 17
    assert result.dropped == 5


def test_roll_d20_disadvantage_keeps_lower(monkeypatch):
    values = iter([5, 17])
    monkeypatch.setattr("rules.dice.roll_die", lambda sides: next(values))
    result = roll_d20(disadvantage=True)
    assert result.kept == 5
    assert result.dropped == 17


def test_advantage_and_disadvantage_cancel_out(monkeypatch):
    # Con vantaggio e svantaggio insieme si tira un solo d20 (si annullano, §3).
    monkeypatch.setattr("rules.dice.roll_die", lambda sides: 9)
    result = roll_d20(advantage=True, disadvantage=True)
    assert result.dropped is None
    assert not result.advantage and not result.disadvantage
    assert result.kept == 9


def test_natural_20_and_1():
    from rules.dice import D20Roll

    assert D20Roll(kept=20, dropped=None, advantage=False, disadvantage=False).natural_20
    assert D20Roll(kept=1, dropped=None, advantage=False, disadvantage=False).natural_1


def test_parse_dice_expression():
    assert parse_dice_expression("2d6+3") == (2, 6, 3)
    assert parse_dice_expression("1d10-1") == (1, 10, -1)
    assert parse_dice_expression("1d4") == (1, 4, 0)


def test_parse_dice_expression_invalid():
    with pytest.raises(ValueError):
        parse_dice_expression("banana")


def test_roll_expression_range():
    for _ in range(50):
        total = roll_expression("2d6+3")
        assert 5 <= total <= 15
