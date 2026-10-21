# ======================================================================================================
#  ______   ___  _   _ ___ ____ _   _ _____  __        ___   _ ____    _   _ _____ ____  _____  ______  
# / / / /  / _ \| \ | |_ _/ ___| | | |_   _| \ \      / / | | / ___|  | | | | ____|  _ \| ____| \ \ \ \ 
#/ / / /  | (_) |  \| || | |  _| |_| | | |    \ \ /\ / /| | | \___ \  | |_| |  _| | |_) |  _|    \ \ \ \
#\ \ \ \   \__, | |\  || | |_| |  _  | | |     \ V  V / | |_| |___) | |  _  | |___|  _ <| |___   / / / /
# \_\_\_\    /_/|_| \_|___\____|_| |_| |_|      \_/\_/   \___/|____/  |_| |_|_____|_| \_\_____| /_/_/_/ 
# ======================================================================================================
# Tetris
# ---------------------
# Controls:
#    A / D   - move left / right
#    S       - soft drop
#    W       - rotate piece
#    SPACE   - hard drop
#    P       - pause
#    ESC     - quit

#Features:
#    - Classic 7-piece bag randomizer
#    - Adjustable block margin (visual gap between cells) via BLOCK_MARGIN
#    - Persistent JSON leaderboard (top 10), with initials entry on qualifying game over

import pygame
import random
import json
import os
import copy

# ----------------------------------------------------------------------------
# Config
# ----------------------------------------------------------------------------
COLS, ROWS = 10, 20
CELL_SIZE = 30          # size of each cell in pixels (before margin is applied)
BLOCK_MARGIN = 3        # <-- adjust this to change spacing between blocks
SIDE_PANEL_WIDTH = 220

PLAY_WIDTH = COLS * CELL_SIZE
PLAY_HEIGHT = ROWS * CELL_SIZE
SCREEN_WIDTH = PLAY_WIDTH + SIDE_PANEL_WIDTH
SCREEN_HEIGHT = PLAY_HEIGHT

TOP_LEFT_X = 20
TOP_LEFT_Y = 0

FPS = 60
LEADERBOARD_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "leaderboard.json")
MAX_LEADERBOARD_ENTRIES = 10

# Continuous-movement (auto-repeat) tuning for held keys, a la DAS/ARR:
# DAS_DELAY = time held before repeat kicks in, ARR = time between repeats once it does.
DAS_DELAY = 0.16
ARR = 0.05
SOFT_DROP_ARR = 0.03

# Colors
BLACK = (18, 18, 24)
GRAY = (40, 40, 50)
WHITE = (235, 235, 235)
RED = (220, 50, 60)

# Piece colors (standard-ish Tetris palette)
COLORS = {
    "I": (0, 200, 220),
    "O": (230, 210, 30),
    "T": (170, 60, 200),
    "S": (60, 200, 90),
    "Z": (220, 60, 70),
    "J": (60, 90, 220),
    "L": (230, 140, 40),
}

# Shapes defined as list of rotation states, each a list of (x, y) offsets on a 4x4 grid
SHAPES = {
    "I": [
        [(0, 1), (1, 1), (2, 1), (3, 1)],
        [(2, 0), (2, 1), (2, 2), (2, 3)],
        [(0, 2), (1, 2), (2, 2), (3, 2)],
        [(1, 0), (1, 1), (1, 2), (1, 3)],
    ],
    "O": [
        [(1, 0), (2, 0), (1, 1), (2, 1)],
    ] * 4,
    "T": [
        [(1, 0), (0, 1), (1, 1), (2, 1)],
        [(1, 0), (1, 1), (2, 1), (1, 2)],
        [(0, 1), (1, 1), (2, 1), (1, 2)],
        [(1, 0), (0, 1), (1, 1), (1, 2)],
    ],
    "S": [
        [(1, 0), (2, 0), (0, 1), (1, 1)],
        [(1, 0), (1, 1), (2, 1), (2, 2)],
        [(1, 1), (2, 1), (0, 2), (1, 2)],
        [(0, 0), (0, 1), (1, 1), (1, 2)],
    ],
    "Z": [
        [(0, 0), (1, 0), (1, 1), (2, 1)],
        [(2, 0), (1, 1), (2, 1), (1, 2)],
        [(0, 1), (1, 1), (1, 2), (2, 2)],
        [(1, 0), (0, 1), (1, 1), (0, 2)],
    ],
    "J": [
        [(0, 0), (0, 1), (1, 1), (2, 1)],
        [(1, 0), (2, 0), (1, 1), (1, 2)],
        [(0, 1), (1, 1), (2, 1), (2, 2)],
        [(1, 0), (1, 1), (0, 2), (1, 2)],
    ],
    "L": [
        [(2, 0), (0, 1), (1, 1), (2, 1)],
        [(1, 0), (1, 1), (1, 2), (2, 2)],
        [(0, 1), (1, 1), (2, 1), (0, 2)],
        [(0, 0), (1, 0), (1, 1), (1, 2)],
    ],
}

