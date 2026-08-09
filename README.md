# Chess Coach

A **decision-procedure trainer** for chess. Not an engine project — a tool that
drills the *thinking routine* a strong player runs in their head, and only uses
an engine (Stockfish) as the answer key at the very end.

The belief this is built around: **strong chess is an algorithm.** A good player
runs a shallow, heavily-pruned search with a hand-tuned evaluation, in their
head. Beginners lose because they run no procedure at all — they look, they feel
something, they move. This software makes the procedure explicit and drills it
until it becomes automatic.

## The five-step routine it teaches

1. **Scan for forcing moves (CCT).** Every turn, before anything else: list all
   **C**hecks, **C**aptures, and **T**hreats — for *both* sides. This is what
   stops you hanging pieces.
2. **Safety check.** Is anything of mine hanging? Am I walking into a fork, pin,
   or skewer?
3. **Pick 2–3 candidate moves.** Narrow and deep, not wide and shallow.
4. **Calculate each candidate until the position is quiet.** Don't stop
   mid-capture.
5. **Evaluate the resulting positions.** Decompose it — material, king safety,
   activity, pawn structure, space — don't eyeball it.

## What's built so far

### Phase 1 — the five-step drill

The interactive five-step drill, on the command line, taking a FEN as input.

The rule that makes it a trainer and not a toy: **it never shows you the answer
before you commit to yours.** It asks you to list the forcing moves *first*, then
grades you. It asks for your candidates and your evaluation *first*, then reveals
Stockfish. Grading your reasoning is the entire product.

Per session it tracks: how many forcing moves you missed, how often your
candidate list contained the best move, and how far off your evaluations were.

### Phase 2 — play and review

Play a full game against a **deliberately weakened** Stockfish (default ~900
Elo — beatable on purpose), then have the coach walk back through it and grade
every move: **best / good / inaccuracy / mistake / blunder**, by how many
centipawns it cost you. For every mistake and blunder it explains the tactic in
plain words — what you left hanging, the fork or pin you walked into, your
opponent's punishing reply, and the move you should have played. It writes the
whole thing out as an **annotated PGN** you can keep or open in any chess app.

You can also review any **saved PGN** the same way, whether Chess Coach produced
it or not.

## Install

Requires Python 3.11+ and (optionally, but recommended) the Stockfish engine.

```bash
# 1. Stockfish — the answer key. On Debian/Ubuntu:
sudo apt install stockfish
# (it lands in /usr/games/stockfish, which may not be on your PATH — that's fine,
#  the app looks there automatically. Or set STOCKFISH_PATH to point at it.)

# 2. Python dependencies, in a virtual environment:
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

The drill runs even without Stockfish — it just skips the engine's assessment at
the end and shows only the human breakdown. Everything else (the CCT scan, the
safety check, the evaluation decomposition) is our own code.

## Use

```bash
# The main event — the interactive drill on a position:
python -m chess_coach drill --fen "r1bqkbnr/pppp1ppp/2n5/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 2 3"

# No FEN drills the starting position:
python -m chess_coach drill

# Quick non-interactive lookups (handy for checking a position):
python -m chess_coach scan --fen "<FEN>"   # just the CCT forcing-move scan
python -m chess_coach eval --fen "<FEN>"   # just the evaluation breakdown

# Phase 2 — play a game vs a weakened engine, then auto-review it:
python -m chess_coach play --elo 900              # play White; --color black to switch
python -m chess_coach play --elo 1200 --no-review # skip the post-game review

# Review any saved PGN and write an annotated copy:
python -m chess_coach review game.pgn -o annotated.pgn
```

During a game, type moves in algebraic notation (`Nf3` or `g1f3`); `takeback`
undoes your last move, `resign` ends the game. Strength below ~1320 is set via
Stockfish's Skill Level (its `UCI_Elo` won't go lower); at or above 1320 the
real Elo limiter is used.

Inside a drill, after each position you can type a move (e.g. `e4`) to play it
and drill the next position, paste a new FEN, or `q` to finish and see your
session summary.

Useful flags: `--depth N` (Stockfish search depth, default 15), `--no-engine`
(run without Stockfish), `--engine-path /path/to/stockfish`.

## How it fits together

| Module | Job |
| --- | --- |
| `forcing.py` | The CCT scanner: every check, capture, and threat for both sides. Includes **static exchange evaluation** (who wins a trade) and hanging-piece detection. |
| `evaluation.py` | The human evaluation checklist: material, king safety, activity, pawn structure, space — in plain language. |
| `engine.py` | A thin, forgiving wrapper around Stockfish (auto-discovers the binary; degrades gracefully if it's missing). |
| `grading.py` | Compares what you said to what was true (lenient move matching, eval error). |
| `session.py` | Tracks your recurring mistakes across a sitting. |
| `drill.py` | The interactive five-step loop that ties it together. |
| `play.py` | Phase 2: the human-vs-weakened-Stockfish game loop. |
| `classify.py` | Phase 2: centipawn loss → best/good/inaccuracy/mistake/blunder. |
| `tactics.py` | Phase 2: plain-language explanations (hanging pieces, forks, pins, mate). |
| `review.py` | Phase 2: grades a whole game and writes the annotated PGN. |
| `cli.py` | The `chess-coach` command line (`drill`, `play`, `review`, `scan`, `eval`). |

## A note on the "threat" and trade math

To judge whether a capture or a threat actually *wins* material, the scanner
uses **static exchange evaluation (SEE)**: it plays out the whole sequence of
captures on a square, each side grabbing with its cheapest piece, and reports
the net result in pawns. That's what lets it say "Nxe5 loses a piece" instead of
just "Nxe5 is a capture".

Two deliberate simplifications, worth knowing since this is a beginner tool:

- SEE ignores pins on the *recapturing* pieces (a pinned defender is still
  counted). This can occasionally make a defence look one pawn better than it is.
- Threat detection asks "if my opponent did nothing, could I win material or
  give mate next move?" — it doesn't check whether they can defend. That's on
  purpose: *naming* the threat is the skill; *refuting* it is the next step of
  your calculation.

## Tests

```bash
python -m pytest
```

The engine tests skip automatically if Stockfish isn't installed.

## Roadmap

- **Phase 1** ✅ — the interactive five-step drill.
- **Phase 2** ✅ — play full games against a weakened Stockfish, then review with
  per-move classification (best / good / inaccuracy / mistake / blunder) and
  plain-language explanations of every blunder. Export annotated PGN.
- **Phase 3** — auto-generate puzzles from your own blunders, with spaced
  repetition and per-motif accuracy tracking (fork, pin, skewer, …). A
  "blindfold" visualisation mode.
- **Phase 4** — photograph your real board and read the position from occupancy
  changes, using the rules of chess as the strong prior.
