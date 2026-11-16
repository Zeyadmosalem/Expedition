"""The game screen: isometric pixel-art renderer, lighting, input, HUD and menus.

The world is drawn on a 640x360 canvas and scaled x2 with nearest-neighbour
so every pixel stays crisp; the HUD is drawn at full 1280x720 resolution. All
rules live in expedition.world (headless and unit-tested).
"""
from __future__ import annotations
from math import atan2, cos, sin, degrees, hypot, pi
from random import Random
from expedition import pixel_art as art
from expedition import ui
from expedition.director import Director
from expedition.levels import LEVELS, build_map
from expedition.menus import Menu, settings_screen, HELP
from expedition.tutorial import Tutorial, STEPS
from expedition.rooms import ROOM
from expedition.ui import WIDTH, HEIGHT, PALETTE as P
from expedition.world import Expedition, RELOAD_TIME, MAG_SIZE

LOW_W, LOW_H = WIDTH // 2, HEIGHT // 2      # world canvas, scaled x2 to the window
HW, HH = art.TILE_W // 2, art.TILE_H // 2     # half diamond: 16 x 8
WALL_H, PILLAR_H, CRATE_H = 22, 30, 11
THEMES = {      # floor tint, wall (top, left, right, trim), ambient light where no lamp reaches
    'outpost': {'tint': None, 'wall': ((74, 80, 112), (46, 50, 76), (34, 36, 58), (90, 200, 220)),
                'ambient': (78, 82, 112)},
    'hive': {'tint': (60, 96, 80), 'wall': ((62, 92, 72), (40, 62, 48), (30, 46, 36), (140, 230, 120)),
             'ambient': (70, 92, 82)},
    'lair': {'tint': (104, 56, 66), 'wall': ((98, 56, 66), (66, 36, 46), (50, 28, 36), (255, 120, 120)),
             'ambient': (96, 70, 84)},
}
ROOM_FLOOR = {'start': (78, 88, 116), 'exit': (60, 98, 116), 'open': (72, 78, 106), 'supply': (86, 82, 102),
              'cover': (70, 76, 102), 'hazard': (62, 84, 84), 'nest': (86, 62, 100)}
GOO = {'glob': (120, 230, 90), 'skitter': (200, 110, 255), 'brute': (255, 150, 70)}
SOUND_FOR = {'hit': 'hit', 'kill': 'kill', 'hurt': 'hurt', 'pickup': 'pickup', 'drop': 'drop',
             'reload': 'reload', 'alert': 'alert', 'spawn': 'spawn', 'nest_down': 'nest_down',
             'win': 'win', 'dead': 'lose', 'spit': 'spawn', 'summon': 'alert', 'boss_down': 'nest_down',
             'gate_open': 'ui_select', 'splash': 'hit'}


def iso(wx, wy):
    return (wx - wy) * HW, (wx + wy) * HH


def from_screen(dx, dy):
    """Screen offset (low-res pixels) back to a world direction."""
    return (dx / HW + dy / HH) / 2, (dy / HH - dx / HW) / 2


class Visuals:
    """Pre-rendered floor and block sprites for one map."""

    def __init__(self, pg, m, theme='outpost'):
        style = THEMES[theme]
        self.ambient = style['ambient']
        self.ox = m.height * HW + HW
        self.floor = pg.Surface(((m.width + m.height) * HW + 2 * HW, (m.width + m.height) * HH + 2 * HH)).convert()
        self.floor.fill((6, 7, 14))
        self.acid = []
        self.blocks = []
        for y in range(m.height):
            for x in range(m.width):
                t = m.tile(x, y)
                room = m.rooms[m.room_index(x, y)]
                base = ROOM_FLOOR.get(room.template.kind, (70, 76, 102))
                if style['tint'] is not None:
                    base = ui.mix(base, style['tint'], 0.6)
                color = tuple(min(255, c + (5 if (x + y) % 2 else 0)) for c in base)
                cx, cy = self.ox + (x - y) * HW, (x + y) * HH
                diamond = [(cx, cy), (cx + HW, cy + HH), (cx, cy + 2 * HH), (cx - HW, cy + HH)]
                if t == '~':
                    pg.draw.polygon(self.floor, (24, 70, 34), diamond)
                    self.acid.append((x, y))
                elif t != '#':
                    pg.draw.polygon(self.floor, color, diamond)
                    pg.draw.lines(self.floor, tuple(max(0, c - 14) for c in color), True, diamond)
                    if (x * 7 + y * 3) % 9 == 0:
                        pg.draw.line(self.floor, tuple(min(255, c + 10) for c in color), (cx - 4, cy + 8), (cx + 4, cy + 8))
                if t == 'S':
                    pg.draw.polygon(self.floor, (120, 220, 240), diamond, 1)
                if t in '#cpNG':
                    self.blocks.append((x + y + 1.0, x, y, t))
        self.wall = art.iso_block(pg, WALL_H, *style['wall'])
        self.gate = art.iso_block(pg, WALL_H, (255, 96, 128), (196, 44, 80), (150, 32, 64), (255, 210, 225))
        self.gate.set_alpha(205)
        self.crate = art.iso_block(pg, CRATE_H, (156, 116, 64), (114, 80, 42), (90, 62, 32), (196, 156, 96), rivets=False)
        self.pillar = art.iso_block(pg, PILLAR_H, (116, 124, 156), (72, 78, 106), (58, 62, 88), (255, 206, 110))
        self.solid = {'#': self.wall, 'c': self.crate, 'p': self.pillar, 'G': self.gate}
        self.faded = {}
        for k, s in self.solid.items():
            self.faded[k] = s.copy()
            self.faded[k].set_alpha(90)
        self.heights = {'#': WALL_H, 'c': CRATE_H, 'p': PILLAR_H, 'G': WALL_H}


