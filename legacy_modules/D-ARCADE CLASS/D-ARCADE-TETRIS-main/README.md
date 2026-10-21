# D-ARCADE-TETRIS
This project is one of the games from the side branch of project DILARA called: D-Arcade 

A classic-inspired Tetris clone built with Python and `pygame` — WASD controls, a persistent local leaderboard, and a fixed, no-surprises fall speed so the challenge stays in your stacking, not a creeping clock.

## Features

- **7-bag randomizer** — every piece appears exactly once per bag, so you'll never get a brutal drought of the piece you need.
- **WASD controls** with proper held-key auto-repeat (DAS/ARR-style), so holding a direction moves continuously instead of requiring repeated taps.
- **Ghost piece** preview showing where the current piece will land.
- **Next piece** preview panel.
- **Fixed fall speed** — gravity does not accelerate as you play; the challenge comes from your play, not a ramping timer.
- **Persistent leaderboard** — top 10 scores saved locally to `leaderboard.json`, with an initials-entry prompt when you post a qualifying score.
- **Adjustable visuals** — block spacing/margin is a single constant, easy to retune.

## Requirements

- Python 3.8+
- `pygame`

Install pygame if you don't already have it:

```bash
pip install pygame
```

## Running the game

```bash
python3 tetris.py
```

## Controls

| Key      | Action                  |
|----------|--------------------------|
| `A`      | Move left (hold to repeat) |
| `D`      | Move right (hold to repeat) |
| `S`      | Soft drop (hold to repeat) |
| `W`      | Rotate                  |
| `Space`  | Hard drop                |
| `P`      | Pause / unpause          |
| `Esc`    | Quit to leaderboard / exit |
| `Enter`  | Confirm on leaderboard / game over screens |

## Scoring

| Lines cleared | Points (× level) |
|----------------|------------------|
| 1              | 100              |
| 2              | 300              |
| 3              | 500              |
| 4 (Tetris)     | 800              |

Soft drop and hard drop also award small bonus points per row dropped. Level increases every 10 lines cleared (affecting score multiplier only — not fall speed).

## Leaderboard

Scores are stored locally in `leaderboard.json`, created in the same folder as `tetris.py` the first time you play. The top 10 all-time scores are kept, sorted highest first. If your run qualifies, you'll be prompted for up to 8 initials before returning to the leaderboard screen.

## Configuration

A few constants near the top of `tetris.py` are the easiest levers to tweak:

- `BLOCK_MARGIN` — visual gap between blocks (in pixels). Set to `0` for classic flush blocks.
- `CELL_SIZE` — size of each grid cell in pixels.
- `DAS_DELAY` / `ARR` / `SOFT_DROP_ARR` — how long a key must be held before auto-repeat kicks in, and how fast it repeats afterward.
- `MAX_LEADERBOARD_ENTRIES` — how many scores the leaderboard keeps.

## Project structure

```
D-ARCADE-Tetris/
├── tetris.py         # Game source
├── leaderboard.json  # Auto-generated on first play; stores top scores
└── README.md
```

## Roadmap ideas

- Additional D-ARCADE titles alongside Tetris (chess, tic-tac-toe, etc.)
- Shared/synced leaderboard across games
- Hold-piece slot
- Alternate color themes
