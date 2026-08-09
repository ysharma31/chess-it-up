"""Game review: summary, annotated PGN, and (engine-backed) classification."""

import io

import chess
import chess.pgn
import pytest

from chess_coach import classify, review
from chess_coach.engine import Engine, find_stockfish

needs_engine = pytest.mark.skipif(
    find_stockfish() is None, reason="Stockfish not installed"
)


def _rm(ply, san, white, label, cp, expl=""):
    """A synthetic ReviewedMove (no engine needed) for the pure tests."""
    return review.ReviewedMove(
        ply=ply, move=chess.Move.null(), san=san, mover_white=white,
        classification=label, cp_loss=cp, eval_before=0.0, eval_after=0.0,
        best_move=None, best_san="Xx", best_line=[], explanation=expl,
    )


def test_summarize_counts_per_side():
    reviewed = [
        _rm(1, "e4", True, classify.BEST, 0),
        _rm(2, "e5", False, classify.BLUNDER, 400),
        _rm(3, "Nf3", True, classify.GOOD, 30),
        _rm(4, "Nc6", False, classify.MISTAKE, 200),
    ]
    summary = review.summarize(reviewed)
    assert summary.counts["White"][classify.BEST] == 1
    assert summary.counts["Black"][classify.BLUNDER] == 1
    assert summary.counts["Black"][classify.MISTAKE] == 1


def test_blunders_and_mistakes_sorted_worst_first():
    reviewed = [
        _rm(1, "a", True, classify.MISTAKE, 200),
        _rm(2, "b", False, classify.BLUNDER, 600),
        _rm(3, "c", True, classify.GOOD, 10),
    ]
    serious = review.blunders_and_mistakes(reviewed)
    assert [rm.san for rm in serious] == ["b", "a"]  # 600 before 200, 'c' excluded


def test_annotated_pgn_roundtrips_with_nags_and_comments():
    # Two real moves so the PGN is playable; mark the second a blunder.
    board = chess.Board()
    e4 = board.parse_san("e4")
    reviewed = [
        review.ReviewedMove(1, e4, "e4", True, classify.BEST, 0, 0.2, 0.2, e4, "e4", []),
    ]
    b2 = board.copy()
    b2.push(e4)
    f6 = b2.parse_san("f6")
    reviewed.append(
        review.ReviewedMove(
            2, f6, "f6", False, classify.BLUNDER, 350, 0.2, 3.5, None, "e5", [],
            explanation="it weakens your king.",
        )
    )

    game = review.to_annotated_pgn(chess.Board(), reviewed, white="You", black="SF")
    exported = str(game)

    # Re-parse to confirm it's valid PGN with the right moves.
    reparsed = chess.pgn.read_game(io.StringIO(exported))
    assert [m.uci() for m in reparsed.mainline_moves()] == [e4.uci(), f6.uci()]
    assert "blunder" in exported.lower()
    assert game.headers["White"] == "You"


def test_format_report_mentions_blunders():
    reviewed = [
        _rm(1, "e4", True, classify.BEST, 0),
        _rm(2, "Qh4", False, classify.BLUNDER, 500, expl="it hangs the queen."),
    ]
    text = "\n".join(review.format_report(reviewed))
    assert "blunder" in text.lower()
    assert "hangs the queen" in text


@needs_engine
def test_review_flags_a_real_blunder():
    # 1. e4 e5 2. Qh5 Ke7?? — Black's king walk is a serious error.
    board = chess.Board()
    moves = []
    for san in ("e4", "e5", "Qh5", "Ke7"):
        move = board.parse_san(san)
        moves.append(move)
        board.push(move)
    with Engine(depth=12) as eng:
        reviewed = review.review_moves(chess.Board(), moves, eng)
    ke7 = reviewed[-1]
    assert ke7.san == "Ke7"
    assert classify.is_serious(ke7.classification)
    assert ke7.explanation  # a non-empty explanation was produced
