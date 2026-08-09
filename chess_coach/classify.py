"""Classify a move by how much it cost you, in centipawns.

After a game, we replay it and ask of each move: how far is it from the best
move available? The gap, measured in centipawns (hundredths of a pawn) by
Stockfish, is the "centipawn loss". Small loss = a fine move; large loss = you
threw something away. The labels below are the familiar review vocabulary.

The thresholds are deliberately simple and are the standard sort used by online
review tools. They are not sacred — they are a teaching scale, not a rating.
"""

from __future__ import annotations

# The five labels, best to worst.
BEST = "best"
GOOD = "good"
INACCURACY = "inaccuracy"
MISTAKE = "mistake"
BLUNDER = "blunder"

ORDER = [BEST, GOOD, INACCURACY, MISTAKE, BLUNDER]

# Punctuation marks and PGN "NAG" codes reviewers expect. Best/good get none.
SYMBOL = {BEST: "", GOOD: "", INACCURACY: "?!", MISTAKE: "?", BLUNDER: "??"}
NAG = {INACCURACY: 6, MISTAKE: 2, BLUNDER: 4}  # $6 dubious, $2 mistake, $4 blunder

# Evaluations are clamped to +/-10 pawns before measuring loss, so that walking
# into (or out of) a forced mate produces a large-but-sane number instead of a
# five-figure swing that would dwarf everything else.
EVAL_CLAMP = 10.0


def _clamp(pawns: float) -> float:
    return max(-EVAL_CLAMP, min(EVAL_CLAMP, pawns))


def centipawn_loss(eval_before: float, eval_after: float, mover_is_white: bool) -> float:
    """How much the move gave away, in centipawns (never negative).

    Both evals are from White's point of view, in pawns. `eval_before` is the
    position's value with best play; `eval_after` is its value after the move
    actually played. For White a good move keeps the eval up; for Black a good
    move keeps it down. We flip the sign for Black so "loss" always means
    "worse for the player who moved".
    """
    before = _clamp(eval_before)
    after = _clamp(eval_after)
    drop = (before - after) if mover_is_white else (after - before)
    return max(0.0, drop) * 100.0


def classify(cp_loss: float, played_the_best_move: bool = False) -> str:
    """Turn a centipawn loss into a label.

    Playing the exact engine move is always "best", even if the arithmetic
    rounds to a point or two of loss.
    """
    if played_the_best_move or cp_loss < 20:
        return BEST
    if cp_loss < 75:
        return GOOD
    if cp_loss < 150:
        return INACCURACY
    if cp_loss < 300:
        return MISTAKE
    return BLUNDER


def is_serious(label: str) -> bool:
    """Mistakes and blunders are the ones worth explaining in words."""
    return label in (MISTAKE, BLUNDER)
