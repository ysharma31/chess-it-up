"""Turn your own blunders into puzzles.

The brief: "any position where the evaluation swung sharply becomes a puzzle."
So after reviewing a game, every mistake and blunder becomes a puzzle set at the
position *you* faced, with *you* to move, and the solution is the move you
should have found. That drills the exact decision you got wrong — not a random
tactic from a book, but your own recurring leak.

Each puzzle also carries motif tags (fork, pin, …) so accuracy can be tracked
per motif, and a little spaced-repetition state so it comes back around.

A puzzle is a plain dataclass that serialises to JSON — no engine or board
objects stored, just strings and numbers — so a deck is a small, portable file.
"""

from __future__ import annotations

import datetime
import hashlib
from dataclasses import asdict, dataclass, field

import chess

from . import motifs as motif_mod
from . import srs
from .classify import is_serious
from .review import ReviewedMove


@dataclass
class Puzzle:
    """One position to solve, plus its motifs and spaced-repetition state."""

    id: str
    fen: str  # the position to solve (the side to move is the one who erred)
    solution_uci: str  # the move you should have played
    solution_san: str
    motifs: list[str]
    swing_cp: float  # how much the original blunder cost, in centipawns
    source: str  # where it came from, e.g. "game 2026-08-09, move 14"
    color: str  # "white" or "black" — whose move / whose mistake

    # Spaced-repetition state (see srs.py).
    ease: float = srs.DEFAULT_EASE
    interval: int = 0
    reps: int = 0
    due: str = ""  # ISO date; empty = brand new, due immediately
    attempts: int = 0
    correct: int = 0

    @property
    def board(self) -> chess.Board:
        return chess.Board(self.fen)

    @property
    def solution(self) -> chess.Move:
        return chess.Move.from_uci(self.solution_uci)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Puzzle":
        return cls(**data)


def _puzzle_id(fen: str, solution_uci: str) -> str:
    """A short, stable id so the same blunder isn't added to a deck twice."""
    digest = hashlib.sha1(f"{fen}|{solution_uci}".encode()).hexdigest()
    return digest[:12]


def generate_from_review(
    reviewed: list[ReviewedMove],
    source: str = "game",
    today: datetime.date | None = None,
) -> list[Puzzle]:
    """Make a puzzle from every mistake and blunder in a reviewed game."""
    today = today or datetime.date.today()
    puzzles: list[Puzzle] = []
    for rm in reviewed:
        if not is_serious(rm.classification):
            continue
        if rm.best_move is None or not rm.fen_before or rm.best_san is None:
            continue  # nothing concrete to ask for

        before_board = chess.Board(rm.fen_before)
        tags = motif_mod.detect_motifs(before_board, rm.move, rm.refutation_move)
        move_number = (rm.ply + 1) // 2

        puzzles.append(
            Puzzle(
                id=_puzzle_id(rm.fen_before, rm.best_move.uci()),
                fen=rm.fen_before,
                solution_uci=rm.best_move.uci(),
                solution_san=rm.best_san,
                motifs=tags,
                swing_cp=rm.cp_loss,
                source=f"{source}, move {move_number}",
                color="white" if rm.mover_white else "black",
                due=today.isoformat(),
            )
        )
    return puzzles


# ---------------------------------------------------------------------------
# Grading a solve
# ---------------------------------------------------------------------------

def parse_move(board: chess.Board, text: str) -> chess.Move | None:
    """Read a user's answer as a legal move (SAN or UCI), or None."""
    text = text.strip()
    for parser in (board.parse_san, lambda t: board.parse_uci(t.lower())):
        try:
            move = parser(text)
        except (ValueError, chess.InvalidMoveError, chess.IllegalMoveError,
                chess.AmbiguousMoveError):
            continue
        if move in board.legal_moves:
            return move
    return None


def is_correct(
    puzzle: Puzzle,
    user_move: chess.Move,
    engine=None,
    tolerance_cp: float = 50.0,
) -> bool:
    """Is the user's move an acceptable solution?

    The stored solution always counts. If an engine is supplied, a *different*
    move also counts when it's nearly as good (within `tolerance_cp` centipawns
    of the best move) — because many positions have more than one good answer,
    and a trainer that rejects them is just annoying.
    """
    if user_move.uci() == puzzle.solution_uci:
        return True
    if engine is None:
        return False

    from . import classify  # local import to avoid a cycle at module load

    board = puzzle.board
    before = engine.assess(board)
    after = engine.evaluate_after(board, user_move)
    loss = classify.centipawn_loss(before.pawns, after.pawns, board.turn == chess.WHITE)
    return loss <= tolerance_cp
