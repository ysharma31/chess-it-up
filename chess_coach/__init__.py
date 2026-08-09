"""Chess Coach — a decision-procedure trainer.

This is not an engine project. It is a trainer for the *procedure* a strong
player runs in their head. The engine (Stockfish) is only the answer key.

Phase 1 lives in these modules:

- forcing:    the "CCT" scanner — every Check, Capture, and Threat, for both
              sides, plus static exchange evaluation (who wins a trade) and
              hanging-piece detection.
- evaluation: decompose a position the way a human should — material, king
              safety, piece activity, pawn structure, space.
- engine:     a thin, forgiving wrapper around Stockfish.
- grading:    compare what you said to what was true.
- session:    track your recurring mistakes across a sitting.
- drill:      the interactive five-step loop that ties it all together.

Phase 2 adds play-and-review:

- play:       a game loop against a deliberately weakened Stockfish.
- classify:   grade a move by its centipawn loss (best..blunder).
- tactics:    explain a mistake in plain words (hanging piece, fork, pin, mate).
- review:     grade a whole game and export an annotated PGN.

Phase 3 turns your mistakes into training:

- motifs:     tag a tactic (fork, pin, skewer, discovered attack, back rank, …).
- puzzles:    make a puzzle from every sharp eval swing in your games.
- srs:        spaced-repetition scheduling (SM-2), so patterns recur on time.
- deck:       a JSON store of puzzles plus your accuracy per motif.
- blindfold:  show a position, hide it, then ask what is under attack.
"""

__version__ = "0.1.0"
