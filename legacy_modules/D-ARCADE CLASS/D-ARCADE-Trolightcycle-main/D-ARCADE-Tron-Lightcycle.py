# ======================================================================================================
#  ______   ___  _   _ ___ ____ _   _ _____  __        ___   _ ____    _   _ _____ ____  _____  ______  
# / / / /  / _ \| \ | |_ _/ ___| | | |_   _| \ \      / / | | / ___|  | | | | ____|  _ \| ____| \ \ \ \ 
#/ / / /  | (_) |  \| || | |  _| |_| | | |    \ \ /\ / /| | | \___ \  | |_| |  _| | |_) |  _|    \ \ \ \
#\ \ \ \   \__, | |\  || | |_| |  _  | | |     \ V  V / | |_| |___) | |  _  | |___|  _ <| |___   / / / /
# \_\_\_\    /_/|_| \_|___\____|_| |_| |_|      \_/\_/   \___/|____/  |_| |_|_____|_| \_\_____| /_/_/_/ 
# ======================================================================================================
# Two-player local arena game replicating the classic Tron light cycle rules.

# Controls:
#    Player 1 (Blue) : W A S D
#    Player 2 (Side to side PvP): Arrow Keys other than that its mostly ai based

# Rules:
#    - Both cycles move at a constant, static speed (grid-locked movement).
#    - Every cell a cycle passes through becomes a permanent wall.
#    - Hitting any wall (yours, theirs, or the arena boundary) = instant death.
#    - Last cycle standing wins the round.
#    - Press R to restart after a round ends. Press ESC to quit.

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

BG_COLOR = (5, 8, 15)
GRID_COLOR = (20, 28, 40)
P1_COLOR = (60, 170, 255)      # blue
P1_TRAIL_COLOR = (20, 90, 150)
P2_COLOR = (255, 140, 40)      # orange
P2_TRAIL_COLOR = (150, 70, 15)
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
        self.pending_direction = start_dir   # buffered input, applied next tick
        self.color = color
        self.trail_color = trail_color
        self.controls = controls             # dict: pygame key -> Direction
        self.trail = set()                   # occupied cells (permanent walls)
        self.trail_order = []                # ordered list, useful for drawing/fx later
        self.alive = True
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
        # prevent reversing directly into your own neck
        if not new_dir.is_opposite(self.direction):
            self.pending_direction = new_dir

    def step(self):
        if not self.alive:
            return
        self.direction = self.pending_direction
        dx, dy = self.direction.value
        x, y = self.pos
        new_pos = (x + dx, y + dy)
        self.pos = new_pos
        self.trail.add(new_pos)
        self.trail_order.append(new_pos)

    def check_collision(self, other):
        x, y = self.pos
        # arena bounds
        if x < 0 or x >= GRID_W or y < 0 or y >= GRID_H:
            self.alive = False
            return
        # own trail (excluding the cell we just left is irrelevant since we
        # add pos to trail immediately -> any repeat = crash)
        if list(self.trail_order).count(self.pos) > 1:
            self.alive = False
            return
        # other player's trail
        if self.pos in other.trail:
            self.alive = False
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
                (cx * CELL_SIZE + CELL_SIZE // 3, cy * CELL_SIZE + CELL_SIZE // 2)
                for (cx, cy) in self.trail_order
            ]
            pygame.draw.lines(surface, self.color, False, points, core_width)

    def draw_head(self, surface):
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


