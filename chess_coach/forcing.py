"""The CCT scanner: Checks, Captures, Threats — for both sides.

This is Step 1 and Step 2 of the human algorithm. Every turn, before anything
else, a strong player lists every forcing move on the board. Forcing moves are
the ones the opponent *cannot ignore*, so they are what you must calculate
first. In order of forcing-ness:

    Checks    — attacks on the king. The opponent must respond right now.
    Captures  — taking a piece. Often forcing, and the main way you lose or
                win material.
    Threats   — a quiet move that, next turn, would win material or give mate.

To judge whether a capture or threat actually *wins* material, we use "static
exchange evaluation" (SEE): play out the whole sequence of captures on one
square, each side grabbing with its cheapest attacker, and see who comes out
ahead. This is what lets the trainer say "Nxe5 loses a piece" instead of just
"Nxe5 is a capture".

Simplifications worth knowing (this is a beginner tool, not an engine):
  - SEE ignores pins and other move-legality of the *recaptures*. A pinned
    defender is still counted as a defender. In rare cases this makes SEE
    slightly optimistic about a defence.
  - Threat detection asks "if my opponent did nothing, could I win material or
    give mate next move?" — it does not check whether the opponent can defend.
    That is deliberate: naming the threat is the skill; refuting it is the next
    step of calculation.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import chess

# Piece values in pawns. The king is given a large value so that in a capture
# sequence nothing is ever "worth" trading for the king (you can't capture the
# king anyway, but this keeps the arithmetic honest).
PIECE_VALUES = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
    chess.KING: 100,
}


@dataclass
class ForcingMove:
    """One forcing move, with a plain-language note about what it does."""

    move: chess.Move
    san: str
    kind: str  # "check", "capture", or "threat"
    is_mate: bool = False
    gain: float = 0.0  # material swing in pawns (for captures/threats)
    target: str = ""  # e.g. "the knight on f6"
    also_capture: bool = False  # a check that is also a capture

    def describe(self) -> str:
        """A short human line, e.g. 'Qxf7# — checkmate' or 'Nxe5 — wins 1'."""
        parts = [self.san]
        if self.is_mate:
            parts.append("checkmate")
        elif self.kind == "capture":
            if self.gain > 0:
                parts.append(f"wins {_pawns(self.gain)}")
            elif self.gain < 0:
                parts.append(f"loses {_pawns(-self.gain)}")
            else:
                parts.append("even trade")
        elif self.kind == "threat":
            parts.append(f"threatens {self.target}" if self.target else "makes a threat")
        elif self.kind == "check" and self.also_capture and self.gain:
            sign = "wins" if self.gain > 0 else "loses"
            parts.append(f"{sign} {_pawns(abs(self.gain))}")
        return " — ".join(parts)


@dataclass
class ForcingScan:
    """All forcing moves for one side, split into the three CCT buckets."""

    checks: list[ForcingMove] = field(default_factory=list)
    captures: list[ForcingMove] = field(default_factory=list)
    threats: list[ForcingMove] = field(default_factory=list)

    def all_moves(self) -> list[ForcingMove]:
        return self.checks + self.captures + self.threats

    def total(self) -> int:
        return len(self.checks) + len(self.captures) + len(self.threats)


def _pawns(x: float) -> str:
    """Format a pawn count, dropping a trailing '.0' so 3.0 reads as '3'."""
    x = round(x, 1)
    return str(int(x)) if x == int(x) else str(x)


# ---------------------------------------------------------------------------
# Static exchange evaluation (SEE)
# ---------------------------------------------------------------------------

def _see_recapture(board: chess.Board, square: int, side: bool) -> float:
    """How much material `side` can win by *starting* to capture on `square`.

    Recursive: `side` grabs with its cheapest attacker, then the other side may
    recapture, and so on. Each side stops when continuing would lose material,
    so the result is never negative for the side to move. Attackers are
    recomputed from the board after every capture, so an attacker hiding behind
    another (an "x-ray", e.g. a rook behind a rook) is revealed naturally.
    """
    attackers = board.attackers(side, square)
    if not attackers:
        return 0.0

    # Cheapest attacker moves first — that is optimal in a capture sequence.
    from_sq = min(attackers, key=lambda s: PIECE_VALUES[board.piece_type_at(s)])
    attacker_type = board.piece_type_at(from_sq)

    # A king cannot capture a square the enemy still defends (it would be moving
    # into check). Treat that as "no capture available".
    if attacker_type == chess.KING and board.attackers(not side, square):
        return 0.0

    target_value = PIECE_VALUES[board.piece_type_at(square)]

    after = board.copy(stack=False)
    piece = after.piece_at(from_sq)
    after.remove_piece_at(from_sq)
    after.set_piece_at(square, piece)

    # We captured `target_value`; the opponent may now recapture, which costs us
    # whatever they can win back. We only continue if it nets out in our favour.
    gain = target_value - _see_recapture(after, square, not side)
    return max(0.0, gain)


def static_exchange_eval(board: chess.Board, move: chess.Move) -> float:
    """Net material (in pawns) from playing `move`, assuming best recaptures.

    Positive means the capture wins material; negative means it loses material
    (e.g. taking a defended pawn with a queen). This is the number behind
    "don't hang your pieces".
    """
    to_sq = move.to_square
    side = board.turn

    if board.is_en_passant(move):
        target_value = 1.0  # an en-passant capture always takes a pawn
        after = board.copy(stack=False)
        captured_pawn_sq = to_sq + (-8 if side == chess.WHITE else 8)
        after.remove_piece_at(captured_pawn_sq)
    else:
        target = board.piece_at(to_sq)
        target_value = PIECE_VALUES[target.piece_type] if target else 0.0
        after = board.copy(stack=False)

    piece = after.piece_at(move.from_square)
    after.remove_piece_at(move.from_square)
    # If this move promotes, the piece that sits on the square is the new piece.
    if move.promotion:
        piece = chess.Piece(move.promotion, side)
    after.set_piece_at(to_sq, piece)

    return target_value - _see_recapture(after, to_sq, not side)


def best_capture_gain(board: chess.Board, square: int, side: bool) -> tuple[float, int | None]:
    """Best material `side` can win by capturing whatever sits on `square`.

    Works regardless of whose turn it is, so it can answer "is this piece of
    mine hanging?" — where the *enemy* would be the one capturing.
    """
    target = board.piece_at(square)
    if target is None or target.color == side:
        return 0.0, None

    best_gain = 0.0
    best_from: int | None = None
    for from_sq in board.attackers(side, square):
        attacker_type = board.piece_type_at(from_sq)
        if attacker_type == chess.KING and board.attackers(not side, square):
            continue  # king can't take a defended piece
        after = board.copy(stack=False)
        piece = after.piece_at(from_sq)
        after.remove_piece_at(from_sq)
        after.set_piece_at(square, piece)
        gain = PIECE_VALUES[target.piece_type] - _see_recapture(after, square, not side)
        if gain > best_gain:
            best_gain, best_from = gain, from_sq
    return best_gain, best_from


# ---------------------------------------------------------------------------
# Threat detection helpers
# ---------------------------------------------------------------------------

def _winning_capture_targets(board: chess.Board) -> dict[int, tuple[float, str]]:
    """For the side to move: squares they could capture for a material gain.

    Returns {target_square: (gain, description)} keeping the best gain per
    square. Used as the "what do I already threaten" baseline and, after a
    trial move, as "what do I threaten now".
    """
    targets: dict[int, tuple[float, str]] = {}
    for move in board.legal_moves:
        if not board.is_capture(move):
            continue
        gain = static_exchange_eval(board, move)
        if gain <= 0:
            continue
        desc = _victim_description(board, move)
        if move.to_square not in targets or gain > targets[move.to_square][0]:
            targets[move.to_square] = (gain, desc)
    return targets


def _victim_description(board: chess.Board, move: chess.Move) -> str:
    """e.g. 'the queen on d8'. Handles en passant (victim isn't on to_square)."""
    square = move.to_square
    victim = board.piece_at(square)
    name = chess.piece_name(victim.piece_type) if victim else "pawn"
    return f"the {name} on {chess.square_name(square)}"


def _has_mate_in_one(board: chess.Board) -> bool:
    """Does the side to move have a checkmate available right now?"""
    for move in board.legal_moves:
        board.push(move)
        mate = board.is_checkmate()
        board.pop()
        if mate:
            return True
    return False


def _is_checkmate_move(board: chess.Board, move: chess.Move) -> bool:
    board.push(move)
    mate = board.is_checkmate()
    board.pop()
    return mate


# ---------------------------------------------------------------------------
# The scanner
# ---------------------------------------------------------------------------

def scan_forcing_moves(board: chess.Board) -> ForcingScan:
    """List every Check, Capture, and Threat for the side to move.

    A move that is both a check and a capture is filed under Checks (checks are
    the most forcing), and marked as also_capture so nothing is hidden.
    """
    scan = ForcingScan()

    # Baseline: what does the side to move already threaten before any quiet
    # move? A "threat" only counts if it creates something *new*.
    baseline_targets = _winning_capture_targets(board)
    baseline_mate = _has_mate_in_one(board)

    for move in board.legal_moves:
        gives_check = board.gives_check(move)
        is_capture = board.is_capture(move)
        san = board.san(move)

        if gives_check:
            gain = static_exchange_eval(board, move) if is_capture else 0.0
            scan.checks.append(
                ForcingMove(
                    move, san, "check",
                    is_mate=_is_checkmate_move(board, move),
                    gain=gain,
                    also_capture=is_capture,
                )
            )
        elif is_capture:
            scan.captures.append(
                ForcingMove(move, san, "capture", gain=static_exchange_eval(board, move))
            )

    # Threats are quiet moves (not a check, not a capture) that create a new
    # winning capture or a new mate-in-one next move.
    for move in board.legal_moves:
        if board.gives_check(move) or board.is_capture(move):
            continue
        san = board.san(move)
        board.push(move)
        desc, gain, is_mate = _threat_created(board, baseline_targets, baseline_mate)
        board.pop()
        if desc:
            scan.threats.append(
                ForcingMove(move, san, "threat", is_mate=is_mate, gain=gain, target=desc)
            )

    # Show the biggest threats first — they matter most.
    scan.threats.sort(key=lambda m: (m.is_mate, m.gain), reverse=True)
    scan.captures.sort(key=lambda m: m.gain, reverse=True)
    return scan


def _threat_created(
    board_after: chess.Board,
    baseline_targets: dict[int, tuple[float, str]],
    baseline_mate: bool,
) -> tuple[str, float, bool]:
    """After our quiet move (opponent now to move), what do we newly threaten?

    We let the opponent "pass" (a null move) so it becomes our turn again, then
    ask what we could win. Comparing against the baseline keeps us from
    reporting threats that already existed before our move.
    """
    if board_after.is_check():
        return "", 0.0, False  # shouldn't happen after a quiet move, but be safe

    board_after.push(chess.Move.null())  # opponent does nothing
    new_targets = _winning_capture_targets(board_after)
    mate_now = _has_mate_in_one(board_after)
    board_after.pop()

    if mate_now and not baseline_mate:
        return "checkmate", 99.0, True

    best_desc, best_gain = "", 0.0
    for square, (gain, desc) in new_targets.items():
        baseline_gain = baseline_targets.get(square, (0.0, ""))[0]
        if gain > baseline_gain + 1e-9 and gain > best_gain:
            best_gain, best_desc = gain, desc
    return best_desc, best_gain, False


def scan_opponent_forcing_moves(board: chess.Board) -> ForcingScan | None:
    """The same CCT scan, but for the *other* side — what they can do to you.

    Returns None if the side to move is in check, because then it isn't
    meaningfully the opponent's turn: you must deal with the check first.
    """
    if board.is_check():
        return None
    board.push(chess.Move.null())  # hand the move to the opponent
    scan = scan_forcing_moves(board)
    board.pop()
    return scan


# ---------------------------------------------------------------------------
# Hanging pieces (Step 2: the safety check)
# ---------------------------------------------------------------------------

@dataclass
class HangingPiece:
    square: int
    piece: chess.Piece
    loss: float  # pawns lost if the enemy takes it and the trade plays out

    def describe(self) -> str:
        name = chess.piece_name(self.piece.piece_type)
        return f"the {name} on {chess.square_name(self.square)} (loses {_pawns(self.loss)})"


def find_hanging_pieces(board: chess.Board, color: bool) -> list[HangingPiece]:
    """Pieces of `color` the enemy can win material by capturing.

    This powers Step 2 — the safety check. "Hanging" here means the enemy comes
    out ahead on material if they take it, accounting for your defenders via
    SEE (not merely "it is attacked").
    """
    enemy = not color
    hanging: list[HangingPiece] = []
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece is None or piece.color != color:
            continue
        loss, _ = best_capture_gain(board, square, enemy)
        if loss > 0:
            hanging.append(HangingPiece(square, piece, loss))
    hanging.sort(key=lambda h: h.loss, reverse=True)
    return hanging
