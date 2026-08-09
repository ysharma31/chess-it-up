"""Spaced repetition: show a pattern again just before you'd forget it.

This is a compact version of the SM-2 algorithm (the one behind Anki). Each
puzzle carries three numbers — an *ease* factor, the current *interval* in days,
and how many times in a row you've got it right (*reps*). Get a puzzle right and
its interval stretches (you'll see it later); get it wrong and it snaps back to
tomorrow. The effect: your weak patterns come round often, your solid ones fade
into the background.

Everything here is pure arithmetic on those three numbers, so it's trivial to
test and has no idea what a chess puzzle is.
"""

from __future__ import annotations

import datetime

DEFAULT_EASE = 2.5
MIN_EASE = 1.3


def _ease_delta(quality: int) -> float:
    """SM-2's ease adjustment for an answer of the given quality (0-5)."""
    return 0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)


def update(ease: float, interval: int, reps: int, correct: bool) -> tuple[float, int, int]:
    """Return the new (ease, interval, reps) after grading an attempt.

    We use two answer qualities: a confident 5 for correct, a failing 2 for
    wrong. A wrong answer resets the schedule to tomorrow; a right one grows the
    interval (1 day, then 6, then interval * ease).
    """
    quality = 5 if correct else 2
    new_ease = max(MIN_EASE, ease + _ease_delta(quality))

    if not correct:
        return new_ease, 1, 0

    if reps == 0:
        new_interval = 1
    elif reps == 1:
        new_interval = 6
    else:
        new_interval = max(1, round(interval * ease))
    return new_ease, new_interval, reps + 1


def due_date(today: datetime.date, interval: int) -> datetime.date:
    return today + datetime.timedelta(days=interval)


def is_due(due_iso: str, today: datetime.date) -> bool:
    """A puzzle with no due date (brand new) or a due date on/before today."""
    if not due_iso:
        return True
    return datetime.date.fromisoformat(due_iso) <= today
