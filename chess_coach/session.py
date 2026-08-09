"""Track your recurring mistakes across a sitting.

The brief asks the trainer to record, per session: how many forcing moves you
missed, how often your candidate list contained the best move, and how far off
your evaluations were. That is what tells you what to work on — which is the
whole point of a trainer, as opposed to a toy that shows engine lines.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class DrillResult:
    """The outcome of a single position's drill."""

    fen: str
    forcing_total: int
    forcing_found: int
    candidate_had_best: bool | None  # None if the engine wasn't consulted
    eval_error: float | None  # pawns off, or None if not graded
    best_san: str | None

    @property
    def forcing_missed(self) -> int:
        return self.forcing_total - self.forcing_found


@dataclass
class Session:
    """A run of drills, with a summary you can act on."""

    results: list[DrillResult] = field(default_factory=list)

    def record(self, result: DrillResult) -> None:
        self.results.append(result)

    @property
    def positions(self) -> int:
        return len(self.results)

    @property
    def total_forcing(self) -> int:
        return sum(r.forcing_total for r in self.results)

    @property
    def total_forcing_missed(self) -> int:
        return sum(r.forcing_missed for r in self.results)

    def forcing_recall_pct(self) -> float | None:
        """Percent of forcing moves you spotted across the session."""
        if self.total_forcing == 0:
            return None
        found = self.total_forcing - self.total_forcing_missed
        return 100.0 * found / self.total_forcing

    def candidate_hit_rate(self) -> float | None:
        """Of positions where the engine had a best move, how often was it in
        your candidate list?"""
        graded = [r for r in self.results if r.candidate_had_best is not None]
        if not graded:
            return None
        hits = sum(1 for r in graded if r.candidate_had_best)
        return 100.0 * hits / len(graded)

    def average_eval_error(self) -> float | None:
        """Your average evaluation error, in pawns."""
        errors = [r.eval_error for r in self.results if r.eval_error is not None]
        if not errors:
            return None
        return sum(errors) / len(errors)

    def summary_lines(self) -> list[str]:
        """Human-readable end-of-session report."""
        if not self.results:
            return ["No positions drilled this session."]

        lines = [f"You drilled {self.positions} position(s)."]

        recall = self.forcing_recall_pct()
        if recall is not None:
            lines.append(
                f"Forcing moves spotted: {self.total_forcing - self.total_forcing_missed}"
                f"/{self.total_forcing} ({recall:.0f}%). "
                f"Missed {self.total_forcing_missed}."
            )

        hit = self.candidate_hit_rate()
        if hit is not None:
            lines.append(f"Best move was among your candidates {hit:.0f}% of the time.")

        avg = self.average_eval_error()
        if avg is not None:
            lines.append(f"Average evaluation error: {avg:.2f} pawns.")

        return lines
