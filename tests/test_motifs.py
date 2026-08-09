"""Motif detection: naming the tactic in a mistake."""

import chess

from chess_coach import motifs as M


def _motifs(fen, played, refutation):
    board = chess.Board(fen)
    pm = board.parse_san(played)
    after = board.copy()
    after.push(pm)
    rm = after.parse_san(refutation) if refutation else None
    return M.detect_motifs(board, pm, rm)


def test_fork_detected():
    # a3 then Nd3+ forks the king on e1 and the queen on f4.
    tags = _motifs("6k1/8/8/8/1n3Q2/8/P7/4K3 w - - 0 1", "a3", "Nd3+")
    assert M.FORK in tags


def test_back_rank_mate_detected():
    # Kh1 then Ra1# is mate on White's back rank.
    tags = _motifs("6k1/5ppp/8/8/8/8/r4PPP/6K1 w - - 0 1", "Kh1", "Ra1#")
    assert M.BACK_RANK in tags


def test_hanging_piece_detected():
    # Qd5 hangs the queen to the rook on d8.
    tags = _motifs("3r3k/8/8/8/8/8/8/3QK3 w - - 0 1", "Qd5", "Rxd5")
    assert M.HANGING in tags


def test_skewer_detected():
    # Re8+ checks the king on e4 with the rook on e2 behind it.
    tags = _motifs("r6k/8/8/8/4K3/8/P3R3/8 w - - 0 1", "a3", "Re8+")
    assert M.SKEWER in tags


def test_discovered_check_detected():
    # The knight leaves the e-file, and the rook on e8 delivers a discovered check.
    tags = _motifs("4r1k1/8/8/8/4n3/8/P7/4K3 w - - 0 1", "a3", "Nc3")
    assert M.DISCOVERED in tags


def test_pin_detected():
    # Bb4 pins the knight on c3 to the king on e1.
    tags = _motifs("4kb2/8/8/8/8/2N5/P7/4K3 w - - 0 1", "a3", "Bb4")
    assert M.PIN in tags


def test_quiet_position_has_no_tactic_motifs():
    # A dead-equal king-and-pawn position: nothing tactical to tag.
    board = chess.Board("8/8/4k3/8/8/4K3/8/8 w - - 0 1")
    tags = M.detect_motifs(board, board.parse_san("Kd3"), None)
    assert M.FORK not in tags and M.PIN not in tags and M.SKEWER not in tags
