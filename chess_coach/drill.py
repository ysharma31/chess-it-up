"""The interactive five-step drill — the core of Phase 1.

This walks you through the exact procedure a strong player runs, and it never
shows you the answer before you commit to yours. That ordering is the entire
product: a tool that just prints the engine's move teaches nothing.

The five steps (see the project brief):

  1. Scan for forcing moves (Checks, Captures, Threats) — for both sides.
  2. Safety check — is anything of mine hanging?
  3. Pick 2-3 candidate moves.
  4. Calculate each candidate until the position is quiet.
  5. Evaluate the resulting positions, then compare to the engine.

I/O is injected (`ask` / `say`) so the flow can be driven by a test or by the
real terminal. `ask` takes a prompt and returns the user's line; `say` prints.
"""

from __future__ import annotations

from typing import Callable

import chess

from . import grading
from .engine import Assessment, Engine
from .evaluation import evaluate_position
from .forcing import (
    find_hanging_pieces,
    scan_forcing_moves,
    scan_opponent_forcing_moves,
)
from .render import render_board, turn_line
from .session import DrillResult

Ask = Callable[[str], str]
Say = Callable[[str], None]


def _default_ask(prompt: str) -> str:
    return input(prompt)


def _default_say(text: str = "") -> None:
    print(text)


def _rule(say: Say, title: str) -> None:
    say("")
    say(f"── {title} " + "─" * max(0, 60 - len(title)))


def run_drill(
    board: chess.Board,
    engine: Engine | None = None,
    ask: Ask = _default_ask,
    say: Say = _default_say,
) -> DrillResult:
    """Run one position through all five steps. Returns a DrillResult."""

    say("")
    say(render_board(board))
    say("")
    say(turn_line(board))
    say(f"FEN: {board.fen()}")

    # If the game is already over there is nothing to drill.
    if board.is_game_over():
        say("")
        say(f"This position is already finished: {board.result()}.")
        return DrillResult(board.fen(), 0, 0, None, None, None)

    scan = scan_forcing_moves(board)

    # ---- Step 1: forcing moves (commit, then reveal) --------------------
    _rule(say, "Step 1 — Scan for forcing moves (Checks, Captures, Threats)")
    say("List every check, capture, and threat you can see for the side to move.")
    say("Use algebraic notation, separated by commas (e.g. Nxe5, Qh5+, Bb5).")
    answer = ask("Your forcing moves: ")

    recall = grading.grade_forcing_recall(board, answer, scan.all_moves())
    _reveal_forcing(say, scan, recall)

    # Also show what the *opponent* can do — half of Step 1 is their forcing moves.
    opp = scan_opponent_forcing_moves(board)
    _reveal_opponent(say, opp)

    # ---- Step 2: safety check -------------------------------------------
    _rule(say, "Step 2 — Safety check")
    say("Before you reveal it: is anything of yours hanging (can be won for free)?")
    ask("Name any of your pieces you think are in danger: ")
    hanging = find_hanging_pieces(board, board.turn)
    if hanging:
        say("At risk right now:")
        for h in hanging:
            say(f"  • {h.describe()}")
    else:
        say("Nothing of yours is hanging in this position. Good — but stay alert.")

    # ---- Step 3: candidate moves ----------------------------------------
    _rule(say, "Step 3 — Pick 2-3 candidate moves")
    say("Not twenty. Narrow and deep. Choosing good candidates is the skill.")
    candidate_text = ask("Your candidate moves: ")
    candidates = grading.parse_candidate_moves(board, candidate_text)
    if candidate_text.strip() and not candidates:
        say("(Couldn't read any legal moves from that — carrying on without them.)")

    # ---- Step 4 + 5: calculate and evaluate, then commit an eval --------
    _rule(say, "Step 5 — Evaluate the position (commit before the engine speaks)")
    say("Evaluation is from White's point of view, in pawns.")
    say("e.g.  +1.5 = White is better by ~1.5 pawns,  -2 = Black is better,  0 = equal.")
    eval_text = ask("Your evaluation: ")
    user_eval = grading.parse_eval_guess(eval_text)

    # Now — and only now — the engine speaks.
    return _reveal_engine(
        board, engine, candidates, candidate_text, user_eval, recall, say
    )


