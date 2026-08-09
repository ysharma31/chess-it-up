"""Name the tactic in a mistake: fork, pin, skewer, and friends.

Phase 3 wants to tell you *what kind* of thing you keep missing — not "you
blundered 4 pawns" but "that's the third fork you've walked into this week".
So every puzzle carries motif tags, and accuracy is tracked per motif.

The tags we detect:

  hanging piece      — you left something the opponent simply wins.
  fork               — one enemy piece attacks two of yours at once.
  pin                — a piece of yours can't move without exposing a bigger one.
  skewer             — a valuable piece is attacked and, when it moves, a
                       lesser piece behind it falls (a pin, backwards).
  discovered attack  — moving one piece unveils an attack from the piece behind.
  back rank          — mate on your first rank, king trapped by its own pawns.
  overloaded defender— one defender guarding two things at once; take one, the
                       other falls.

Detection is heuristic and errs toward *not* tagging when unsure — a wrong
label teaches the wrong lesson. Everything is read from the position right after
your mistake and your opponent's best reply, using the Phase 1 tools.
"""

from __future__ import annotations

from collections import Counter

import chess

from .forcing import PIECE_VALUES, find_hanging_pieces

FORK = "fork"
PIN = "pin"
SKEWER = "skewer"
DISCOVERED = "discovered attack"
BACK_RANK = "back rank"
HANGING = "hanging piece"
OVERLOAD = "overloaded defender"

ALL_MOTIFS = [FORK, PIN, SKEWER, DISCOVERED, BACK_RANK, HANGING, OVERLOAD]


def detect_motifs(
    before_board: chess.Board,
    played_move: chess.Move,
    refutation: chess.Move | None,
) -> list[str]:
    """Tag the tactic in a mistake.

    - before_board: the position where the player (to move) went wrong.
    - played_move: the mistaken move they played.
    - refutation: the opponent's best reply that punishes it (may be None).

    Returns a list of motif tags (possibly empty).
    """
    player = before_board.turn
    after = before_board.copy(stack=False)
    after.push(played_move)

    motifs: list[str] = []

    # The move left material simply hangable.
    if find_hanging_pieces(after, player):
        motifs.append(HANGING)

    if refutation is not None:
        resulting = after.copy(stack=False)
        resulting.push(refutation)
        landing = refutation.to_square

        if _is_back_rank_mate(resulting, player):
            motifs.append(BACK_RANK)
        if _is_fork(resulting, landing, player):
            motifs.append(FORK)
        if _is_discovered_check(resulting, refutation):
            motifs.append(DISCOVERED)
        if _is_skewer(resulting, landing, player):
            motifs.append(SKEWER)
        if _creates_pin(resulting, landing, player):
            motifs.append(PIN)

    if _has_overloaded_defender(after, player):
        motifs.append(OVERLOAD)

    # De-duplicate, preserving order.
    seen: set[str] = set()
    return [m for m in motifs if not (m in seen or seen.add(m))]


# ---------------------------------------------------------------------------
# Individual detectors
# ---------------------------------------------------------------------------

def _is_fork(board: chess.Board, from_square: int, victim_color: bool) -> bool:
    """One piece on `from_square` attacks two+ winnable targets of victim_color."""
    forker = board.piece_at(from_square)
    if forker is None:
        return False
    forker_value = PIECE_VALUES[forker.piece_type]
    targets = 0
    for sq in board.attacks(from_square):
        piece = board.piece_at(sq)
        if piece is None or piece.color != victim_color:
            continue
        if piece.piece_type == chess.KING:  # a check is one prong
            targets += 1
        elif PIECE_VALUES[piece.piece_type] > forker_value:
            targets += 1
        elif not board.attackers(victim_color, sq):  # undefended
            targets += 1
    return targets >= 2


def _is_back_rank_mate(board: chess.Board, player: bool) -> bool:
    """Checkmate delivered on the player's own back rank by a rook or queen."""
    if not board.is_checkmate():
        return False
    king_sq = board.king(player)
    back_rank = 0 if player == chess.WHITE else 7
    if chess.square_rank(king_sq) != back_rank:
        return False
    for sq in board.checkers():
        piece = board.piece_at(sq)
        if (
            piece
            and piece.piece_type in (chess.ROOK, chess.QUEEN)
            and chess.square_rank(sq) == back_rank
        ):
            return True
    return False


def _is_discovered_check(board: chess.Board, refutation: chess.Move) -> bool:
    """A check delivered by a piece *other* than the one that just moved."""
    if not board.is_check():
        return False
    return any(sq != refutation.to_square for sq in board.checkers())


def _sign(n: int) -> int:
    return (n > 0) - (n < 0)


def _squares_behind(attacker: int, target: int) -> list[int]:
    """Squares in line beyond `target`, moving away from `attacker`."""
    af, ar = chess.square_file(attacker), chess.square_rank(attacker)
    tf, tr = chess.square_file(target), chess.square_rank(target)
    df, dr = _sign(tf - af), _sign(tr - ar)
    squares: list[int] = []
    f, r = tf + df, tr + dr
    while 0 <= f <= 7 and 0 <= r <= 7:
        squares.append(chess.square(f, r))
        f, r = f + df, r + dr
    return squares


def _is_skewer(board: chess.Board, from_square: int, victim_color: bool) -> bool:
    """A valuable piece is attacked along a line with a lesser one behind it."""
    piece = board.piece_at(from_square)
    if piece is None or piece.piece_type not in (chess.BISHOP, chess.ROOK, chess.QUEEN):
        return False
    for front_sq in board.attacks(from_square):
        front = board.piece_at(front_sq)
        # The front piece must be the king or queen for a genuine skewer.
        if front is None or front.color != victim_color:
            continue
        if front.piece_type not in (chess.KING, chess.QUEEN):
            continue
        for behind_sq in _squares_behind(from_square, front_sq):
            behind = board.piece_at(behind_sq)
            if behind is None:
                continue  # keep sliding until we hit something
            if (
                behind.color == victim_color
                and PIECE_VALUES[behind.piece_type] < PIECE_VALUES[front.piece_type]
            ):
                return True
            break  # the line is blocked by this first piece
    return False


def _creates_pin(board: chess.Board, from_square: int, victim_color: bool) -> bool:
    """The piece on `from_square` pins a victim piece against the victim's king."""
    piece = board.piece_at(from_square)
    if piece is None or piece.piece_type not in (chess.BISHOP, chess.ROOK, chess.QUEEN):
        return False
    king_sq = board.king(victim_color)
    for sq in chess.SQUARES:
        p = board.piece_at(sq)
        if p is None or p.color != victim_color or sq == king_sq:
            continue
        if not board.is_pinned(victim_color, sq):
            continue
        ray = board.pin(victim_color, sq)  # the line the piece is pinned along
        if from_square in ray and king_sq in ray:
            return True
    return False


def _has_overloaded_defender(board: chess.Board, player: bool) -> bool:
    """One player piece is the defender of two+ pieces the opponent attacks."""
    opp = not player
    attacked = [
        sq
        for sq in chess.SQUARES
        if (p := board.piece_at(sq)) and p.color == player and board.attackers(opp, sq)
    ]
    if len(attacked) < 2:
        return False
    defends = Counter()
    for sq in attacked:
        for defender in board.attackers(player, sq):
            defends[defender] += 1
    return any(count >= 2 for count in defends.values())
