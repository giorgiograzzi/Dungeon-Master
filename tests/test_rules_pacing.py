from __future__ import annotations

from rules.pacing import compute_pacing


def test_pacing_in_linea_when_act_matches_expected_progress():
    # breve = 12 turni, ~4 a atto: al turno 5 ci si aspetta l'atto 2.
    result = compute_pacing(duration_target="breve", turn_count=5, current_act=2)
    assert result["status"] == "in_linea"
    assert result["expected_act"] == 2


def test_pacing_in_ritardo_when_behind_expected_act():
    result = compute_pacing(duration_target="breve", turn_count=10, current_act=1)
    assert result["status"] == "in_ritardo"
    assert result["expected_act"] == 3


def test_pacing_in_anticipo_when_ahead_of_expected_act():
    result = compute_pacing(duration_target="lunga", turn_count=1, current_act=3)
    assert result["status"] == "in_anticipo"
    assert result["expected_act"] == 1


def test_pacing_expected_act_never_exceeds_three():
    result = compute_pacing(duration_target="breve", turn_count=999, current_act=3)
    assert result["expected_act"] == 3
    assert result["status"] == "in_linea"


def test_pacing_estimated_turns_remaining_never_negative():
    result = compute_pacing(duration_target="breve", turn_count=999, current_act=3)
    assert result["estimated_turns_remaining"] == 0


def test_pacing_unknown_duration_falls_back_to_media_budget():
    result = compute_pacing(duration_target="???", turn_count=0, current_act=1)
    assert result["estimated_turns_remaining"] == 24
