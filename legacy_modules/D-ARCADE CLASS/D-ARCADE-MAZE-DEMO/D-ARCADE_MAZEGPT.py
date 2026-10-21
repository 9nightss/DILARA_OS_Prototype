"""
Maze Lab — Phase 1: bidirectional Randomized Prim
Python 3.x, standard library only (Tkinter).

Canvas: 500x500 pixels. Logical cell size: 4 pixels by default (125x125 cells).
Two frontiers grow from opposite corners. The two regions are joined by opening
a valid wall between them, guaranteeing a connected maze.

This is a bidirectional randomized Prim-style growth variant. A* uses Manhattan
distance, four-directional movement, and uniform edge costs.
"""

import heapq
import itertools
import random
import time
import tkinter as tk
from tkinter import ttk, messagebox
from collections import deque

CANVAS_SIZE = 500
DEFAULT_CELL_SIZE = 4
WALL = "#202733"
FLOOR = "#f4f6f8"
START = "#20a464"
GOAL = "#e24b4b"


class Maze:
    DIRECTIONS = (
        (0, -1, "N", "S"),
        (1, 0, "E", "W"),
        (0, 1, "S", "N"),
        (-1, 0, "W", "E"),
    )

    def __init__(self, cols, rows, rng):
        self.cols = cols
        self.rows = rows
        self.rng = rng
        self.walls = [
            [{"N": True, "E": True, "S": True, "W": True} for _ in range(cols)]
            for _ in range(rows)
        ]

    def neighbors(self, x, y):
        result = []
        for dx, dy, direction, opposite in self.DIRECTIONS:
            nx, ny = x + dx, y + dy
            if 0 <= nx < self.cols and 0 <= ny < self.rows:
                result.append((nx, ny, direction, opposite))
        return result

    def remove_wall(self, x, y, nx, ny, direction, opposite):
        self.walls[y][x][direction] = False
        self.walls[ny][nx][opposite] = False

    def bidirectional_prim(self):
        """Synchronous compatibility wrapper; consume the incremental generator."""
        for _ in self.iter_bidirectional_prim():
            pass

    def iter_bidirectional_prim(self):
        """Incremental bidirectional randomized Prim; yields generation progress."""
        visited = [[False] * self.cols for _ in range(self.rows)]
        region = [[-1] * self.cols for _ in range(self.rows)]
        frontiers = [[], []]
        seeds = [(0, 0), (self.cols - 1, self.rows - 1)]
        visited_count = 0
        joined = False

        for region_id, (sx, sy) in enumerate(seeds):
            if visited[sy][sx]:
                continue
            visited[sy][sx] = True
            region[sy][sx] = region_id
            visited_count += 1
            self._add_frontier(sx, sy, region_id, visited, region, frontiers[region_id])
            yield visited_count, (sx, sy), region_id

        while visited_count < self.cols * self.rows:
            available = [rid for rid in (0, 1) if frontiers[rid]]
            if not available:
                raise RuntimeError("Prim frontiers exhausted before covering the grid")
            rid = self.rng.choice(available)
            frontier = frontiers[rid]
            idx = self.rng.randrange(len(frontier))
            x, y, nx, ny, direction, opposite = frontier.pop(idx)
            if visited[ny][nx]:
                continue

            self.remove_wall(x, y, nx, ny, direction, opposite)
            visited[ny][nx] = True
            region[ny][nx] = rid
            visited_count += 1
            self._add_frontier(nx, ny, rid, visited, region, frontier)

            if not joined:
                cross_edges = []
                for ax, ay, d, od in self.neighbors(nx, ny):
                    if region[ay][ax] == 1 - rid:
                        cross_edges.append((nx, ny, ax, ay, d, od))
                if cross_edges:
                    bx, by, ox, oy, d, od = self.rng.choice(cross_edges)
                    self.remove_wall(bx, by, ox, oy, d, od)
                    joined = True
            yield visited_count, (nx, ny), rid

        if not joined and self.cols * self.rows > 1:
            raise RuntimeError("The two Prim regions did not connect")

    def _add_frontier(self, x, y, region_id, visited, region, frontier):
        for nx, ny, direction, opposite in self.neighbors(x, y):
            if not visited[ny][nx]:
                frontier.append((x, y, nx, ny, direction, opposite))

    def astar(self, start=(0, 0), goal=None):
        """Return (path, expanded_count, discovered_count, elapsed_ms)."""
        if goal is None:
            goal = (self.cols - 1, self.rows - 1)
        t0 = time.perf_counter()

        def heuristic(pos):
            return abs(pos[0] - goal[0]) + abs(pos[1] - goal[1])

        counter = itertools.count()
        open_heap = [(heuristic(start), 0, next(counter), start)]
        g_score = {start: 0}
        parent = {}
        closed = set()
        expanded = 0
        discovered = {start}

        while open_heap:
            f_score, g_current, _, current = heapq.heappop(open_heap)
            if current in closed or g_current != g_score.get(current):
                continue
            if current == goal:
                path = [goal]
                while path[-1] != start:
                    path.append(parent[path[-1]])
                path.reverse()
                return path, expanded, len(discovered), (time.perf_counter() - t0) * 1000

            closed.add(current)
            expanded += 1
            x, y = current
            for nx, ny, direction, opposite in self.neighbors(x, y):
                if self.walls[y][x][direction]:
                    continue
                neighbor = (nx, ny)
                tentative_g = g_current + 1
                if tentative_g < g_score.get(neighbor, float("inf")):
                    parent[neighbor] = current
                    g_score[neighbor] = tentative_g
                    discovered.add(neighbor)
                    if neighbor in closed:
                        closed.remove(neighbor)
                    heapq.heappush(
                        open_heap,
                        (tentative_g + heuristic(neighbor), tentative_g, next(counter), neighbor),
                    )

        return None, expanded, len(discovered), (time.perf_counter() - t0) * 1000

    def bfs(self, start=(0, 0), goal=None):
        """Reference BFS for comparison; returns path and standard search metrics."""
        from collections import deque
        if goal is None:
            goal = (self.cols - 1, self.rows - 1)
        t0 = time.perf_counter()
        queue = deque([start])
        parent = {start: None}
        discovered = {start}
        expanded = 0
        while queue:
            current = queue.popleft()
            if current == goal:
                path = []
                node = goal
                while node is not None:
                    path.append(node)
                    node = parent[node]
                path.reverse()
                return path, expanded, len(discovered), (time.perf_counter() - t0) * 1000
            expanded += 1
            x, y = current
            for nx, ny, direction, opposite in self.neighbors(x, y):
                if self.walls[y][x][direction]:
                    continue
                neighbor = (nx, ny)
                if neighbor not in discovered:
                    discovered.add(neighbor)
                    parent[neighbor] = current
                    queue.append(neighbor)
        return None, expanded, len(discovered), (time.perf_counter() - t0) * 1000

    def bidirectional_bfs(self, start=(0, 0), goal=None):
        """Layer-based bidirectional BFS; shortest path for unit-cost edges."""
        from collections import deque
        if goal is None:
            goal = (self.cols - 1, self.rows - 1)
        t0 = time.perf_counter()
        if start == goal:
            return [start], 0, 1, (time.perf_counter() - t0) * 1000

        queues = [deque([start]), deque([goal])]
        parents = [{start: None}, {goal: None}]
        distances = [{start: 0}, {goal: 0}]
        expanded = 0
        best_distance = float('inf')
        meeting = None

        def open_neighbors(pos):
            x, y = pos
            for nx, ny, direction, opposite in self.neighbors(x, y):
                if not self.walls[y][x][direction]:
                    yield (nx, ny)

        while queues[0] and queues[1]:
            # Each iteration expands a complete depth layer from the smaller frontier.
            side = 0 if len(queues[0]) <= len(queues[1]) else 1
            other = 1 - side
            layer_depth = distances[side][queues[side][0]]
            layer_count = len(queues[side])

            for _ in range(layer_count):
                current = queues[side].popleft()
                expanded += 1
                if current in distances[other]:
                    candidate = distances[side][current] + distances[other][current]
                    if candidate < best_distance:
                        best_distance, meeting = candidate, current
                for neighbor in open_neighbors(current):
                    if neighbor not in distances[side]:
                        distances[side][neighbor] = distances[side][current] + 1
                        parents[side][neighbor] = current
                        queues[side].append(neighbor)
                    if neighbor in distances[other]:
                        candidate = distances[side][current] + 1 + distances[other][neighbor]
                        if candidate < best_distance:
                            best_distance = candidate
                            meeting = (current, neighbor) if side == 0 else (neighbor, current)

            # The queue heads are the shallowest not-yet-expanded layers.
            # Once their depth lower bound reaches the best complete route,
            # no shorter path can still be discovered.
            if best_distance < float('inf') and queues[0] and queues[1]:
                lower_bound = distances[0][queues[0][0]] + distances[1][queues[1][0]]
                if lower_bound >= best_distance:
                    break

        if meeting is None:
            return None, expanded, len(set(parents[0]) | set(parents[1])), (time.perf_counter() - t0) * 1000

        if isinstance(meeting[0], tuple):
            left_meet, right_meet = meeting
            left_path = []
            node = left_meet
            while node is not None:
                left_path.append(node)
                node = parents[0][node]
            left_path.reverse()
            right_path = []
            node = right_meet
            while node is not None:
                right_path.append(node)
                node = parents[1][node]
            path = left_path + right_path
        else:
            left_path = []
            node = meeting
            while node is not None:
                left_path.append(node)
                node = parents[0][node]
            left_path.reverse()
            right_path = []
            node = parents[1][meeting]
            while node is not None:
                right_path.append(node)
                node = parents[1][node]
            path = left_path + right_path

        # Remove a possible duplicate where both halves meet at one cell.
        deduped = [path[0]]
        for node in path[1:]:
            if node != deduped[-1]:
                deduped.append(node)
        return deduped, expanded, len(set(parents[0]) | set(parents[1])), (time.perf_counter() - t0) * 1000

    def open_edges_count(self):
        count = 0
        for y in range(self.rows):
            for x in range(self.cols):
                if x + 1 < self.cols and not self.walls[y][x]["E"]:
                    count += 1
                if y + 1 < self.rows and not self.walls[y][x]["S"]:
                    count += 1
        return count

    def reachable_count(self, start=(0, 0)):
        """Connectivity sanity check; later reusable for solver validation."""
        sx, sy = start
        seen = {(sx, sy)}
        stack = [(sx, sy)]
        while stack:
            x, y = stack.pop()
            for nx, ny, direction, opposite in self.neighbors(x, y):
                if not self.walls[y][x][direction] and (nx, ny) not in seen:
                    seen.add((nx, ny))
                    stack.append((nx, ny))
        return len(seen)