SHAPE_KEYS = list(SHAPES.keys())


# ----------------------------------------------------------------------------
# Leaderboard
# ----------------------------------------------------------------------------
def load_leaderboard():
    if os.path.exists(LEADERBOARD_FILE):
        try:
            with open(LEADERBOARD_FILE, "r") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
        except (json.JSONDecodeError, IOError):
            pass
    return []


def save_leaderboard(entries):
    try:
        with open(LEADERBOARD_FILE, "w") as f:
            json.dump(entries, f, indent=2)
    except IOError:
        pass


def qualifies_for_leaderboard(score, entries):
    if len(entries) < MAX_LEADERBOARD_ENTRIES:
        return True
    return score > min(e["score"] for e in entries)


def add_leaderboard_entry(name, score, entries):
    entries.append({"name": name[:8].upper() or "AAA", "score": score})
    entries.sort(key=lambda e: e["score"], reverse=True)
    del entries[MAX_LEADERBOARD_ENTRIES:]
    save_leaderboard(entries)
    return entries


# ----------------------------------------------------------------------------
# Piece
# ----------------------------------------------------------------------------
class Piece:
    def __init__(self, kind):
        self.kind = kind
        self.rotation = 0
        self.x = 3
        self.y = -2

    def cells(self, rotation=None):
        rot = self.rotation if rotation is None else rotation
        return SHAPES[self.kind][rot % len(SHAPES[self.kind])]

    def color(self):
        return COLORS[self.kind]


class Bag:
    """7-bag randomizer: each of the 7 pieces appears once per bag."""
    def __init__(self):
        self.bag = []

    def next(self):
        if not self.bag:
            self.bag = SHAPE_KEYS[:]
            random.shuffle(self.bag)
        return self.bag.pop()


# ----------------------------------------------------------------------------
# Board / Game logic
# ----------------------------------------------------------------------------
class Game:
    def __init__(self):
        self.grid = [[None for _ in range(COLS)] for _ in range(ROWS)]
        self.bag = Bag()
        self.current = Piece(self.bag.next())
        self.next_piece = Piece(self.bag.next())
        self.score = 0
        self.lines_cleared = 0
        self.level = 1
        self.fall_time = 0
        self.fall_speed = 0.8  # seconds per gravity step
        self.game_over = False
        self.paused = False

    # -- collision / placement -----------------------------------------
    def valid_position(self, piece, dx=0, dy=0, rotation=None):
        for (cx, cy) in piece.cells(rotation):
            x = piece.x + cx + dx
            y = piece.y + cy + dy
            if x < 0 or x >= COLS or y >= ROWS:
                return False
            if y >= 0 and self.grid[y][x] is not None:
                return False
        return True

    def lock_piece(self):
        for (cx, cy) in self.current.cells():
            x = self.current.x + cx
            y = self.current.y + cy
            if y < 0:
                self.game_over = True
                return
            self.grid[y][x] = self.current.color()
        self.clear_lines()
        self.current = self.next_piece
        self.next_piece = Piece(self.bag.next())
        if not self.valid_position(self.current):
            self.game_over = True

    def clear_lines(self):
        full_rows = [r for r in range(ROWS) if all(cell is not None for cell in self.grid[r])]
        if not full_rows:
            return
        for r in full_rows:
            del self.grid[r]
            self.grid.insert(0, [None for _ in range(COLS)])

        n = len(full_rows)
        self.lines_cleared += n
        # Classic-ish scoring
        line_scores = {1: 100, 2: 300, 3: 500, 4: 800}
        self.score += line_scores.get(n, 0) * self.level

        # Level still increments for scoring purposes, but fall_speed stays fixed
        # (no auto speed-up over the course of a game).
        self.level = self.lines_cleared // 10 + 1

    # -- movement --------------------------------------------------------
    def move(self, dx):
        if not self.paused and not self.game_over and self.valid_position(self.current, dx=dx):
            self.current.x += dx

    def rotate(self):
        if self.paused or self.game_over:
            return
        new_rotation = (self.current.rotation + 1) % len(SHAPES[self.current.kind])
        # simple wall-kick attempts
        for kick in (0, -1, 1, -2, 2):
            if self.valid_position(self.current, dx=kick, rotation=new_rotation):
                self.current.x += kick
                self.current.rotation = new_rotation
                return

    def soft_drop(self):
        if self.paused or self.game_over:
            return
        if self.valid_position(self.current, dy=1):
            self.current.y += 1
            self.score += 1
        else:
            self.lock_piece()

    def hard_drop(self):
        if self.paused or self.game_over:
            return
        dist = 0
        while self.valid_position(self.current, dy=dist + 1):
            dist += 1
        self.current.y += dist
        self.score += dist * 2
        self.lock_piece()

    def gravity_step(self, dt):
        if self.paused or self.game_over:
            return
        self.fall_time += dt
        if self.fall_time >= self.fall_speed:
            self.fall_time = 0
            if self.valid_position(self.current, dy=1):
                self.current.y += 1
            else:
                self.lock_piece()

    def ghost_y(self):
        dist = 0
        while self.valid_position(self.current, dy=dist + 1):
            dist += 1
        return self.current.y + dist


