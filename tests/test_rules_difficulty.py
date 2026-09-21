from __future__ import annotations

import pytest

from rules.difficulty import DC_BANDS, check_result, dc_for_band


@pytest.mark.parametrize(
    "band,expected",
    [
        ("molto_facile", 5),
        ("facile", 10),
        ("media", 15),
        ("difficile", 20),
        ("molto_difficile", 25),
        ("quasi_impossibile", 30),
    ],
)
def test_dc_for_band(band, expected):
    assert dc_for_band(band) == expected
    assert DC_BANDS[band] == expected


def test_dc_for_unknown_band():
    with pytest.raises(ValueError):
        dc_for_band("impossibile")


def test_check_result():
    assert check_result(15, 15)
    assert check_result(16, 15)
    assert not check_result(14, 15)