class MazeLab:
    def __init__(self, root):
        self.root = root
        root.title("Maze Lab — Bidirectional Prim + A*")
        root.resizable(False, False)

        self.cell_size = tk.IntVar(value=DEFAULT_CELL_SIZE)
        self.solver_name = tk.StringVar(value="Bidirectional BFS")
        self.seed_text = tk.StringVar(value="")
        self.status = tk.StringVar(value="Ready.")
        self.maze = None
        self.path = None
        self.last_seed = None
        self.last_stats = None
        self.generation_job = None
        self.generation_iter = None
        self.generation_started = None
        self.generation_count = 0
        self.debug_window = None
        self.debug_text = None
        self.debug_lines = deque(maxlen=500)
        self.debug_enabled = tk.BooleanVar(value=True)
        self.speed = tk.DoubleVar(value=1.0)
        self.generation_batch = tk.IntVar(value=100)
        self.max_cells = tk.IntVar(value=15625)
        self.constraint_tree = tk.BooleanVar(value=True)
        self.constraint_connected = tk.BooleanVar(value=True)
        self.constraint_min_size = tk.IntVar(value=4)

        outer = ttk.Frame(root, padding=12)
        outer.grid(row=0, column=0)

        ttk.Label(outer, text="MAZE LAB", font=("Segoe UI", 16, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w"
        )
        ttk.Label(
            outer,
            text="Bidirectional Randomized Prim + A* • 500 × 500 px canvas",
            foreground="#536171",
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(2, 10))

        controls = ttk.Frame(outer)
        controls.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(0, 8))

        ttk.Label(controls, text="Cell size").grid(row=0, column=0, sticky="w")
        ttk.Combobox(
            controls, textvariable=self.cell_size, values=(4, 5, 10, 20, 25, 50),
            state="readonly", width=5
        ).grid(row=0, column=1, padx=(8, 16), sticky="w")

        ttk.Label(controls, text="Seed (optional)").grid(row=0, column=2, sticky="w")
        ttk.Entry(controls, textvariable=self.seed_text, width=12).grid(
            row=0, column=3, padx=(8, 12), sticky="w"
        )
        ttk.Button(controls, text="Generate", command=self.generate).grid(
            row=0, column=4, sticky="w", padx=(0, 6)
        )
        ttk.Label(controls, text="Solver").grid(row=0, column=5, sticky="w", padx=(0, 4))
        ttk.Combobox(
            controls, textvariable=self.solver_name,
            values=("A*", "BFS", "Bidirectional BFS"),
            state="readonly", width=18
        ).grid(row=0, column=6, padx=(0, 8), sticky="w")
        ttk.Button(controls, text="Run search", command=self.solve).grid(
            row=0, column=7, sticky="w"
        )
        ttk.Button(controls, text="Debugger", command=self.toggle_debugger).grid(
            row=0, column=8, sticky="w", padx=(8, 0)
        )

        settings = ttk.LabelFrame(outer, text="Generation speed and constraints", padding=(8, 5))
        settings.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        ttk.Label(settings, text="Animation speed").grid(row=0, column=0, sticky="w")
        self.speed_scale = ttk.Scale(settings, from_=0.25, to=4.0, variable=self.speed,
                                     orient="horizontal", length=170,
                                     command=self._speed_changed)
        self.speed_scale.grid(row=0, column=1, padx=(6, 8), sticky="w")
        self.speed_label = ttk.Label(settings, text="1.0×")
        self.speed_label.grid(row=0, column=2, sticky="w", padx=(0, 16))
        ttk.Label(settings, text="Max cells").grid(row=0, column=3, sticky="w")
        ttk.Spinbox(settings, from_=1, to=15625, increment=625, textvariable=self.max_cells,
                    width=7).grid(row=0, column=4, padx=(5, 14), sticky="w")
        ttk.Checkbutton(settings, text="Perfect-maze tree (N−1 edges)",
                        variable=self.constraint_tree).grid(row=0, column=5, sticky="w")
        ttk.Checkbutton(settings, text="Require connected grid",
                        variable=self.constraint_connected).grid(row=0, column=6, sticky="w", padx=(8, 0))
        ttk.Label(settings, text="Minimum cell px").grid(row=1, column=0, sticky="w", pady=(5, 0))
        ttk.Spinbox(settings, from_=1, to=50, increment=1, textvariable=self.constraint_min_size,
                    width=5).grid(row=1, column=1, sticky="w", pady=(5, 0))
        ttk.Label(settings, text="Speed changes animation batching, not maze topology.",
                  foreground="#536171").grid(row=1, column=3, columnspan=4, sticky="w", pady=(5, 0))

        self.canvas = tk.Canvas(
            outer, width=CANVAS_SIZE, height=CANVAS_SIZE,
            bg=FLOOR, highlightthickness=1, highlightbackground="#aab3bf"
        )
        self.canvas.grid(row=4, column=0, columnspan=2)

        self.stats_label = ttk.Label(outer, text="Grid: — | Cells: — | Open connections: —")
        self.stats_label.grid(row=5, column=0, columnspan=2, sticky="w", pady=(10, 0))
        self.time_label = ttk.Label(outer, text="Generation: — | Connectivity: —")
        self.time_label.grid(row=6, column=0, columnspan=2, sticky="w", pady=(3, 0))
        self.path_label = ttk.Label(outer, text="A*: not run | Path: — | Expanded: — | Discovered: —")
        self.path_label.grid(row=7, column=0, columnspan=2, sticky="w", pady=(3, 0))
        ttk.Label(
            outer,
            text="Green = start (top-left)   •   Red = goal (bottom-right)",
            foreground="#536171",
        ).grid(row=8, column=0, columnspan=2, sticky="w", pady=(8, 0))
        ttk.Label(outer, textvariable=self.status, foreground="#245c9c").grid(
            row=9, column=0, columnspan=2, sticky="w", pady=(5, 0)
        )

        self.generate()

    def _speed_changed(self, _value=None):
        value = self.speed.get()
        self.speed_label.config(text=f"{value:.2f}×")

    def _log(self, message):
        stamp = time.strftime("%H:%M:%S")
        line = f"[{stamp}] {message}"
        self.debug_lines.append(line)
        if self.debug_text is not None and self.debug_window is not None and self.debug_window.winfo_exists():
            self.debug_text.configure(state="normal")
            self.debug_text.insert("end", line + "\n")
            self.debug_text.see("end")
            self.debug_text.configure(state="disabled")

    def toggle_debugger(self):
        if self.debug_window is not None and self.debug_window.winfo_exists():
            self.debug_window.destroy()
            self.debug_window = None
            self.debug_text = None
            return
        win = tk.Toplevel(self.root)
        win.title("Maze Lab — Debugger")
        win.geometry("520x360")
        self.debug_window = win
        frame = ttk.Frame(win, padding=8)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Generation / solver event log", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        text_frame = ttk.Frame(frame)
        text_frame.pack(fill="both", expand=True, pady=(6, 0))
        self.debug_text = tk.Text(text_frame, wrap="word", state="disabled", font=("Consolas", 9))
        scroll = ttk.Scrollbar(text_frame, orient="vertical", command=self.debug_text.yview)
        self.debug_text.configure(yscrollcommand=scroll.set)
        self.debug_text.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        ttk.Button(frame, text="Clear log", command=self.clear_debug_log).pack(anchor="e", pady=(6, 0))
        for line in self.debug_lines:
            self.debug_text.configure(state="normal")
            self.debug_text.insert("end", line + "\n")
            self.debug_text.configure(state="disabled")
        self.debug_text.see("end")
        win.protocol("WM_DELETE_WINDOW", self._close_debugger)

    def _close_debugger(self):
        if self.debug_window is not None:
            self.debug_window.destroy()
        self.debug_window = None
        self.debug_text = None

    def clear_debug_log(self):
        self.debug_lines.clear()
        if self.debug_text is not None:
            self.debug_text.configure(state="normal")
            self.debug_text.delete("1.0", "end")
            self.debug_text.configure(state="disabled")

    def generate(self):
        if self.generation_job is not None:
            try:
                self.root.after_cancel(self.generation_job)
            except tk.TclError:
                pass
            self.generation_job = None
        try:
            size = int(self.cell_size.get())
            seed_raw = self.seed_text.get().strip()
            seed = int(seed_raw) if seed_raw else None
            max_cells = int(self.max_cells.get())
            min_size = int(self.constraint_min_size.get())
        except (ValueError, tk.TclError):
            messagebox.showerror("Invalid input", "Seed, max cells and minimum cell size must be integers.")
            return

        if size < 1 or CANVAS_SIZE % size:
            messagebox.showerror("Invalid cell size", "Cell size must divide 500 exactly.")
            return
        if size < min_size:
            messagebox.showerror("Constraint violation", f"Cell size {size}px is below the configured minimum of {min_size}px.")
            return
        cols = rows = CANVAS_SIZE // size
        cells = cols * rows
        if cells > max_cells:
            messagebox.showerror("Constraint violation", f"This grid needs {cells:,} cells, exceeding the configured limit of {max_cells:,}.")
            return

        rng = random.Random(seed)
        maze = Maze(cols, rows, rng)
        self.maze = maze
        self.path = None
        self.last_seed = seed
        self.last_stats = None
        self.generation_count = 0
        self.generation_started = time.perf_counter()
        self.generation_iter = maze.iter_bidirectional_prim()
        self.path_label.config(text="Search: not run | Path: — | Expanded: — | Discovered: —")
        self.stats_label.config(text=f"Grid: {cols} × {rows} | Cells: {cells:,} | Open connections: generating…")
        self.time_label.config(text="Generation: running… | Connectivity: pending")
        self.status.set("Generating maze… animation speed controls cells processed per UI tick.")
        self._log(f"Generation started: grid={cols}x{rows}, cells={cells}, seed={seed if seed is not None else 'random'}")
        self.draw_maze()
        self._generation_tick()

    def _generation_tick(self):
        if self.generation_iter is None:
            return
        # Higher speed means more algorithm steps per Tkinter event, preserving UI responsiveness.
        batch = max(1, int(40 * self.speed.get()))
        total = self.maze.cols * self.maze.rows
        try:
            for _ in range(batch):
                count, position, region_id = next(self.generation_iter)
                self.generation_count = count
        except StopIteration:
            self.generation_iter = None
            elapsed_ms = (time.perf_counter() - self.generation_started) * 1000
            reachable = self.maze.reachable_count()
            edges = self.maze.open_edges_count()
            connected = reachable == total
            tree_ok = edges == total - 1
            constraints_ok = (not self.constraint_connected.get() or connected) and (not self.constraint_tree.get() or tree_ok)
            self.stats_label.config(text=f"Grid: {self.maze.cols} × {self.maze.rows} | Cells: {total:,} | Open connections: {edges:,}")
            self.time_label.config(text=f"Generation: {elapsed_ms:.3f} ms | Connectivity: {'PASS' if connected else f'FAIL ({reachable:,}/{total:,})'} | Tree: {'PASS' if tree_ok else 'FAIL'}")
            seed_label = str(self.last_seed) if self.last_seed is not None else "random"
            self.status.set(f"Generation complete | seed: {seed_label} | constraints: {'PASS' if constraints_ok else 'FAIL'}")
            self._log(f"Generation complete: {elapsed_ms:.3f} ms, edges={edges}, connected={connected}, tree={tree_ok}")
            self.draw_maze()
            if self.constraint_connected.get() and not connected:
                messagebox.showerror("Constraint failure", "Generated maze is not fully connected.")
            if self.constraint_tree.get() and not tree_ok:
                messagebox.showerror("Constraint failure", "Perfect-maze constraint failed: open edges must equal cells − 1.")
            return
        except Exception as exc:
            self.generation_iter = None
            self._log(f"Generation ERROR: {type(exc).__name__}: {exc}")
            self.status.set(f"Generation failed: {exc}")
            messagebox.showerror("Generation failed", str(exc))
            return

        # Repaint only at batch boundaries; the current wall state shows the build-up.
        if self.generation_count % 1250 < batch or self.generation_count == total:
            self.draw_maze()
            self._log(f"Progress: {self.generation_count:,}/{total:,} cells ({100*self.generation_count/total:.1f}%)")
        self.generation_job = self.root.after(1, self._generation_tick)

    def solve(self):
        if self.generation_iter is not None:
            self.status.set("Wait for maze generation to finish before running a search.")
            self._log("Search blocked: generation is still running")
            return
        if self.maze is None:
            return
        selected = self.solver_name.get()
        self._log(f"Search started: solver={selected}, grid={self.maze.cols}x{self.maze.rows}")
        if selected == "BFS":
            path, expanded, discovered, elapsed_ms = self.maze.bfs()
        elif selected == "Bidirectional BFS":
            path, expanded, discovered, elapsed_ms = self.maze.bidirectional_bfs()
        else:
            path, expanded, discovered, elapsed_ms = self.maze.astar()
        self.path = path
        if path is None:
            self.path_label.config(
                text=f"{selected}: no route | Expanded: {expanded:,} | Discovered: {discovered:,}"
            )
            self.status.set(f"{selected} could not find a route; check maze connectivity.")
        else:
            self.path_label.config(
                text=f"{selected}: {elapsed_ms:.3f} ms | Path: {len(path) - 1:,} moves | "
                     f"Expanded: {expanded:,} | Discovered: {discovered:,}"
            )
            detail = "Manhattan heuristic" if selected == "A*" else "uniform-cost search"
            self.status.set(f"{selected} complete | {detail} | 4-way movement")
        self.last_stats = (expanded, discovered, elapsed_ms, len(path) - 1 if path else None)
        self._log(f"Search finished: solver={selected}, time={elapsed_ms:.3f} ms, expanded={expanded}, discovered={discovered}, moves={len(path)-1 if path else 'no route'}")
        self.draw_maze()

    def draw_maze(self):
        self.canvas.delete("all")
        maze = self.maze
        if maze is None:
            return
        cw = CANVAS_SIZE / maze.cols
        ch = CANVAS_SIZE / maze.rows

        for y in range(maze.rows):
            for x in range(maze.cols):
                x0, y0 = x * cw, y * ch
                x1, y1 = x0 + cw, y0 + ch
                walls = maze.walls[y][x]
                if walls["N"]:
                    self.canvas.create_line(x0, y0, x1, y0, fill=WALL, width=1)
                if walls["W"]:
                    self.canvas.create_line(x0, y0, x0, y1, fill=WALL, width=1)
                if x == maze.cols - 1 and walls["E"]:
                    self.canvas.create_line(x1, y0, x1, y1, fill=WALL, width=1)
                if y == maze.rows - 1 and walls["S"]:
                    self.canvas.create_line(x0, y1, x1, y1, fill=WALL, width=1)

        # Draw the A* route over the passages, beneath the endpoint markers.
        if self.path and len(self.path) > 1:
            points = []
            for px, py in self.path:
                points.extend(((px + 0.5) * cw, (py + 0.5) * ch))
            self.canvas.create_line(
                *points, fill="#2878d0", width=max(1, min(cw, ch) * 0.55),
                capstyle=tk.ROUND, joinstyle=tk.ROUND
            )

        inset = max(0.5, min(cw, ch) * 0.18)
        self.canvas.create_oval(
            inset, inset, cw - inset, ch - inset, fill=START, outline=""
        )
        gx0, gy0 = (maze.cols - 1) * cw, (maze.rows - 1) * ch
        self.canvas.create_oval(
            gx0 + inset, gy0 + inset, gx0 + cw - inset, gy0 + ch - inset,
            fill=GOAL, outline=""
        )


def main():
    root = tk.Tk()
    try:
        style = ttk.Style(root)
        if "clam" in style.theme_names():
            style.theme_use("clam")
    except tk.TclError:
        pass
    MazeLab(root)
    root.mainloop()


if __name__ == "__main__":
    main()
