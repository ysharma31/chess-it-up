"""Plain-language explanations of mistakes."""

import chess

from chess_coach import tactics


def test_explains_a_hung_piece():
    # White to move plays Qd5??, a quiet move that parks the queen where the
    # black rook on d8 simply takes it. The refutation is Rxd5.
    before = chess.Board("3r3k/8/8/8/8/8/8/3QK3 w - - 0 1")
    played = before.parse_san("Qd5")
    after = before.copy()
    after.push(played)
    refutation = after.parse_san("Rxd5")

    text = tactics.explain(before, played, better_san="Qd2", refutation=refutation)
    assert "Rxd5" in text
    assert "queen" in text.lower()
    assert "winning" in text.lower()
    assert "Qd2" in text  # the better move is mentioned


def test_detects_a_fork():
    # White plays a harmless a3; Black answers Nd3+, forking the king on e1 and
    # the queen on f4.
    before = chess.Board("6k1/8/8/8/1n3Q2/8/P7/4K3 w - - 0 1")
    played = before.parse_san("a3")
    after = before.copy()
    after.push(played)
    refutation = after.parse_san("Nd3+")

    text = tactics.explain(before, played, better_san=None, refutation=refutation)
    assert "fork" in text.lower()
    assert "king" in text.lower()
    assert "queen" in text.lower()


def test_detects_checkmate_refutation():
    # White blunders into a back-rank mate. Black's reply is mate.
    # White king boxed on g1 behind f2/g2/h2, black rook lands on the back rank.
    before = chess.Board("6k1/5ppp/8/8/8/8/r4PPP/6K1 w - - 0 1")
    played = before.parse_san("Kh1")  # a legal but doomed move; Ra1 is mate
    after = before.copy()
    after.push(played)
    refutation = after.parse_san("Ra1#")

    text = tactics.explain(before, played, better_san=None, refutation=refutation)
    assert "checkmate" in text.lower()
