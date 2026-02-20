import pygame, sys, random, math
from collections import deque

pygame.init()

# Window
WIDTH, HEIGHT = 800, 600
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Ultimate Maze Game")
clock = pygame.time.Clock()
font = pygame.font.SysFont(None, 28)

# Tile / speeds / sizes
TILE = 40
PLAYER_SPEED = 4
SPRINT_SPEED = 7
PLAYER_SIZE = 30
FOG_RADIUS = 200

# Gameplay
STAMINA_MAX = 100
STAMINA_DRAIN = 2
STAMINA_RECOVER = 1

# Colors
WALL_COLOR = (20, 80, 200)
FLOOR_COLOR = (30, 30, 30)
PLAYER_COLOR = (0, 255, 0)
ENEMY_COLOR = (255, 50, 50)
KEY_COLOR = (255, 200, 0)
DOOR_COLOR = (140, 70, 0)
EXIT_COLOR = (0, 200, 200)
UI_BG = (40, 40, 40)
TEXT_COLOR = (255, 255, 255)

# ------------------ Maze / Pathfinding ------------------

def generate_maze(w_tiles, h_tiles):
    w = w_tiles // 2
    h = h_tiles // 2
    grid = [[1 for _ in range(w * 2 + 1)] for _ in range(h * 2 + 1)]
    stack = [(1, 1)]
    grid[1][1] = 0
    dirs = [(2,0),(-2,0),(0,2),(0,-2)]
    while stack:
        x, y = stack[-1]
        moves = []
        for dx, dy in dirs:
            nx, ny = x+dx, y+dy
            if 1 <= nx < 2*w and 1 <= ny < 2*h and grid[ny][nx] == 1:
                moves.append((nx,ny,dx,dy))
        if not moves:
            stack.pop()
            continue
        nx, ny, dx, dy = random.choice(moves)
        grid[y+dy//2][x+dx//2] = 0
        grid[ny][nx] = 0
        stack.append((nx,ny))
    grid[1][1] = 2
    grid[-2][-2] = 3
    return ["".join(str(c) for c in row) for row in grid]

def bfs_reachable(start, maze, blocked=set()):
    w, h = len(maze[0]), len(maze)
    q = deque([start])
    vis = {start}
    while q:
        x,y = q.popleft()
        for dx,dy in [(1,0),(-1,0),(0,1),(0,-1)]:
            nx,ny = x+dx,y+dy
            if 0<=nx<w and 0<=ny<h and (nx,ny) not in vis and (nx,ny) not in blocked:
                if maze[ny][nx] != "1":
                    vis.add((nx,ny))
                    q.append((nx,ny))
    return vis

def astar(start, end, maze, blocked=set()):
    w,h = len(maze[0]), len(maze)
    open_set = {start}
    came = {}
    g = {start:0}
    f = {start:abs(start[0]-end[0])+abs(start[1]-end[1])}
    while open_set:
        cur = min(open_set, key=lambda c:f.get(c,999999))
        if cur == end:
            path=[]
            while cur in came:
                path.append(cur)
                cur = came[cur]
            return path[::-1]
        open_set.remove(cur)
        x,y = cur
        for dx,dy in [(1,0),(-1,0),(0,1),(0,-1)]:
            nx,ny = x+dx,y+dy
            if 0<=nx<w and 0<=ny<h:
                if maze[ny][nx]=="1" or (nx,ny) in blocked:
                    continue
                ng = g[cur]+1
                if ng < g.get((nx,ny),999999):
                    came[(nx,ny)] = cur
                    g[(nx,ny)] = ng
                    f[(nx,ny)] = ng + abs(nx-end[0]) + abs(ny-end[1])
                    open_set.add((nx,ny))
    return []

# ------------------ Level Class ------------------

class Level:
    def __init__(self, level_count):
        self.level_count = level_count
        self.generate()

    def generate(self):
        w = min(21 + self.level_count*4, 51)
        h = min(15 + self.level_count*3, 31)
        while True:
            self.maze = generate_maze(w,h)
            spawn, exit_t, empties = self.find_specials()
            reachable = bfs_reachable(spawn, self.maze, {exit_t})
            empties = [e for e in empties if e in reachable]
            if not empties:
                continue
            self.spawn = spawn
            self.exit = exit_t
            self.key = random.choice(empties)
            enemies = [e for e in empties if e not in {self.spawn,self.key}]
            self.enemy_spawn = random.choice(enemies)
            self.door = self.exit
            break

    def find_specials(self):
        spawn = exit_t = None
        empties = []
        for y,row in enumerate(self.maze):
            for x,ch in enumerate(row):
                if ch=="2": spawn=(x,y)
                elif ch=="3": exit_t=(x,y)
                elif ch=="0": empties.append((x,y))
        return spawn, exit_t, empties

# ------------------ Player Class ------------------

class Player:
    def __init__(self, tile):
        self.x = tile[0]*TILE + (TILE-PLAYER_SIZE)/2
        self.y = tile[1]*TILE + (TILE-PLAYER_SIZE)/2
        self.stamina = STAMINA_MAX
        self.has_key = False

    def rect(self):
        return pygame.Rect(self.x,self.y,PLAYER_SIZE,PLAYER_SIZE)

    def update(self, keys, maze, door):
        sprinting = keys[pygame.K_LSHIFT] and self.stamina>0
        speed = SPRINT_SPEED if sprinting else PLAYER_SPEED
        self.stamina += -STAMINA_DRAIN if sprinting else STAMINA_RECOVER
        self.stamina = max(0,min(STAMINA_MAX,self.stamina))

        nx,ny = self.x,self.y
        if keys[pygame.K_w]: ny-=speed
        if keys[pygame.K_s]: ny+=speed
        if keys[pygame.K_a]: nx-=speed
        if keys[pygame.K_d]: nx+=speed

        if can_move_to(nx,self.y,maze,door,self.has_key): self.x=nx
        if can_move_to(self.x,ny,maze,door,self.has_key): self.y=ny
        return sprinting

# ------------------ Enemy Class ------------------

class Enemy:
    def __init__(self, tile):
        self.x = tile[0]*TILE + (TILE-PLAYER_SIZE)/2
        self.y = tile[1]*TILE + (TILE-PLAYER_SIZE)/2
        self.path=[]
        self.timer=0

    def rect(self):
        return pygame.Rect(self.x,self.y,PLAYER_SIZE,PLAYER_SIZE)

    def update(self, dt, maze, player_tile, blocked):
        self.timer+=dt
        egx = int((self.x+PLAYER_SIZE/2)//TILE)
        egy = int((self.y+PLAYER_SIZE/2)//TILE)
        if self.timer>0.25:
            self.timer=0
            self.path = astar((egx,egy), player_tile, maze, blocked)

        if self.path:
            tx,ty = self.path[0]
            txw = tx*TILE+(TILE-PLAYER_SIZE)/2
            tyw = ty*TILE+(TILE-PLAYER_SIZE)/2
            dx,dy = txw-self.x, tyw-self.y
            dist = math.hypot(dx,dy)
            if dist>0:
                self.x += (dx/dist)*2.2
                self.y += (dy/dist)*2.2
            if dist<3:
                self.path.pop(0)

# ------------------ Collision helpers ------------------

def rect_tile_coords(px, py):
    pts=[(px+1,py+1),(px+PLAYER_SIZE-1,py+1),(px+1,py+PLAYER_SIZE-1),(px+PLAYER_SIZE-1,py+PLAYER_SIZE-1)]
    return {(int(x//TILE),int(y//TILE)) for x,y in pts}

def can_move_to(px,py,maze,door,has_key):
    for gx,gy in rect_tile_coords(px,py):
        if gx<0 or gy<0 or gy>=len(maze) or gx>=len(maze[0]):
            return False
        if maze[gy][gx]=="1": return False
        if (gx,gy)==door and not has_key: return False
    return True

# ------------------ Death screen ------------------

def show_death():
    screen.fill((0,0,0))
    t = pygame.font.SysFont(None,60).render("YOU DIED",True,(255,0,0))
    screen.blit(t,t.get_rect(center=(WIDTH//2,HEIGHT//2)))
    pygame.display.flip()
    while True:
        for e in pygame.event.get():
            if e.type==pygame.KEYDOWN:
                return

# ------------------ Game Loop ------------------

level_count = 1
level = Level(level_count)
player = Player(level.spawn)
enemy = Enemy(level.enemy_spawn)

while True:
    dt = clock.tick(60)/60
    for e in pygame.event.get():
        if e.type==pygame.QUIT:
            pygame.quit(); sys.exit()

    keys = pygame.key.get_pressed()
    sprinting = player.update(keys, level.maze, level.door)

    pgx = int((player.x+PLAYER_SIZE/2)//TILE)
    pgy = int((player.y+PLAYER_SIZE/2)//TILE)

    if (pgx,pgy)==level.key:
        player.has_key=True

    if (pgx,pgy)==level.exit and player.has_key:
        level_count+=1
        level = Level(level_count)
        player = Player(level.spawn)
        enemy = Enemy(level.enemy_spawn)
        continue

    blocked = set() if player.has_key else {level.door}
    enemy.update(dt, level.maze, (pgx,pgy), blocked)

    if player.rect().colliderect(enemy.rect()) and not sprinting:
        show_death()
        level = Level(level_count)
        player = Player(level.spawn)
        enemy = Enemy(level.enemy_spawn)
        continue

    cam_x = player.x-WIDTH//2
    cam_y = player.y-HEIGHT//2

    screen.fill((0,0,0))
    for y,row in enumerate(level.maze):
        for x,ch in enumerate(row):
            wx,wy = x*TILE-cam_x,y*TILE-cam_y
            pygame.draw.rect(screen, WALL_COLOR if ch=="1" else FLOOR_COLOR,(wx,wy,TILE,TILE))
            if (x,y)==level.key:
                pygame.draw.rect(screen,KEY_COLOR,(wx+10,wy+10,20,20))
            if (x,y)==level.exit:
                pygame.draw.rect(screen,EXIT_COLOR,(wx+10,wy+10,20,20))
            if (x,y)==level.door and not player.has_key:
                pygame.draw.rect(screen,DOOR_COLOR,(wx,wy,TILE,TILE))

    pygame.draw.rect(screen,ENEMY_COLOR,(enemy.x-cam_x,enemy.y-cam_y,PLAYER_SIZE,PLAYER_SIZE))
    pygame.draw.rect(screen,PLAYER_COLOR,(player.x-cam_x,player.y-cam_y,PLAYER_SIZE,PLAYER_SIZE))

    fog = pygame.Surface((WIDTH,HEIGHT),pygame.SRCALPHA)
    fog.fill((0,0,0,220))
    pygame.draw.circle(fog,(0,0,0,0),
        (int(player.x-cam_x+PLAYER_SIZE/2),int(player.y-cam_y+PLAYER_SIZE/2)),FOG_RADIUS)
    screen.blit(fog,(0,0))

    pygame.draw.rect(screen,UI_BG,(20,20,220,60))
    pygame.draw.rect(screen,(80,80,80),(30,30,200,16))
    pygame.draw.rect(screen,(0,200,0),(30,30,int(200*(player.stamina/STAMINA_MAX)),16))
    if player.has_key:
        pygame.draw.rect(screen,KEY_COLOR,(30,52,20,14))

    screen.blit(font.render("Find the key. Avoid the enemy.",True,TEXT_COLOR),(WIDTH-260,HEIGHT-30))
    pygame.display.flip()
