"""Grading: compare what you *said* to what was *true*.

The whole point of this trainer is that it never shows the answer before you
commit to yours. These functions do the comparing — matching your typed answers
against the real forcing moves, and scoring your evaluation guess against the
engine — with matching lenient enough that a beginner typing "Nxe5" or "nxe5"
or even the raw "g1f3" all count.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import chess

from .forcing import ForcingMove


def normalize_move_text(text: str) -> str:
    """Reduce a move string to a comparable core.

    Drops check/mate/capture marks and annotations so 'Qxf7#' , 'Qf7',
    'qxf7', and 'Q f7' all collapse to the same token 'qf7'. Castling is
    normalised to 'oo' / 'ooo'.
    """
    t = text.strip().lower()
    t = t.replace("0", "o")  # people write 0-0 for O-O
    if t in ("o-o", "oo"):
        return "oo"
    if t in ("o-o-o", "ooo"):
        return "ooo"
    # Remove everything that isn't a piece letter, file, rank, or promotion.
    t = re.sub(r"[x+#!?=\s\-]", "", t)
    return t


def _tokens(user_text: str) -> set[str]:
    """Split a free-text answer into normalised move tokens."""
    raw = re.split(r"[,\n;/]+|\s{2,}|\s+", user_text.strip())
    return {normalize_move_text(part) for part in raw if part.strip()}


def _keys_for(board: chess.Board, fm: ForcingMove) -> set[str]:
    """All the ways a user might legitimately name this one move."""
    keys = {normalize_move_text(fm.san), normalize_move_text(fm.move.uci())}
    # Also accept just the destination square (a beginner might say "e5").
    keys.add(chess.square_name(fm.move.to_square))
    return keys


@dataclass
class RecallResult:
    found: list[ForcingMove]
    missed: list[ForcingMove]
    spurious: list[str]  # things the user listed that aren't forcing moves

    @property
    def total(self) -> int:
        return len(self.found) + len(self.missed)


def grade_forcing_recall(
    board: chess.Board, user_text: str, forcing_moves: list[ForcingMove]
) -> RecallResult:
    """Which of the real forcing moves did the user name, and which did they miss?

    Matching is by normalised SAN, UCI, or destination square. Duplicate moves
    (a move that is both a check and a capture appears once) are de-duplicated
    by their UCI.
    """
    tokens = _tokens(user_text)

    # De-duplicate the forcing moves by the actual move played.
    unique: dict[str, ForcingMove] = {}
    for fm in forcing_moves:
        unique.setdefault(fm.move.uci(), fm)

    found, missed = [], []
    matched_tokens: set[str] = set()
    for fm in unique.values():
        keys = _keys_for(board, fm)
        hit = keys & tokens
        if hit:
            found.append(fm)
            matched_tokens |= hit
        else:
            missed.append(fm)

    spurious = sorted(tokens - matched_tokens)
    return RecallResult(found=found, missed=missed, spurious=spurious)


def parse_eval_guess(text: str) -> float | None:
    """Read a pawn-count guess like '+1.5', '-2', '0', or 'mate'.

    Returns the guess in pawns (White's point of view), or None if unparseable.
    'mate' / 'M' / '#' is read as a winning +100 for the side to move's guess —
    but since the guess is White-POV, we accept a signed number primarily.
    """
    t = text.strip().lower().replace("pawns", "").strip()
    if t in ("mate", "m", "#", "+m", "mate for white"):
        return 100.0
    if t in ("-m", "mate for black"):
        return -100.0
    t = t.replace("+", "")  # leading + is fine for float() only if we strip it
    try:
        # Re-add sign handling: float() accepts a leading '-' but we removed '+'.
        return float(text.strip().replace("pawns", "").strip())
    except ValueError:
        try:
            return float(t)
        except ValueError:
            return None


def eval_error(user_pawns: float, engine_pawns: float) -> float:
    """How far off (in pawns) the user's evaluation was."""
    return abs(user_pawns - engine_pawns)


def candidate_contains_best(
    board: chess.Board, candidate_text: str, best_move: chess.Move | None
) -> bool:
    """Did the user's candidate list include the engine's top move?"""
    if best_move is None:
        return False
    tokens = _tokens(candidate_text)
    best_keys = {
        normalize_move_text(board.san(best_move)),
        normalize_move_text(best_move.uci()),
    }
    return bool(best_keys & tokens)


def parse_candidate_moves(board: chess.Board, candidate_text: str) -> list[chess.Move]:
    """Turn a user's candidate list into legal moves we can analyse.

    Accepts SAN ('Nf3'), UCI ('g1f3'), and is lenient about check marks. Silently
    skips anything that isn't a legal move so a typo doesn't crash the drill.
    """
    moves: list[chess.Move] = []
    seen: set[str] = set()
    for part in re.split(r"[,\n;/]+|\s+", candidate_text.strip()):
        part = part.strip()
        if not part:
            continue
        move = _parse_one(board, part)
        if move is not None and move.uci() not in seen:
            moves.append(move)
            seen.add(move.uci())
    return moves


def _parse_one(board: chess.Board, text: str) -> chess.Move | None:
    # Try SAN first (most common), then UCI.
    try:
        return board.parse_san(text)
    except (ValueError, chess.IllegalMoveError, chess.InvalidMoveError, chess.AmbiguousMoveError):
        pass
    try:
        move = board.parse_uci(text.lower())
        return move if move in board.legal_moves else None
    except (ValueError, chess.IllegalMoveError, chess.InvalidMoveError):
        return None