# ----------------------------------------------------------------------------
# Rendering helpers
# ----------------------------------------------------------------------------
def draw_cell(surface, x, y, color, alpha=255):
    """Draw a single grid cell at board coords (x, y) with margin applied."""
    px = TOP_LEFT_X + x * CELL_SIZE + BLOCK_MARGIN
    py = TOP_LEFT_Y + y * CELL_SIZE + BLOCK_MARGIN
    size = CELL_SIZE - BLOCK_MARGIN * 2
    if size <= 0:
        size = CELL_SIZE
    rect = pygame.Rect(px, py, size, size)
    if alpha < 255:
        s = pygame.Surface((size, size), pygame.SRCALPHA)
        s.fill((*color, alpha))
        surface.blit(s, (px, py))
    else:
        pygame.draw.rect(surface, color, rect, border_radius=4)
        pygame.draw.rect(surface, tuple(min(255, c + 40) for c in color), rect, width=2, border_radius=4)


def draw_grid_lines(surface):
    for r in range(ROWS + 1):
        y = TOP_LEFT_Y + r * CELL_SIZE
        pygame.draw.line(surface, GRAY, (TOP_LEFT_X, y), (TOP_LEFT_X + PLAY_WIDTH, y))
    for c in range(COLS + 1):
        x = TOP_LEFT_X + c * CELL_SIZE
        pygame.draw.line(surface, GRAY, (x, TOP_LEFT_Y), (x, TOP_LEFT_Y + PLAY_HEIGHT))


def draw_board(surface, game):
    surface.fill(BLACK)
    pygame.draw.rect(surface, (10, 10, 14), (TOP_LEFT_X, TOP_LEFT_Y, PLAY_WIDTH, PLAY_HEIGHT))
    draw_grid_lines(surface)

    # settled blocks
    for r in range(ROWS):
        for c in range(COLS):
            if game.grid[r][c] is not None:
                draw_cell(surface, c, r, game.grid[r][c])

    if not game.game_over:
        # ghost piece
        ghost_y = game.ghost_y()
        for (cx, cy) in game.current.cells():
            gx = game.current.x + cx
            gy = ghost_y + cy
            if gy >= 0:
                draw_cell(surface, gx, gy, game.current.color(), alpha=70)

        # current piece
        for (cx, cy) in game.current.cells():
            x = game.current.x + cx
            y = game.current.y + cy
            if y >= 0:
                draw_cell(surface, x, y, game.current.color())

    pygame.draw.rect(surface, WHITE, (TOP_LEFT_X, TOP_LEFT_Y, PLAY_WIDTH, PLAY_HEIGHT), width=2)


