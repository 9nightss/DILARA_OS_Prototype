# D-ARCADE-Trolightcycle
This project is one of the games from the side branch of project DILARA called: D-Arcade

A Python/pygame prototype of the classic Tron light cycle arena game — grid-locked movement, permanent light-trail walls, and a from-scratch Voronoi-based AI opponent. Includes a standalone AI-vs-AI test harness for tuning bot behavior outside of actual gameplay.

This is an experimental prototype, built iteratively — expect rough edges and placeholder art.

## Files

| File | Purpose |
|---|---|
| `D-ARCADE-Tron-Lightcycle.py` | The main playable game (Player 1 vs. Player 2/AI) |
| `highscores.csv` | Auto-generated top-10 leaderboard (created on first run, gitignore recommended) |

## Requirements

- Python 3.9+
- `pygame` or `pygame-ce`

```bash
pip install pygame
# or, if you're using the community fork:
pip install pygame-ce
```

## Running the game

```bash
python tron_lightcycle.py
```

### Controls

| Key | Action |
|---|---|
| `W A S D` | Player 1 movement |
| `Arrow Keys` | Player 2 movement (only active when Player 2 is human-controlled) |
| `T` | Toggle Player 2 between AI and human control |
| `R` | Restart after a round ends |
| `ESC` | Quit (or skip name entry, if that's active) |

### Rules

- Both cycles move at a constant, static speed — one grid cell per tick, no acceleration, no braking.
- Every cell a cycle passes through becomes a permanent wall. Walls never disappear.
- Hitting any wall — your own, your opponent's, or the arena boundary — is instant death.
- Last cycle standing wins the round. Both crashing simultaneously (e.g. a head-on collision) is a draw.

## The AI opponent

Player 2 defaults to an AI (`AIPlayer`), built in two layers:

1. **Reactive survival** — any move that would hit a wall or the boundary next tick is discarded outright, no exceptions.
2. **Voronoi territory scoring** — among the moves that survive, the AI compares BFS distance maps grown from its own candidate position and from the opponent's current position. Every open cell is "claimed" by whichever cycle would reach it first; the AI picks the move that maximizes *(cells it would claim) − (cells the opponent would claim)*.

To avoid being fully deterministic and memorizable, if the top-scoring moves are within `AI_TIE_THRESHOLD` cells of each other, the AI picks randomly among them instead of always taking the single best-scoring option.

**Deliberate scope limit:** the AI does not predict the opponent's next move — it only reacts to walls that already exist. This keeps its behavior legible (a human can always explain a turn by pointing at a wall on screen) at the cost of occasional head-on collisions when both cycles are on a direct, wall-free collision course. This is intentional, not a bug.

## Scoring & leaderboard

- A hidden timer starts the instant a round begins and is never displayed during play.
- On round end, score = `floor(seconds survived) × 100` (e.g. surviving 1:25 → 8500 points), regardless of whether the round was won, lost, or drawn.
- Every end screen offers arcade-style name entry (up to 8 characters, `ENTER` to confirm, `ESC` to skip).
- Scores are deduplicated per name — a new score only overwrites that name's entry in the table if it's actually higher, and the game flags it as a **"NEW PERSONAL BEST!"** on screen when it is.
- The top 10 scores persist to `highscores.csv` next to the script, reloaded on launch.
- Every 3rd end screen shown in a session additionally displays the full top-10 leaderboard (name + score only).



| Flag | Effect |
|---|---|
| `--visual` | Watch matches in a pygame window instead of running headless batches |
| `--matches N` | Number of matches to simulate in batch mode (default: 20) |
| `--tie-threshold N` | Override `AI_TIE_THRESHOLD` for this run only |
| `--seed N` | Fix the random seed for reproducible runs |

Visual mode controls: `SPACE` skips to the next match immediately, `ESC` quits.

**Notes from testing:**
- Starting positions are intentionally offset (not perfectly mirrored) — two identical bots placed in perfectly symmetric starting positions will otherwise walk straight into each other 100% of the time, since neither has a reason to turn before the other does. The offset must be asymmetric (not split evenly between both sides) to actually break this, since a symmetric split preserves the same 180°-rotational symmetry that causes it.
- Starting sides alternate every match specifically so you can sanity-check for positional bias — if one identity wins meaningfully more often than the other despite running identical logic, that's a sign of an arena/setup bias, not a smarter bot.
- Batch mode is CPU-bound (BFS flood-fills over the full 80×60 grid, several times per tick per bot) — expect a few seconds per match. Ctrl+C at any point during a batch run prints stats for whatever finished so far instead of a raw traceback.

## Known limitations / roadmap

- **No custom icons yet** — cycle heads currently render as colored placeholder triangles. `Player.icon_path` + `load_icon()` are already wired up to auto-load, scale, and rotate a sprite per player once image assets exist.
- **No opponent-move prediction** in the AI (see above) — accepted tradeoff for legibility, revisit if head-on collisions become a real gameplay complaint rather than a rare edge case.
