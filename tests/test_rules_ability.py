from __future__ import annotations

import pytest

from rules.ability import ability_modifier, proficiency_bonus


@pytest.mark.parametrize(
    "score,expected",
    [(1, -5), (8, -1), (9, -1), (10, 0), (11, 0), (12, 1), (20, 5), (30, 10)],
)
def test_ability_modifier(score, expected):
    assert ability_modifier(score) == expected


@pytest.mark.parametrize(
    "level,expected",
    [(1, 2), (4, 2), (5, 3), (8, 3), (9, 4), (12, 4), (13, 5), (16, 5), (17, 6), (20, 6)],
)
def test_proficiency_bonus(level, expected):
    assert proficiency_bonus(level) == expected


def test_proficiency_bonus_out_of_range():
    with pytest.raises(ValueError):
        proficiency_bonus(0)
    with pytest.raises(ValueError):
        proficiency_bonus(21)
