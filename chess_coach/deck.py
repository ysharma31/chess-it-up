"""The puzzle deck: a portable JSON file of your puzzles and your track record.

The deck holds every puzzle generated from your games, their spaced-repetition
schedules, and — the part the brief really cares about — a running tally of your
accuracy *per motif*. That last bit is what lets the coach say "you're 40% on
pins but 90% on forks; drill pins", which is the whole point: it tells you what
you're actually weak at, not what you think you're weak at.
"""

from __future__ import annotations

import datetime
import json
import os
from dataclasses import dataclass, field

from . import srs
from .puzzles import Puzzle


@dataclass
class Deck:
    puzzles: list[Puzzle] = field(default_factory=list)
    # motif -> {"attempts": int, "correct": int}
    motif_stats: dict[str, dict[str, int]] = field(default_factory=dict)

    # -- membership --------------------------------------------------------
    def _by_id(self) -> dict[str, Puzzle]:
        return {p.id: p for p in self.puzzles}

    def add(self, puzzle: Puzzle) -> bool:
        """Add a puzzle. Returns False if it was already in the deck."""
        if puzzle.id in self._by_id():
            return False
        self.puzzles.append(puzzle)
        return True

    def add_many(self, puzzles: list[Puzzle]) -> int:
        return sum(1 for p in puzzles if self.add(p))

    # -- scheduling --------------------------------------------------------
    def due(self, today: datetime.date | None = None) -> list[Puzzle]:
        """Puzzles ready to be seen today, hardest-swing first."""
        today = today or datetime.date.today()
        ready = [p for p in self.puzzles if srs.is_due(p.due, today)]
        ready.sort(key=lambda p: p.swing_cp, reverse=True)
        return ready

    def record_attempt(
        self, puzzle: Puzzle, correct: bool, today: datetime.date | None = None
    ) -> None:
        """Update a puzzle's schedule and the per-motif accuracy after an attempt."""
        today = today or datetime.date.today()

        puzzle.ease, puzzle.interval, puzzle.reps = srs.update(
            puzzle.ease, puzzle.interval, puzzle.reps, correct
        )
        puzzle.due = srs.due_date(today, puzzle.interval).isoformat()
        puzzle.attempts += 1
        if correct:
            puzzle.correct += 1

        for motif in puzzle.motifs or ["untagged"]:
            stat = self.motif_stats.setdefault(motif, {"attempts": 0, "correct": 0})
            stat["attempts"] += 1
            if correct:
                stat["correct"] += 1

    # -- reporting ---------------------------------------------------------
    def motif_accuracy(self) -> dict[str, tuple[int, int, float]]:
        """motif -> (correct, attempts, percent). Worst accuracy is the weak spot."""
        out: dict[str, tuple[int, int, float]] = {}
        for motif, stat in self.motif_stats.items():
            attempts = stat["attempts"]
            correct = stat["correct"]
            pct = (100.0 * correct / attempts) if attempts else 0.0
            out[motif] = (correct, attempts, pct)
        return out

    def stats_lines(self, today: datetime.date | None = None) -> list[str]:
        today = today or datetime.date.today()
        lines = [
            f"Deck: {len(self.puzzles)} puzzle(s), {len(self.due(today))} due now.",
        ]
        acc = self.motif_accuracy()
        if not acc:
            lines.append("No attempts yet — train some puzzles to see your weak motifs.")
            return lines
        lines.append("Accuracy by motif (weakest first):")
        for motif, (correct, attempts, pct) in sorted(acc.items(), key=lambda kv: kv[1][2]):
            lines.append(f"  {motif:<20} {correct}/{attempts}  ({pct:.0f}%)")
        return lines

    # -- persistence -------------------------------------------------------
    def to_dict(self) -> dict:
        return {
            "puzzles": [p.to_dict() for p in self.puzzles],
            "motif_stats": self.motif_stats,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Deck":
        return cls(
            puzzles=[Puzzle.from_dict(d) for d in data.get("puzzles", [])],
            motif_stats=data.get("motif_stats", {}),
        )

    def save(self, path: str) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(self.to_dict(), fh, indent=2)

    @classmethod
    def load(cls, path: str) -> "Deck":
        """Load a deck, or return an empty one if the file doesn't exist yet."""
        if not os.path.exists(path):
            return cls()
        with open(path, encoding="utf-8") as fh:
            return cls.from_dict(json.load(fh))


def default_deck_path() -> str:
    """Where the deck lives by default: ~/.chess_coach/deck.json."""
    return os.path.join(os.path.expanduser("~"), ".chess_coach", "deck.json")
