"""Grading the user's answers."""

import chess

from chess_coach.forcing import scan_forcing_moves
from chess_coach.grading import (
    candidate_contains_best,
    eval_error,
    grade_forcing_recall,
    normalize_move_text,
    parse_candidate_moves,
    parse_eval_guess,
)


def test_normalize_strips_marks():
    assert normalize_move_text("Qxf7#") == normalize_move_text("Qf7")
    assert normalize_move_text("Nxe5+") == "ne5"
    assert normalize_move_text("O-O") == "oo"
    assert normalize_move_text("0-0-0") == "ooo"


def test_recall_matches_san_leniently():
    # Position where White has a clean capture Rxe5.
    board = chess.Board("4k3/8/8/4p3/8/8/8/4R1K1 w - - 0 1")
    scan = scan_forcing_moves(board)
    # User types it in lower case, with the capture 'x' — should still match.
    result = grade_forcing_recall(board, "rxe5", scan.all_moves())
    assert len(result.found) == 1
    assert result.missed == []


def test_recall_reports_missed_moves():
    board = chess.Board(
        "r1bqkbnr/pppp1ppp/2n5/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 2 3"
    )
    scan = scan_forcing_moves(board)
    # User only mentions one capture; they should have several missed items.
    result = grade_forcing_recall(board, "Qxf7", scan.all_moves())
    assert len(result.found) >= 1
    assert len(result.missed) >= 1


def test_recall_flags_spurious_answers():
    board = chess.Board()  # no forcing moves at all
    scan = scan_forcing_moves(board)
    result = grade_forcing_recall(board, "Qh5", scan.all_moves())
    assert "qh5" in result.spurious


def test_parse_eval_guess():
    assert parse_eval_guess("+1.5") == 1.5
    assert parse_eval_guess("-2") == -2.0
    assert parse_eval_guess("0") == 0.0
    assert parse_eval_guess("mate") == 100.0
    assert parse_eval_guess("garbage") is None


def test_eval_error():
    assert eval_error(1.5, 1.0) == 0.5
    assert eval_error(-2.0, 1.0) == 3.0


def test_candidate_contains_best():
    board = chess.Board()
    best = board.parse_san("e4")
    assert candidate_contains_best(board, "d4, e4, Nf3", best) is True
    assert candidate_contains_best(board, "d4, c4", best) is False


def test_parse_candidate_moves_accepts_san_and_uci():
    board = chess.Board()
    moves = parse_candidate_moves(board, "e4, g1f3, garbage, d4")
    sans = {board.san(m) for m in moves}
    assert sans == {"e4", "Nf3", "d4"}