# ---------------------------------------------------------------------------
# Reveal helpers
# ---------------------------------------------------------------------------

def _reveal_forcing(say: Say, scan, recall: grading.RecallResult) -> None:
    say("")
    say("The complete list of forcing moves for the side to move:")
    _print_bucket(say, "Checks", scan.checks)
    _print_bucket(say, "Captures", scan.captures)
    _print_bucket(say, "Threats", scan.threats)

    say("")
    if recall.total == 0:
        say("There were no forcing moves here — spotting that is itself the answer.")
    else:
        say(f"You found {len(recall.found)} of {recall.total} forcing moves.")
    if recall.missed:
        say("You missed:")
        for fm in recall.missed:
            say(f"  ✗ {fm.describe()}")
    if recall.spurious:
        say(
            "Not forcing moves (or not legal here): "
            + ", ".join(recall.spurious)
        )


def _print_bucket(say: Say, label: str, moves: list) -> None:
    if moves:
        say(f"  {label}: " + ", ".join(m.describe() for m in moves))
    else:
        say(f"  {label}: none")


def _reveal_opponent(say: Say, opp) -> None:
    say("")
    if opp is None:
        say("(You're in check — deal with that before worrying about their threats.)")
        return
    say("What your opponent could do in reply (their forcing moves):")
    _print_bucket(say, "Checks", opp.checks)
    _print_bucket(say, "Captures", opp.captures)
    _print_bucket(say, "Threats", opp.threats)


def _reveal_engine(
    board: chess.Board,
    engine: Engine | None,
    candidates: list[chess.Move],
    candidate_text: str,
    user_eval: float | None,
    recall: grading.RecallResult,
    say: Say,
) -> DrillResult:
    """Steps 4 and 5's reveal: engine best move, candidate lines, and the eval
    comparison. Then build the DrillResult for the session tracker."""

    fen = board.fen()
    candidate_had_best: bool | None = None
    eval_err: float | None = None
    best_san: str | None = None

    if engine is None:
        say("")
        say("(No engine available — skipping the engine's assessment. Install")
        say(" Stockfish or set STOCKFISH_PATH to enable it.)")
        _show_human_eval(board, say)
        return DrillResult(
            fen, recall.total, len(recall.found), None, None, None
        )

    assessment = engine.assess(board)
    best_san = assessment.best_san

    # Step 4: show each candidate calculated out to a quiet line, with a score.
    if candidates:
        say("")
        say("Step 4 — your candidates, calculated out (engine's continuation):")
        for mv in candidates:
            san = board.san(mv)
            after = engine.evaluate_after(board, mv)
            if after.pv_san:
                say(f"  {san}:  {after.as_text()}   line: {san} {' '.join(after.pv_san)}")
            else:
                say(f"  {san}:  {after.as_text()}")

    # The engine's own choice.
    say("")
    say(f"Engine's best move: {best_san}   (evaluation {assessment.as_text()})")
    if assessment.pv_san:
        say("Main line: " + " ".join(assessment.pv_san))

    candidate_had_best = grading.candidate_contains_best(
        board, candidate_text, assessment.best_move
    )
    if assessment.best_move is not None:
        if candidate_had_best:
            say("✓ The best move was in your candidate list.")
        else:
            say("✗ The best move was NOT in your candidate list.")

    # Step 5: compare your evaluation to the engine's.
    say("")
    if user_eval is None:
        say("(Couldn't read your evaluation, so no comparison this time.)")
    else:
        eval_err = grading.eval_error(user_eval, assessment.pawns)
        say(
            f"Your evaluation: {user_eval:+.2f}   "
            f"Engine: {assessment.pawns:+.2f}   "
            f"Off by {eval_err:.2f} pawns."
        )

    _show_human_eval(board, say)

    return DrillResult(
        fen, recall.total, len(recall.found), candidate_had_best, eval_err, best_san
    )


def _show_human_eval(board: chess.Board, say: Say) -> None:
    """The human decomposition — the *why* behind the number."""
    say("")
    say("Why (the human breakdown — this is what to train your eye on):")
    for line in evaluate_position(board).summary_lines():
        say(f"  • {line}")
