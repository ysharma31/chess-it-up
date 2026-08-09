"""Stockfish wrapper. These tests skip cleanly if no engine is installed."""

import chess
import pytest

from chess_coach.engine import Assessment, Engine, find_stockfish


def test_as_text_formats():
    assert Assessment(1.4, None, None, None, []).as_text() == "+1.40"
    assert Assessment(100.0, 3, None, None, []).as_text() == "mate in 3 for White"
    assert Assessment(-100.0, -2, None, None, []).as_text() == "mate in 2 for Black"
    # A position that is already checkmate is reported as a result, not "mate in 0".
    assert Assessment(100.0, 0, None, None, []).as_text() == "checkmate — White wins"
    assert Assessment(-100.0, 0, None, None, []).as_text() == "checkmate — Black wins"

stockfish = find_stockfish()
needs_engine = pytest.mark.skipif(stockfish is None, reason="Stockfish not installed")


def test_find_stockfish_returns_path_or_none():
    # Either a real path string, or None — never a crash.
    assert stockfish is None or isinstance(stockfish, str)


@needs_engine
def test_assess_starting_position():
    with Engine(depth=10) as eng:
        a = eng.assess(chess.Board())
    assert a.best_move is not None
    assert a.best_san is not None
    # The start is roughly balanced; sanity-bound the eval.
    assert -2.0 < a.pawns < 2.0
    assert a.mate is None


@needs_engine
def test_assess_finds_forced_mate():
    # White to move, mate in one (Qxf7#) in the Scholar's-mate position.
    board = chess.Board(
        "r1bqkbnr/pppp1ppp/2n5/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 2 3"
    )
    with Engine(depth=10) as eng:
        a = eng.assess(board)
    assert a.mate is not None and a.mate > 0
    assert a.best_san == "Qxf7#"


@needs_engine
def test_evaluate_after_move():
    board = chess.Board()
    with Engine(depth=10) as eng:
        a = eng.evaluate_after(board, board.parse_san("e4"))
    assert isinstance(a.pawns, float)


def test_unavailable_raises_when_no_binary(monkeypatch):
    # Force discovery to fail and confirm we raise the catchable error.
    monkeypatch.setattr("chess_coach.engine.find_stockfish", lambda: None)
    with pytest.raises(Engine.Unavailable):
        Engine(path=None)
