"""Step 5: evaluate a position by decomposing it, not by eyeballing it.

Beginners look at a position and "feel" something. Strong players break the
position into a handful of named factors, judge each one, and add them up. This
module computes those factors so the trainer can show you the breakdown — the
*why* — next to Stockfish's single number.

The factors, in plain language:

  Material       — who has more, and how much (in pawns).
  King safety    — is each king tucked behind pawns, or out in the open?
  Piece activity — how many moves does each side have (mobility), and how many
                   minor pieces (knights/bishops) are developed off the back rank?
  Pawn structure — doubled, isolated, and passed pawns. Weaknesses and assets.
  Space          — how many squares in the enemy half your pawns control.

This is intentionally a *human* checklist, not a tuned engine evaluation. The
numbers are rough on purpose; their job is to teach you what to look at.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

import chess

# Material values in pawns (the king is not counted — it is never traded).
_MATERIAL = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
}


def _side_name(color: bool) -> str:
    return "White" if color == chess.WHITE else "Black"


# ---------------------------------------------------------------------------
# Individual factors
# ---------------------------------------------------------------------------

def material_count(board: chess.Board) -> tuple[int, int, int]:
    """(white total, black total, difference). Difference is White minus Black."""
    white = black = 0
    for piece_type, value in _MATERIAL.items():
        white += len(board.pieces(piece_type, chess.WHITE)) * value
        black += len(board.pieces(piece_type, chess.BLACK)) * value
    return white, black, white - black


def mobility(board: chess.Board, color: bool) -> int:
    """How many legal moves `color` has — a simple measure of activity."""
    if board.turn == color:
        return board.legal_moves.count()
    if board.is_check():
        # The side to move is in check; measuring the other side's mobility via
        # a null move isn't possible. Activity is moot when you're in check.
        return 0
    board.push(chess.Move.null())
    count = board.legal_moves.count()
    board.pop()
    return count


# Home squares of the minor pieces, used to tell "developed" from "still at home".
_MINOR_HOME = {
    chess.WHITE: {chess.B1, chess.G1, chess.C1, chess.F1},
    chess.BLACK: {chess.B8, chess.G8, chess.C8, chess.F8},
}


def developed_minors(board: chess.Board, color: bool) -> int:
    """Count knights and bishops that have left their starting square."""
    count = 0
    for piece_type in (chess.KNIGHT, chess.BISHOP):
        for square in board.pieces(piece_type, color):
            if square not in _MINOR_HOME[color]:
                count += 1
    return count


def _pawn_files(board: chess.Board, color: bool) -> list[int]:
    return [chess.square_file(sq) for sq in board.pieces(chess.PAWN, color)]


def doubled_pawns(board: chess.Board, color: bool) -> int:
    """Extra pawns stacked on a file (two on a file = 1 doubled, three = 2)."""
    counts = Counter(_pawn_files(board, color))
    return sum(n - 1 for n in counts.values() if n > 1)


def isolated_pawns(board: chess.Board, color: bool) -> int:
    """Pawns with no friendly pawn on either neighbouring file (no support)."""
    files = _pawn_files(board, color)
    present = set(files)
    isolated = 0
    for f in files:
        if (f - 1) not in present and (f + 1) not in present:
            isolated += 1
    return isolated


def passed_pawns(board: chess.Board, color: bool) -> int:
    """Pawns with no enemy pawn able to stop them on their file or neighbours.

    A passed pawn has a clear run to promotion — a major long-term asset.
    """
    enemy = not color
    enemy_pawns = list(board.pieces(chess.PAWN, enemy))
    forward = 1 if color == chess.WHITE else -1
    passed = 0
    for sq in board.pieces(chess.PAWN, color):
        f, r = chess.square_file(sq), chess.square_rank(sq)
        blocked = False
        for esq in enemy_pawns:
            ef, er = chess.square_file(esq), chess.square_rank(esq)
            if abs(ef - f) <= 1 and (er - r) * forward > 0:
                blocked = True
                break
        if not blocked:
            passed += 1
    return passed


def king_pawn_shield(board: chess.Board, color: bool) -> int:
    """Friendly pawns on the up-to-six squares directly in front of the king.

    A healthy castled king usually has three; zero means the king is exposed.
    """
    king_sq = board.king(color)
    if king_sq is None:
        return 0
    kf, kr = chess.square_file(king_sq), chess.square_rank(king_sq)
    forward = 1 if color == chess.WHITE else -1
    shield = 0
    for df in (-1, 0, 1):
        f = kf + df
        if not 0 <= f <= 7:
            continue
        for dr in (1, 2):
            r = kr + forward * dr
            if not 0 <= r <= 7:
                continue
            piece = board.piece_at(chess.square(f, r))
            if piece and piece.piece_type == chess.PAWN and piece.color == color:
                shield += 1
    return shield


def king_attackers(board: chess.Board, color: bool) -> int:
    """Count enemy pieces bearing down on squares next to `color`'s king."""
    king_sq = board.king(color)
    if king_sq is None:
        return 0
    kf, kr = chess.square_file(king_sq), chess.square_rank(king_sq)
    enemy = not color
    attacking = set()
    for df in (-1, 0, 1):
        for dr in (-1, 0, 1):
            if df == 0 and dr == 0:
                continue
            f, r = kf + df, kr + dr
            if 0 <= f <= 7 and 0 <= r <= 7:
                attacking |= set(board.attackers(enemy, chess.square(f, r)))
    return len(attacking)


