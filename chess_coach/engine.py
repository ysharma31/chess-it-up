"""A thin, forgiving wrapper around Stockfish (the answer key).

The trainer works without an engine — the CCT scan and the evaluation
decomposition are all our own code. Stockfish only comes in at the end, to
grade your candidate moves and your evaluation guess. So this wrapper is built
to *degrade gracefully*: if the binary can't be found, the drill still runs,
it just skips the "here's what the engine thinks" reveal.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass

import chess
import chess.engine

# Places Stockfish commonly lives. STOCKFISH_PATH (env var) wins if set. The
# Debian/Ubuntu package installs to /usr/games, which is often not on PATH.
_CANDIDATE_PATHS = [
    "/usr/games/stockfish",
    "/usr/local/bin/stockfish",
    "/usr/bin/stockfish",
    "/opt/homebrew/bin/stockfish",
    "stockfish.exe",
]

# A large pawn value standing in for "mate". Real mate scores are reported
# separately (see Assessment.mate), but for arithmetic (how far off was your
# guess?) we need a number, and +/-100 pawns is effectively winning/losing.
MATE_PAWNS = 100.0


def find_stockfish() -> str | None:
    """Locate a Stockfish binary, or return None if there isn't one."""
    env = os.environ.get("STOCKFISH_PATH")
    if env and shutil.which(env):
        return shutil.which(env)
    if env and os.path.isfile(env):
        return env

    on_path = shutil.which("stockfish")
    if on_path:
        return on_path

    for path in _CANDIDATE_PATHS:
        if os.path.isfile(path):
            return path
    return None


@dataclass
class Assessment:
    """What the engine thinks of a position, from White's point of view.

    pawns: positive = good for White, negative = good for Black.
    mate:  moves-to-mate if forced mate is seen (positive = White mates), else None.
    best_move / best_san: the engine's top choice (None if no legal move).
    pv_san: the start of the engine's main line, in readable notation.
    """

    pawns: float
    mate: int | None
    best_move: chess.Move | None
    best_san: str | None
    pv_san: list[str]

    def as_text(self) -> str:
        """e.g. '+1.4', 'mate in 3 for White', or 'checkmate — White wins'."""
        if self.mate is not None:
            if self.mate == 0:
                # The position on the board is already checkmate; the winner is
                # whoever just delivered it (read off the pawn sign, +100/-100).
                winner = "White" if self.pawns > 0 else "Black"
                return f"checkmate — {winner} wins"
            side = "White" if self.mate > 0 else "Black"
            return f"mate in {abs(self.mate)} for {side}"
        return f"{self.pawns:+.2f}"


class Engine:
    """Context-managed Stockfish. Use `with Engine() as eng:`.

    Raises EngineUnavailable at construction if no binary is found, so callers
    can catch it and fall back to an engine-free drill.
    """

    class Unavailable(RuntimeError):
        pass

    def __init__(self, path: str | None = None, depth: int = 15, skill: int | None = None):
        self.path = path or find_stockfish()
        if not self.path:
            raise Engine.Unavailable(
                "Stockfish not found. Install it (e.g. `apt install stockfish`) "
                "or set STOCKFISH_PATH. The drill still runs without it."
            )
        self.depth = depth
        self._engine = chess.engine.SimpleEngine.popen_uci(self.path)
        if skill is not None:
            # Skill Level (0-20) is how Phase 2 will weaken the engine to play
            # a beginner. Not used by Phase 1's analysis, but wired up here.
            self._engine.configure({"Skill Level": max(0, min(20, skill))})

    # -- context manager ---------------------------------------------------
    def __enter__(self) -> "Engine":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def close(self) -> None:
        try:
            self._engine.quit()
        except Exception:
            pass

    # -- analysis ----------------------------------------------------------
    def _limit(self) -> chess.engine.Limit:
        return chess.engine.Limit(depth=self.depth)

    def assess(self, board: chess.Board, pv_len: int = 6) -> Assessment:
        """Analyse a position and return a White-POV Assessment."""
        if board.is_game_over():
            return self._terminal_assessment(board)

        info = self._engine.analyse(board, self._limit())
        score = info["score"].white()
        pv = info.get("pv", []) or []

        best_move = pv[0] if pv else None
        best_san = board.san(best_move) if best_move else None
        pv_san = self._line_to_san(board, pv[:pv_len])

        return Assessment(
            pawns=self._score_to_pawns(score),
            mate=score.mate(),
            best_move=best_move,
            best_san=best_san,
            pv_san=pv_san,
        )

    def evaluate_after(self, board: chess.Board, move: chess.Move, pv_len: int = 6) -> Assessment:
        """Assess the position that results from playing `move` (White-POV).

        This is how the drill scores each of your candidate moves and shows the
        forced continuation ("calculate until the position is quiet").
        """
        board.push(move)
        try:
            assessment = self.assess(board, pv_len=pv_len)
        finally:
            board.pop()
        return assessment

    # -- helpers -----------------------------------------------------------
    @staticmethod
    def _score_to_pawns(score: chess.engine.Score) -> float:
        mate = score.mate()
        if mate is not None:
            return MATE_PAWNS if mate > 0 else -MATE_PAWNS
        cp = score.score()
        return (cp or 0) / 100.0

    @staticmethod
    def _line_to_san(board: chess.Board, moves: list[chess.Move]) -> list[str]:
        line, work = [], board.copy(stack=False)
        for mv in moves:
            line.append(work.san(mv))
            work.push(mv)
        return line

    def _terminal_assessment(self, board: chess.Board) -> Assessment:
        if board.is_checkmate():
            # Side to move is checkmated: bad for whoever is to move.
            pawns = -MATE_PAWNS if board.turn == chess.WHITE else MATE_PAWNS
            return Assessment(pawns, 0, None, None, [])
        return Assessment(0.0, None, None, None, [])  # stalemate / draw
