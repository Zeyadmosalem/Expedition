"""The headless game simulation: player, bullets, aliens, nests, pickups.

No Pygame here, so every rule is unit-testable. Coordinates are in tiles; a
tile (x, y) covers [x, x+1) x [y, y+1).

Aliens hunt with graph search: Globs walk downhill on one shared BFS distance
field from the player, Skitters replan with Greedy best-first, Brutes with A*.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from math import hypot, floor, ceil
from random import Random
from expedition.rooms import ExpeditionMap, ROOM
from expedition.search import solve_grid, bfs_distance_field

ALIENS = {
    'glob':    {'speed': 1.7, 'hp': 3, 'damage': 9, 'radius': 0.32, 'algorithm': 'bfs', 'replan': 0.3},
    'skitter': {'speed': 3.3, 'hp': 1, 'damage': 5, 'radius': 0.25, 'algorithm': 'greedy', 'replan': 0.45},
    'brute':   {'speed': 1.25, 'hp': 9, 'damage': 18, 'radius': 0.42, 'algorithm': 'astar', 'replan': 0.6},
}
DROP_CHANCE = {'glob': 0.2, 'skitter': 0.15, 'brute': 0.7}   # chance a killed alien drops ammo
DROP_AMMO = 12
PLAYER_SPEED = 4.2
PLAYER_RADIUS = 0.28
BODY_RADIUS = 0.22          # collision radius used for every body against walls
MAG_SIZE = 12
START_AMMO = 60
RELOAD_TIME = 1.1
FIRE_DELAY = 0.11
SIDEARM_DELAY = 0.42        # the unlimited backup weapon fires slowly
BULLET_SPEED = 18.0
BULLET_LIFE = 0.8
AGGRO_STEPS = 13            # field distance at which a dormant alien notices the player
ATTACK_COOLDOWN = 0.8
ACID_DPS = 12.0
NEST_HP = 14
NEST_RANGE = 10.0
NEST_MAX_ALIVE = 4
FIELD_REFRESH = 0.3


@dataclass
class Player:
    x: float
    y: float
    hp: float = 100.0
    ammo: int = START_AMMO
    mag: int = MAG_SIZE
    aim: tuple = (1.0, 0.0)
    reload_left: float = 0.0
    fire_cd: float = 0.0
    moving: bool = False

    @property
    def sidearm(self):
        """True when the rifle is completely empty: the sidearm never runs out."""
        return self.mag == 0 and self.ammo == 0 and self.reload_left <= 0


@dataclass
class Alien:
    kind: str
    x: float
    y: float
    hp: float
    algorithm: str
    speed: float
    damage: float
    radius: float
    active: bool = True
    frozen: bool = False
    path: list = field(default_factory=list)
    replan_in: float = 0.0
    cooldown: float = 0.0
    hit_t: float = 0.0
    nest: int | None = None
    heading: tuple = (1.0, 0.0)


@dataclass
class Bullet:
    x: float
    y: float
    dx: float
    dy: float
    life: float = BULLET_LIFE


@dataclass
class Pickup:
    kind: str           # 'ammo' or 'health'
    x: float
    y: float
    amount: int = 30
    taken: bool = False


@dataclass
class Nest:
    x: int
    y: int
    hp: float = NEST_HP
    timer: float = 1.5
    alive: int = 0

    @property
    def dead(self):
        return self.hp <= 0


class Expedition:
    """One sector. Call update(dt, ...) once per frame; it returns events for
    sounds and effects: ('shot', x, y, weapon), ('hit', x, y), ('kill', x, y, kind),
    ('drop', x, y), ('pickup', x, y, kind), ('hurt', x, y), ('win', ...), ('dead', ...)."""

    def __init__(self, m: ExpeditionMap, seed=42, spawning=True):
        self.map = m
        self.rng = Random(seed)
        self.spawning = spawning
        sx, sy = m.start
        self.player = Player(sx + 0.5, sy + 0.5)
        self.aliens: list[Alien] = []
        self.bullets: list[Bullet] = []
        self.pickups = []
        for y in range(m.height):
            for x in range(m.width):
                t = m.tile(x, y)
                if t == 'a':
                    self.pickups.append(Pickup('ammo', x + 0.5, y + 0.5, 30))
                elif t == 'h':
                    self.pickups.append(Pickup('health', x + 0.5, y + 0.5, 35))
        self.nests = [Nest(x, y, timer=1.0 + self.rng.random() * 2) for x, y in m.nests]
        self.kills = self.shots = self.hits = 0
        self.time = 0.0
        self.won = self.dead = False
        self.field = {}
        self.field_age = FIELD_REFRESH
        self.acid_tick = 0.0
        self.exit_field = bfs_distance_field(m.passable, m.exit, m.width, m.height)
        self.route_length = max(1, self.exit_field.get(m.start, 1))
        self._solid = {(x, y) for y in range(m.height) for x in range(m.width) if not m.passable(x, y)}
        if spawning:
            self._place_dormant_aliens()

    # ---- geometry -------------------------------------------------------------------
    def solid(self, x, y):
        return (x, y) in self._solid or not (0 <= x < self.map.width and 0 <= y < self.map.height)

    def blocked(self, x, y, r=BODY_RADIUS):
        for ty in range(floor(y - r), floor(y + r) + 1):
            for tx in range(floor(x - r), floor(x + r) + 1):
                if self.solid(tx, ty):
                    return True
        return False

    def move_body(self, body, dx, dy):
        if dx and not self.blocked(body.x + dx, body.y):
            body.x += dx
        if dy and not self.blocked(body.x, body.y + dy):
            body.y += dy

    def tile_of(self, body):
        return int(floor(body.x)), int(floor(body.y))

    def progress(self):
        d = self.exit_field.get(self.tile_of(self.player), self.route_length)
        return max(0.0, min(1.0, 1 - d / self.route_length))

    # ---- spawning ------------------------------------------------------------------
    def spawn(self, kind, x, y, active=True, nest=None):
        spec = ALIENS[kind]
        alien = Alien(kind, x, y, spec['hp'], spec['algorithm'], spec['speed'], spec['damage'], spec['radius'],
                      active=active, nest=nest, replan_in=self.rng.random() * spec['replan'])
        self.aliens.append(alien)
        return alien

    def _place_dormant_aliens(self):
        m = self.map
        for index, room in enumerate(m.rooms):
            if room.template.kind in ('start', 'exit', 'supply'):
                continue
            count = self.rng.randint(0, 1 + room.template.difficulty // 2)
            r, c = divmod(index, m.cols)
            cells = [(c * ROOM + x, r * ROOM + y) for x in range(2, 8) for y in range(2, 8)
                     if m.passable(c * ROOM + x, r * ROOM + y) and m.tile(c * ROOM + x, r * ROOM + y) != '~']
            for cell in self.rng.sample(cells, min(count, len(cells))):
                kind = self.rng.choices(('glob', 'skitter', 'brute'), (0.55, 0.3, 0.15 + 0.3 * m.difficulty))[0]
                self.spawn(kind, cell[0] + 0.5, cell[1] + 0.5, active=False)

    def _nest_spawn(self, index, nest, events):
        m = self.map
        around = [(nest.x + dx, nest.y + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)
                  if (dx or dy) and m.passable(nest.x + dx, nest.y + dy)]
        if not around:
            return
        x, y = self.rng.choice(around)
        kind = self.rng.choices(('glob', 'skitter', 'brute'), (0.5, 0.35, 0.1 + 0.25 * m.difficulty))[0]
        self.spawn(kind, x + 0.5, y + 0.5, nest=index)
        nest.alive += 1
        events.append(('spawn', x + 0.5, y + 0.5))

    # ---- alien steering -------------------------------------------------------------
    def _steer(self, alien, dt):
        p = self.player
        if hypot(p.x - alien.x, p.y - alien.y) < 1.1:
            tx, ty = p.x, p.y
        elif alien.algorithm == 'bfs':
            # Glob: step to the neighbouring tile closest to the player on the BFS field.
            ax, ay = self.tile_of(alien)
            best = None
            for nx, ny in ((ax + 1, ay), (ax - 1, ay), (ax, ay + 1), (ax, ay - 1), (ax, ay)):
                d = self.field.get((nx, ny))
                if d is not None and (best is None or d < best[0]):
                    best = (d, nx, ny)
            if best is None:
                return
            tx, ty = best[1] + 0.5, best[2] + 0.5
        else:
            alien.replan_in -= dt
            if alien.replan_in <= 0 or not alien.path:
                alien.replan_in = ALIENS[alien.kind]['replan']
                budget = 1500 if alien.algorithm == 'greedy' else 2500
                result = solve_grid(self.map.passable, self.tile_of(alien), self.tile_of(p),
                                    alien.algorithm, budget, trace_limit=0)
                alien.path = list(result.path[1:]) if result.found else []
            while alien.path and hypot(alien.path[0][0] + 0.5 - alien.x, alien.path[0][1] + 0.5 - alien.y) < 0.15:
                alien.path.pop(0)
            if not alien.path:
                return
            tx, ty = alien.path[0][0] + 0.5, alien.path[0][1] + 0.5
        dx, dy = tx - alien.x, ty - alien.y
        length = hypot(dx, dy)
        if length > 1e-6:
            step = min(length, alien.speed * dt)
            alien.heading = (dx / length, dy / length)
            self.move_body(alien, dx / length * step, dy / length * step)

    # ---- main update ---------------------------------------------------------------
    def update(self, dt, move=(0.0, 0.0), aim=(1.0, 0.0), shoot=False, reload=False):
        if self.won or self.dead:
            return []
        events = []
        self.time += dt
        p = self.player
        mx, my = move
        length = hypot(mx, my)
        p.moving = length > 1e-6
        if p.moving:
            scale = PLAYER_SPEED * dt / max(1.0, length)
            self.move_body(p, mx * scale, my * scale)
        ax, ay = aim
        alen = hypot(ax, ay)
        if alen > 1e-6:
            p.aim = (ax / alen, ay / alen)
        self._weapon(dt, shoot, reload, events)
        self._bullets(dt, events)
        self._aliens(dt, events)
        self._nests(dt, events)
        self._ground(dt, events)
        ex, ey = self.map.exit
        if hypot(ex + 0.5 - p.x, ey + 0.5 - p.y) < 0.9:
            self.won = True
            events.append(('win', p.x, p.y))
        elif p.hp <= 0:
            p.hp = 0.0
            self.dead = True
            events.append(('dead', p.x, p.y))
        return events

    def _weapon(self, dt, shoot, reload, events):
        p = self.player
        p.fire_cd = max(0.0, p.fire_cd - dt)
        if p.reload_left > 0:
            p.reload_left -= dt
            if p.reload_left <= 0:
                take = min(MAG_SIZE - p.mag, p.ammo)
                p.mag += take; p.ammo -= take
                events.append(('reloaded', p.x, p.y))
            return
        if (reload and p.mag < MAG_SIZE and p.ammo > 0) or (shoot and p.mag == 0 and p.ammo > 0):
            p.reload_left = RELOAD_TIME
            events.append(('reload', p.x, p.y))
            return
        if not shoot or p.fire_cd > 0:
            return
        if p.mag > 0:
            p.mag -= 1
            p.fire_cd = FIRE_DELAY
            weapon = 'rifle'
        else:
            p.fire_cd = SIDEARM_DELAY        # rifle and reserve both empty
            weapon = 'sidearm'
        self.shots += 1
        spread = (self.rng.random() - 0.5) * 0.06
        dx, dy = p.aim[0] - p.aim[1] * spread, p.aim[1] + p.aim[0] * spread
        self.bullets.append(Bullet(p.x + dx * 0.4, p.y + dy * 0.4, dx * BULLET_SPEED, dy * BULLET_SPEED))
        events.append(('shot', p.x + dx * 0.5, p.y + dy * 0.5, weapon))

    def _bullets(self, dt, events):
        alive = []
        for b in self.bullets:
            b.life -= dt
            steps = max(1, ceil(hypot(b.dx, b.dy) * dt / 0.2))
            hit = False
            for _ in range(steps):
                b.x += b.dx * dt / steps; b.y += b.dy * dt / steps
                tx, ty = int(floor(b.x)), int(floor(b.y))
                if self.solid(tx, ty):
                    for nest in self.nests:
                        if (nest.x, nest.y) == (tx, ty) and not nest.dead:
                            nest.hp -= 1; self.hits += 1
                            events.append(('hit', b.x, b.y))
                            if nest.dead:
                                events.append(('nest_down', nest.x + 0.5, nest.y + 0.5))
                            break
                    else:
                        events.append(('spark', b.x, b.y))
                    hit = True
                    break
                for alien in self.aliens:
                    if hypot(alien.x - b.x, alien.y - b.y) < alien.radius + 0.08:
                        alien.hp -= 1; alien.hit_t = 0.12; alien.active = True
                        self.hits += 1
                        events.append(('hit', b.x, b.y))
                        hit = True
                        break
                if hit:
                    break
            if not hit and b.life > 0:
                alive.append(b)
        self.bullets = alive
        survivors = []
        for alien in self.aliens:
            if alien.hp > 0:
                survivors.append(alien)
                continue
            self.kills += 1
            if alien.nest is not None:
                self.nests[alien.nest].alive -= 1
            events.append(('kill', alien.x, alien.y, alien.kind))
            if self.rng.random() < DROP_CHANCE[alien.kind]:
                self.pickups.append(Pickup('ammo', alien.x, alien.y, DROP_AMMO))
                events.append(('drop', alien.x, alien.y))
        self.aliens = survivors

    def _aliens(self, dt, events):
        p = self.player
        self.field_age += dt
        if self.field_age >= FIELD_REFRESH:
            self.field_age = 0.0
            self.field = bfs_distance_field(self.map.passable, self.tile_of(p), self.map.width, self.map.height)
        for alien in self.aliens:
            alien.hit_t = max(0.0, alien.hit_t - dt)
            alien.cooldown = max(0.0, alien.cooldown - dt)
            if not alien.active:
                d = self.field.get(self.tile_of(alien))
                if d is not None and d <= AGGRO_STEPS:
                    alien.active = True
                    events.append(('alert', alien.x, alien.y))
                continue
            if alien.frozen:
                continue
            self._steer(alien, dt)
            if hypot(p.x - alien.x, p.y - alien.y) < alien.radius + PLAYER_RADIUS + 0.12 and alien.cooldown <= 0:
                alien.cooldown = ATTACK_COOLDOWN
                p.hp -= alien.damage
                events.append(('hurt', p.x, p.y))
        for i, a in enumerate(self.aliens):          # keep aliens from stacking up
            for b in self.aliens[i + 1:]:
                dx, dy = b.x - a.x, b.y - a.y
                d = hypot(dx, dy)
                gap = a.radius + b.radius
                if 1e-6 < d < gap:
                    push = (gap - d) / 2 / d
                    self.move_body(a, -dx * push, -dy * push)
                    self.move_body(b, dx * push, dy * push)

    def _nests(self, dt, events):
        if not self.spawning:
            return
        p = self.player
        for index, nest in enumerate(self.nests):
            if nest.dead or nest.alive >= NEST_MAX_ALIVE:
                continue
            if hypot(nest.x + 0.5 - p.x, nest.y + 0.5 - p.y) > NEST_RANGE:
                continue
            nest.timer -= dt
            if nest.timer <= 0:
                nest.timer = (3.2 - 1.6 * self.map.difficulty) * (0.7 + self.rng.random() * 0.6)
                self._nest_spawn(index, nest, events)

    def _ground(self, dt, events):
        p = self.player
        for item in self.pickups:
            if not item.taken and hypot(item.x - p.x, item.y - p.y) < 0.6:
                item.taken = True
                if item.kind == 'ammo':
                    p.ammo += item.amount
                else:
                    p.hp = min(100.0, p.hp + item.amount)
                events.append(('pickup', item.x, item.y, item.kind))
        if self.map.tile(*self.tile_of(p)) == '~':
            p.hp -= ACID_DPS * dt
            self.acid_tick -= dt
            if self.acid_tick <= 0:
                self.acid_tick = 0.4
                events.append(('acid', p.x, p.y))
