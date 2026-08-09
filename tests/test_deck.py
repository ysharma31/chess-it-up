"""The puzzle deck: dedup, scheduling, per-motif accuracy, persistence."""

import datetime

from chess_coach import motifs
from chess_coach.deck import Deck
from chess_coach.puzzles import Puzzle


def _puzzle(pid="a", motif=motifs.FORK, swing=300.0, due=""):
    return Puzzle(
        id=pid,
        fen="3r3k/8/8/8/8/8/8/3QK3 w - - 0 1",
        solution_uci="d1d2",
        solution_san="Qd2",
        motifs=[motif],
        swing_cp=swing,
        source="test",
        color="white",
        due=due,
    )


def test_add_dedupes_by_id():
    deck = Deck()
    assert deck.add(_puzzle("a")) is True
    assert deck.add(_puzzle("a")) is False  # same id, ignored
    assert len(deck.puzzles) == 1


def test_due_sorts_by_swing():
    deck = Deck()
    deck.add(_puzzle("small", swing=100))
    deck.add(_puzzle("big", swing=900))
    due = deck.due(datetime.date(2026, 8, 9))
    assert [p.id for p in due] == ["big", "small"]


def test_future_puzzles_are_not_due():
    deck = Deck()
    deck.add(_puzzle("later", due="2999-01-01"))
    assert deck.due(datetime.date(2026, 8, 9)) == []


def test_record_attempt_updates_schedule_and_motif_stats():
    deck = Deck()
    puzzle = _puzzle("a", motif=motifs.PIN)
    deck.add(puzzle)
    today = datetime.date(2026, 8, 9)

    deck.record_attempt(puzzle, correct=True, today=today)
    assert puzzle.attempts == 1
    assert puzzle.correct == 1
    assert puzzle.interval == 1
    assert puzzle.due == "2026-08-10"  # one day out

    acc = deck.motif_accuracy()
    assert acc[motifs.PIN] == (1, 1, 100.0)


def test_motif_accuracy_tracks_weakness():
    deck = Deck()
    fork_p = _puzzle("f", motif=motifs.FORK)
    pin_p = _puzzle("p", motif=motifs.PIN)
    deck.add(fork_p)
    deck.add(pin_p)
    deck.record_attempt(fork_p, correct=True)
    deck.record_attempt(pin_p, correct=False)

    acc = deck.motif_accuracy()
    assert acc[motifs.FORK][2] == 100.0
    assert acc[motifs.PIN][2] == 0.0


def test_save_and_load_roundtrip(tmp_path):
    deck = Deck()
    puzzle = _puzzle("a", motif=motifs.SKEWER)
    deck.add(puzzle)
    deck.record_attempt(puzzle, correct=True)

    path = str(tmp_path / "sub" / "deck.json")  # also exercises directory creation
    deck.save(path)

    loaded = Deck.load(path)
    assert len(loaded.puzzles) == 1
    assert loaded.puzzles[0].id == "a"
    assert loaded.puzzles[0].motifs == [motifs.SKEWER]
    assert loaded.motif_stats[motifs.SKEWER]["correct"] == 1


def test_load_missing_file_gives_empty_deck(tmp_path):
    deck = Deck.load(str(tmp_path / "nope.json"))
    assert deck.puzzles == []
