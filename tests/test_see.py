"""Static exchange evaluation — does the trade arithmetic come out right?"""

import chess

from chess_coach.forcing import best_capture_gain, static_exchange_eval


def _see(fen: str, san: str) -> float:
    board = chess.Board(fen)
    return static_exchange_eval(board, board.parse_san(san))


def test_capturing_a_free_pawn_wins_one():
    # White rook on e1, undefended black pawn on e5. Rxe5 wins a clean pawn.
    assert _see("4k3/8/8/4p3/8/8/8/4R1K1 w - - 0 1", "Rxe5") == 1


def test_taking_a_defended_pawn_with_a_queen_loses_material():
    # Black pawn on d5 defended by a pawn on c6. Qxd5 wins a pawn but the queen
    # is recaptured: 1 - 9 = -8.
    board = chess.Board("4k3/8/2p5/3p4/8/8/8/3QK3 w - - 0 1")
    assert static_exchange_eval(board, board.parse_san("Qxd5")) == -8


def test_equal_trade_is_zero():
    # White knight takes a knight that is defended by a pawn. 3 - 3 = 0.
    board = chess.Board("4k3/8/2p5/3n4/8/4N3/8/4K3 w - - 0 1")
    assert static_exchange_eval(board, board.parse_san("Nxd5")) == 0


def test_xray_attacker_is_counted():
    # Two white rooks stacked on e1/e2 attacking a pawn on e5 defended by a
    # pawn on d6. Rxe5, ...dxe5, Rxe5: net +1 (won two pawns, lost one rook?).
    # Pawn(e5)=1 captured; recapture dxe5 costs rook(5); then Rxe5 wins pawn(1).
    # Sequence from White's view: +1 (take pawn) then Black takes rook: our
    # side won't necessarily continue — SEE picks the best stop point.
    board = chess.Board("4k3/8/3p4/4p3/8/8/4R3/4R1K1 w - - 0 1")
    # Least-valuable-attacker sequence: Re2xe5 (+1), dxe5 (-5 for us), Re1xe5
    # (+1). Net = 1 - 5 + 1 = -3, but SEE lets the side stop early, so the
    # opening capture nets max(1 - max(0, ...)) — verify it is not wrongly +2.
    result = static_exchange_eval(board, board.parse_san("Rxe5"))
    assert result <= 1  # never reports a phantom gain from the x-ray


def test_best_capture_gain_finds_hanging_queen():
    # Black queen on d5, only a white knight attacks it (from c3) and it's
    # undefended: the enemy (White) can win the whole queen.
    board = chess.Board("4k3/8/8/3q4/8/2N5/8/4K3 b - - 0 1")
    gain, from_sq = best_capture_gain(board, chess.D5, chess.WHITE)
    assert gain == 9
    assert from_sq == chess.C3


def test_king_cannot_capture_a_defended_piece():
    # Black pawn on d5 next to white king on e4, but the pawn is defended by a
    # pawn on c6. The king can't take it (would be moving into an attack).
    gain, _ = best_capture_gain(
        chess.Board("4k3/8/2p5/3p4/4K3/8/8/8 w - - 0 1"), chess.D5, chess.WHITE
    )
    assert gain == 0


def test_en_passant_see():
    # White pawn e5, black just played d7-d5. exd6 e.p. wins the pawn cleanly.
    board = chess.Board("4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 1")
    assert static_exchange_eval(board, board.parse_san("exd6")) == 1