def run(app, mode='endless', level=1):
    """Endless runs, or the campaign from `level`. Returns 'title' or 'quit'."""
    pg = app.pg
    kit = app.kit
    screen = app.screen
    sprites = app.sprites
    settings = app.settings
    records = app.records
    audio = app.audio
    rng = Random(app.seed)
    world = pg.Surface((LOW_W, LOW_H)).convert()
    lightmap = pg.Surface((LOW_W, LOW_H)).convert()
    lights = {
        'player': art.radial_light(pg, 88, (150, 140, 124)),
        'muzzle': art.radial_light(pg, 60, (255, 196, 110)),
        'bullet': art.radial_light(pg, 12, (255, 210, 130)),
        'acid': art.radial_light(pg, 20, (40, 130, 50)),
        'nest': art.radial_light(pg, 44, (170, 60, 190)),
        'beacon': art.radial_light(pg, 80, (70, 200, 230)),
        'pickup': art.radial_light(pg, 16, (130, 120, 70)),
        'boom': art.radial_light(pg, 50, (255, 170, 90)),
    }
    cone = art.cone_light(pg, 190, 46, (190, 182, 160))
    cone_cache = {}
    toasts = ui.Toasts()
    campaign = mode == 'campaign'
    director = Director(seed=app.seed, challenge=settings.challenge)
    run_state = {'cleared': 0, 'kills': 0, 'sector': 0, 'level': level, 'campaign_time': 0.0,
                 'full_campaign': level == 1}
    state = {}
    pause_menu = Menu(kit, [('RESUME', 'resume'), ('SETTINGS', 'settings'), ('QUIT TO MENU', 'quit')], 330)

    def now():
        return app.now()

    def start_map(m, theme, tutorial=False):
        g = Expedition(m, seed=rng.randrange(1 << 30), dormant=not tutorial)
        state.update(game=g, visuals=Visuals(pg, m, theme), visited=set(), outcome=None, particles=[], decals=[],
                     flashes=[], alerts=[], shake=0.0, hurt=0.0, muzzle=0.0, new_records=[], fastest=False,
                     tutorial=Tutorial(g) if tutorial else None, new_best=False)
        px, py = iso(g.player.x, g.player.y)
        state['cam'] = [px - LOW_W / 2, py - LOW_H / 2]
        return g

    def new_sector():
        if campaign:
            lv = LEVELS[run_state['level'] - 1]
            start_map(build_map(lv, rng.randrange(1 << 30)), lv.theme, lv.tutorial)
            toasts.push(f'LEVEL {lv.number}  //  {lv.name}  //  {lv.subtitle.upper()}', P['cyan'], 3.5, now())
            return
        result = director.next_map()
        run_state['sector'] += 1
        start_map(result.map, 'outpost')
        nests = len(result.map.nests)
        toasts.push(f'SECTOR {run_state["sector"]:02}  //  {nests} NEST{"S" if nests != 1 else ""}  //  REACH THE BEACON',
                    P['cyan'], 3.0, now())

    def new_run():
        run_state.update(cleared=0, kills=0, sector=0)
        new_sector()

    def finish_run():
        """Close the run for the records (death, or leaving mid-run)."""
        if campaign:
            return 0
        g = state['game']
        kills = run_state['kills'] + (0 if state['outcome'] else g.kills)
        state['new_records'] = records.finish_run(run_state['cleared'], kills)
        records.save()
        return kills

    new_run()
    show_tips = not settings.seen_tips and not state['tutorial']
    tips_until = now() + 9.0
    show_help = False
    paused = False
    pg.mouse.set_visible(False)

    def burst(x, y, color, count, speed=3.0, up=40.0, life=0.6, size=1):
        for _ in range(count):
            a = rng.random() * 2 * pi
            v = speed * (0.3 + rng.random())
            state['particles'].append([x, y, 6.0, cos(a) * v, sin(a) * v, up * (0.4 + rng.random()),
                                       life * (0.6 + rng.random() * 0.6), life, color, size])

    def shake(amount):
        if settings.shake:
            state['shake'] = max(state['shake'], amount)

    def handle(events):
        g = state['game']
        for e in events:
            kind, x, y = e[0], e[1], e[2]
            if kind == 'shot':
                audio.play(e[3])
                state['muzzle'] = 0.06
                shake(1.2 if e[3] == 'rifle' else 0.6)
                burst(x, y, (255, 220, 140), 2, speed=1.5, up=20, life=0.15)
                continue
            if kind in SOUND_FOR:
                audio.play(SOUND_FOR[kind])
            if kind == 'hit':
                burst(x, y, (150, 240, 110), 5, speed=2.5, up=30, life=0.35)
            elif kind == 'spark':
                burst(x, y, (255, 214, 120), 4, speed=3, up=40, life=0.25)
            elif kind == 'kill':
                color = GOO.get(e[3], (150, 240, 110))
                burst(x, y, color, 22, speed=4, up=70, life=0.8, size=2)
                state['decals'].append((x, y, ui.mix((12, 12, 20), color, 0.45), 5 + rng.random() * 4))
                state['decals'] = state['decals'][-140:]
                state['flashes'].append([x, y, 0.18])
                shake(2.5)
            elif kind == 'drop':
                burst(x, y, (255, 214, 92), 8, speed=1.5, up=50, life=0.5)
            elif kind == 'hurt':
                state['hurt'] = 0.35
                shake(4.0)
                burst(x, y, (255, 70, 90), 8, speed=2.5, up=50, life=0.4)
            elif kind == 'acid':
                burst(x, y, (120, 240, 100), 3, speed=1, up=30, life=0.4)
            elif kind == 'pickup':
                burst(x, y, (255, 230, 140), 14, speed=2, up=60, life=0.6)
                toasts.push('+AMMO' if e[3] == 'ammo' else '+35 HEALTH', P['gold'] if e[3] == 'ammo' else P['green'], 1.2, now())
            elif kind == 'spawn':
                burst(x, y, (200, 110, 255), 10, speed=2, up=40, life=0.5)
            elif kind == 'nest_down':
                burst(x, y, (220, 120, 255), 40, speed=5, up=90, life=1.0, size=2)
                state['flashes'].append([x, y, 0.4])
                shake(6.0)
                toasts.push('NEST DESTROYED', P['pink'], 2.0, now())
            elif kind == 'alert':
                state['alerts'].append([x, y, 0.7])
            elif kind == 'boss_down':
                burst(x, y, (255, 120, 200), 60, speed=6, up=110, life=1.3, size=2)
                state['flashes'].append([x, y, 0.6])
                shake(9.0)
                toasts.push('THE QUEEN IS DEAD', P['pink'], 2.5, now())
            elif kind == 'gate_open':
                burst(x, y, (255, 150, 180), 30, speed=3, up=80, life=0.9, size=2)
                toasts.push('THE GATE IS OPEN  //  REACH THE BEACON', P['green'], 3.0, now())
            elif kind == 'splash':
                burst(x, y, (140, 255, 110), 5, speed=2, up=30, life=0.3)
            elif kind == 'win' and not state['outcome'] and campaign:
                lv = run_state['level']
                run_state['campaign_time'] += g.time
                records.total_kills += g.kills
                records.level_cleared(lv)
                if lv >= len(LEVELS):
                    state['outcome'] = 'victory'
                    if run_state['full_campaign']:
                        state['new_best'] = records.campaign_finished(run_state['campaign_time'])
                else:
                    state['outcome'] = 'win'
                records.save()
                if state['tutorial']:
                    settings.seen_tips = True
                    settings.save()
            elif kind == 'dead' and not state['outcome'] and campaign:
                state['outcome'] = 'dead'
                records.total_kills += g.kills
                records.save()
                burst(x, y, (255, 70, 90), 40, speed=4, up=80, life=1.0, size=2)
            elif kind == 'win' and not state['outcome']:
                state['outcome'] = 'win'
                run_state['cleared'] += 1
                run_state['kills'] += g.kills
                state['fastest'] = records.sector_cleared(g.time)
                records.save()
                settings.challenge = director.record(True)
                settings.save()
            elif kind == 'dead' and not state['outcome']:
                state['outcome'] = 'dead'
                run_state['kills'] += g.kills
                settings.challenge = director.record(False)
                settings.save()
                burst(x, y, (255, 70, 90), 40, speed=4, up=80, life=1.0, size=2)
                state['new_records'] = records.finish_run(run_state['cleared'], run_state['kills'])
                records.save()

    # ---- drawing -----------------------------------------------------------------------
    def draw_world(t, cam):
        g = state['game']; v = state['visuals']; m = g.map
        cx, cy = cam
        world.fill((6, 7, 14))
        world.blit(v.floor, (-v.ox - cx, -cy))
        for x, y in v.acid:
            sx, sy = iso(x, y)
            sx -= cx; sy -= cy
            if -HW < sx < LOW_W + HW and -2 * HH < sy < LOW_H:
                glow = 0.5 + 0.5 * sin(t * 3 + x * 1.7 + y)
                pg.draw.polygon(world, ui.mix((30, 90, 40), (80, 200, 70), glow),
                                [(sx, sy + 2), (sx + HW - 3, sy + HH), (sx, sy + 2 * HH - 2), (sx - HW + 3, sy + HH)])
                world.set_at((int(sx + 5 * sin(t * 2 + x * 3)), int(sy + HH + 2 * cos(t * 2.4 + y))), (190, 255, 160))
        for x, y, color, r in state['decals']:
            sx, sy = iso(x, y)
            pg.draw.ellipse(world, color, (sx - cx - r, sy - cy - r / 2, 2 * r, r))
        for x, y, r in [(g.player.x, g.player.y, 7)] + [(a.x, a.y, 4 + 10 * a.radius) for a in g.aliens]:
            sx, sy = iso(x, y)
            pg.draw.ellipse(world, (8, 9, 18), (sx - cx - r, sy - cy - r / 2.4, 2 * r, r / 1.2))
        p = g.player
        psx, psy = iso(p.x, p.y)
        player_box = pg.Rect(psx - cx - 10, psy - cy - 28, 20, 30)
        p_depth = p.x + p.y
        drawables = []
        for depth, x, y, code in v.blocks:
            bx, by = iso(x + 0.5, y + 0.5)
            sx, sy = bx - cx, by - cy
            if -40 < sx < LOW_W + 40 and -20 < sy < LOW_H + 50:
                drawables.append((depth, 0, 'block', (sx, sy, code, x, y)))
        for item in g.pickups:
            if not item.taken:
                drawables.append((item.x + item.y, 1, 'pickup', item))
        for alien in g.aliens:
            drawables.append((alien.x + alien.y, 1, 'alien', alien))
        drawables.append((p_depth, 1, 'player', p))
        ex, ey = m.exit
        drawables.append((ex + ey + 1.0, 1, 'beacon', (ex + 0.5, ey + 0.5)))
        drawables.sort(key=lambda d: (d[0], d[1]))
        nests = {(n.x, n.y): n for n in g.nests}
        for _, _, kind, obj in drawables:
            if kind == 'block':
                sx, sy, code, x, y = obj
                if code == 'G' and not g.gate_closed:
                    continue
                if code == 'N':
                    nest = nests.get((x, y))
                    img = sprites.nest
                    if nest is not None and not nest.dead:
                        pulse = 1 + int(sin(t * 5 + x) > 0.4)
                        world.blit(img, (sx - img.get_width() // 2, sy - img.get_height() + 4 - pulse))
                    else:
                        dark = img.copy(); dark.fill((70, 60, 70), special_flags=pg.BLEND_RGB_MULT)
                        world.blit(dark, (sx - img.get_width() // 2, sy - img.get_height() + 6))
                    continue
                h = v.heights[code]
                rect = pg.Rect(sx - HW, sy - HH - h, 2 * HW, 2 * HH + h)
                in_front = x + y + 1.0 > p_depth and rect.colliderect(player_box)
                world.blit(v.faded[code] if in_front else v.solid[code], (sx - HW, sy - HH - h))
            elif kind == 'pickup':
                sx, sy = iso(obj.x, obj.y)
                img = sprites.ammo if obj.kind == 'ammo' else sprites.health
                bob = int(2 * sin(t * 4 + obj.x))
                world.blit(img, (sx - cx - img.get_width() // 2, sy - cy - img.get_height() - 3 + bob))
            elif kind == 'alien':
                a = obj
                sx, sy = iso(a.x, a.y)
                hx, hy = a.heading
                facing = 'r' if (hx - hy) >= 0 else 'l'
                frame = int(t * (7 if a.kind == 'skitter' else 4) + a.x * 3) % 2 if a.active else 0
                key = (a.kind, frame, facing, 'hit') if a.hit_t > 0 else (a.kind, frame, facing)
                img = sprites.aliens[key]
                if not a.active:
                    img = img.copy(); img.fill((150, 150, 170), special_flags=pg.BLEND_RGB_MULT)
                world.blit(img, (sx - cx - img.get_width() // 2, sy - cy - img.get_height() + 2))
            elif kind == 'player':
                facing = 'r' if (p.aim[0] - p.aim[1]) >= 0 else 'l'
                img = sprites.hero[(facing, int(t * 10) % 4 if p.moving else 0)]
                x0 = psx - cx - img.get_width() // 2
                y0 = psy - cy - img.get_height() + 1
                world.blit(img, (x0, y0))
                gun = sprites.gun[facing]
                gx = psx - cx + (2 if facing == 'r' else -gun.get_width() - 2)
                gy = y0 + img.get_height() - 10
                world.blit(gun, (gx, gy))
                state['gun_tip'] = (gx + (gun.get_width() if facing == 'r' else 0), gy + 1)
            elif kind == 'beacon':
                sx, sy = iso(*obj)
                sx -= cx; sy -= cy
                pg.draw.polygon(world, (40, 120, 140), [(sx, sy - 6), (sx + 10, sy - 1), (sx, sy + 4), (sx - 10, sy - 1)])
                beam = 0.5 + 0.5 * sin(t * 3)
                pg.draw.line(world, ui.mix((60, 160, 190), (200, 255, 255), beam), (sx, sy - 4), (sx, sy - 40), 3)
                top = sy - 50 + 3 * sin(t * 2)
                pg.draw.polygon(world, (150, 250, 255), [(sx, top - 6), (sx + 5, top), (sx, top + 6), (sx - 5, top)])

    def draw_lighting(cam):
        g = state['game']; m = g.map; v = state['visuals']
        cx, cy = cam
        lightmap.fill(v.ambient)

        def add(name, wx, wy, lift=0):
            tex = lights[name]
            sx, sy = iso(wx, wy)
            w, h = tex.get_size()
            lightmap.blit(tex, (sx - cx - w // 2, sy - cy - h // 2 - lift), special_flags=pg.BLEND_ADD)

        p = g.player
        add('player', p.x, p.y, 8)
        ax, ay = p.aim
        angle = int(round(degrees(atan2(-(ax + ay) * HH, (ax - ay) * HW)) / 4)) * 4
        rotated = cone_cache.get(angle)
        if rotated is None:
            rotated = cone_cache[angle] = pg.transform.rotate(cone, angle)
        psx, psy = iso(p.x, p.y)
        lightmap.blit(rotated, rotated.get_rect(center=(psx - cx, psy - cy - 8)), special_flags=pg.BLEND_ADD)
        if state['muzzle'] > 0:
            add('muzzle', p.x + ax * 0.6, p.y + ay * 0.6, 10)
        for b in g.bullets:
            add('bullet', b.x, b.y, 10)
        for s in g.spit:
            add('acid', s.x, s.y, 8)
        if g.gate_closed:
            gx, gy = g.gate[0]
            add('nest', gx + 0.5, gy + 0.5, 10)
        for x, y in v.acid:
            sx, sy = iso(x + 0.5, y + 0.5)
            if -30 < sx - cx < LOW_W + 30 and -30 < sy - cy < LOW_H + 30:
                add('acid', x + 0.5, y + 0.5)
        for nest in g.nests:
            if not nest.dead:
                add('nest', nest.x + 0.5, nest.y + 0.5, 6)
        add('beacon', m.exit[0] + 0.5, m.exit[1] + 0.5, 20)
        for item in g.pickups:
            if not item.taken:
                add('pickup', item.x, item.y, 4)
        for x, y, _ in state['flashes']:
            add('boom', x, y, 6)
        world.blit(lightmap, (0, 0), special_flags=pg.BLEND_MULT)

    def draw_unlit(cam):
        g = state['game']
        cx, cy = cam
        for b in g.bullets:
            sx, sy = iso(b.x, b.y)
            sx -= cx; sy -= cy + 10
            speed = hypot(b.dx, b.dy) or 1
            pg.draw.line(world, (255, 236, 170), (sx, sy),
                         (sx - (b.dx - b.dy) / speed * HW * 0.35, sy - (b.dx + b.dy) / speed * HH * 0.35), 2)
        for s in g.spit:
            sx, sy = iso(s.x, s.y)
            sx -= cx; sy -= cy + 9
            pg.draw.circle(world, (60, 140, 40), (int(sx), int(sy)), 4)
            pg.draw.circle(world, (170, 255, 120), (int(sx), int(sy)), 2)
        if state['muzzle'] > 0 and 'gun_tip' in state:
            gx, gy = state['gun_tip']
            pg.draw.circle(world, (255, 230, 150), (gx, gy), 3)
            pg.draw.circle(world, (255, 255, 255), (gx, gy), 1)
        for part in state['particles']:
            sx, sy = iso(part[0], part[1])
            k = max(0.0, part[6] / part[7])
            pg.draw.rect(world, ui.mix((20, 20, 30), part[8], 0.35 + 0.65 * k),
                         (sx - cx, sy - cy - part[2], part[9], part[9]))
        for x, y, life in state['alerts']:
            sx, sy = iso(x, y)
            sx -= cx; sy -= cy + 26 + (0.7 - life) * 10
            pg.draw.rect(world, (255, 214, 92), (sx - 1, sy - 6, 2, 5))
            pg.draw.rect(world, (255, 214, 92), (sx - 1, sy + 1, 2, 2))

    def draw_minimap(g, x0, y0):
        m = g.map
        cell = 24
        kit.panel(screen, (x0 - 10, y0 - 30, m.cols * cell + 20, m.rows * cell + 40), alpha=215, radius=12)
        kit.text(screen, 'MAP', (x0, y0 - 24), P['muted'], 'tiny')
        state['visited'].add(m.room_index(g.player.x, g.player.y))
        for i, room in enumerate(m.rooms):
            r, c = divmod(i, m.cols)
            rect = pg.Rect(x0 + c * cell + 2, y0 + r * cell + 2, cell - 4, cell - 4)
            seen = i in state['visited']
            base = ROOM_FLOOR.get(room.template.kind, (70, 76, 102))
            pg.draw.rect(screen, ui.mix((16, 18, 34), tuple(min(255, v + 30) for v in base), 1.0 if seen else 0.35),
                         rect, border_radius=3)
            for side in room.doors:
                if side == 'E':
                    pg.draw.line(screen, P['dim'], (rect.right, rect.centery), (rect.right + 4, rect.centery), 2)
                elif side == 'S':
                    pg.draw.line(screen, P['dim'], (rect.centerx, rect.bottom), (rect.centerx, rect.bottom + 4), 2)
            if room.template.kind == 'nest' and any(not n.dead and m.room_index(n.x, n.y) == i for n in g.nests):
                pg.draw.circle(screen, P['pink'], rect.center, 4)
            if room.template.kind == 'exit':
                pg.draw.circle(screen, P['cyan'], rect.center, 5, 2)
        pg.draw.circle(screen, P['text'], (int(x0 + g.player.x / ROOM * cell), int(y0 + g.player.y / ROOM * cell)), 3)

    def draw_hud():
        g = state['game']; p = g.player
        kit.panel(screen, (16, 12, 470, 58), alpha=215, radius=14)
        kit.glow_text(screen, 'EXPEDITION', (34, 41), P['cyan'], 'h1', 'midleft', strength=110)
        kit.pill(screen, (232, 41), f'LEVEL {run_state["level"]}' if campaign else f'SECTOR {run_state["sector"]:02}',
                 P['text'])
        kit.text(screen, 'KILLS', (290, 22), P['muted'], 'tiny')
        kit.text(screen, f'{run_state["kills"] + (0 if state["outcome"] else g.kills):02}', (290, 34), P['pink'], 'numsm')
        kit.text(screen, 'TIME', (360, 22), P['muted'], 'tiny')
        kit.text(screen, f'{g.time:5.1f}s', (360, 34), P['text'], 'numsm')
        kit.panel(screen, (506, 12, 268, 58), alpha=215, radius=14)
        kit.text(screen, 'THREAT', (522, 22), P['muted'], 'tiny')
        threat = g.map.difficulty
        kit.bar(screen, (522, 42, 130, 10), threat, ui.mix(P['green'], P['red'], threat), radius=5)
        if campaign:
            kit.text(screen, 'LEVEL', (676, 22), P['muted'], 'tiny')
            kit.text(screen, f'{run_state["level"]} / {len(LEVELS)}', (676, 34), P['green'], 'numsm')
        else:
            kit.text(screen, 'CLEARED', (676, 22), P['muted'], 'tiny')
            kit.text(screen, f'{run_state["cleared"]}', (676, 34), P['green'], 'numsm')
        boss = g.boss
        if boss is not None and boss.active:
            box = pg.Rect(0, 0, 520, 40)
            box.midtop = (WIDTH // 2, 80)
            kit.panel(screen, box, alpha=230, radius=12, border=P['pink'])
            kit.text(screen, 'THE QUEEN', (box.left + 16, box.centery), P['pink'], 'h3', 'midleft')
            kit.bar(screen, (box.left + 120, box.centery - 6, box.width - 136, 12), boss.hp / g.boss_max_hp,
                    P['pink'], radius=6)
        tut = state['tutorial']
        if tut is not None and not tut.done:
            box = pg.Rect(0, 0, 640, 48)
            box.midtop = (WIDTH // 2, 80)
            kit.panel(screen, box, alpha=235, radius=14, border=P['gold'])
            kit.text(screen, f'TRAINING {tut.step + 1}/{len(STEPS)}', (box.left + 18, box.centery), P['gold'], 'h3',
                     'midleft')
            kit.text(screen, tut.text, (box.left + 150, box.centery), P['text'], 'body', 'midleft', width=box.width - 170)
        draw_minimap(g, WIDTH - 16 - g.map.cols * 24 - 10, 52)
        kit.panel(screen, (16, HEIGHT - 70, 330, 54), alpha=215, radius=14)
        kit.text(screen, 'HEALTH', (34, HEIGHT - 62), P['muted'], 'tiny')
        hp = max(0.0, p.hp) / 100
        kit.bar(screen, (34, HEIGHT - 44, 220, 14), hp, ui.mix(P['red'], P['green'], hp), radius=6)
        kit.text(screen, f'{int(max(0, p.hp))}', (268, HEIGHT - 37), P['text'], 'numsm', 'midleft')
        if g.map.tile(*g.tile_of(p)) == '~':
            kit.text(screen, 'ACID!', (300, HEIGHT - 62), P['green'], 'h3')
        kit.panel(screen, (WIDTH - 346, HEIGHT - 70, 330, 54), alpha=215, radius=14)
        if p.sidearm:
            kit.text(screen, 'SIDEARM', (WIDTH - 328, HEIGHT - 62), P['gold'], 'tiny')
            kit.text(screen, 'UNLIMITED  //  FIND AMMO', (WIDTH - 328, HEIGHT - 44), P['text'], 'h3')
        else:
            kit.text(screen, 'AMMO', (WIDTH - 328, HEIGHT - 62), P['muted'], 'tiny')
            for i in range(MAG_SIZE):
                pg.draw.rect(screen, P['gold'] if i < p.mag else P['panel_hi'],
                             (WIDTH - 328 + i * 15, HEIGHT - 46, 10, 18), border_radius=3)
            if p.reload_left > 0:
                kit.bar(screen, (WIDTH - 328, HEIGHT - 24, 175, 4), 1 - p.reload_left / RELOAD_TIME, P['cyan'])
            kit.text(screen, f'/ {p.ammo}', (WIDTH - 130, HEIGHT - 37), P['text'], 'numsm', 'midleft')
        kit.chips_row(screen, [('WASD', 'Move'), ('Mouse', 'Shoot'), ('R', 'Reload'), ('Esc', 'Pause')],
                      HEIGHT - 32, center_x=WIDTH // 2)

    def draw_tips():
        box = pg.Rect(0, 0, 560, 236)
        box.center = (WIDTH // 2, HEIGHT // 2 + 40)
        kit.panel(screen, box, alpha=240, radius=18, border=P['cyan'])
        kit.text(screen, 'HOW TO SURVIVE', (box.centerx, box.top + 20), P['cyan'], 'h1', 'midtop')
        rows = [('WASD', 'Move'), ('Mouse', 'Aim, click or hold to shoot'), ('R', 'Reload'),
                ('Beacon', 'Reach the glowing beacon to clear the sector'),
                ('Nests', 'Shoot them down before they flood the room')]
        for n, (key, desc) in enumerate(rows):
            y = box.top + 62 + n * 30
            kit.chip(screen, box.left + 36, y, key, '')
            kit.text(screen, desc, (box.left + 140, y + 11), P['text'], 'small', 'midleft')
        kit.text(screen, 'Press any key to start', (box.centerx, box.bottom - 18), P['muted'], 'small', 'center')

    def draw_outcome():
        g = state['game']
        kit.shade(screen, 170)
        outcome = state['outcome']
        if campaign:
            lv = LEVELS[run_state['level'] - 1]
            if outcome == 'victory':
                kit.glow_text(screen, 'VICTORY', (WIDTH // 2, HEIGHT // 2 - 90), P['gold'], 'logo', strength=220)
                kit.text(screen, 'The Queen is dead and the expedition is complete.', (WIDTH // 2, HEIGHT // 2 - 20),
                         P['text'], 'h2', 'center')
                if run_state['full_campaign']:
                    t = run_state['campaign_time']
                    best = '   //   NEW BEST TIME' if state['new_best'] else ''
                    kit.text(screen, f'Campaign time {t:.1f}s{best}', (WIDTH // 2, HEIGHT // 2 + 14),
                             P['gold'] if state['new_best'] else P['muted'], 'h3', 'center')
                kit.text(screen, 'Enter or click: back to the menu', (WIDTH // 2, HEIGHT // 2 + 70), P['cyan'], 'h3', 'center')
            elif outcome == 'win':
                nxt = LEVELS[lv.number]
                kit.glow_text(screen, 'LEVEL CLEARED', (WIDTH // 2, HEIGHT // 2 - 80), P['green'], 'logo', strength=200)
                kit.text(screen, f'{g.kills} kills   |   {g.time:.1f}s', (WIDTH // 2, HEIGHT // 2), P['text'], 'h2', 'center')
                kit.text(screen, f'Next: LEVEL {nxt.number}  //  {nxt.name}', (WIDTH // 2, HEIGHT // 2 + 34),
                         P['muted'], 'small', 'center')
                kit.text(screen, 'Enter or click: continue   //   Esc: menu', (WIDTH // 2, HEIGHT // 2 + 80), P['cyan'], 'h3', 'center')
            else:
                kit.glow_text(screen, 'YOU DIED', (WIDTH // 2, HEIGHT // 2 - 80), P['red'], 'logo', strength=200)
                kit.text(screen, f'LEVEL {lv.number}  //  {lv.name}', (WIDTH // 2, HEIGHT // 2), P['text'], 'h2', 'center')
                kit.text(screen, 'Enter or click: try again on a fresh map   //   Esc: menu',
                         (WIDTH // 2, HEIGHT // 2 + 60), P['cyan'], 'h3', 'center')
            return
        if state['outcome'] == 'win':
            kit.glow_text(screen, 'SECTOR CLEARED', (WIDTH // 2, HEIGHT // 2 - 80), P['green'], 'logo', strength=200)
            line = f'{g.kills} kills   |   {g.time:.1f}s' + ('   |   NEW FASTEST CLEAR' if state['fastest'] else '')
            kit.text(screen, line, (WIDTH // 2, HEIGHT // 2), P['gold'] if state['fastest'] else P['text'], 'h2', 'center')
            kit.text(screen, f'Sectors cleared this run: {run_state["cleared"]}   //   the next one is harder',
                     (WIDTH // 2, HEIGHT // 2 + 34), P['muted'], 'small', 'center')
            kit.text(screen, 'Enter or click: next sector   //   Esc: menu', (WIDTH // 2, HEIGHT // 2 + 80), P['cyan'], 'h3', 'center')
        else:
            kit.glow_text(screen, 'RUN OVER', (WIDTH // 2, HEIGHT // 2 - 80), P['red'], 'logo', strength=200)
            kit.text(screen, f'Sectors cleared: {run_state["cleared"]}   |   kills: {run_state["kills"]}',
                     (WIDTH // 2, HEIGHT // 2), P['text'], 'h2', 'center')
            names = {'best_run': 'BEST RUN', 'most_kills': 'MOST KILLS'}
            if state['new_records']:
                kit.text(screen, 'NEW RECORD: ' + ', '.join(names[n] for n in state['new_records']),
                         (WIDTH // 2, HEIGHT // 2 + 34), P['gold'], 'h3', 'center')
            kit.text(screen, 'Enter or click: new run   //   Esc: menu', (WIDTH // 2, HEIGHT // 2 + 80), P['cyan'], 'h3', 'center')

    def draw_crosshair():
        mx, my = pg.mouse.get_pos()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            pg.draw.line(screen, (10, 10, 20), (mx + dx * 5, my + dy * 5), (mx + dx * 13, my + dy * 13), 4)
            pg.draw.line(screen, P['cyan'], (mx + dx * 5, my + dy * 5), (mx + dx * 12, my + dy * 12), 2)
        pg.draw.circle(screen, P['text'], (mx, my), 2)

    def draw_scene(t):
        cam = state['cam']
        amount = state['shake']
        view = (int(cam[0] + (rng.random() - 0.5) * amount), int(cam[1] + (rng.random() - 0.5) * amount))
        draw_world(t, view)
        draw_lighting(view)
        draw_unlit(view)
        pg.transform.scale(world, (WIDTH, HEIGHT), screen)
        if state['hurt'] > 0:
            red = pg.Surface((WIDTH, HEIGHT), pg.SRCALPHA)
            red.fill((255, 40, 70, int(80 * state['hurt'])))
            screen.blit(red, (0, 0))
        draw_hud()
        busy_top = state['tutorial'] is not None and not state['tutorial'].done
        busy_top = busy_top or (state['game'].boss is not None and state['game'].boss.active)
        toasts.draw(kit, screen, WIDTH // 2, 136 if busy_top else 84, t)

    def continue_after_outcome():
        """Returns 'title' when the game should leave this screen."""
        outcome = state['outcome']
        if campaign:
            if outcome == 'victory':
                return 'title'
            if outcome == 'win':
                run_state['level'] += 1
            new_sector()                       # next level, or a fresh map of the same level after a death
            return None
        if outcome == 'win':
            new_sector()
        else:
            new_run()
        return None

    reload_pressed = False
    while True:
        dt = min(app.clock.tick(60) / 1000, 0.05)
        t = now()
        g = state['game']
        for event in pg.event.get():
            if event.type == pg.QUIT:
                if not state['outcome'] or state['outcome'] == 'win':
                    finish_run()
                return 'quit'
            if show_help:
                if event.type == pg.KEYDOWN and event.key in (pg.K_ESCAPE, pg.K_F1):
                    show_help = False
                continue
            if show_tips:
                if event.type in (pg.KEYDOWN, pg.MOUSEBUTTONDOWN):
                    show_tips = False
                    settings.seen_tips = True
                    settings.save()
                continue
            if paused:
                if event.type == pg.KEYDOWN and event.key == pg.K_ESCAPE:
                    paused = False
                    continue
                choice = pause_menu.handle(event, audio)
                if choice == 'resume':
                    paused = False
                elif choice == 'settings':
                    if settings_screen(app, draw_scene) == 'quit':
                        finish_run()
                        return 'quit'
                elif choice == 'quit':
                    finish_run()
                    return 'title'
                continue
            if event.type == pg.MOUSEBUTTONDOWN and event.button == 1 and state['outcome']:
                if continue_after_outcome() == 'title':
                    return 'title'
                continue
            if event.type != pg.KEYDOWN:
                continue
            if event.key == pg.K_ESCAPE:
                if state['outcome'] in ('dead', 'victory') or (campaign and state['outcome']):
                    return 'title'
                if state['outcome'] == 'win':
                    finish_run()
                    return 'title'
                paused = True
                pause_menu.selected = 0
            elif event.key == pg.K_F1:
                show_help = True
            elif event.key == pg.K_F11:
                settings.fullscreen = not settings.fullscreen
                app.apply_fullscreen()
            elif event.key == pg.K_r:
                reload_pressed = True
            elif event.key in (pg.K_RETURN, pg.K_KP_ENTER) and state['outcome']:
                if continue_after_outcome() == 'title':
                    return 'title'
        g = state['game']
        frozen = paused or show_help or show_tips or bool(state['outcome'])
        keys = pg.key.get_pressed()
        sx = (keys[pg.K_d] or keys[pg.K_RIGHT]) - (keys[pg.K_a] or keys[pg.K_LEFT])
        sy = (keys[pg.K_s] or keys[pg.K_DOWN]) - (keys[pg.K_w] or keys[pg.K_UP])
        cam = state['cam']
        psx, psy = iso(g.player.x, g.player.y)
        mx, my = pg.mouse.get_pos()
        aim = from_screen(mx / 2 + cam[0] - psx, my / 2 + cam[1] - psy)
        shoot = bool(pg.mouse.get_pressed()[0] or keys[pg.K_SPACE])
        if not frozen:
            events = g.update(dt, move=(sx + sy, sy - sx), aim=aim, shoot=shoot, reload=reload_pressed)
            handle(events)
            tut = state['tutorial']
            if tut is not None and tut.update(events, reload_key=reload_pressed) and not tut.done:
                audio.play('pickup')
        reload_pressed = False
        if show_tips and t > tips_until:
            show_tips = False
            settings.seen_tips = True
            settings.save()
        # effects
        for part in state['particles']:
            part[0] += part[3] * dt; part[1] += part[4] * dt
            part[2] += part[5] * dt; part[5] -= 260 * dt
            if part[2] < 0:
                part[2] = 0; part[5] *= -0.3; part[3] *= 0.5; part[4] *= 0.5
            part[6] -= dt
        state['particles'] = [q for q in state['particles'] if q[6] > 0][-500:]
        for f in state['flashes']:
            f[2] -= dt
        state['flashes'] = [f for f in state['flashes'] if f[2] > 0]
        for a in state['alerts']:
            a[2] -= dt
        state['alerts'] = [a for a in state['alerts'] if a[2] > 0]
        state['muzzle'] = max(0.0, state['muzzle'] - dt)
        state['hurt'] = max(0.0, state['hurt'] - dt)
        state['shake'] = max(0.0, state['shake'] - dt * 18)
        # camera: follow the player and lean toward the cursor
        g = state['game']
        psx, psy = iso(g.player.x, g.player.y)
        lean_x = max(-60, min(60, (mx / 2 - LOW_W / 2) * 0.25))
        lean_y = max(-40, min(40, (my / 2 - LOW_H / 2) * 0.25))
        target = (psx - LOW_W / 2 + lean_x, psy - LOW_H / 2 - 8 + lean_y)
        cam[0] += (target[0] - cam[0]) * min(1.0, dt * 8)
        cam[1] += (target[1] - cam[1]) * min(1.0, dt * 8)
        draw_scene(t)
        if state['outcome']:
            draw_outcome()
        if show_tips:
            draw_tips()
        if paused:
            kit.shade(screen, 160)
            kit.glow_text(screen, 'PAUSED', (WIDTH // 2, 240), P['cyan'], 'title', strength=140)
            pause_menu.draw(screen, t)
        if show_help:
            kit.overlay_help(screen, 'HOW TO PLAY', HELP)
        draw_crosshair()
        app.flip()
