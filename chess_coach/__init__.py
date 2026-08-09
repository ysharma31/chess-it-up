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
"""

__version__ = "0.1.0"
