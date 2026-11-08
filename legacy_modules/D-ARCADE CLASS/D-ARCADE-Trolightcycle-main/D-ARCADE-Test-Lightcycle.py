# ======================================================================================================
#  ______   ___  _   _ ___ ____ _   _ _____  __        ___   _ ____    _   _ _____ ____  _____  ______  
# / / / /  / _ \| \ | |_ _/ ___| | | |_   _| \ \      / / | | / ___|  | | | | ____|  _ \| ____| \ \ \ \ 
#/ / / /  | (_) |  \| || | |  _| |_| | | |    \ \ /\ / /| | | \___ \  | |_| |  _| | |_) |  _|    \ \ \ \
#\ \ \ \   \__, | |\  || | |_| |  _  | | |     \ V  V / | |_| |___) | |  _  | |___|  _ <| |___   / / / /
# \_\_\_\    /_/|_| \_|___\____|_| |_| |_|      \_/\_/   \___/|____/  |_| |_|_____|_| \_\_____| /_/_/_/ 
# ======================================================================================================
# Four-cycle free-for-all replicating the classic Tron light cycle rules:
# you (Blue, top-left) against three AI cycles, one in each other corner.

# Controls:
#    Player 1 (Blue) : W A S D
#    Player 2 (Side to side PvP): Arrow Keys other than that its mostly ai based
#    (T toggles P2 between AI and a second human; the other two cycles stay AI)

# Rules:
#    - All cycles move at a constant, static speed (grid-locked movement).
#    - Every cell a cycle passes through becomes a wall - until that cycle
#      crashes, at which point its entire trail disappears from the arena.
#    - Hitting any wall (yours, theirs, or the arena boundary) = instant death.
#    - Last cycle standing wins the round. The round also ends as soon as no
#      human cycle is left alive (no point watching the bots finish it).
#    - Press R to restart after a round ends. Press ESC to quit.

# Playtest A/B (enemy behaviour):
#    Each round the three AI cycles all use ONE behaviour, drawn at random
#    (balanced) from: voronoi (original territory bot), rinzler (competitor:
#    straight until blocked), clu (competitor: taxicab chaser). Nothing on
#    screen reveals which; every finished round appends a row to
#    playtest_log.csv - summarise it with analyze_playtest.py.
#      python tron_lightcycle.py                 # random per round (playtest)
#      python tron_lightcycle.py --bots voronoi  # force one behaviour

# Icon hook:
#    Each Player has `icon_path`. If set to a valid image file, it will be
#    loaded and rotated to face the direction of travel and drawn as the
#    cycle's head. Until then, a colored triangle placeholder is used.
#    See Player.load_icon() and Player.draw_head() below.


import pygame
import sys
import random
import csv
import os
from datetime import datetime
from enum import Enum
from collections import deque

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
CELL_SIZE = 10          # size of one grid cell in pixels
GRID_W, GRID_H = 80, 60  # arena size in cells
SCREEN_W, SCREEN_H = GRID_W * CELL_SIZE, GRID_H * CELL_SIZE

TICK_RATE = 15          # moves per second -> THIS is what makes speed "static"
                         # both players always move exactly 1 cell per tick,
                         # so neither can ever be faster/slower than the other.

START_MARGIN = 4        # how many cells in from each corner the cycles spawn
NUM_PLAYERS = 4         # 1 human + 3 AI (corner spawns are defined for exactly 4)

INPUT_QUEUE_SIZE = 2    # how many buffered turns a human can stack per tick.
                         # 2 lets a quick "up then left" double-turn register
                         # instead of the first press being overwritten.

# -- AI tuning --------------------------------------------------------------
# Voronoi tie-break jitter: if the best move and runner-up move are within
# this many cells of each other in territory score, treat them as "close
# enough" and pick randomly among them, instead of always deterministically
# picking the single highest-scoring move. Keeps the bot from being fully
# predictable/memorizable while never overriding a genuinely better move.
AI_TIE_THRESHOLD = 3

# -- Scoring / leaderboard ----------------------------------------------------
# Score = whole seconds survived x 100 (arcade-style padded score, e.g. a
# round lasting 1:25 / 85 seconds scores 8500). The timer itself is never
# shown during play - it only surfaces on the end screen.
SCORE_MULTIPLIER = 100
MAX_NAME_LEN = 8
LEADERBOARD_SIZE = 10
LEADERBOARD_EVERY_N_ROUNDS = 3   # show the top-10 board every 3rd end screen
HIGHSCORE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "highscores.csv")

# -- Playtest A/B log -----------------------------------------------------------
# One row per finished round, appended to playtest_log.csv next to this file
# (read it with analyze_playtest.py). Contains no names or personal data.
PLAYTEST_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "playtest_log.csv")
PLAYTEST_FIELDS = ["session", "round", "time", "mode", "condition", "outcome",
                   "p1_survival_s", "p1_death_cause", "enemies_dead",
                   "first_enemy_death_s", "score"]