def draw_side_panel(surface, game, font, small_font):
    panel_x = TOP_LEFT_X + PLAY_WIDTH + 20

    title = font.render("TETRIS", True, WHITE)
    surface.blit(title, (panel_x, 20))

    score_label = small_font.render("SCORE", True, GRAY)
    score_val = font.render(str(game.score), True, WHITE)
    surface.blit(score_label, (panel_x, 80))
    surface.blit(score_val, (panel_x, 105))

    level_label = small_font.render("LEVEL", True, GRAY)
    level_val = font.render(str(game.level), True, WHITE)
    surface.blit(level_label, (panel_x, 150))
    surface.blit(level_val, (panel_x, 175))

    lines_label = small_font.render("LINES", True, GRAY)
    lines_val = font.render(str(game.lines_cleared), True, WHITE)
    surface.blit(lines_label, (panel_x, 220))
    surface.blit(lines_val, (panel_x, 245))

    next_label = small_font.render("NEXT", True, GRAY)
    surface.blit(next_label, (panel_x, 300))

    # draw next piece preview
    preview_cell = 20
    preview_margin = 2
    for (cx, cy) in game.next_piece.cells(rotation=0):
        px = panel_x + cx * preview_cell + preview_margin
        py = 330 + cy * preview_cell + preview_margin
        size = preview_cell - preview_margin * 2
        pygame.draw.rect(surface, game.next_piece.color(), (px, py, size, size), border_radius=3)

    controls = [
        "CONTROLS",
        "A/D  move",
        "S    soft drop",
        "W    rotate",
        "SPACE hard drop",
        "P    pause",
        "ESC  quit",
    ]
    y = 430
    for i, line in enumerate(controls):
        c = GRAY if i == 0 else WHITE
        f = small_font if i == 0 else small_font
        surface.blit(f.render(line, True, c), (panel_x, y))
        y += 22


