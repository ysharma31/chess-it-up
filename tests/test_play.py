"""The play loop (with a stand-in engine, so no Stockfish needed)."""

import chess

from chess_coach import play
from chess_coach.engine import elo_to_skill


class DummyEngine:
    """A minimal engine stand-in: configures nothing, plays the first legal move."""

    strength_desc = "dummy"

    def configure_strength(self, elo=None, skill=None):
        pass

    def play_move(self, board, movetime=0.1):
        return next(iter(board.legal_moves))


def test_parse_move_accepts_san_and_uci():
    board = chess.Board()
    assert play._parse_move(board, "e4") == board.parse_san("e4")
    assert play._parse_move(board, "g1f3") == board.parse_san("Nf3")
    assert play._parse_move(board, "not a move") is None


def test_elo_to_skill_monotonic_and_bounded():
    assert elo_to_skill(600) == 0
    assert elo_to_skill(800) == 0
    assert elo_to_skill(3000) <= 8
    assert elo_to_skill(1000) >= elo_to_skill(800)


def test_resign_ends_the_game():
    # The human resigns on move one; result should favour the engine.
    answers = iter(["resign"])
    game = play.play_game(
        DummyEngine(), human_white=True, elo=900,
        ask=lambda _: next(answers), say=lambda *_: None,
    )
    assert game.result == "0-1"
    assert game.moves == []


def test_a_short_scripted_game_records_moves():
    # Human plays e4, then resigns after the engine replies.
    answers = iter(["e4", "resign"])
    game = play.play_game(
        DummyEngine(), human_white=True, elo=900,
        ask=lambda _: next(answers), say=lambda *_: None,
    )
    # e4 (human) + one engine reply were recorded before the resignation.
    assert len(game.moves) == 2
    assert game.start_board.san(game.moves[0]) == "e4"


def test_takeback_undoes_to_your_turn():
    board = chess.Board()
    moves = []
    for san in ("e4", "e5", "Nf3"):
        # play through a few half-moves manually
        mv = board.parse_san(san)
        board.push(mv)
        moves.append(mv)
    # It is now Black to move; a human playing White takes back to their turn.
    play._takeback(board, moves, chess.WHITE, say=lambda *_: None)
    assert board.turn == chess.WHITE
    assert len(moves) == len(board.move_stack)


def test_outcome_text_reports_checkmate():
    # Fool's mate: 1. f3 e5 2. g4 Qh4#
    board = chess.Board()
    for san in ("f3", "e5", "g4", "Qh4#"):
        board.push_san(san)
    assert "Checkmate" in play._outcome_text(board)
    assert "Black wins" in play._outcome_text(board)
