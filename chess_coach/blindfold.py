"""Blindfold mode: show the position, hide it, then ask what's under attack.

Visualisation is trainable and undertrained. You look at a position for a few
seconds, it disappears, and you have to say — from memory — which of your pieces
your opponent is attacking. It forces you to hold the board in your head, which
is exactly the muscle that lets stronger players calculate lines they can't see.

Grading is against the pieces that are genuinely attacked: your pieces that an
enemy piece could capture. I/O and the clock are injected so this is testable
without actually sleeping.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Callable

import chess

from .render import render_board, turn_line

Ask = Callable[[str], str]
Say = Callable[[str], None]
Sleep = Callable[[float], None]


def attacked_pieces(board: chess.Board, color: bool) -> set[int]:
    """Squares holding a `color` piece that an enemy piece attacks."""
    enemy = not color
    return {
        sq
        for sq in chess.SQUARES
        if (p := board.piece_at(sq)) and p.color == color and board.attackers(enemy, sq)
    }


def parse_squares(text: str) -> set[str]:
    """Pull square names (like 'e4') out of a free-text answer."""
    return set(re.findall(r"[a-h][1-8]", text.lower()))


@dataclass
class BlindfoldResult:
    found: set[str]
    missed: set[str]
    wrong: set[str]  # squares the user named that weren't actually attacked

    @property
    def all_correct(self) -> bool:
        return not self.missed and not self.wrong


def run_blindfold(
    board: chess.Board,
    ask: Ask = input,
    say: Say = print,
    sleep: Sleep = time.sleep,
    reveal_seconds: float = 10.0,
) -> BlindfoldResult:
    """Show the board, hide it, then quiz which of your pieces are attacked."""
    say("Blindfold drill — study the position, then it disappears.")
    say("")
    say(render_board(board))
    say(turn_line(board))
    say(f"(hiding in {reveal_seconds:.0f} seconds…)")

    sleep(reveal_seconds)

    say("\n" * 30)  # scroll the board out of sight
    say("Board hidden.")
    answer = ask(
        "From memory: which of your pieces are under attack? (list squares, e.g. e5 c4): "
    )

    target_squares = attacked_pieces(board, board.turn)
    target_names = {chess.square_name(sq) for sq in target_squares}
    named = parse_squares(answer)

    result = BlindfoldResult(
        found=named & target_names,
        missed=target_names - named,
        wrong=named - target_names,
    )

    say("")
    say(render_board(board))  # reveal it again
    if not target_names:
        say("Nothing of yours was actually under attack.")
        if result.wrong:
            say("You named: " + ", ".join(sorted(result.wrong)) + " — none were attacked.")
    else:
        say("Under attack: " + ", ".join(sorted(target_names)) + ".")
        if result.found:
            say("You spotted: " + ", ".join(sorted(result.found)) + ".")
        if result.missed:
            say("You missed: " + ", ".join(sorted(result.missed)) + ".")
        if result.wrong:
            say("Not actually attacked: " + ", ".join(sorted(result.wrong)) + ".")
    return result
