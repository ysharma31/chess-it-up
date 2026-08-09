"""Explain a mistake in plain language a beginner can act on.

When the review finds a mistake or blunder, a centipawn number isn't teaching.
"You dropped 4 pawns" tells you nothing about *why*. This module reconstructs
the story: what you left hanging, how your opponent punishes it, and whether
the shape is a familiar one — a fork, a pin, a piece pulled off its defence.

It leans entirely on the Phase 1 tools (forcing scan, static exchange
evaluation, hanging-piece detection). The engine only supplies the two moves
that matter: the move you should have played, and your opponent's punishing
reply. The words around them are ours, so they can be beginner-plain.
"""

from __future__ import annotations

import chess

from .forcing import (
    PIECE_VALUES,
    find_hanging_pieces,
    static_exchange_eval,
)


def _piece_word(piece: chess.Piece) -> str:
    return chess.piece_name(piece.piece_type)  # "knight", "queen", ...


def _name_on(board: chess.Board, square: int) -> str:
    piece = board.piece_at(square)
    if piece is None:
        return f"the pawn on {chess.square_name(square)}"
    return f"the {_piece_word(piece)} on {chess.square_name(square)}"


def explain(
    before_board: chess.Board,
    played_move: chess.Move,
    better_san: str | None,
    refutation: chess.Move | None,
) -> str:
    """Return a one-paragraph, plain-language explanation of what went wrong.

    - before_board: the position with the player to move (before their move).
    - played_move: the move they actually played.
    - better_san: the move they should have played (engine's best), in SAN.
    - refutation: the opponent's best reply to the played move (what punishes it).
    """
    player = before_board.turn
    after_board = before_board.copy(stack=False)
    after_board.push(played_move)

    pieces: list[str] = []

    if refutation is not None:
        pieces.append(_describe_refutation(after_board, refutation, player))
    else:
        # No single punishing move — the damage is positional or slow.
        hanging = find_hanging_pieces(after_board, player)
        if hanging:
            pieces.append(
                "it leaves " + hanging[0].describe() + " for your opponent to win"
            )
        else:
            pieces.append("it hands your opponent a lasting edge")

    if better_san:
        pieces.append(f"Instead, {better_san} held the position")

    return ". ".join(p for p in pieces if p).strip() + "."


def _describe_refutation(
    after_board: chess.Board, refutation: chess.Move, player: bool
) -> str:
    """Describe the opponent's punishing move: what it wins, and its shape."""
    opp = after_board.turn  # opponent is to move in after_board
    san = after_board.san(refutation)

    resulting = after_board.copy(stack=False)
    resulting.push(refutation)

    # Checkmate is the sharpest possible punishment.
    if resulting.is_checkmate():
        return f"it allows checkmate with {san}"

    # A fork: the arriving piece hits two (or more) valuable targets at once.
    forked = _fork_targets(resulting, refutation.to_square, player, opp)
    if len(forked) >= 2:
        names = _join([_fork_name(resulting, sq, player) for sq in forked])
        return f"it walks into a fork — {san} hits {names} at once"

    if after_board.is_capture(refutation):
        gain = static_exchange_eval(after_board, refutation)
        victim = _name_on(after_board, refutation.to_square)
        pin_note = _pin_note(after_board, refutation.to_square, player)
        won = f"winning {victim}" if gain > 0 else f"taking {victim}"
        gain_txt = f" (about {_round(gain)} pawns)" if gain > 0 else ""
        return f"your opponent replies {san}, {won}{gain_txt}{pin_note}"

    # A quiet punishing move that sets up winning something next.
    hanging = find_hanging_pieces(resulting, player)
    if hanging:
        return (
            f"your opponent plays {san}, and you cannot save "
            + hanging[0].describe()
        )
    return f"your opponent seizes the initiative with {san}"


def _fork_targets(
    board: chess.Board, from_square: int, victim_color: bool, forker_color: bool
) -> list[int]:
    """Squares of `victim_color` pieces the piece on `from_square` wins/checks.

    A target counts if it is the king (a check), a piece worth more than the
    forking piece, or an undefended piece — i.e. something the fork actually
    threatens to win.
    """
    forker = board.piece_at(from_square)
    if forker is None:
        return []
    forker_value = PIECE_VALUES[forker.piece_type]
    targets: list[int] = []
    for sq in board.attacks(from_square):
        piece = board.piece_at(sq)
        if piece is None or piece.color != victim_color:
            continue
        if piece.piece_type == chess.KING:
            targets.append(sq)
        elif PIECE_VALUES[piece.piece_type] > forker_value:
            targets.append(sq)
        elif not board.attackers(victim_color, sq):  # undefended
            targets.append(sq)
    return targets


def _fork_name(board: chess.Board, square: int, victim_color: bool) -> str:
    piece = board.piece_at(square)
    if piece and piece.piece_type == chess.KING:
        return "your king"
    return _name_on(board, square)


def _pin_note(after_board: chess.Board, victim_square: int, player: bool) -> str:
    """If the piece being won was pinned (couldn't run), say so."""
    if after_board.is_pinned(player, victim_square):
        return " — the piece was pinned and couldn't move"
    return ""


def _join(items: list[str]) -> str:
    items = [i for i in items if i]
    if len(items) <= 1:
        return items[0] if items else ""
    return ", ".join(items[:-1]) + " and " + items[-1]


def _round(x: float) -> str:
    x = round(x, 1)
    return str(int(x)) if x == int(x) else str(x)
