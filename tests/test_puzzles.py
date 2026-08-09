"""Puzzle generation from a review, and grading a solve."""

import datetime

import chess

from chess_coach import classify, motifs
from chess_coach import puzzles as P
from chess_coach.review import ReviewedMove


def _hung_queen_review():
    """A one-move 'review' where White hangs the queen with Qd5."""
    board = chess.Board("3r3k/8/8/8/8/8/8/3QK3 w - - 0 1")
    played = board.parse_san("Qd5")
    best = board.parse_san("Qd2")
    after = board.copy()
    after.push(played)
    refutation = after.parse_san("Rxd5")
    rm = ReviewedMove(
        ply=5, move=played, san="Qd5", mover_white=True,
        classification=classify.BLUNDER, cp_loss=800.0,
        eval_before=0.0, eval_after=-8.0,
        best_move=best, best_san="Qd2", best_line=[], explanation="",
        fen_before=board.fen(), refutation_move=refutation,
    )
    return board, rm


def test_generate_makes_a_puzzle_from_a_blunder():
    board, rm = _hung_queen_review()
    made = P.generate_from_review([rm], source="test", today=datetime.date(2026, 8, 9))
    assert len(made) == 1
    puzzle = made[0]
    assert puzzle.fen == board.fen()
    assert puzzle.solution_uci == board.parse_san("Qd2").uci()
    assert puzzle.color == "white"
    assert puzzle.due == "2026-08-09"
    assert motifs.HANGING in puzzle.motifs


def test_good_moves_do_not_become_puzzles():
    board = chess.Board()
    e4 = board.parse_san("e4")
    rm = ReviewedMove(
        1, e4, "e4", True, classify.BEST, 0.0, 0.2, 0.2, e4, "e4", [],
        fen_before=board.fen(), refutation_move=None,
    )
    assert P.generate_from_review([rm]) == []


def test_is_correct_accepts_exact_solution():
    _, rm = _hung_queen_review()
    puzzle = P.generate_from_review([rm])[0]
    assert P.is_correct(puzzle, puzzle.board.parse_san("Qd2")) is True


def test_is_correct_rejects_wrong_move_without_engine():
    _, rm = _hung_queen_review()
    puzzle = P.generate_from_review([rm])[0]
    # Playing the losing move again is not a solution.
    assert P.is_correct(puzzle, puzzle.board.parse_san("Qd5")) is False


def test_parse_move_reads_san_and_uci():
    board = chess.Board("3r3k/8/8/8/8/8/8/3QK3 w - - 0 1")
    assert P.parse_move(board, "Qd2") == board.parse_san("Qd2")
    assert P.parse_move(board, "d1d2") == board.parse_san("Qd2")
    assert P.parse_move(board, "nonsense") is None
