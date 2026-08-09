"""Spaced-repetition arithmetic (SM-2)."""

import datetime

from chess_coach import srs


def test_first_correct_sets_interval_one():
    ease, interval, reps = srs.update(srs.DEFAULT_EASE, 0, 0, correct=True)
    assert interval == 1
    assert reps == 1
    assert ease > srs.DEFAULT_EASE  # a correct answer nudges ease up


def test_second_correct_sets_interval_six():
    _, interval, reps = srs.update(srs.DEFAULT_EASE, 1, 1, correct=True)
    assert interval == 6
    assert reps == 2


def test_third_correct_multiplies_by_ease():
    ease, interval, reps = srs.update(2.5, 6, 2, correct=True)
    assert interval == round(6 * 2.5)  # 15
    assert reps == 3


def test_wrong_answer_resets_and_lowers_ease():
    ease, interval, reps = srs.update(2.5, 15, 3, correct=False)
    assert interval == 1
    assert reps == 0
    assert ease < 2.5


def test_ease_never_below_floor():
    ease = 1.3
    for _ in range(10):
        ease, _, _ = srs.update(ease, 1, 0, correct=False)
    assert ease >= srs.MIN_EASE


def test_is_due():
    today = datetime.date(2026, 8, 9)
    assert srs.is_due("", today)  # brand new
    assert srs.is_due("2026-08-08", today)  # past
    assert srs.is_due("2026-08-09", today)  # today
    assert not srs.is_due("2026-08-10", today)  # future
