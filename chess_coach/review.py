"""Replay a finished game and grade every move.

This is Phase 2's payoff: you play a game, then the coach walks back through it
and, for each move, says how good it was and — when it was a mistake or blunder
— why, in words. The output is both a printed report and an annotated PGN you
can keep or load into any chess program.

The work splits cleanly:
  - classify.py decides the label from the centipawn loss,
  - tactics.py writes the plain-language "why",
  - this module orchestrates the engine passes and builds the PGN.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field

import chess
import chess.pgn

from . import classify, tactics
from .engine import Engine


@dataclass
class ReviewedMove:
    """One move, graded."""

    ply: int  # 1 = the first move of the game
    move: chess.Move
    san: str
    mover_white: bool
    classification: str
    cp_loss: float
    eval_before: float  # White-POV pawns, best play
    eval_after: float  # White-POV pawns, after the move played
    best_move: chess.Move | None
    best_san: str | None
    best_line: list[str]
    explanation: str = ""  # only for mistakes/blunders
    # Extra context Phase 3 needs to turn a blunder into a puzzle:
    fen_before: str = ""  # the position with the player to move
    refutation_move: chess.Move | None = None  # opponent's best reply to the mistake

    @property
    def mover(self) -> str:
        return "White" if self.mover_white else "Black"


def review_moves(
    start_board: chess.Board,
    moves: list[chess.Move],
    engine: Engine,
) -> list[ReviewedMove]:
    """Grade every move in `moves`, played from `start_board`.

    We evaluate each *position* once (there are one more of them than there are
    moves) and read every move off two consecutive evaluations — the value
    before the move and the value after it. That is the fewest engine calls the
    job needs.
    """
    # Build the sequence of positions the game passed through.
    positions = [start_board.copy(stack=False)]
    walker = start_board.copy(stack=False)
    for move in moves:
        walker.push(move)
        positions.append(walker.copy(stack=False))

    assessments = [engine.assess(pos) for pos in positions]

    reviewed: list[ReviewedMove] = []
    for i, move in enumerate(moves):
        before_board = positions[i]
        before = assessments[i]
        after = assessments[i + 1]
        mover_white = before_board.turn == chess.WHITE

        cp_loss = classify.centipawn_loss(before.pawns, after.pawns, mover_white)
        played_best = before.best_move is not None and move == before.best_move
        label = classify.classify(cp_loss, played_best)

        explanation = ""
        if classify.is_serious(label):
            explanation = tactics.explain(
                before_board, move, before.best_san, after.best_move
            )

        reviewed.append(
            ReviewedMove(
                ply=i + 1,
                move=move,
                san=before_board.san(move),
                mover_white=mover_white,
                classification=label,
                cp_loss=cp_loss,
                eval_before=before.pawns,
                eval_after=after.pawns,
                best_move=before.best_move,
                best_san=before.best_san,
                best_line=before.pv_san,
                explanation=explanation,
                fen_before=before_board.fen(),
                refutation_move=after.best_move,
            )
        )
    return reviewed


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

@dataclass
class GameSummary:
    counts: dict[str, dict[str, int]]  # "White"/"Black" -> label -> count
    avg_cp_loss: dict[str, float]  # "White"/"Black" -> average centipawn loss

    def lines(self) -> list[str]:
        out = []
        for side in ("White", "Black"):
            c = self.counts[side]
            out.append(
                f"{side}: "
                f"{c[classify.BEST]} best, {c[classify.GOOD]} good, "
                f"{c[classify.INACCURACY]} inaccuracies, "
                f"{c[classify.MISTAKE]} mistakes, {c[classify.BLUNDER]} blunders "
                f"(avg loss {self.avg_cp_loss[side]:.0f}cp)."
            )
        return out


def summarize(reviewed: list[ReviewedMove]) -> GameSummary:
    counts = {
        "White": {label: 0 for label in classify.ORDER},
        "Black": {label: 0 for label in classify.ORDER},
    }
    losses = {"White": [], "Black": []}
    for rm in reviewed:
        counts[rm.mover][rm.classification] += 1
        losses[rm.mover].append(rm.cp_loss)

    avg = {
        side: (sum(vals) / len(vals) if vals else 0.0)
        for side, vals in losses.items()
    }
    return GameSummary(counts=counts, avg_cp_loss=avg)


def blunders_and_mistakes(reviewed: list[ReviewedMove]) -> list[ReviewedMove]:
    """The moves worth studying, worst first."""
    serious = [rm for rm in reviewed if classify.is_serious(rm.classification)]
    serious.sort(key=lambda rm: rm.cp_loss, reverse=True)
    return serious


# ---------------------------------------------------------------------------
# Annotated PGN
# ---------------------------------------------------------------------------

def to_annotated_pgn(
    start_board: chess.Board,
    reviewed: list[ReviewedMove],
    white: str = "You",
    black: str = "Stockfish",
    event: str = "Chess Coach training game",
    result: str | None = None,
) -> chess.pgn.Game:
    """Build a PGN game with a NAG and comment on every notable move."""
    game = chess.pgn.Game()
    game.setup(start_board)  # writes FEN/SetUp headers only if non-standard
    game.headers["Event"] = event
    game.headers["Site"] = "Chess Coach"
    game.headers["Date"] = datetime.date.today().strftime("%Y.%m.%d")
    game.headers["White"] = white
    game.headers["Black"] = black

    node = game
    final = start_board.copy(stack=False)
    for rm in reviewed:
        node = node.add_main_variation(rm.move)
        if rm.classification in classify.NAG:
            node.nags.add(classify.NAG[rm.classification])
        comment = _comment_for(rm)
        if comment:
            node.comment = comment
        final.push(rm.move)

    game.headers["Result"] = result or (
        final.result() if final.is_game_over() else "*"
    )
    return game


def _fmt_eval(pawns: float) -> str:
    """Render a White-POV eval, showing a forced mate as +M / -M."""
    if pawns >= 99:
        return "+M"  # White is mating
    if pawns <= -99:
        return "-M"  # Black is mating
    return f"{pawns:+.1f}"


def _comment_for(rm: ReviewedMove) -> str:
    """The PGN comment for a move — only for inaccuracies and worse."""
    if rm.classification in (classify.BEST, classify.GOOD):
        return ""
    bits = [
        f"{rm.classification.capitalize()} "
        f"(lost {rm.cp_loss:.0f}cp; eval now {_fmt_eval(rm.eval_after)})."
    ]
    if rm.explanation:
        bits.append(rm.explanation)
    if rm.best_san:
        line = " ".join(rm.best_line[:5])
        bits.append(f"Better was {rm.best_san}" + (f" ({line})." if line else "."))
    return " ".join(bits)


def write_pgn(game: chess.pgn.Game, path: str) -> None:
    """Write a game to a .pgn file."""
    with open(path, "w", encoding="utf-8") as fh:
        print(game, file=fh, end="\n")


# ---------------------------------------------------------------------------
# Text report
# ---------------------------------------------------------------------------

def _move_number(rm: ReviewedMove) -> str:
    """Render a move like '12.' (White) or '12...' (Black)."""
    number = (rm.ply + 1) // 2
    return f"{number}." if rm.mover_white else f"{number}..."


def format_report(reviewed: list[ReviewedMove]) -> list[str]:
    """A printable review: the summary, then each mistake/blunder explained."""
    summary = summarize(reviewed)
    lines = ["Game review", "-----------"]
    lines += summary.lines()

    serious = blunders_and_mistakes(reviewed)
    lines.append("")
    if not serious:
        lines.append("No mistakes or blunders — clean game. Nice.")
        return lines

    lines.append(f"{len(serious)} moment(s) worth studying (worst first):")
    for rm in serious:
        sym = classify.SYMBOL[rm.classification]
        lines.append("")
        lines.append(
            f"  {_move_number(rm)} {rm.san}{sym}  "
            f"[{rm.classification}, lost {rm.cp_loss:.0f}cp, "
            f"eval {_fmt_eval(rm.eval_before)} → {_fmt_eval(rm.eval_after)}]"
        )
        if rm.explanation:
            lines.append(f"     {rm.explanation}")
    return lines
