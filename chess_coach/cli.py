"""The command-line interface (Typer).

Commands:
  chess-coach drill [--fen FEN]   run the interactive five-step drill
  chess-coach scan  [--fen FEN]   just print the CCT forcing-move scan
  chess-coach eval  [--fen FEN]   just print the human evaluation breakdown
  chess-coach version             show the version

`drill` is the real product; `scan` and `eval` are quick non-interactive
lookups (handy for checking a position, or for me while developing).
"""

from __future__ import annotations

import typer

import chess

from . import __version__
from .drill import run_drill
from .engine import Engine
from .evaluation import evaluate_position
from .forcing import scan_forcing_moves, scan_opponent_forcing_moves
from .render import render_board, turn_line
from .session import Session

app = typer.Typer(
    add_completion=False,
    help="A chess decision-procedure trainer. It drills the thinking, not the moves.",
)


def _make_board(fen: str | None) -> chess.Board:
    if not fen or fen.strip().lower() in ("start", "startpos", ""):
        return chess.Board()
    try:
        return chess.Board(fen.strip())
    except ValueError as exc:
        typer.secho(f"That FEN didn't parse: {exc}", fg=typer.colors.RED)
        raise typer.Exit(code=1)


def _open_engine(depth: int, no_engine: bool, path: str | None) -> Engine | None:
    if no_engine:
        return None
    try:
        return Engine(path=path, depth=depth)
    except Engine.Unavailable as exc:
        typer.secho(str(exc), fg=typer.colors.YELLOW)
        return None


@app.command()
def drill(
    fen: str = typer.Option(
        None, "--fen", "-f", help="Position to drill (FEN). Defaults to the start."
    ),
    depth: int = typer.Option(15, "--depth", "-d", help="Stockfish search depth."),
    no_engine: bool = typer.Option(
        False, "--no-engine", help="Run without Stockfish (skips the engine reveal)."
    ),
    engine_path: str = typer.Option(
        None, "--engine-path", help="Path to the Stockfish binary."
    ),
):
    """Run the interactive five-step drill on a position.

    After each position you can play a move to advance to the next one, paste a
    new FEN, or quit. A session summary is printed at the end.
    """
    board = _make_board(fen)
    session = Session()
    engine = _open_engine(depth, no_engine, engine_path)

    try:
        while True:
            result = run_drill(board, engine=engine)
            session.record(result)

            typer.echo("")
            choice = typer.prompt(
                "Next? Enter a move to play (e.g. e4), a FEN to load, "
                "or 'q' to finish",
                default="q",
            ).strip()

            if choice.lower() in ("q", "quit", "exit"):
                break

            advanced = _try_play_move(board, choice)
            if advanced:
                continue
            # Not a move — try to read it as a new FEN.
            try:
                board = chess.Board(choice)
            except ValueError:
                typer.secho(
                    "Didn't recognise that as a move or a FEN. Finishing up.",
                    fg=typer.colors.YELLOW,
                )
                break
    finally:
        if engine is not None:
            engine.close()

    typer.echo("")
    typer.echo("=" * 64)
    typer.secho("Session summary", bold=True)
    for line in session.summary_lines():
        typer.echo(f"  {line}")


def _try_play_move(board: chess.Board, text: str) -> bool:
    """Attempt to play `text` as a move on `board`. Returns True on success."""
    for parser in (board.parse_san, lambda t: board.parse_uci(t.lower())):
        try:
            move = parser(text)
        except (ValueError, chess.InvalidMoveError, chess.IllegalMoveError,
                chess.AmbiguousMoveError):
            continue
        if move in board.legal_moves:
            board.push(move)
            return True
    return False


@app.command()
def scan(
    fen: str = typer.Option(None, "--fen", "-f", help="Position (FEN)."),
):
    """Print the CCT forcing-move scan for a position (non-interactive)."""
    board = _make_board(fen)
    typer.echo(render_board(board))
    typer.echo("")
    typer.echo(turn_line(board))

    s = scan_forcing_moves(board)
    typer.echo("")
    typer.secho("Side to move — forcing moves:", bold=True)
    _echo_bucket("Checks", s.checks)
    _echo_bucket("Captures", s.captures)
    _echo_bucket("Threats", s.threats)

    opp = scan_opponent_forcing_moves(board)
    typer.echo("")
    if opp is None:
        typer.echo("(Side to move is in check — opponent scan skipped.)")
    else:
        typer.secho("Opponent — forcing moves:", bold=True)
        _echo_bucket("Checks", opp.checks)
        _echo_bucket("Captures", opp.captures)
        _echo_bucket("Threats", opp.threats)


def _echo_bucket(label: str, moves: list) -> None:
    if moves:
        typer.echo(f"  {label}: " + ", ".join(m.describe() for m in moves))
    else:
        typer.echo(f"  {label}: none")


@app.command(name="eval")
def eval_cmd(
    fen: str = typer.Option(None, "--fen", "-f", help="Position (FEN)."),
    depth: int = typer.Option(15, "--depth", "-d", help="Stockfish search depth."),
    no_engine: bool = typer.Option(False, "--no-engine", help="Skip Stockfish."),
    engine_path: str = typer.Option(None, "--engine-path", help="Stockfish path."),
):
    """Print the human evaluation breakdown (and the engine number, if available)."""
    board = _make_board(fen)
    typer.echo(render_board(board))
    typer.echo("")
    typer.echo(turn_line(board))

    engine = _open_engine(depth, no_engine, engine_path)
    if engine is not None:
        try:
            assessment = engine.assess(board)
            typer.echo("")
            typer.secho(f"Engine: {assessment.as_text()}", bold=True)
            if assessment.best_san:
                typer.echo(f"Best move: {assessment.best_san}")
        finally:
            engine.close()

    typer.echo("")
    typer.secho("Human breakdown:", bold=True)
    for line in evaluate_position(board).summary_lines():
        typer.echo(f"  • {line}")


@app.command()
def version():
    """Show the version."""
    typer.echo(f"chess-coach {__version__}")


if __name__ == "__main__":
    app()
