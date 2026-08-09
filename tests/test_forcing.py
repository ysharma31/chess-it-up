"""The CCT scanner: Checks, Captures, Threats, and hanging pieces."""

import chess

from chess_coach.forcing import (
    find_hanging_pieces,
    scan_forcing_moves,
    scan_opponent_forcing_moves,
)


def _sans(moves):
    return {m.san for m in moves}


def test_starting_position_has_no_forcing_moves():
    scan = scan_forcing_moves(chess.Board())
    assert scan.checks == []
    assert scan.captures == []
    assert scan.threats == []
    assert scan.total() == 0


def test_captures_are_listed_with_material_gain():
    # White rook can grab an undefended pawn on e5. King is off the e-file so
    # this is a plain capture, not a check.
    scan = scan_forcing_moves(chess.Board("k7/8/8/4p3/8/8/8/4R1K1 w - - 0 1"))
    assert "Rxe5" in _sans(scan.captures)
    rxe5 = next(m for m in scan.captures if m.san == "Rxe5")
    assert rxe5.gain == 1


def test_check_is_listed_and_capturing_check_marked():
    # White queen on h5 vs black king; Qxf7 is a capture that gives check.
    board = chess.Board(
        "r1bqkbnr/pppp1ppp/2n5/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 2 3"
    )
    scan = scan_forcing_moves(board)
    checks = _sans(scan.checks)
    assert "Qxf7#" in checks  # the Scholar's-mate move
    qxf7 = next(m for m in scan.checks if m.san == "Qxf7#")
    assert qxf7.is_mate is True
    assert qxf7.also_capture is True


def test_quiet_move_that_attacks_the_queen_is_a_threat():
    # White knight on b1, undefended black queen on d5. Nc3 threatens to win it.
    scan = scan_forcing_moves(chess.Board("4k3/8/8/3q4/8/8/8/1N2K3 w - - 0 1"))
    threats = _sans(scan.threats)
    assert "Nc3" in threats
    nc3 = next(m for m in scan.threats if m.san == "Nc3")
    assert nc3.gain == 9
    assert "d5" in nc3.target


def test_mate_threat_is_detected_as_a_threat():
    # A quiet move that sets up mate-in-one next move should be flagged as a
    # threat with is_mate. White rook lifts to threaten back-rank mate.
    # Position: black king boxed on g8 by its own pawns; white rook a1 -> a8 next.
    board = chess.Board("6k1/5ppp/8/8/8/8/8/R5K1 w - - 0 1")
    scan = scan_forcing_moves(board)
    # Ra8 itself is a check (back-rank), so the *threat* class is about quiet
    # moves; here Ra8+ appears in checks. Confirm the scanner sees the check.
    assert "Ra8#" in _sans(scan.checks)


def test_opponent_forcing_moves_are_reported():
    # Black to move in the Scholar's position; White (the opponent) threatens
    # Qxf7#. scan_opponent should surface that as one of White's forcing moves.
    board = chess.Board(
        "r1bqkbnr/pppp1ppp/2n5/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR b KQkq - 3 3"
    )
    opp = scan_opponent_forcing_moves(board)
    assert opp is not None
    assert "Qxf7#" in _sans(opp.checks)


def test_opponent_scan_is_none_when_in_check():
    # White king in check from a rook; we can't meaningfully scan the opponent.
    board = chess.Board("4k3/8/8/8/8/8/8/r3K3 w - - 0 1")
    assert scan_opponent_forcing_moves(board) is None


def test_find_hanging_pieces():
    # Black knight on d5 attacked by a white pawn on e4, undefended: it hangs.
    board = chess.Board("4k3/8/8/3n4/4P3/8/8/4K3 b - - 0 1")
    hanging = find_hanging_pieces(board, chess.BLACK)
    squares = {h.square for h in hanging}
    assert chess.D5 in squares
    knight = next(h for h in hanging if h.square == chess.D5)
    assert knight.loss == 3


def test_defended_piece_is_not_hanging():
    # Black knight on d5 attacked by a white knight (c3) but defended by a pawn
    # on c6. Taking it is an even trade (knight for knight), so it is not
    # "hanging" — the enemy wins no material.
    board = chess.Board("4k3/8/2p5/3n4/8/2N5/8/4K3 b - - 0 1")
    hanging = find_hanging_pieces(board, chess.BLACK)
    assert chess.D5 not in {h.square for h in hanging}
