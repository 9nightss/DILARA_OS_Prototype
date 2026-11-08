import math
import random
import pygame

# --- CONFIGURATION ---
SCREEN_WIDTH = 640
SCREEN_HEIGHT = 480
FOV = math.pi / 3  # 60 degrees field of view
MAX_DEPTH = 16.0   # Maximum render distance in grid units
CELL_SIZE = 20     # World scale per cell

# Color palette (Retro aesthetic)
COLOR_SKY = (32, 39, 51)
COLOR_FLOOR = (80, 90, 105)
COLOR_WALL_N = (160, 50, 50)
COLOR_WALL_S = (120, 35, 35)
COLOR_WALL_E = (140, 40, 40)
COLOR_WALL_W = (100, 30, 30)

class MazeRaycaster:
    def __init__(self, cols, rows, seed=None):
        self.cols = cols
        self.rows = rows
        self.rng = random.Random(seed)
        self.walls = self._generate_maze()
        
        # Player state (starts at center of top-left cell)
        self.player_x = 1.5
        self.player_y = 1.5
        self.player_angle = 0.0
        self.player_speed = 3.0
        self.rot_speed = 2.5

    def _generate_maze(self):
        """Generates the grid using randomized Prim's algorithm matching your architecture."""
        DIRECTIONS = ((0, -1, "N", "S"), (1, 0, "E", "W"), (0, 1, "S", "N"), (-1, 0, "W", "E"))
        walls = [[{"N": True, "E": True, "S": True, "W": True} for _ in range(self.cols)] for _ in range(self.rows)]
        visited = [[False] * self.cols for _ in range(self.rows)]
        region = [[-1] * self.cols for _ in range(self.rows)]
        
        # Simple Prim's growth from top-left
        frontier = []
        sx, sy = 0, 0
        visited[sy][sx] = True
        
        def add_frontier(x, y):
            for dx, dy, d, od in DIRECTIONS:
                nx, ny = x + dx, y + dy
                if 0 <= nx < self.cols and 0 <= ny < self.rows and not visited[ny][nx]:
                    frontier.append((x, y, nx, ny, d, od))

        add_frontier(sx, sy)
        
        while frontier:
            idx = self.rng.randrange(len(frontier))
            x, y, nx, ny, d, od = frontier.pop(idx)
            if visited[ny][nx]:
                continue
            walls[y][x][d] = False
            walls[ny][nx][od] = False
            visited[ny][nx] = True
            add_frontier(nx, ny)
            
        return walls

    def cast_rays(self, surface):
        """Renders 3D columns using a software buffer."""
        # Draw background flats (sky and floor)
        half_height = SCREEN_HEIGHT // 2
        pygame.draw.rect(surface, COLOR_SKY, (0, 0, SCREEN_WIDTH, half_height))
        pygame.draw.rect(surface, COLOR_FLOOR, (0, half_height, SCREEN_WIDTH, half_height))

        num_rays = SCREEN_WIDTH
        half_fov = FOV / 2
        
        for ray_idx in range(num_rays):
            # Calculate ray angle relative to player view direction
            ray_angle = self.player_angle - half_fov + (ray_idx / num_rays) * FOV
            
            # Raycasting DDA initialization
            distance_to_wall = 0.0
            hit_wall = False
            hit_side = "N" # Track which wall face was struck for coloring
            
            cos_a = math.cos(ray_angle)
            sin_a = math.sin(ray_angle)
            
            # Step-by-step ray march through grid cells
            step_size = 0.02
            while not hit_wall and distance_to_wall < MAX_DEPTH:
                distance_to_wall += step_size
                
                test_x = int(self.player_x + cos_a * distance_to_wall)
                test_y = int(self.player_y + sin_a * distance_to_wall)
                
                # Boundary check
                if test_x < 0 or test_x >= self.cols or test_y < 0 or test_y >= self.rows:
                    hit_wall = True
                    distance_to_wall = MAX_DEPTH
                else:
                    # Check fractional offsets to determine exact wall face hit
                    fx = (self.player_x + cos_a * distance_to_wall) % 1.0
                    fy = (self.player_y + sin_a * distance_to_wall) % 1.0
                    
                    cell = self.walls[test_y][test_x]
                    
                    if fx < 0.05 and cell["W"]:
                        hit_wall, hit_side = True, "W"
                    elif fx > 0.95 and cell["E"]:
                        hit_wall, hit_side = True, "E"
                    elif fy < 0.05 and cell["N"]:
                        hit_wall, hit_side = True, "N"
                    elif fy > 0.95 and cell["S"]:
                        hit_wall, hit_side = True, "S"

            # Remove fish-eye distortion
            corrected_distance = distance_to_wall * math.cos(ray_angle - self.player_angle)
            if corrected_distance < 0.0001:
                corrected_distance = 0.0001

            # Calculate wall strip height
            wall_height = min(SCREEN_HEIGHT, int(SCREEN_HEIGHT / corrected_distance))
            
            # Select base color mapped to wall orientation (Point 3 color-based texture base)
            base_colors = {"N": COLOR_WALL_N, "S": COLOR_WALL_S, "E": COLOR_WALL_E, "W": COLOR_WALL_W}
            color = base_colors.get(hit_side, COLOR_WALL_N)
            
            # Apply distance-based shading (fog/darkening effect)
            shading_factor = max(0.2, 1.0 - (corrected_distance / MAX_DEPTH))
            shaded_color = (
                int(color[0] * shading_factor),
                int(color[1] * shading_factor),
                int(color[2] * shading_factor)
            )

            # Draw vertical wall slice onto software buffer
            top_y = half_height - (wall_height // 2)
            pygame.draw.line(surface, shaded_color, (ray_idx, top_y), (ray_idx, top_y + wall_height))

    def update(self, dt):
        keys = pygame.key.get_pressed()
        dx, dy = 0.0, 0.0
        
        if keys[pygame.K_w] or keys[pygame.K_UP]:
            dx += math.cos(self.player_angle) * self.player_speed * dt
            dy += math.sin(self.player_angle) * self.player_speed * dt
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:
            dx -= math.cos(self.player_angle) * self.player_speed * dt
            dy -= math.sin(self.player_angle) * self.player_speed * dt
        if keys[pygame.K_a]:
            self.player_angle -= self.rot_speed * dt
        if keys[pygame.K_d]:
            self.player_angle += self.rot_speed * dt

        # Simple collision verification against maze array
        new_x = self.player_x + dx
        new_y = self.player_y + dy
        if not self.walls[int(new_y)][int(new_x)][ "N" if dy < 0 else "S" ] if 0 <= int(new_x) < self.cols and 0 <= int(new_y) < self.rows else True:
            self.player_x = new_x
            self.player_y = new_y

def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Retro Raycaster Engine — Maze Core")
    clock = pygame.time.Clock()

    engine = MazeRaycaster(cols=20, rows=20, seed=42)

    running = True
    while running:
        dt = clock.tick(60) / 1000.0
        for event in pygame.event.get():
            if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                running = false

        engine.update(dt)
        engine.cast_rays(screen)
        pygame.display.flip()

    pygame.quit()

if __name__ == "__main__":
    main()