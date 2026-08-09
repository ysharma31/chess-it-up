"""The human evaluation decomposition."""

import chess

from chess_coach.evaluation import (
    developed_minors,
    doubled_pawns,
    evaluate_position,
    isolated_pawns,
    king_pawn_shield,
    material_count,
    passed_pawns,
    space,
)


def test_material_even_at_start():
    white, black, diff = material_count(chess.Board())
    assert white == black
    assert diff == 0


def test_material_difference_when_up_a_queen():
    # White has an extra queen (black has none besides king+rook setup here).
    board = chess.Board("4k3/8/8/8/8/8/8/3QK3 w - - 0 1")
    _, _, diff = material_count(board)
    assert diff == 9


def test_doubled_pawns_detected():
    # White pawns doubled on the e-file (e2 and e4).
    board = chess.Board("4k3/8/8/8/4P3/8/4P3/4K3 w - - 0 1")
    assert doubled_pawns(board, chess.WHITE) == 1


def test_isolated_pawn_detected():
    # A lone white pawn on a4 with no neighbours on the b-file.
    board = chess.Board("4k3/8/8/8/P7/8/8/4K3 w - - 0 1")
    assert isolated_pawns(board, chess.WHITE) == 1


def test_connected_pawns_not_isolated():
    board = chess.Board("4k3/8/8/8/PP6/8/8/4K3 w - - 0 1")
    assert isolated_pawns(board, chess.WHITE) == 0


def test_passed_pawn_detected():
    # White pawn on e6 with no black pawns anywhere ahead: passed.
    board = chess.Board("4k3/8/4P3/8/8/8/8/4K3 w - - 0 1")
    assert passed_pawns(board, chess.WHITE) == 1


def test_pawn_is_not_passed_when_blocked():
    # White pawn e5 with a black pawn on d6 that can capture/stop it: not passed.
    board = chess.Board("4k3/8/3p4/4P3/8/8/8/4K3 w - - 0 1")
    assert passed_pawns(board, chess.WHITE) == 0


def test_developed_minors_at_start_is_zero():
    assert developed_minors(chess.Board(), chess.WHITE) == 0


def test_developed_minors_counts_moved_pieces():
    # After 1.Nf3 the knight has left g1.
    board = chess.Board()
    board.push_san("Nf3")
    assert developed_minors(board, chess.WHITE) == 1


def test_king_shield_after_castling():
    # A freshly castled king on g1 with pawns on f2/g2/h2 has a full shield of 3.
    board = chess.Board("4k3/8/8/8/8/8/5PPP/6K1 w - - 0 1")
    assert king_pawn_shield(board, chess.WHITE) == 3


def test_evaluate_position_returns_summary_lines():
    report = evaluate_position(chess.Board())
    lines = report.summary_lines()
    assert any("Material" in line for line in lines)
    assert len(lines) == 5  # material, king safety, activity, structure, space


def test_space_is_symmetric_at_start():
    board = chess.Board()
    assert space(board, chess.WHITE) == space(board, chess.BLACK)