def space(board: chess.Board, color: bool) -> int:
    """Squares in the enemy half that `color`'s pawns control.

    A rough space count: more controlled squares in the opponent's territory
    means more room for your pieces.
    """
    # White's target half is ranks 5-8 (indices 4-7); Black's is ranks 1-4.
    if color == chess.WHITE:
        enemy_half = range(4, 8)
    else:
        enemy_half = range(0, 4)
    enemy_half_squares = {
        chess.square(f, r) for f in range(8) for r in enemy_half
    }
    controlled = set()
    for sq in board.pieces(chess.PAWN, color):
        controlled |= set(board.attacks(sq)) & enemy_half_squares
    return len(controlled)


# ---------------------------------------------------------------------------
# The full report
# ---------------------------------------------------------------------------

@dataclass
class EvalReport:
    """A human-style decomposition of one position."""

    material: tuple[int, int, int]
    mobility: tuple[int, int]
    developed: tuple[int, int]
    doubled: tuple[int, int]
    isolated: tuple[int, int]
    passed: tuple[int, int]
    shield: tuple[int, int]
    king_attackers: tuple[int, int]
    space: tuple[int, int]

    def summary_lines(self) -> list[str]:
        """Plain-language lines, one factor per line, White vs Black."""
        w_mat, b_mat, diff = self.material
        lines: list[str] = []

        if diff == 0:
            lines.append(f"Material: even ({w_mat} each).")
        else:
            leader = "White" if diff > 0 else "Black"
            lines.append(
                f"Material: {leader} is up {abs(diff)} "
                f"(White {w_mat} vs Black {b_mat})."
            )

        lines.append(
            f"King safety: pawn shield White {self.shield[0]} / Black {self.shield[1]}; "
            f"enemy pieces aimed at the king White {self.king_attackers[0]} / "
            f"Black {self.king_attackers[1]} (higher is more dangerous for that king)."
        )
        lines.append(
            f"Activity: moves available White {self.mobility[0]} / Black {self.mobility[1]}; "
            f"developed minor pieces White {self.developed[0]} / Black {self.developed[1]}."
        )
        lines.append(
            f"Pawn structure — doubled White {self.doubled[0]} / Black {self.doubled[1]}, "
            f"isolated White {self.isolated[0]} / Black {self.isolated[1]}, "
            f"passed White {self.passed[0]} / Black {self.passed[1]} "
            f"(doubled and isolated are weaknesses; passed pawns are assets)."
        )
        lines.append(
            f"Space: squares held in the enemy half — "
            f"White {self.space[0]} / Black {self.space[1]}."
        )
        return lines


def evaluate_position(board: chess.Board) -> EvalReport:
    """Run the whole human checklist over a position."""
    return EvalReport(
        material=material_count(board),
        mobility=(mobility(board, chess.WHITE), mobility(board, chess.BLACK)),
        developed=(developed_minors(board, chess.WHITE), developed_minors(board, chess.BLACK)),
        doubled=(doubled_pawns(board, chess.WHITE), doubled_pawns(board, chess.BLACK)),
        isolated=(isolated_pawns(board, chess.WHITE), isolated_pawns(board, chess.BLACK)),
        passed=(passed_pawns(board, chess.WHITE), passed_pawns(board, chess.BLACK)),
        shield=(king_pawn_shield(board, chess.WHITE), king_pawn_shield(board, chess.BLACK)),
        king_attackers=(king_attackers(board, chess.WHITE), king_attackers(board, chess.BLACK)),
        space=(space(board, chess.WHITE), space(board, chess.BLACK)),
    )
