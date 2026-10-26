import pygame
import random
import sys
import heapq
import time

# Constants
WIDTH, HEIGHT = 800, 600
GRID_WIDTH, GRID_HEIGHT = 500, 500
CELL_SIZE = 4
GRID_SIZE = GRID_WIDTH // CELL_SIZE  # 125x125 logical grid

# Color Palette
BG_COLOR = (15, 15, 20)
SIDEBAR_BG = (25, 25, 35)
WALL_COLOR = (35, 35, 45)
PASSAGE_COLOR = (245, 245, 250)
TERRAIN_MUD = (85, 60, 35)          # High-cost friction zones (Cost = 5.0)
EXPLORED_START = (40, 90, 140)
EXPLORED_END = (140, 60, 40)
FINAL_PATH_COLOR = (0, 255, 127)
START_COLOR = (255, 215, 0)
END_COLOR = (255, 69, 0)
UI_BORDER = (70, 70, 90)
BUTTON_COLOR = (0, 150, 200)
BUTTON_HOVER = (0, 180, 240)
TEXT_COLOR = (240, 240, 245)
DEBUG_BG = (20, 20, 28)

MAZE_ALGOS = [
    "Randomized Prim",
    "Recursive DFS",
    "Randomized Kruskal",
    "Recursive Division"
]

PATH_ALGOS = [
    "A* Search",
    "Weighted A*",
    "Dijkstra",
    "Greedy Best-First",
    "Bidirectional A*"
]

class Slider:
    def __init__(self, x, y, w, h, min_val, max_val, val, label):
        self.rect = pygame.Rect(x, y, w, h)
        self.min_val = min_val
        self.max_val = max_val
        self.val = val
        self.label = label
        self.dragging = False

    def draw(self, screen, font):
        lbl = font.render(f"{self.label}: {self.val:.1f}" if isinstance(self.val, float) else f"{self.label}: {self.val}", True, TEXT_COLOR)
        screen.blit(lbl, (self.rect.x, self.rect.y - 18))
        
        pygame.draw.rect(screen, (50, 50, 65), self.rect, border_radius=4)
        pygame.draw.rect(screen, UI_BORDER, self.rect, 1, border_radius=4)
        
        val_range = self.max_val - self.min_val
        pos_x = self.rect.x + int((self.val - self.min_val) / val_range * self.rect.width)
        handle_rect = pygame.Rect(pos_x - 6, self.rect.y - 3, 12, self.rect.height + 6)
        pygame.draw.rect(screen, BUTTON_COLOR, handle_rect, border_radius=3)

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.rect.collidepoint(event.pos) or pygame.Rect(self.rect.x - 10, self.rect.y - 5, self.rect.width + 20, self.rect.height + 10).collidepoint(event.pos):
                self.dragging = True
                self.update_val(event.pos[0])
        elif event.type == pygame.MOUSEBUTTONUP:
            self.dragging = False
        elif event.type == pygame.MOUSEMOTION and self.dragging:
            self.update_val(event.pos[0])

    def update_val(self, mouse_x):
        rel_x = max(self.rect.x, min(mouse_x, self.rect.x + self.rect.width))
        pct = (rel_x - self.rect.x) / self.rect.width
        val_range = self.max_val - self.min_val
        self.val = self.min_val + pct * val_range
        if isinstance(self.min_val, int) and isinstance(self.max_val, int):
            self.val = round(self.val)


