"""Blindfold mode: what's under attack, from memory."""

import chess

from chess_coach import blindfold as B


def test_attacked_pieces_finds_the_target():
    # Black rook on h8 attacks the white bishop on h1 down the open h-file.
    board = chess.Board("4k2r/8/8/8/8/8/8/4K2B w - - 0 1")
    attacked = B.attacked_pieces(board, chess.WHITE)
    assert attacked == {chess.H1}


def test_parse_squares_extracts_coordinates():
    assert B.parse_squares("e5, c4 and h1!") == {"e5", "c4", "h1"}
    assert B.parse_squares("nothing here") == set()


def test_run_blindfold_grades_a_correct_answer():
    board = chess.Board("4k2r/8/8/8/8/8/8/4K2B w - - 0 1")
    slept = []
    result = B.run_blindfold(
        board,
        ask=lambda _: "h1",
        say=lambda *_: None,
        sleep=slept.append,  # record instead of actually sleeping
        reveal_seconds=10,
    )
    assert result.found == {"h1"}
    assert result.missed == set()
    assert result.all_correct
    assert slept == [10]  # the reveal delay was used, not skipped


def test_run_blindfold_reports_a_miss():
    board = chess.Board("4k2r/8/8/8/8/8/8/4K2B w - - 0 1")
    result = B.run_blindfold(
        board, ask=lambda _: "", say=lambda *_: None, sleep=lambda _: None,
    )
    assert result.missed == {"h1"}
    assert not result.all_correct