def draw_text_center(surface, text, font, color, y, width=SCREEN_WIDTH, x=0):
    rendered = font.render(text, True, color)
    rect = rendered.get_rect(center=(x + width // 2, y))
    surface.blit(rendered, rect)


# ----------------------------------------------------------------------------
# Leaderboard screens
# ----------------------------------------------------------------------------
def draw_leaderboard_screen(surface, font, small_font, entries, highlight_index=None):
    surface.fill(BLACK)
    draw_text_center(surface, "LEADERBOARD", font, WHITE, 60)
    if not entries:
        draw_text_center(surface, "No scores yet - go set one!", small_font, GRAY, 120)
    for i, entry in enumerate(entries):
        color = (250, 210, 60) if i == highlight_index else WHITE
        line = f"{i + 1:>2}.  {entry['name']:<8}  {entry['score']}"
        draw_text_center(surface, line, small_font, color, 120 + i * 30)
    draw_text_center(surface, "Press ENTER to play  -  ESC to quit", small_font, GRAY, SCREEN_HEIGHT - 40)


def prompt_for_initials(screen, clock, font, small_font, score):
    name = ""
    active = True
    while active:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                raise SystemExit
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN:
                    active = False
                elif event.key == pygame.K_BACKSPACE:
                    name = name[:-1]
                elif event.key == pygame.K_ESCAPE:
                    name = name or "AAA"
                    active = False
                else:
                    if len(name) < 8 and event.unicode.isprintable():
                        name += event.unicode

        screen.fill(BLACK)
        draw_text_center(screen, "NEW HIGH SCORE!", font, (250, 210, 60), 140)
        draw_text_center(screen, f"Score: {score}", small_font, WHITE, 190)
        draw_text_center(screen, "Enter your initials:", small_font, GRAY, 240)
        draw_text_center(screen, name + ("_" if len(name) < 8 else ""), font, WHITE, 290)
        draw_text_center(screen, "Press ENTER to confirm", small_font, GRAY, SCREEN_HEIGHT - 60)
        pygame.display.flip()
        clock.tick(FPS)

    return name.strip() or "AAA"


# ----------------------------------------------------------------------------
# Main loop
# ----------------------------------------------------------------------------
def run_game(screen, clock, font, small_font):
    game = Game()
    running = True

    # Held-key state for continuous (auto-repeat) movement.
    # Each entry tracks how long the key has been held and when its next repeat fires.
    held = {
        "left": {"down": False, "held_time": 0.0, "next_repeat": DAS_DELAY},
        "right": {"down": False, "held_time": 0.0, "next_repeat": DAS_DELAY},
        "down": {"down": False, "held_time": 0.0, "next_repeat": DAS_DELAY},
    }

    while running:
        dt = clock.tick(FPS) / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                raise SystemExit
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return game.score
                if event.key == pygame.K_p:
                    game.paused = not game.paused
                if not game.paused and not game.game_over:
                    if event.key == pygame.K_a:
                        game.move(-1)
                        held["left"] = {"down": True, "held_time": 0.0, "next_repeat": DAS_DELAY}
                    elif event.key == pygame.K_d:
                        game.move(1)
                        held["right"] = {"down": True, "held_time": 0.0, "next_repeat": DAS_DELAY}
                    elif event.key == pygame.K_s:
                        game.soft_drop()
                        held["down"] = {"down": True, "held_time": 0.0, "next_repeat": DAS_DELAY}
                    elif event.key == pygame.K_w:
                        game.rotate()
                    elif event.key == pygame.K_SPACE:
                        game.hard_drop()
                if game.game_over and event.key == pygame.K_RETURN:
                    return game.score
            if event.type == pygame.KEYUP:
                if event.key == pygame.K_a:
                    held["left"]["down"] = False
                elif event.key == pygame.K_d:
                    held["right"]["down"] = False
                elif event.key == pygame.K_s:
                    held["down"]["down"] = False

        # Continuous movement: while a key is held past the initial DAS delay,
        # keep repeating the action at the ARR interval instead of requiring re-presses.
        if not game.paused and not game.game_over:
            for name, action, arr in (
                ("left", lambda: game.move(-1), ARR),
                ("right", lambda: game.move(1), ARR),
                ("down", game.soft_drop, SOFT_DROP_ARR),
            ):
                state = held[name]
                if state["down"]:
                    state["held_time"] += dt
                    if state["held_time"] >= state["next_repeat"]:
                        action()
                        state["next_repeat"] += arr

        game.gravity_step(dt)

        draw_board(screen, game)
        draw_side_panel(screen, game, font, small_font)

        if game.paused:
            overlay = pygame.Surface((PLAY_WIDTH, PLAY_HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 160))
            screen.blit(overlay, (TOP_LEFT_X, TOP_LEFT_Y))
            draw_text_center(screen, "PAUSED", font, WHITE, PLAY_HEIGHT // 2, width=PLAY_WIDTH, x=TOP_LEFT_X)

        if game.game_over:
            overlay = pygame.Surface((PLAY_WIDTH, PLAY_HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 180))
            screen.blit(overlay, (TOP_LEFT_X, TOP_LEFT_Y))
            draw_text_center(screen, "GAME OVER", font, RED, PLAY_HEIGHT // 2 - 20, width=PLAY_WIDTH, x=TOP_LEFT_X)
            draw_text_center(screen, "Press ENTER to continue", small_font, WHITE,
                              PLAY_HEIGHT // 2 + 20, width=PLAY_WIDTH, x=TOP_LEFT_X)

        pygame.display.flip()

    return game.score


def main():
    pygame.init()
    pygame.display.set_caption("Tetris — WASD Edition")
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    clock = pygame.time.Clock()

    font = pygame.font.SysFont("consolas", 28, bold=True)
    small_font = pygame.font.SysFont("consolas", 18)

    entries = load_leaderboard()

    show_leaderboard = True
    while True:
        if show_leaderboard:
            waiting = True
            while waiting:
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        pygame.quit()
                        return
                    if event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_RETURN:
                            waiting = False
                        elif event.key == pygame.K_ESCAPE:
                            pygame.quit()
                            return
                draw_leaderboard_screen(screen, font, small_font, entries)
                pygame.display.flip()
                clock.tick(FPS)

        final_score = run_game(screen, clock, font, small_font)

        if qualifies_for_leaderboard(final_score, entries) and final_score > 0:
            name = prompt_for_initials(screen, clock, font, small_font, final_score)
            entries = add_leaderboard_entry(name, final_score, entries)
            highlight = next((i for i, e in enumerate(entries)
                               if e["name"] == name[:8].upper() and e["score"] == final_score), None)
        else:
            highlight = None

        show_leaderboard = True
        # briefly show leaderboard with highlight then fall into loop's waiting screen
        if highlight is not None:
            for _ in range(1):
                draw_leaderboard_screen(screen, font, small_font, entries, highlight_index=highlight)
                pygame.display.flip()


if __name__ == "__main__":
    main()