class MazeLaboratory:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Constraint-Driven Maze & Pathfinding Laboratory")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("Consolas", 13)
        self.font_bold = pygame.font.SysFont("Consolas", 14, bold=True)
        
        # Grid & Constraint Matrices (1 = Wall, 0 = Passage)
        self.grid = [[1 for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]
        self.cost_grid = [[1.0 for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]
        
        # State Data
        self.explored_start = set()
        self.explored_end = set()
        self.path = []
        self.start_pos = (1, 1)
        self.end_pos = (GRID_SIZE - 2, GRID_SIZE - 2)
        
        # Solver Animation State
        self.animating = False
        self.solver_generator = None
        
        # Debugger Metrics
        self.exec_time_ms = 0.0
        self.nodes_explored_count = 0
        self.path_cost_total = 0.0
        self.path_length = 0
        
        # UI State & Controls
        self.selected_maze_idx = 0
        self.selected_path_idx = 0
        self.maze_dropdown_open = False
        self.path_dropdown_open = False
        
        # Sliders
        self.solver_speed_slider = Slider(530, 205, 240, 16, 1, 100, 30, "Solver Speed (Steps/Frame)")
        self.weight_slider = Slider(530, 265, 240, 16, 0.0, 3.0, 1.0, "Heuristic Weight (W)")
        self.friction_slider = Slider(530, 325, 240, 16, 0.0, 1.0, 0.15, "Terrain Friction Density")
        
        # UI Rectangles
        self.maze_drop_rect = pygame.Rect(530, 60, 240, 30)
        self.path_drop_rect = pygame.Rect(530, 120, 240, 30)
        self.gen_btn_rect = pygame.Rect(530, 510, 115, 36)
        self.solve_btn_rect = pygame.Rect(655, 510, 115, 36)
        
        self.generate_maze()

    def generate_maze(self):
        algo = MAZE_ALGOS[self.selected_maze_idx]
        self.grid = [[1 for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]
        self.cost_grid = [[1.0 for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]
        self.explored_start.clear()
        self.explored_end.clear()
        self.path.clear()
        self.animating = False
        self.solver_generator = None
        
        if algo == "Randomized Prim":
            self.generate_prim()
        elif algo == "Recursive DFS":
            self.generate_dfs()
        elif algo == "Randomized Kruskal":
            self.generate_kruskal()
        elif algo == "Recursive Division":
            self.generate_division()
            
        # Ensure 2-point seed clearance
        self.grid[self.start_pos[1]][self.start_pos[0]] = 0
        self.grid[self.end_pos[1]][self.end_pos[0]] = 0
        
        # Inject Constraint Map (Terrain Friction)
        self.generate_constraints()
        
        self.start_solver_animation()

    def generate_constraints(self):
        # Scatter true-random high-friction hazard zones across passages
        density = self.friction_slider.val
        for y in range(GRID_SIZE):
            for x in range(GRID_SIZE):
                if self.grid[y][x] == 0:
                    # Keep start and end clear of harsh penalties
                    if (x, y) == self.start_pos or (x, y) == self.end_pos:
                        self.cost_grid[y][x] = 1.0
                    else:
                        if random.random() < density:
                            self.cost_grid[y][x] = 5.0  # High friction "mud" zone
                        else:
                            self.cost_grid[y][x] = 1.0  # Normal floor

    def start_solver_animation(self):
        self.explored_start.clear()
        self.explored_end.clear()
        self.path.clear()
        
        algo = PATH_ALGOS[self.selected_path_idx]
        
        if algo == "A* Search":
            self.solver_generator = self.step_astar(weight=1.0)
        elif algo == "Weighted A*":
            self.solver_generator = self.step_astar(weight=self.weight_slider.val)
        elif algo == "Dijkstra":
            self.solver_generator = self.step_astar(weight=0.0)
        elif algo == "Greedy Best-First":
            self.solver_generator = self.step_greedy()
        elif algo == "Bidirectional A*":
            self.solver_generator = self.step_bidirectional_astar()
            
        self.animating = True

    # --- Cost-Aware Pathfinding Step Generators ---
    def step_astar(self, weight=1.0):
        start_time = time.perf_counter()
        start, end = self.start_pos, self.end_pos
        def heuristic(a, b):
            return (abs(a[0] - b[0]) + abs(a[1] - b[1])) * weight
        
        open_set = [(0, start)]
        came_from = {}
        g_score = {start: 0.0}
        f_score = {start: heuristic(start, end)}
        open_set_hash = {start}
        
        while open_set:
            current = heapq.heappop(open_set)[1]
            open_set_hash.remove(current)
            
            if current == end:
                curr = end
                while curr in came_from:
                    self.path.append(curr)
                    curr = came_from[curr]
                self.path.reverse()
                self.exec_time_ms = (time.perf_counter() - start_time) * 1000
                self.nodes_explored_count = len(self.explored_start) + len(self.explored_end)
                self.path_length = len(self.path)
                self.path_cost_total = g_score[end]
                return
            
            self.explored_start.add(current)
            cx, cy = current
            for dx, dy in [(0, -1), (0, 1), (-1, 0), (1, 0)]:
                nx, ny = cx + dx, cy + dy
                if 0 <= nx < GRID_SIZE and 0 <= ny < GRID_SIZE and self.grid[ny][nx] == 0:
                    neighbor = (nx, ny)
                    # Cost-aware traversal calculation
                    travel_cost = self.cost_grid[ny][nx]
                    temp_g = g_score[current] + travel_cost
                    
                    if temp_g < g_score.get(neighbor, float('inf')):
                        came_from[neighbor] = current
                        g_score[neighbor] = temp_g
                        f_score[neighbor] = temp_g + heuristic(neighbor, end)
                        if neighbor not in open_set_hash:
                            heapq.heappush(open_set, (f_score[neighbor], neighbor))
                            open_set_hash.add(neighbor)
            yield

    def step_greedy(self):
        start_time = time.perf_counter()
        start, end = self.start_pos, self.end_pos
        def heuristic(a, b):
            return abs(a[0] - b[0]) + abs(a[1] - b[1])
        
        open_set = [(heuristic(start, end), start)]
        came_from = {}
        open_set_hash = {start}
        g_score = {start: 0.0}
        
        while open_set:
            current = heapq.heappop(open_set)[1]
            open_set_hash.remove(current)
            
            if current == end:
                curr = end
                while curr in came_from:
                    self.path.append(curr)
                    curr = came_from[curr]
                self.path.reverse()
                self.exec_time_ms = (time.perf_counter() - start_time) * 1000
                self.nodes_explored_count = len(self.explored_start) + len(self.explored_end)
                self.path_length = len(self.path)
                self.path_cost_total = g_score[end]
                return
            
            self.explored_start.add(current)
            cx, cy = current
            for dx, dy in [(0, -1), (0, 1), (-1, 0), (1, 0)]:
                nx, ny = cx + dx, cy + dy
                if 0 <= nx < GRID_SIZE and 0 <= ny < GRID_SIZE and self.grid[ny][nx] == 0:
                    neighbor = (nx, ny)
                    if neighbor not in came_from and neighbor != start:
                        came_from[neighbor] = current
                        g_score[neighbor] = g_score[current] + self.cost_grid[ny][nx]
                        heapq.heappush(open_set, (heuristic(neighbor, end), neighbor))
                        open_set_hash.add(neighbor)
            yield

    def step_bidirectional_astar(self):
        start_time = time.perf_counter()
        start, end = self.start_pos, self.end_pos
        def heuristic(a, b):
            return abs(a[0] - b[0]) + abs(a[1] - b[1])
        
        open_start = [(0, start)]
        came_from_start = {start: None}
        g_start = {start: 0.0}
        hash_start = {start}
        
        open_end = [(0, end)]
        came_from_end = {end: None}
        g_end = {end: 0.0}
        hash_end = {end}
        
        meeting_node = None
        
        while open_start and open_end:
            current_s = heapq.heappop(open_start)[1]
            hash_start.remove(current_s)
            self.explored_start.add(current_s)
            
            if current_s in hash_end:
                meeting_node = current_s
                break
                
            cx, cy = current_s
            for dx, dy in [(0, -1), (0, 1), (-1, 0), (1, 0)]:
                nx, ny = cx + dx, cy + dy
                if 0 <= nx < GRID_SIZE and 0 <= ny < GRID_SIZE and self.grid[ny][nx] == 0:
                    neighbor = (nx, ny)
                    travel_cost = self.cost_grid[ny][nx]
                    temp_g = g_start[current_s] + travel_cost
                    if temp_g < g_start.get(neighbor, float('inf')):
                        came_from_start[neighbor] = current_s
                        g_start[neighbor] = temp_g
                        heapq.heappush(open_start, (temp_g + heuristic(neighbor, end), neighbor))
                        hash_start.add(neighbor)
            
            current_e = heapq.heappop(open_end)[1]
            hash_end.remove(current_e)
            self.explored_end.add(current_e)
            
            if current_e in hash_start:
                meeting_node = current_e
                break
                
            cx, cy = current_e
            for dx, dy in [(0, -1), (0, 1), (-1, 0), (1, 0)]:
                nx, ny = cx + dx, cy + dy
                if 0 <= nx < GRID_SIZE and 0 <= ny < GRID_SIZE and self.grid[ny][nx] == 0:
                    neighbor = (nx, ny)
                    travel_cost = self.cost_grid[ny][nx]
                    temp_g = g_end[current_e] + travel_cost
                    if temp_g < g_end.get(neighbor, float('inf')):
                        came_from_end[neighbor] = current_e
                        g_end[neighbor] = temp_g
                        heapq.heappush(open_end, (temp_g + heuristic(neighbor, start), neighbor))
                        hash_end.add(neighbor)
            yield
                            
        if meeting_node:
            path_s, curr = [], meeting_node
            while curr is not None:
                path_s.append(curr)
                curr = came_from_start.get(curr)
            path_s.reverse()
            
            path_e, curr = [], came_from_end.get(meeting_node)
            while curr is not None:
                path_e.append(curr)
                curr = came_from_end.get(curr)
            self.path = path_s + path_e
            self.exec_time_ms = (time.perf_counter() - start_time) * 1000
            self.nodes_explored_count = len(self.explored_start) + len(self.explored_end)
            self.path_length = len(self.path)
            self.path_cost_total = g_start.get(meeting_node, 0) + g_end.get(meeting_node, 0)

    # --- Maze Generators ---
    def generate_prim(self):
        seed_a, seed_b = self.start_pos, self.end_pos
        frontier = []
        def add_frontier(cx, cy):
            for dx, dy in [(0, -2), (0, 2), (-2, 0), (2, 0)]:
                nx, ny = cx + dx, cy + dy
                if 0 <= nx < GRID_SIZE and 0 <= ny < GRID_SIZE and self.grid[ny][nx] == 1:
                    frontier.append((cx + dx // 2, cy + dy // 2, cx, cy))
        self.grid[seed_a[1]][seed_a[0]] = 0
        add_frontier(*seed_a)
        self.grid[seed_b[1]][seed_b[0]] = 0
        add_frontier(*seed_b)
        while frontier:
            idx = random.randint(0, len(frontier) - 1)
            x, y, px, py = frontier.pop(idx)
            if self.grid[y][x] == 1:
                dx, dy = x - px, y - py
                nx, ny = x + dx, y + dy
                if 0 <= nx < GRID_SIZE and 0 <= ny < GRID_SIZE:
                    if self.grid[ny][nx] == 1:
                        self.grid[y][x], self.grid[ny][nx] = 0, 0
                        add_frontier(nx, ny)
                    elif self.grid[ny][nx] == 0:
                        self.grid[y][x] = 0

    def generate_dfs(self):
        stack = [self.start_pos]
        self.grid[self.start_pos[1]][self.start_pos[0]] = 0
        while stack:
            cx, cy = stack[-1]
            neighbors = []
            for dx, dy in [(0, -2), (0, 2), (-2, 0), (2, 0)]:
                nx, ny = cx + dx, cy + dy
                if 0 < nx < GRID_SIZE - 1 and 0 < ny < GRID_SIZE - 1 and self.grid[ny][nx] == 1:
                    neighbors.append((nx, ny, dx, dy))
            if neighbors:
                nx, ny, dx, dy = random.choice(neighbors)
                self.grid[cy + dy // 2][cx + dx // 2] = 0
                self.grid[ny][nx] = 0
                stack.append((nx, ny))
            else:
                stack.pop()

    def generate_kruskal(self):
        parent = {}
        for y in range(1, GRID_SIZE - 1, 2):
            for x in range(1, GRID_SIZE - 1, 2):
                parent[(x, y)] = (x, y)
                self.grid[y][x] = 0
        
        def find(i):
            if parent[i] == i: return i
            parent[i] = find(parent[i])
            return parent[i]
        
        def union(i, j):
            root_i, root_j = find(i), find(j)
            if root_i != root_j:
                parent[root_i] = root_j
                return True
            return False

        edges = []
        for y in range(1, GRID_SIZE - 1, 2):
            for x in range(1, GRID_SIZE - 1, 2):
                if x + 2 < GRID_SIZE - 1: edges.append((x + 1, y, (x, y), (x + 2, y)))
                if y + 2 < GRID_SIZE - 1: edges.append((x, y + 1, (x, y), (x, y + 2)))
        
        random.shuffle(edges)
        for wx, wy, c1, c2 in edges:
            if c1 in parent and c2 in parent and union(c1, c2):
                self.grid[wy][wx] = 0
                self.grid[c1[1]][c1[0]] = 0
                self.grid[c2[1]][c2[0]] = 0

    def generate_division(self):
        for y in range(1, GRID_SIZE - 1):
            for x in range(1, GRID_SIZE - 1):
                self.grid[y][x] = 0
                
        def divide(x, y, w, h):
            if w < 3 or h < 3: return
            horizontal = w < h if w != h else random.choice([True, False])
            
            if horizontal:
                possible_y = [i for i in range(y + 2, y + h - 1, 2)]
                if not possible_y: return
                wy = random.choice(possible_y)
                possible_x = [i for i in range(x + 1, x + w, 2)]
                if not possible_x: return
                px = random.choice(possible_x)
                
                for cx in range(x, x + w):
                    if cx != px: self.grid[wy][cx] = 1
                divide(x, y, w, wy - y)
                divide(x, wy + 1, w, y + h - (wy + 1))
            else:
                possible_x = [i for i in range(x + 2, x + w - 1, 2)]
                if not possible_x: return
                wx = random.choice(possible_x)
                possible_y = [i for i in range(y + 1, y + h, 2)]
                if not possible_y: return
                py = random.choice(possible_y)
                
                for cy in range(y, y + h):
                    if cy != py: self.grid[cy][wx] = 1
                divide(x, y, wx - x, h)
                divide(wx + 1, y, x + w - (wx + 1), h)
                
        divide(1, 1, GRID_SIZE - 2, GRID_SIZE - 2)

    def draw(self):
        self.screen.fill(BG_COLOR)
        
        # Draw Maze Grid & Constraint Terrain
        for y in range(GRID_SIZE):
            for x in range(GRID_SIZE):
                rect = pygame.Rect(x * CELL_SIZE, y * CELL_SIZE, CELL_SIZE, CELL_SIZE)
                pos = (x, y)
                if self.grid[y][x] == 1:
                    pygame.draw.rect(self.screen, WALL_COLOR, rect)
                elif pos in self.explored_start:
                    pygame.draw.rect(self.screen, EXPLORED_START, rect)
                elif pos in self.explored_end:
                    pygame.draw.rect(self.screen, EXPLORED_END, rect)
                elif self.cost_grid[y][x] > 1.0:
                    pygame.draw.rect(self.screen, TERRAIN_MUD, rect)
                
        # Draw Final Path
        for pos in self.path:
            rect = pygame.Rect(pos[0] * CELL_SIZE, pos[1] * CELL_SIZE, CELL_SIZE, CELL_SIZE)
            pygame.draw.rect(self.screen, FINAL_PATH_COLOR, rect)
            
        # Draw Start / End Markers
        start_rect = pygame.Rect(self.start_pos[0] * CELL_SIZE, self.start_pos[1] * CELL_SIZE, CELL_SIZE, CELL_SIZE)
        end_rect = pygame.Rect(self.end_pos[0] * CELL_SIZE, self.end_pos[1] * CELL_SIZE, CELL_SIZE, CELL_SIZE)
        pygame.draw.rect(self.screen, START_COLOR, start_rect)
        pygame.draw.rect(self.screen, END_COLOR, end_rect)
        
        # --- Sidebar UI ---
        pygame.draw.rect(self.screen, SIDEBAR_BG, (GRID_WIDTH, 0, WIDTH - GRID_WIDTH, HEIGHT))
        pygame.draw.line(self.screen, UI_BORDER, (GRID_WIDTH, 0), (GRID_WIDTH, HEIGHT), 2)
        
        mouse_pos = pygame.mouse.get_pos()
        
        self.screen.blit(self.font_bold.render("MAZE GENERATION", True, TEXT_COLOR), (530, 35))
        self.screen.blit(self.font_bold.render("PATHFINDING ALGO", True, TEXT_COLOR), (530, 95))
        
        # Dropdown Boxes
        pygame.draw.rect(self.screen, (40, 40, 55), self.maze_drop_rect, border_radius=5)
        pygame.draw.rect(self.screen, UI_BORDER, self.maze_drop_rect, 1, border_radius=5)
        m_text = self.font.render(MAZE_ALGOS[self.selected_maze_idx], True, TEXT_COLOR)
        self.screen.blit(m_text, (self.maze_drop_rect.x + 8, self.maze_drop_rect.centery - m_text.get_height() // 2))
        
        pygame.draw.rect(self.screen, (40, 40, 55), self.path_drop_rect, border_radius=5)
        pygame.draw.rect(self.screen, UI_BORDER, self.path_drop_rect, 1, border_radius=5)
        p_text = self.font.render(PATH_ALGOS[self.selected_path_idx], True, TEXT_COLOR)
        self.screen.blit(p_text, (self.path_drop_rect.x + 8, self.path_drop_rect.centery - p_text.get_height() // 2))
        
        # Sliders
        self.solver_speed_slider.draw(self.screen, self.font)
        self.weight_slider.draw(self.screen, self.font)
        self.friction_slider.draw(self.screen, self.font)
        
        # Debugger Metrics Box
        debug_box = pygame.Rect(525, 360, 250, 135)
        pygame.draw.rect(self.screen, DEBUG_BG, debug_box, border_radius=6)
        pygame.draw.rect(self.screen, UI_BORDER, debug_box, 1, border_radius=6)
        
        self.screen.blit(self.font_bold.render("--- DEBUGGER METRICS ---", True, (0, 200, 255)), (535, 370))
        stats = [
            f"Nodes Explored: {self.nodes_explored_count:,}",
            f"Path Steps: {self.path_length:,}",
            f"Total Path Cost: {self.path_cost_total:.1f}",
            f"Exec Time: {self.exec_time_ms:.3f} ms"
        ]
        for idx, stat in enumerate(stats):
            st_text = self.font.render(stat, True, TEXT_COLOR)
            self.screen.blit(st_text, (535, 395 + idx * 20))
        
        # Buttons
        gen_color = BUTTON_HOVER if self.gen_btn_rect.collidepoint(mouse_pos) else BUTTON_COLOR
        pygame.draw.rect(self.screen, gen_color, self.gen_btn_rect, border_radius=5)
        gen_lbl = self.font_bold.render("Generate", True, TEXT_COLOR)
        self.screen.blit(gen_lbl, (self.gen_btn_rect.centerx - gen_lbl.get_width() // 2, self.gen_btn_rect.centery - gen_lbl.get_height() // 2))
        
        solve_color = BUTTON_HOVER if self.solve_btn_rect.collidepoint(mouse_pos) else BUTTON_COLOR
        pygame.draw.rect(self.screen, solve_color, self.solve_btn_rect, border_radius=5)
        solve_lbl = self.font_bold.render("Re-Solve", True, TEXT_COLOR)
        self.screen.blit(solve_lbl, (self.solve_btn_rect.centerx - solve_lbl.get_width() // 2, self.solve_btn_rect.centery - solve_lbl.get_height() // 2))
        
        # Dropdown Menus
        if self.maze_dropdown_open:
            for i, algo in enumerate(MAZE_ALGOS):
                item_rect = pygame.Rect(self.maze_drop_rect.x, self.maze_drop_rect.y + (i + 1) * 32, self.maze_drop_rect.width, 30)
                bg_c = (60, 60, 80) if item_rect.collidepoint(mouse_pos) else (35, 35, 50)
                pygame.draw.rect(self.screen, bg_c, item_rect, border_radius=4)
                pygame.draw.rect(self.screen, UI_BORDER, item_rect, 1, border_radius=4)
                self.screen.blit(self.font.render(algo, True, TEXT_COLOR), (item_rect.x + 8, item_rect.centery - 7))
                
        if self.path_dropdown_open:
            for i, algo in enumerate(PATH_ALGOS):
                item_rect = pygame.Rect(self.path_drop_rect.x, self.path_drop_rect.y + (i + 1) * 32, self.path_drop_rect.width, 30)
                bg_c = (60, 60, 80) if item_rect.collidepoint(mouse_pos) else (35, 35, 50)
                pygame.draw.rect(self.screen, bg_c, item_rect, border_radius=4)
                pygame.draw.rect(self.screen, UI_BORDER, item_rect, 1, border_radius=4)
                self.screen.blit(self.font.render(algo, True, TEXT_COLOR), (item_rect.x + 8, item_rect.centery - 7))

        pygame.display.flip()

    def handle_event(self, event):
        self.solver_speed_slider.handle_event(event)
        self.weight_slider.handle_event(event)
        self.friction_slider.handle_event(event)
        
        if event.type == pygame.MOUSEBUTTONDOWN:
            pos = event.pos
            if self.gen_btn_rect.collidepoint(pos):
                self.maze_dropdown_open = False
                self.path_dropdown_open = False
                self.generate_maze()
            elif self.solve_btn_rect.collidepoint(pos):
                self.maze_dropdown_open = False
                self.path_dropdown_open = False
                self.start_solver_animation()
            elif self.maze_drop_rect.collidepoint(pos):
                self.maze_dropdown_open = not self.maze_dropdown_open
                self.path_dropdown_open = False
            elif self.path_drop_rect.collidepoint(pos):
                self.path_dropdown_open = not self.path_dropdown_open
                self.maze_dropdown_open = False
            elif self.maze_dropdown_open:
                for i, algo in enumerate(MAZE_ALGOS):
                    item_rect = pygame.Rect(self.maze_drop_rect.x, self.maze_drop_rect.y + (i + 1) * 32, self.maze_drop_rect.width, 30)
                    if item_rect.collidepoint(pos):
                        self.selected_maze_idx = i
                        self.maze_dropdown_open = False
                        self.generate_maze()
                        break
            elif self.path_dropdown_open:
                for i, algo in enumerate(PATH_ALGOS):
                    item_rect = pygame.Rect(self.path_drop_rect.x, self.path_drop_rect.y + (i + 1) * 32, self.path_drop_rect.width, 30)
                    if item_rect.collidepoint(pos):
                        self.selected_path_idx = i
                        self.path_dropdown_open = False
                        self.start_solver_animation()
                        break
            else:
                self.maze_dropdown_open = False
                self.path_dropdown_open = False

    def run(self):
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                else:
                    self.handle_event(event)
            
            if self.animating and self.solver_generator:
                steps = int(self.solver_speed_slider.val)
                try:
                    for _ in range(steps):
                        next(self.solver_generator)
                except StopIteration:
                    self.animating = False
                    self.solver_generator = None

            self.draw()
            self.clock.tick(60)
        pygame.quit()
        sys.exit()

if __name__ == "__main__":
    lab = MazeLaboratory()
    lab.run()