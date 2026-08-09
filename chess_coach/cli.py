"""The command-line interface (Typer).

Commands:
  chess-coach drill  [--fen FEN]   run the interactive five-step drill
  chess-coach scan   [--fen FEN]   just print the CCT forcing-move scan
  chess-coach eval   [--fen FEN]   just print the human evaluation breakdown
  chess-coach play   [--elo N]     play a game vs a weakened Stockfish, then review
  chess-coach review GAME.pgn      review a saved PGN and annotate it
  chess-coach version              show the version

`drill` (Phase 1) and `play`/`review` (Phase 2) are the real product; `scan`
and `eval` are quick non-interactive lookups.
"""

from __future__ import annotations

import typer

import chess
import chess.pgn

from . import __version__
from .drill import run_drill
from .engine import Engine
from .evaluation import evaluate_position
from .forcing import scan_forcing_moves, scan_opponent_forcing_moves
from . import review as review_mod
from .play import play_game
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
def play(
    color: str = typer.Option("white", "--color", "-c", help="Play as white or black."),
    elo: int = typer.Option(900, "--elo", "-e", help="Opponent strength (~Elo)."),
    movetime: float = typer.Option(
        0.1, "--movetime", help="Seconds the engine thinks per move."
    ),
    depth: int = typer.Option(
        15, "--depth", "-d", help="Search depth for the post-game review."
    ),
    engine_path: str = typer.Option(None, "--engine-path", help="Stockfish path."),
    no_review: bool = typer.Option(
        False, "--no-review", help="Skip the automatic review after the game."
    ),
):
    """Play a full game against a weakened Stockfish, then review it move by move."""
    human_white = color.strip().lower() not in ("black", "b")

    try:
        engine = Engine(path=engine_path, depth=depth)
    except Engine.Unavailable as exc:
        typer.secho(str(exc), fg=typer.colors.RED)
        typer.secho("Playing needs Stockfish. Install it and try again.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    try:
        game = play_game(
            engine, human_white=human_white, elo=elo, movetime=movetime,
            ask=lambda p: typer.prompt(p.rstrip(), prompt_suffix=""), say=typer.echo,
        )

        if no_review or not game.moves:
            return

        typer.echo("")
        typer.secho("Reviewing your game at full strength…", fg=typer.colors.CYAN)
        engine.configure_strength()  # back to full power for honest analysis
        reviewed = review_mod.review_moves(game.start_board, game.moves, engine)
    finally:
        engine.close()

    typer.echo("")
    for line in review_mod.format_report(reviewed):
        typer.echo(line)

    white = "You" if human_white else "Stockfish"
    black = "Stockfish" if human_white else "You"
    pgn_game = review_mod.to_annotated_pgn(
        game.start_board, reviewed, white=white, black=black, result=game.result
    )
    path = _default_pgn_path()
    review_mod.write_pgn(pgn_game, path)
    typer.echo("")
    typer.secho(f"Annotated game saved to {path}", fg=typer.colors.GREEN)


@app.command()
def review(
    pgn: str = typer.Argument(..., help="Path to a .pgn file to review."),
    depth: int = typer.Option(15, "--depth", "-d", help="Search depth."),
    engine_path: str = typer.Option(None, "--engine-path", help="Stockfish path."),
    out: str = typer.Option(
        None, "--out", "-o", help="Where to write the annotated PGN."
    ),
):
    """Review a saved PGN game move by move and write an annotated copy."""
    try:
        with open(pgn, encoding="utf-8") as fh:
            game = chess.pgn.read_game(fh)
    except OSError as exc:
        typer.secho(f"Couldn't open {pgn}: {exc}", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    if game is None:
        typer.secho("No game found in that file.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    start_board = game.board()  # respects a FEN/SetUp header if present
    moves = list(game.mainline_moves())
    if not moves:
        typer.secho("That game has no moves to review.", fg=typer.colors.YELLOW)
        raise typer.Exit(code=1)

    try:
        engine = Engine(path=engine_path, depth=depth)
    except Engine.Unavailable as exc:
        typer.secho(str(exc), fg=typer.colors.RED)
        raise typer.Exit(code=1)
    try:
        reviewed = review_mod.review_moves(start_board, moves, engine)
    finally:
        engine.close()

    for line in review_mod.format_report(reviewed):
        typer.echo(line)

    annotated = review_mod.to_annotated_pgn(
        start_board,
        reviewed,
        white=game.headers.get("White", "White"),
        black=game.headers.get("Black", "Black"),
        result=game.headers.get("Result", "*"),
    )
    path = out or _default_pgn_path()
    review_mod.write_pgn(annotated, path)
    typer.echo("")
    typer.secho(f"Annotated game saved to {path}", fg=typer.colors.GREEN)


def _default_pgn_path() -> str:
    import datetime

    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"chess-coach-{stamp}.pgn"


@app.command()
def version():
    """Show the version."""
    typer.echo(f"chess-coach {__version__}")


if __name__ == "__main__":
    app()
