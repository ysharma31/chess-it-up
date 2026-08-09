"""Play a full game against a deliberately weakened Stockfish.

The brief wants games against a beatable opponent (~800-1000 to start), not a
3000-rated monster that teaches only despair. Strength is set on the engine
(see engine.configure_strength); here we just run the game loop and hand back
the move list so it can be reviewed afterwards.

I/O is injected (`ask` / `say`) exactly as in the drill, so this is testable
and terminal-agnostic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import chess

from .engine import Engine
from .render import render_board, turn_line

Ask = Callable[[str], str]
Say = Callable[[str], None]


@dataclass
class PlayedGame:
    """The record of a finished game, ready to review."""

    start_board: chess.Board
    moves: list[chess.Move]
    result: str  # "1-0", "0-1", "1/2-1/2", or "*"
    human_white: bool

    @property
    def final_board(self) -> chess.Board:
        board = self.start_board.copy(stack=False)
        for move in self.moves:
            board.push(move)
        return board


def _parse_move(board: chess.Board, text: str) -> chess.Move | None:
    for parser in (board.parse_san, lambda t: board.parse_uci(t.lower())):
        try:
            move = parser(text)
        except (ValueError, chess.InvalidMoveError, chess.IllegalMoveError,
                chess.AmbiguousMoveError):
            continue
        if move in board.legal_moves:
            return move
    return None


def play_game(
    engine: Engine,
    human_white: bool = True,
    elo: int = 900,
    movetime: float = 0.1,
    ask: Ask = input,
    say: Say = print,
) -> PlayedGame:
    """Run one human-vs-engine game and return the record.

    During your turn you can type a move (SAN like `Nf3` or UCI like `g1f3`),
    `takeback` to undo your last move, or `resign`/`quit` to stop.
    """
    engine.configure_strength(elo=elo)
    human_color = chess.WHITE if human_white else chess.BLACK
    board = chess.Board()
    moves: list[chess.Move] = []

    say(f"New game — you are {'White' if human_white else 'Black'}, "
        f"opponent is Stockfish at {engine.strength_desc}.")
    say("Type moves in algebraic notation. 'takeback' undoes; 'resign' ends.")

    result = "*"
    while not board.is_game_over():
        say("")
        say(render_board(board))
        say(turn_line(board))

        if board.turn == human_color:
            raw = ask("Your move: ").strip()
            cmd = raw.lower()
            if cmd in ("resign", "quit", "exit"):
                result = "0-1" if human_white else "1-0"
                say("You resign.")
                break
            if cmd in ("takeback", "undo"):
                _takeback(board, moves, human_color, say)
                continue
            move = _parse_move(board, raw)
            if move is None:
                say("That isn't a legal move here — try again.")
                continue
            board.push(move)
            moves.append(move)
        else:
            move = engine.play_move(board, movetime=movetime)
            if move is None:
                break
            say(f"Stockfish plays {board.san(move)}.")
            board.push(move)
            moves.append(move)

    if board.is_game_over():
        result = board.result()
        say("")
        say(render_board(board))
        say(_outcome_text(board))

    return PlayedGame(
        start_board=chess.Board(),
        moves=moves,
        result=result,
        human_white=human_white,
    )


def _takeback(
    board: chess.Board, moves: list[chess.Move], human_color: bool, say: Say
) -> None:
    """Undo back to the human's previous turn (their move + the engine reply)."""
    undone = 0
    while board.move_stack and undone < 2:
        board.pop()
        moves.pop()
        undone += 1
        if board.turn == human_color:
            break
    if undone:
        say(f"Took back {undone} half-move(s).")
    else:
        say("Nothing to take back yet.")


def _outcome_text(board: chess.Board) -> str:
    if board.is_checkmate():
        winner = "Black" if board.turn == chess.WHITE else "White"
        return f"Checkmate — {winner} wins ({board.result()})."
    if board.is_stalemate():
        return "Stalemate — the game is a draw."
    if board.is_insufficient_material():
        return "Draw — insufficient material to checkmate."
    if board.can_claim_threefold_repetition():
        return "Draw — threefold repetition."
    if board.is_fifty_moves():
        return "Draw — fifty-move rule."
    return f"Game over ({board.result()})."
