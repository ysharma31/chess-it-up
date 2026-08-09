"""Turn a board into something readable in a terminal.

Small on purpose. python-chess can render a unicode board; we add file/rank
labels and a note of whose move it is so a beginner always knows which way is
up and who is thinking.
"""

from __future__ import annotations

import chess


def render_board(board: chess.Board, unicode: bool = True) -> str:
    """A labelled board from the side-to-move-agnostic White's perspective."""
    if unicode:
        # Unicode glyphs, black on empty squares shown as a middle dot.
        grid = board.unicode(borders=False, empty_square="·", orientation=chess.WHITE)
    else:
        grid = str(board)

    rows = grid.split("\n")
    labelled = []
    for i, row in enumerate(rows):
        rank = 8 - i
        labelled.append(f"{rank}  {row}")
    labelled.append("")
    labelled.append("   a b c d e f g h")
    return "\n".join(labelled)


def turn_line(board: chess.Board) -> str:
    who = "White" if board.turn == chess.WHITE else "Black"
    check = "  (in check!)" if board.is_check() else ""
    return f"{who} to move.{check}"