class AIPlayer(Player):
    """
    Tier 1 - Reactive survival: any move that crashes next tick is discarded
             outright, no exceptions, regardless of its territory score.
    Tier 2 - Voronoi territory scoring: among surviving moves, compare BFS
             distance maps grown from the AI's candidate position and from
             the opponent's current position. Every empty cell is "claimed"
             by whichever player reaches it first (fewer steps); score is
             (cells the AI would reach first) - (cells the opponent would
             reach first). Since both cycles move at identical static speed,
             comparing two independent BFS distance maps is equivalent to a
             true simultaneous flood fill, so this stays cheap - no need to
             hand-roll a synchronized dual BFS.
    Scope note - this AI does NOT predict the opponent's next move. It only
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

    def decide(self, opponent):
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
            if new_pos in self.trail or new_pos in opponent.trail:
                continue  # tier 1: wall crash (self or opponent)
            survivors.append((d, new_pos))

        if not survivors:
            # No safe move exists - going down no matter what. Keep current
            # heading; the collision system will register the crash next tick.
            self.pending_direction = self.direction
            return

        blocked_base = self.trail | opponent.trail

        scored = []
        for d, new_pos in survivors:
            blocked = blocked_base | {new_pos}
            dist_self = bfs_distances(new_pos, blocked, GRID_W, GRID_H)
            dist_opp = bfs_distances(opponent.pos, blocked, GRID_W, GRID_H)

            all_cells = set(dist_self.keys()) | set(dist_opp.keys())
            my_territory = 0
            their_territory = 0
            for cell in all_cells:
                ds = dist_self.get(cell)
                do = dist_opp.get(cell)
                if ds is None:
                    their_territory += 1
                elif do is None:
                    my_territory += 1
                elif ds < do:
                    my_territory += 1
                elif do < ds:
                    their_territory += 1
                # equal distance -> contested, counts for neither

            scored.append((d, my_territory - their_territory))

        best_score = max(score for _, score in scored)
        top_choices = [d for d, score in scored if best_score - score <= AI_TIE_THRESHOLD]
        self.pending_direction = random.choice(top_choices)


def make_players(vs_ai=True):
    p1 = Player(
        name="Player 1",
        start_pos=(GRID_W // 4, GRID_H // 2),
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
    p2_class = AIPlayer if vs_ai else Player
    p2 = p2_class(
        name="Player 2 (AI)" if vs_ai else "Player 2",
        start_pos=(GRID_W * 3 // 4, GRID_H // 2),
        start_dir=Direction.LEFT,
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
    return p1, p2


def draw_grid(surface):
    for x in range(0, SCREEN_W, CELL_SIZE):
        pygame.draw.line(surface, GRID_COLOR, (x, 0), (x, SCREEN_H))
    for y in range(0, SCREEN_H, CELL_SIZE):
        pygame.draw.line(surface, GRID_COLOR, (0, y), (SCREEN_W, y))


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
# Insert/update a score for `name`, keeping only their best entry.
#   Returns (new_scores, is_personal_best). is_personal_best is True when
#   this score beats (or is their first-ever) recorded score for that name -
#   it does NOT require making the visible top 10, just beating their own
#   prior best.
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


def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    pygame.display.set_caption("Tron Light Cycle - Prototype")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("consolas", 36, bold=True)
    small_font = pygame.font.SysFont("consolas", 20)

    vs_ai = True
    p1, p2 = make_players(vs_ai)
    game_over = False
    winner_text = ""

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
                    p1, p2 = make_players(vs_ai)
                    game_over = False
                    winner_text = ""
                    time_accumulator = 0.0
                    round_ticks = 0
                elif event.key == pygame.K_t and not name_entry_active:
                    vs_ai = not vs_ai
                    p1, p2 = make_players(vs_ai)
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
                    p1.handle_key(event.key)
                    if not vs_ai:
                        p2.handle_key(event.key)

        # fixed-step movement -> guarantees identical, static speed for both players
        if not game_over:
            while time_accumulator >= tick_interval:
                time_accumulator -= tick_interval
                round_ticks += 1
                if vs_ai:
                    p2.decide(p1)
                p1.step()
                p2.step()
                p1.check_collision(p2)
                p2.check_collision(p1)

                if not p1.alive or not p2.alive:
                    game_over = True
                    if not p1.alive and not p2.alive:
                        winner_text = "DRAW - both crashed!"
                    elif not p1.alive:
                        winner_text = "PLAYER 2 WINS"
                    else:
                        winner_text = "PLAYER 1 WINS"

                    # score is about P1's survival time, independent of outcome
                    elapsed_seconds = round_ticks / TICK_RATE
                    final_score = int(elapsed_seconds) * SCORE_MULTIPLIER
                    round_end_count += 1
                    show_leaderboard_this_round = (round_end_count % LEADERBOARD_EVERY_N_ROUNDS == 0)
                    name_entry_active = True
                    name_input = ""
                    is_personal_best = False
                    break

        # --- draw ---
        screen.fill(BG_COLOR)
        draw_grid(screen)
        p1.draw_trail(screen)
        p2.draw_trail(screen)
        p1.draw_head(screen)
        p2.draw_head(screen)

        p2_label = "P2: ISO" if vs_ai else "P2: Arrow Keys"
        hud = small_font.render(
            f"P1: WASD    {p2_label}    T: toggle AI    ESC: quit", True, TEXT_COLOR
        )
        screen.blit(hud, (10, 10))

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
    main()