BG_COLOR = (5, 8, 15)
GRID_COLOR = (20, 28, 40)
P1_COLOR = (60, 170, 255)      # blue
P1_TRAIL_COLOR = (20, 90, 150)
P2_COLOR = (255, 140, 40)      # orange
P2_TRAIL_COLOR = (150, 70, 15)
P3_COLOR = (80, 230, 120)      # green
P3_TRAIL_COLOR = (25, 120, 60)
P4_COLOR = (230, 80, 220)      # magenta
P4_TRAIL_COLOR = (120, 35, 115)
TEXT_COLOR = (230, 230, 230)


class Direction(Enum):
    UP = (0, -1)
    DOWN = (0, 1)
    LEFT = (-1, 0)
    RIGHT = (1, 0)

    def is_opposite(self, other):
        dx1, dy1 = self.value
        dx2, dy2 = other.value
        return dx1 == -dx2 and dy1 == -dy2


class Player:
    def __init__(self, name, start_pos, start_dir, color, trail_color,
                 controls, icon_path=None):
        self.name = name
        self.pos = start_pos                # (x, y) grid coords
        self.direction = start_dir
        self.pending_direction = start_dir   # next heading (AI writes this directly)
        self.input_queue = deque(maxlen=INPUT_QUEUE_SIZE)  # buffered human turns
        self.color = color
        self.trail_color = trail_color
        self.controls = controls             # dict: pygame key -> Direction
        self.trail = set()                   # occupied cells (walls; cleared by derez() on crash)
        self.trail_order = []                # ordered list, useful for drawing/fx later
        self.alive = True
        self.hit_own_trail = False           # set in step(), read in check_collision()
        self.death_cause = None              # "border" / "self" / "enemy" once crashed (playtest log)
        self.death_tick = None               # round tick on which it crashed (playtest log)
        self.icon_path = icon_path
        self.icon_surface = None
        self.load_icon()

        self.trail.add(start_pos)
        self.trail_order.append(start_pos)

    # -- icon hook (fill in later) ------------------------------------------
    def load_icon(self):
        """Attempt to load a directional icon image. Falls back silently
        to the placeholder triangle if no icon_path is provided or the
        file can't be loaded. Call this again if you swap icon_path later."""
        if not self.icon_path:
            return
        try:
            img = pygame.image.load(self.icon_path).convert_alpha()
            size = int(CELL_SIZE * 3)
            self.icon_surface = pygame.transform.smoothscale(img, (size, size))
        except Exception:
            self.icon_surface = None

    def handle_key(self, key):
        new_dir = self.controls.get(key)
        if new_dir is None:
            return
        # Compare against the last buffered turn (or the current heading if
        # nothing is queued) so stacked inputs can't sneak in a reversal.
        last = self.input_queue[-1] if self.input_queue else self.direction
        if new_dir == last or new_dir.is_opposite(last):
            return
        self.input_queue.append(new_dir)

    def step(self):
        if not self.alive:
            return
        # human input: consume one buffered turn per tick
        if self.input_queue:
            self.pending_direction = self.input_queue.popleft()
        self.direction = self.pending_direction
        dx, dy = self.direction.value
        x, y = self.pos
        new_pos = (x + dx, y + dy)
        # O(1) self-collision test, done BEFORE the cell is added to the trail
        self.hit_own_trail = new_pos in self.trail
        self.pos = new_pos
        self.trail.add(new_pos)
        self.trail_order.append(new_pos)

    def check_collision(self, others):
        """`others` = every other cycle in the arena. Cycles that crashed in
        an earlier tick have already been derezzed (empty trail), so only
        trails still standing - including ones belonging to cycles that crash
        in this very tick - count as walls."""
        x, y = self.pos
        # arena bounds
        if x < 0 or x >= GRID_W or y < 0 or y >= GRID_H:
            self.alive = False
            self.death_cause = "border"
            return
        # own trail
        if self.hit_own_trail:
            self.alive = False
            self.death_cause = "self"
            return
        # any other cycle's trail (includes their new head, so head-on = both die)
        for other in others:
            if self.pos in other.trail:
                self.alive = False
                self.death_cause = "enemy"
                return

    def draw_trail(self, surface):
        for (cx, cy) in self.trail_order[:-1]:
            rect = pygame.Rect(cx * CELL_SIZE, cy * CELL_SIZE, CELL_SIZE, CELL_SIZE)
            pygame.draw.rect(surface, self.trail_color, rect)

        # thin bright "energy core" running through the center of the wall -
        # uses the player's head color so the wall visually reads as an
        # extension of the cycle itself, like a lit tube rather than a block.
        if len(self.trail_order) > 1:
            core_width = max(3, CELL_SIZE // 4)
            points = [
                (cx * CELL_SIZE + CELL_SIZE // 2, cy * CELL_SIZE + CELL_SIZE // 2)
                for (cx, cy) in self.trail_order
            ]
            pygame.draw.lines(surface, self.color, False, points, core_width)

    def derez(self):
        """Remove this cycle's whole trail from the arena (called once it has
        crashed). Safe to call repeatedly."""
        self.trail.clear()
        self.trail_order.clear()

    def draw_head(self, surface):
        if not self.alive:
            return  # crashed cycles vanish along with their trail
        cx, cy = self.pos
        px, py = cx * CELL_SIZE + CELL_SIZE // 2, cy * CELL_SIZE + CELL_SIZE // 2

        if self.icon_surface:
            angle_map = {
                Direction.UP: 0,
                Direction.RIGHT: -90,
                Direction.DOWN: 180,
                Direction.LEFT: 90,
            }
            rotated = pygame.transform.rotate(self.icon_surface, angle_map[self.direction])
            rect = rotated.get_rect(center=(px, py))
            surface.blit(rotated, rect)
            return

        # --- placeholder head: a small triangle pointing in travel direction ---
        size = CELL_SIZE * 0.9
        dx, dy = self.direction.value
        tip = (px + dx * size, py + dy * size)
        left = (px - dy * size * 0.6 - dx * size * 0.3, py + dx * size * 0.6 - dy * size * 0.3)
        right = (px + dy * size * 0.6 - dx * size * 0.3, py - dx * size * 0.6 - dy * size * 0.3)
        pygame.draw.polygon(surface, self.color, [tip, left, right])


# -- turn helpers (clockwise order lets us derive "left"/"right" from "straight") --
_CLOCKWISE = [Direction.UP, Direction.RIGHT, Direction.DOWN, Direction.LEFT]


def turn_left(d):
    return _CLOCKWISE[(_CLOCKWISE.index(d) - 1) % 4]


def turn_right(d):
    return _CLOCKWISE[(_CLOCKWISE.index(d) + 1) % 4]


def neighbors(pos, w, h):
    x, y = pos
    for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
        nx, ny = x + dx, y + dy
        if 0 <= nx < w and 0 <= ny < h:
            yield (nx, ny)


def bfs_distances(start, blocked, w, h):
    """Standard single-source BFS distance map over the open grid."""
    dist = {start: 0}
    q = deque([start])
    while q:
        pos = q.popleft()
        d = dist[pos]
        for n in neighbors(pos, w, h):
            if n in blocked or n in dist:
                continue
            dist[n] = d + 1
            q.append(n)
    return dist


# -- flat-grid BFS (what the AI actually uses) -------------------------------
# With four cycles the AI runs ~20 flood fills per tick, and a tick only has
# 1/15 s. Dicts of (x, y) tuples were ~4 ms per fill (~100 ms per tick - the
# game fell behind); the same fill over a flat list indexed by y*GRID_W+x is
# roughly 3x cheaper. Cell values in a grid / distance map:
#     OPEN (-1)    free and not reached yet
#     BLOCKED (-2) a wall (any cycle's trail) - never entered
#     0, 1, 2...   BFS distance from the nearest start cell
OPEN = -1
BLOCKED = -2
GRID_N = GRID_W * GRID_H


def _build_neighbor_table():
    table = []
    for i in range(GRID_N):
        x, y = i % GRID_W, i // GRID_W
        n = []
        if y > 0:
            n.append(i - GRID_W)
        if y < GRID_H - 1:
            n.append(i + GRID_W)
        if x > 0:
            n.append(i - 1)
        if x < GRID_W - 1:
            n.append(i + 1)
        table.append(tuple(n))
    return tuple(table)


NEIGHBORS = _build_neighbor_table()


def build_occupancy_grid(players):
    """Flat grid with BLOCKED on every cell currently covered by a trail and
    OPEN everywhere else (crashed cycles' trails are already gone). Built once
    per tick and shared by all AIs. Out-of-bounds cells (a cycle's head after
    it leaves the arena) are skipped."""
    grid = [OPEN] * GRID_N
    for p in players:
        for (x, y) in p.trail:
            if 0 <= x < GRID_W and 0 <= y < GRID_H:
                grid[y * GRID_W + x] = BLOCKED
    return grid


def bfs_flat(starts, grid):
    """Multi-source BFS over a flat occupancy grid. Returns a new list where
    each reachable cell holds its distance from the NEAREST start. Start cells
    are seeded directly, so they may sit on BLOCKED cells (a cycle's own head).
    `grid` itself is not modified."""
    dist = grid[:]
    q = list(starts)
    for s in q:
        dist[s] = 0
    for cur in q:               # q grows while we iterate - that is the queue
        d = dist[cur] + 1
        for n in NEIGHBORS[cur]:
            if dist[n] == OPEN:
                dist[n] = d
                q.append(n)
    return dist


class AIPlayer(Player):
    """
    Tier 1 - Reactive survival: any move that crashes next tick is discarded
             outright, no exceptions, regardless of its territory score.
    Tier 2 - Voronoi territory scoring: among surviving moves, compare BFS
             distance maps grown from the AI's candidate position and from
             the rivals' current positions. Every empty cell is "claimed"
             by whoever reaches it first (fewer steps); score is
             (cells the AI would reach first) - (cells ANY rival would
             reach first). Since all cycles move at identical static speed,
             comparing independent BFS distance maps is equivalent to a
             true simultaneous flood fill, so this stays cheap - no need to
             hand-roll a synchronized multi-way BFS. With several rivals the
             rival side is ONE multi-source BFS (distance to the nearest
             rival), so the cost per candidate stays at 2 BFS no matter how
             many rivals there are. Every other cycle is treated as an enemy
             (free-for-all, no alliances).
    Scope note - this AI does NOT predict the rivals' next moves. It only
             reacts to walls that already exist. This is intentional: it
             keeps the bot fully "readable" (a human can always explain why
             it turned by pointing at a wall on screen) at the cost of rare
             head-on collisions when both cycles are on a direct collision
             course with no existing walls to react to. Not a bug - a
             deliberate tradeoff to keep behavior legible over exhaustive.
    Tie handling - if the top move(s) are within AI_TIE_THRESHOLD cells of
             each other, pick randomly among them so the bot isn't fully
             deterministic/memorizable, without ever picking a worse move.
    """

    def decide(self, opponents, grid):
        """opponents - the other cycles still alive (their heads are the BFS
                       sources for the rival side of the territory score)
        grid      - flat occupancy grid from build_occupancy_grid(): BLOCKED on
                       every cell currently covered by a trail.
                       Built once per tick and shared by all AIs; it is only
                       modified temporarily inside this method and restored
                       before returning."""
        if not self.alive:
            return

        candidate_dirs = [self.direction, turn_left(self.direction), turn_right(self.direction)]
        x, y = self.pos

        survivors = []  # (direction, new_pos)
        for d in candidate_dirs:
            dx, dy = d.value
            new_pos = (x + dx, y + dy)
            nx, ny = new_pos
            if nx < 0 or nx >= GRID_W or ny < 0 or ny >= GRID_H:
                continue  # tier 1: boundary crash
            if grid[ny * GRID_W + nx] == BLOCKED:
                continue  # tier 1: wall crash (own or anyone else's trail)
            survivors.append((d, new_pos))

        if not survivors:
            # No safe move exists - going down no matter what. Keep current
            # heading; the collision system will register the crash next tick.
            self.pending_direction = self.direction
            return

        rival_heads = [o.pos[1] * GRID_W + o.pos[0]
                       for o in opponents if o.alive and o is not self]
        if not rival_heads:
            # nobody left to out-claim territory from; just stay safe
            self.pending_direction = survivors[0][0]
            return
        if len(survivors) == 1:
            # forced move - nothing to compare, skip the flood fills entirely
            self.pending_direction = survivors[0][0]
            return

        scored = []
        for d, (nx, ny) in survivors:
            cand = ny * GRID_W + nx
            dist_self = bfs_flat((cand,), grid)
            # the candidate cell is a wall for the rivals' flood fill
            grid[cand] = BLOCKED
            try:
                dist_opp = bfs_flat(rival_heads, grid)
            finally:
                grid[cand] = OPEN

            # In both maps: >= 0 reached (value = distance), < 0 not reached.
            my_territory = 0
            their_territory = 0
            for ds, do in zip(dist_self, dist_opp):
                if ds >= 0:
                    if do < 0:
                        my_territory += 1       # only I can reach it
                    elif ds < do:
                        my_territory += 1
                    elif do < ds:
                        their_territory += 1
                    # equal distance -> contested, counts for neither
                elif do >= 0:
                    their_territory += 1        # only rivals can reach it

            scored.append((d, my_territory - their_territory))

        best_score = max(score for _, score in scored)
        top_choices = [d for d, score in scored if best_score - score <= AI_TIE_THRESHOLD]
        self.pending_direction = random.choice(top_choices)


# ---------------------------------------------------------------------------
# Competitor bots, ported for A/B playtesting
# ---------------------------------------------------------------------------
# The two behaviours below are ports of the "Rinzler" and "CLU" bots from the
# competitor's curses lightcycle. Same decide(opponents, grid) interface as
# AIPlayer, so tick_players()/evaluate_round() treat them as ordinary AIs.
# What changed in the port (behaviour is otherwise line-for-line the same):
#   - their (row, col) coordinates became our (x, y); "up" is still y - 1
#   - "valid cell" = inside the arena and not on a trail (their is_valid)
#   - a 180-degree reversal is never offered (in their game the cell behind
#     you is always your own trail, so it was never valid either)
#   - decisions are made on a simultaneous snapshot instead of after the human
#     has already moved, and CLU's target is the nearest living HUMAN cycle
#     (their one human), falling back to the nearest rival if none is left
_DIRECTION_ORDER = (Direction.UP, Direction.DOWN, Direction.LEFT, Direction.RIGHT)


class RinzlerAI(AIPlayer):
    """Competitor 'genmove': keep going straight; only when the next cell is
    blocked, turn to a random open neighbour. No lookahead at all - it will
    happily run into dead ends and its own pockets."""

    def _open_moves(self, grid):
        x, y = self.pos
        moves = []
        for d in _DIRECTION_ORDER:
            if d.is_opposite(self.direction):
                continue
            dx, dy = d.value
            nx, ny = x + dx, y + dy
            if 0 <= nx < GRID_W and 0 <= ny < GRID_H and grid[ny * GRID_W + nx] != BLOCKED:
                moves.append(d)
        return moves

    def decide(self, opponents, grid):
        if not self.alive:
            return
        moves = self._open_moves(grid)
        if moves:
            self.pending_direction = self.direction if self.direction in moves else random.choice(moves)
        else:
            self.pending_direction = self.direction


class CluAI(RinzlerAI):
    """Competitor 'genmove1': close taxicab distance on the target. Whichever
    axis has the bigger gap is closed first; if that move is unavailable it
    falls through to 'keep heading, else random open move' (same quirk as the
    original - it does not try the other axis). Pure hunter: no territory
    sense, no dead-end awareness."""

    def _target(self, opponents):
        living = [o for o in opponents if o.alive and o is not self]
        humans = [o for o in living if not isinstance(o, AIPlayer)]
        pool = humans or living
        if not pool:
            return None
        x, y = self.pos
        return min(pool, key=lambda o: abs(o.pos[0] - x) + abs(o.pos[1] - y))

    def decide(self, opponents, grid):
        if not self.alive:
            return
        moves = self._open_moves(grid)
        target = self._target(opponents)
        heading = self.direction
        if target is not None:
            x, y = self.pos
            dy = target.pos[1] - y      # original diff[0] (rows)
            dx = target.pos[0] - x      # original diff[1] (cols)
            if abs(dy) > abs(dx):
                # vertical gap dominates
                if dy > 0 and heading != Direction.UP:
                    if Direction.DOWN in moves:
                        self.pending_direction = Direction.DOWN
                        return
                elif dy < 0 and heading != Direction.DOWN:
                    if Direction.UP in moves:
                        self.pending_direction = Direction.UP
                        return
                else:
                    # blocked from closing vertically: slide sideways instead
                    if heading != Direction.LEFT:
                        if Direction.RIGHT in moves:
                            self.pending_direction = Direction.RIGHT
                            return
                    else:
                        if Direction.LEFT in moves:
                            self.pending_direction = Direction.LEFT
                            return
            else:
                # horizontal gap dominates (or tie)
                if dx > 0 and heading != Direction.LEFT:
                    if Direction.RIGHT in moves:
                        self.pending_direction = Direction.RIGHT
                        return
                elif dx < 0 and heading != Direction.RIGHT:
                    if Direction.LEFT in moves:
                        self.pending_direction = Direction.LEFT
                        return
                else:
                    if heading != Direction.UP:
                        if Direction.DOWN in moves:
                            self.pending_direction = Direction.DOWN
                            return
                    else:
                        if Direction.UP in moves:
                            self.pending_direction = Direction.UP
                            return
        if moves:
            self.pending_direction = heading if heading in moves else random.choice(moves)
        else:
            self.pending_direction = heading


# Enemy behaviour sets used for A/B testing. Every enemy in a round uses the
# same behaviour, so a round is one clean condition.
BOT_CLASSES = {
    "voronoi": AIPlayer,      # the original territory-scoring bot
    "rinzler": RinzlerAI,     # competitor: straight until blocked, random turns
    "clu": CluAI,             # competitor: taxicab chaser
}
CONDITIONS = tuple(BOT_CLASSES)


def make_players(vs_ai=True, condition="voronoi"):
    """Return the four cycles, one per corner, in this order:
         [0] top-left      P1, human (WASD)
         [1] top-right     P2, AI - or a second human on arrow keys if vs_ai=False
         [2] bottom-right  AI
         [3] bottom-left   AI
    `condition` picks the behaviour of every AI cycle (see BOT_CLASSES). The
    cycles' names, colours and spawns are identical for every condition, so
    nothing on screen tells a playtester which one is active.
    Spawns form a pinwheel (each cycle runs along an edge toward the next
    corner's side), so nobody starts aimed at a neighbor and every cycle gets
    the same layout rotated by 90 degrees - no corner has a built-in edge."""
    m = START_MARGIN
    left, right = m, GRID_W - 1 - m
    top, bottom = m, GRID_H - 1 - m

    p1 = Player(
        name="Player 1",
        start_pos=(left, top),
        start_dir=Direction.RIGHT,
        color=P1_COLOR,
        trail_color=P1_TRAIL_COLOR,
        controls={
            pygame.K_w: Direction.UP,
            pygame.K_s: Direction.DOWN,
            pygame.K_a: Direction.LEFT,
            pygame.K_d: Direction.RIGHT,
        },
        icon_path=None,  # e.g. "assets/p1_cycle.png" later
    )
    bot_class = BOT_CLASSES[condition]
    p2_class = bot_class if vs_ai else Player
    p2 = p2_class(
        name="ISO-2" if vs_ai else "Player 2",
        start_pos=(right, top),
        start_dir=Direction.DOWN,
        color=P2_COLOR,
        trail_color=P2_TRAIL_COLOR,
        controls={
            pygame.K_UP: Direction.UP,
            pygame.K_DOWN: Direction.DOWN,
            pygame.K_LEFT: Direction.LEFT,
            pygame.K_RIGHT: Direction.RIGHT,
        },
        icon_path=None,  # e.g. "assets/p2_cycle.png" later
    )
    p3 = bot_class(
        name="ISO-3",
        start_pos=(right, bottom),
        start_dir=Direction.LEFT,
        color=P3_COLOR,
        trail_color=P3_TRAIL_COLOR,
        controls={},
        icon_path=None,  # e.g. "assets/p3_cycle.png" later
    )
    p4 = bot_class(
        name="ISO-4",
        start_pos=(left, bottom),
        start_dir=Direction.UP,
        color=P4_COLOR,
        trail_color=P4_TRAIL_COLOR,
        controls={},
        icon_path=None,  # e.g. "assets/p4_cycle.png" later
    )
    return [p1, p2, p3, p4]


def tick_players(players, tick=None):
    """Advance the whole arena by exactly one tick: AI decisions (all made
    against the same snapshot, before anyone moves), movement, collisions.
    `tick` (the round's tick number) is only used to stamp death_tick on
    cycles that crash this tick, for the playtest log."""
    ais = [p for p in players if isinstance(p, AIPlayer) and p.alive]
    if ais:
        grid = build_occupancy_grid(players)
        for ai in ais:
            ai.decide([p for p in players if p is not ai and p.alive], grid)

    for p in players:
        p.step()
    for p in players:
        if p.alive:
            p.check_collision([q for q in players if q is not p])

    # Derez AFTER every collision check: all crashes in a tick are judged
    # against the full, intact trails (so head-ons and pile-ups stay
    # order-independent), and only then do the crashed cycles' walls vanish.
    for p in players:
        if not p.alive:
            if p.death_tick is None:
                p.death_tick = tick
            p.derez()


def evaluate_round(players):
    """Return (game_over, winner_text). The round ends when one or zero
    cycles remain, or when no human cycle is left alive."""
    alive = [p for p in players if p.alive]
    humans_alive = any(p.alive and not isinstance(p, AIPlayer) for p in players)

    if len(alive) == 1:
        return True, f"{alive[0].name.upper()} WINS"
    if len(alive) == 0:
        return True, "DRAW - everyone crashed!"
    if not humans_alive:
        return True, "ELIMINATED"
    return False, ""


def draw_grid(surface):
    for x in range(0, SCREEN_W, CELL_SIZE):
        pygame.draw.line(surface, GRID_COLOR, (x, 0), (x, SCREEN_H))
    for y in range(0, SCREEN_H, CELL_SIZE):
        pygame.draw.line(surface, GRID_COLOR, (0, y), (SCREEN_W, y))


def build_background():
    """Render the background + grid once; main() blits this every frame
    instead of redrawing ~140 lines per frame."""
    bg = pygame.Surface((SCREEN_W, SCREEN_H))
    bg.fill(BG_COLOR)
    draw_grid(bg)
    return bg


def load_scores():
    """Read the top-10 list from disk. Missing/corrupt file -> empty list,
    never crashes the game."""
    scores = []
    if os.path.exists(HIGHSCORE_FILE):
        try:
            with open(HIGHSCORE_FILE, newline="") as f:
                for row in csv.reader(f):
                    if len(row) >= 2:
                        try:
                            scores.append((row[0], int(row[1])))
                        except ValueError:
                            continue
        except OSError:
            pass
    scores.sort(key=lambda entry: entry[1], reverse=True)
    return scores[:LEADERBOARD_SIZE]


def save_scores(scores):
    try:
        with open(HIGHSCORE_FILE, "w", newline="") as f:
            writer = csv.writer(f)
            for name, score in scores[:LEADERBOARD_SIZE]:
                writer.writerow([name, score])
    except OSError:
        pass  # non-fatal - worst case the run's score just doesn't persist


def update_scores(scores, name, score):
    """Insert/update a score for `name`, keeping only their best entry.

    Returns (new_scores, is_personal_best). is_personal_best is True when
    this score beats (or is their first-ever) recorded score for that name -
    it does NOT require making the visible top 10, just beating their own
    prior best.
    """
    existing_index = None
    existing_score = None
    for i, (n, s) in enumerate(scores):
        if n == name:
            existing_index = i
            existing_score = s
            break

    if existing_index is not None:
        if score <= existing_score:
            return scores, False  # not an improvement - table unchanged
        remaining = scores[:existing_index] + scores[existing_index + 1:]
        updated = remaining + [(name, score)]
    else:
        updated = scores + [(name, score)]  # first score ever for this name

    updated.sort(key=lambda entry: entry[1], reverse=True)
    return updated[:LEADERBOARD_SIZE], True


def draw_leaderboard(surface, scores, font, small_font, y_start):
    title = font.render("TOP 10", True, TEXT_COLOR)
    rect = title.get_rect(center=(SCREEN_W // 2, y_start))
    surface.blit(title, rect)

    row_y = y_start + 40
    if not scores:
        empty = small_font.render("-- no scores yet --", True, TEXT_COLOR)
        surface.blit(empty, empty.get_rect(center=(SCREEN_W // 2, row_y)))
        return

    for i, (name, score) in enumerate(scores, start=1):
        line = f"{i:>2}. {name:<{MAX_NAME_LEN}}  {score}"
        row_surf = small_font.render(line, True, TEXT_COLOR)
        surface.blit(row_surf, row_surf.get_rect(center=(SCREEN_W // 2, row_y)))
        row_y += 24


class ConditionBag:
    """Hands out enemy-behaviour conditions in shuffled rounds of the whole
    set (a 'bag'), so over any N x len(conditions) rounds every condition is
    played exactly N times - no streaks of luck in the draw - and the same
    condition never appears twice in a row across a refill."""

    def __init__(self, conditions, rng=None):
        self.conditions = list(conditions)
        self.rng = rng or random
        self.queue = []
        self.last = None

    def next(self):
        if not self.queue:
            self.queue = self.conditions[:]
            self.rng.shuffle(self.queue)
            if len(self.queue) > 1 and self.queue[-1] == self.last:
                self.queue[0], self.queue[-1] = self.queue[-1], self.queue[0]
        self.last = self.queue.pop()
        return self.last


def playtest_record(players, condition, vs_ai, round_ticks, score):
    """Summarise a finished round as one log row (minus session/round/time).
    outcome is from P1's point of view: WIN = last cycle standing, DRAW =
    everyone crashed together, LOSS = anything else."""
    p1 = players[0]
    enemies = players[1:]
    alive = [p for p in players if p.alive]
    if len(alive) == 1 and alive[0] is p1:
        outcome = "WIN"
    elif not alive:
        outcome = "DRAW"
    else:
        outcome = "LOSS"
    p1_ticks = p1.death_tick if p1.death_tick is not None else round_ticks
    enemy_deaths = [e.death_tick for e in enemies if e.death_tick is not None]
    return {
        "mode": "solo" if vs_ai else "pvp",
        "condition": condition,
        "outcome": outcome,
        "p1_survival_s": round(p1_ticks / TICK_RATE, 2),
        "p1_death_cause": p1.death_cause or "",
        "enemies_dead": sum(1 for e in enemies if not e.alive),
        "first_enemy_death_s": round(min(enemy_deaths) / TICK_RATE, 2) if enemy_deaths else "",
        "score": score,
    }


def append_playtest_row(row, path=None):
    """Append one row, writing the header first if the file is new/empty.
    Never raises - a failed log write must not interrupt a playtest."""
    path = path or PLAYTEST_FILE
    try:
        new_file = not os.path.exists(path) or os.path.getsize(path) == 0
        with open(path, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=PLAYTEST_FIELDS)
            if new_file:
                writer.writeheader()
            writer.writerow(row)
    except OSError:
        pass


def main(bots="random"):
    """bots: "random" (default) = every round uses a randomly drawn enemy
    behaviour, balanced across voronoi / rinzler / clu and logged for the
    A/B comparison; or force one of BOT_CLASSES for every round."""
    if bots != "random" and bots not in BOT_CLASSES:
        raise ValueError(f"bots must be 'random' or one of {sorted(BOT_CLASSES)}")
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    pygame.display.set_caption("Tron Light Cycle - Prototype")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("consolas", 36, bold=True)
    small_font = pygame.font.SysFont("consolas", 20)
    background = build_background()

    vs_ai = True
    bag = ConditionBag(CONDITIONS if bots == "random" else (bots,))
    condition = bag.next()
    players = make_players(vs_ai, condition)
    game_over = False
    winner_text = ""

    session_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    playtest_round_no = 0

    # -- scoring / leaderboard state --
    scores = load_scores()
    round_ticks = 0            # hidden timer, counted in game ticks (not wall-clock)
    final_score = 0
    round_end_count = 0        # how many end-screens shown this session
    name_entry_active = False
    name_input = ""
    show_leaderboard_this_round = False
    is_personal_best = False

    time_accumulator = 0.0
    tick_interval = 1.0 / TICK_RATE

    running = True
    while running:
        dt = clock.tick(60) / 1000.0
        time_accumulator += dt

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE and not name_entry_active:
                    running = False
                elif event.key == pygame.K_r and game_over and not name_entry_active:
                    condition = bag.next()          # a new round draws a new condition
                    players = make_players(vs_ai, condition)
                    game_over = False
                    winner_text = ""
                    time_accumulator = 0.0
                    round_ticks = 0
                elif event.key == pygame.K_t and not name_entry_active:
                    vs_ai = not vs_ai
                    players = make_players(vs_ai, condition)   # same condition: this is a mode switch, not a new round
                    game_over = False
                    winner_text = ""
                    time_accumulator = 0.0
                    round_ticks = 0
                elif name_entry_active:
                    if event.key == pygame.K_RETURN:
                        entered_name = name_input.strip() or "PLAYER"
                        scores, is_personal_best = update_scores(scores, entered_name, final_score)
                        save_scores(scores)
                        name_entry_active = False
                    elif event.key == pygame.K_ESCAPE:
                        is_personal_best = False
                        name_entry_active = False  # skip entry, no score saved
                    elif event.key == pygame.K_BACKSPACE:
                        name_input = name_input[:-1]
                    elif event.unicode.isalnum() and len(name_input) < MAX_NAME_LEN:
                        name_input += event.unicode.upper()
                elif not game_over:
                    for p in players:
                        if not isinstance(p, AIPlayer):
                            p.handle_key(event.key)

        # fixed-step movement -> guarantees identical, static speed for every cycle
        if not game_over:
            while time_accumulator >= tick_interval:
                time_accumulator -= tick_interval
                round_ticks += 1
                tick_players(players, round_ticks)

                game_over, winner_text = evaluate_round(players)
                if game_over:
                    # score is the round length in seconds, which is also how
                    # long P1 survived (the round ends when the last human dies)
                    elapsed_seconds = round_ticks / TICK_RATE
                    final_score = int(elapsed_seconds) * SCORE_MULTIPLIER

                    # playtest log: one row per finished round (see PLAYTEST_FIELDS)
                    playtest_round_no += 1
                    row = playtest_record(players, condition, vs_ai, round_ticks, final_score)
                    row.update(session=session_id, round=playtest_round_no,
                               time=datetime.now().isoformat(timespec="seconds"))
                    append_playtest_row(row)

                    round_end_count += 1
                    show_leaderboard_this_round = (round_end_count % LEADERBOARD_EVERY_N_ROUNDS == 0)
                    name_entry_active = True
                    name_input = ""
                    is_personal_best = False
                    break

        # --- draw ---
        screen.blit(background, (0, 0))
        for p in players:
            p.draw_trail(screen)
        for p in players:
            p.draw_head(screen)

        p2_label = "RIVALS: 3x ISO" if vs_ai else "P2: Arrows  +2x ISO"
        hud = small_font.render(
            f"P1: WASD    {p2_label}    T: toggle AI    ESC: quit", True, TEXT_COLOR
        )
        screen.blit(hud, (10, 10))

        alive_count = sum(1 for p in players if p.alive)
        alive_surf = small_font.render(f"ALIVE: {alive_count}/{len(players)}", True, TEXT_COLOR)
        screen.blit(alive_surf, (10, SCREEN_H - 30))

        if game_over:
            overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 160))
            screen.blit(overlay, (0, 0))

            text_surf = font.render(winner_text, True, TEXT_COLOR)
            rect = text_surf.get_rect(center=(SCREEN_W // 2, 90))
            screen.blit(text_surf, rect)

            score_surf = small_font.render(f"SCORE: {final_score}", True, TEXT_COLOR)
            screen.blit(score_surf, score_surf.get_rect(center=(SCREEN_W // 2, 130)))

            if name_entry_active:
                prompt = small_font.render("Enter your name:", True, TEXT_COLOR)
                screen.blit(prompt, prompt.get_rect(center=(SCREEN_W // 2, 180)))

                cursor = "_" if (pygame.time.get_ticks() // 400) % 2 == 0 else " "
                entry_surf = font.render(name_input + cursor, True, TEXT_COLOR)
                screen.blit(entry_surf, entry_surf.get_rect(center=(SCREEN_W // 2, 220)))

                hint = small_font.render("ENTER to confirm    ESC to skip", True, TEXT_COLOR)
                screen.blit(hint, hint.get_rect(center=(SCREEN_W // 2, 260)))
            else:
                if is_personal_best:
                    best_surf = small_font.render("NEW PERSONAL BEST!", True, (255, 215, 60))
                    screen.blit(best_surf, best_surf.get_rect(center=(SCREEN_W // 2, 170)))
                if show_leaderboard_this_round:
                    draw_leaderboard(screen, scores, font, small_font, 210)
                hint = small_font.render("Press R to restart", True, TEXT_COLOR)
                hint_rect = hint.get_rect(center=(SCREEN_W // 2, SCREEN_H - 40))
                screen.blit(hint, hint_rect)

        pygame.display.flip()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Tron light cycle - four-cycle free-for-all")
    parser.add_argument(
        "--bots", choices=["random"] + sorted(BOT_CLASSES), default="random",
        help="enemy behaviour: 'random' (default) draws a balanced random one each round "
             "for A/B playtesting and logs it; or force voronoi / rinzler / clu for every round")
    main(parser.parse_args().bots)