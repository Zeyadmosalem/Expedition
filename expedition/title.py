"""Title screen: play, settings, help, quit, and the player's records."""
from __future__ import annotations
from math import sin
from expedition import __version__
from expedition import game as scene_art
from expedition import pixel_art as art
from expedition.levels import LEVELS
from expedition.menus import Menu, settings_screen, HELP
from expedition.rooms import generate_map
from expedition.search import solve_grid


class TitleScene:
    """The title background: a live isometric sector in the game's own style.
    The skull hero runs the route to the beacon, three aliens on its heels."""

    CHASERS = (('skitter', 2.2), ('glob', 3.6), ('brute', 5.2))     # kind, tiles behind the hero

    def __init__(self, app):
        pg = app.pg
        self.app = app
        self.map = generate_map(seed=4242, target=0.55).map
        self.visuals = scene_art.Visuals(pg, self.map, 'outpost')
        self.route = solve_grid(self.map.passable, self.map.start, self.map.exit, 'astar').path
        self.world = pg.Surface((scene_art.LOW_W, scene_art.LOW_H)).convert()
        self.light = pg.Surface((scene_art.LOW_W, scene_art.LOW_H)).convert()
        self.glow = {'hero': art.radial_light(pg, 90, (150, 140, 124)), 'beacon': art.radial_light(pg, 90, (70, 200, 230)),
                     'nest': art.radial_light(pg, 46, (170, 60, 190)), 'alien': art.radial_light(pg, 26, (90, 110, 70))}
        self.cam = None
        shade = pg.Surface((WIDTH, HEIGHT), pg.SRCALPHA)
        for y in range(HEIGHT):                              # darker top and bottom so the menu reads well
            edge = max(0.0, abs(y - HEIGHT * 0.55) / (HEIGHT * 0.55))
            pg.draw.line(shade, (4, 6, 16, int(35 + 120 * edge ** 1.5)), (0, y), (WIDTH, y))
        self.shade = shade

    def at(self, distance):
        """A point `distance` tiles along the looping route (a short pause at the beacon)."""
        n = len(self.route)
        d = distance % (n + 12)
        i = min(n - 1, int(d))
        j = min(n - 1, i + 1)
        f = d - int(d) if i < n - 1 else 0.0
        (x0, y0), (x1, y1) = self.route[i], self.route[j]
        return x0 + 0.5 + (x1 - x0) * f, y0 + 0.5 + (y1 - y0) * f, (x1 - x0, y1 - y0)

    def draw(self, t):
        pg = self.app.pg
        iso, HW, HH = scene_art.iso, scene_art.HW, scene_art.HH
        v, m, world = self.visuals, self.map, self.world
        travelled = t * 3.0
        hx, hy, step = self.at(travelled)
        tx, ty = iso(hx, hy)
        # keep the chase in the open lower-right area, clear of the menu and records
        target = (tx - scene_art.LOW_W * 0.80, ty - scene_art.LOW_H * 0.74)
        if self.cam is None or abs(self.cam[0] - target[0]) > 300:
            self.cam = list(target)
        self.cam[0] += (target[0] - self.cam[0]) * 0.06
        self.cam[1] += (target[1] - self.cam[1]) * 0.06
        cx, cy = int(self.cam[0]), int(self.cam[1])
        world.fill((6, 7, 14))
        world.blit(v.floor, (-v.ox - cx, -cy))
        sprites = self.app.sprites
        things = []
        for depth, x, y, code in v.blocks:
            bx, by = iso(x + 0.5, y + 0.5)
            sx, sy = bx - cx, by - cy
            if -40 < sx < scene_art.LOW_W + 40 and -20 < sy < scene_art.LOW_H + 50 and code != 'G':
                things.append((depth, 0, 'block', (sx, sy, code)))
        facing = 'r' if (step[0] - step[1]) >= 0 else 'l'
        things.append((hx + hy, 1, 'sprite', (hx, hy, sprites.hero[(facing, int(t * 10) % 4)])))
        lights = [('hero', hx, hy, 8)]
        for n, (kind, behind) in enumerate(self.CHASERS):
            ax, ay, astep = self.at(max(0.0, travelled - behind))
            if travelled - behind < 0:
                continue
            face = 'r' if (astep[0] - astep[1]) >= 0 else 'l'
            img = sprites.aliens[(kind, int(t * 6 + n) % 2, face)]
            things.append((ax + ay, 1, 'sprite', (ax, ay, img)))
            lights.append(('alien', ax, ay, 4))
        ex, ey = m.exit
        things.append((ex + ey + 1.0, 1, 'beacon', (ex + 0.5, ey + 0.5)))
        lights.append(('beacon', ex + 0.5, ey + 0.5, 20))
        lights += [('nest', nx + 0.5, ny + 0.5, 6) for nx, ny in m.nests]
        things.sort(key=lambda d: (d[0], d[1]))
        for _, _, kind, obj in things:
            if kind == 'block':
                sx, sy, code = obj
                if code == 'N':
                    img = sprites.nest
                    world.blit(img, (sx - img.get_width() // 2, sy - img.get_height() + 4))
                    continue
                h = v.heights[code]
                world.blit(v.solid[code], (sx - HW, sy - HH - h))
            elif kind == 'sprite':
                x, y, img = obj
                sx, sy = iso(x, y)
                pg.draw.ellipse(world, (8, 9, 18), (sx - cx - 7, sy - cy - 3, 14, 6))
                world.blit(img, (sx - cx - img.get_width() // 2, sy - cy - img.get_height() + 2))
            else:
                sx, sy = iso(*obj)
                sx -= cx; sy -= cy
                pg.draw.polygon(world, (40, 120, 140), [(sx, sy - 6), (sx + 10, sy - 1), (sx, sy + 4), (sx - 10, sy - 1)])
                pg.draw.line(world, (140, 240, 255), (sx, sy - 4), (sx, sy - 40), 3)
                top = sy - 50 + 3 * sin(t * 2)
                pg.draw.polygon(world, (150, 250, 255), [(sx, top - 6), (sx + 5, top), (sx, top + 6), (sx - 5, top)])
        self.light.fill(v.ambient)
        for name, x, y, lift in lights:
            tex = self.glow[name]
            sx, sy = iso(x, y)
            self.light.blit(tex, (sx - cx - tex.get_width() // 2, sy - cy - tex.get_height() // 2 - lift),
                            special_flags=pg.BLEND_ADD)
        world.blit(self.light, (0, 0), special_flags=pg.BLEND_MULT)
        pg.transform.scale(world, (WIDTH, HEIGHT), self.app.screen)
        self.app.screen.blit(self.shade, (0, 0))
from expedition.ui import WIDTH, HEIGHT, PALETTE as P


def campaign_screen(app, draw_background):
    """Pick a level. Returns its number, None (back) or 'quit'."""
    pg = app.pg
    kit = app.kit
    unlocked = min(len(LEVELS), app.records.levels_cleared + 1)
    selected = unlocked - 1
    cards = []
    for n in range(len(LEVELS)):
        rect = pg.Rect(0, 0, 340, 230)
        rect.center = (WIDTH // 2 + (n - 1) * 370, 380)
        cards.append(rect)
    while True:
        app.clock.tick(60)
        t = app.now()
        for event in pg.event.get():
            if event.type == pg.QUIT:
                return 'quit'
            if event.type == pg.KEYDOWN:
                if event.key == pg.K_ESCAPE:
                    return None
                if event.key in (pg.K_LEFT, pg.K_a, pg.K_UP, pg.K_w):
                    selected = (selected - 1) % len(LEVELS); app.audio.play('ui_move')
                elif event.key in (pg.K_RIGHT, pg.K_d, pg.K_DOWN, pg.K_s, pg.K_TAB):
                    selected = (selected + 1) % len(LEVELS); app.audio.play('ui_move')
                elif event.key in (pg.K_RETURN, pg.K_KP_ENTER, pg.K_SPACE):
                    if selected < unlocked:
                        app.audio.play('ui_select')
                        return selected + 1
                    app.audio.play('hit')
            elif event.type == pg.MOUSEMOTION:
                for n, rect in enumerate(cards):
                    if rect.collidepoint(event.pos):
                        selected = n
            elif event.type == pg.MOUSEBUTTONDOWN and event.button == 1:
                for n, rect in enumerate(cards):
                    if rect.collidepoint(event.pos) and n < unlocked:
                        app.audio.play('ui_select')
                        return n + 1
        draw_background(t)
        kit.shade(app.screen, 140)
        kit.glow_text(app.screen, 'CAMPAIGN', (WIDTH // 2, 150), P['cyan'], 'title', strength=140)
        kit.text(app.screen, 'Three levels: training, the hive, and the Queen', (WIDTH // 2, 192), P['muted'], 'h3', 'center')
        accents = (P['cyan'], P['green'], P['pink'])
        for n, (lv, rect) in enumerate(zip(LEVELS, cards)):
            locked = n >= unlocked
            active = n == selected
            kit.panel(app.screen, rect, fill=P['panel_hi'] if active else P['panel'],
                      border=accents[n] if active else P['line'], radius=16, alpha=245, border_width=2 if active else 1)
            color = P['dim'] if locked else accents[n]
            kit.text(app.screen, f'LEVEL {lv.number}', (rect.centerx, rect.top + 26), color, 'h3', 'midtop')
            kit.text(app.screen, lv.name, (rect.centerx, rect.top + 58), P['dim'] if locked else P['text'], 'h1', 'midtop')
            kit.text(app.screen, lv.subtitle, (rect.centerx, rect.top + 100), P['muted'], 'small', 'midtop')
            status = 'LOCKED' if locked else 'CLEARED' if lv.number <= app.records.levels_cleared else 'PLAY'
            kit.pill(app.screen, (rect.centerx, rect.bottom - 40), status,
                     P['dim'] if locked else P['green'] if status == 'CLEARED' else P['gold'],
                     fill=None if locked else (P['green'] if status == 'CLEARED' else P['gold']), height=28, pad=16)
        kit.chips_row(app.screen, [('Left / Right', 'Choose'), ('Enter', 'Play'), ('Esc', 'Back')], HEIGHT - 60)
        app.flip()


def run(app):
    """Returns ('campaign', level), ('endless', 1) or 'quit'."""
    pg = app.pg
    kit = app.kit
    menu = Menu(kit, [('CAMPAIGN', 'campaign'), ('ENDLESS', 'endless'), ('SETTINGS', 'settings'), ('HELP', 'help'),
                      ('QUIT', 'quit')], 380)
    show_help = False
    pg.mouse.set_visible(True)
    app.audio.ambient(True)
    sprites = app.sprites
    big = {}

    def scaled(img):
        key = id(img)
        if key not in big:
            big[key] = pg.transform.scale(img, (img.get_width() * 3, img.get_height() * 3))
        return big[key]

    if getattr(app, 'title_scene', None) is None:
        app.title_scene = TitleScene(app)

    def draw_background(t):
        app.title_scene.draw(t)

    def draw_records():
        r = app.records
        stats = (('CAMPAIGN', f'{r.levels_cleared} / {len(LEVELS)} levels'),
                 ('BEST CAMPAIGN', '--' if r.best_campaign is None else f'{r.best_campaign:.1f}s'),
                 ('ENDLESS BEST', f'{r.best_run} sector{"s" if r.best_run != 1 else ""}'),
                 ('TOTAL KILLS', str(r.total_kills)))
        for n, (label, value) in enumerate(stats):
            box = pg.Rect(0, 0, 210, 62)
            box.center = (WIDTH // 2 + int((n - 1.5) * 226), 276)
            kit.panel(app.screen, box, alpha=200, radius=12)
            kit.text(app.screen, label, (box.centerx, box.top + 10), P['muted'], 'tiny', 'midtop')
            kit.text(app.screen, value, (box.centerx, box.top + 28), P['gold'], 'numsm', 'midtop')

    while True:
        app.clock.tick(60)
        t = app.now()
        for event in pg.event.get():
            if event.type == pg.QUIT:
                return 'quit'
            if show_help:
                if event.type in (pg.KEYDOWN, pg.MOUSEBUTTONDOWN):
                    show_help = False
                continue
            if event.type == pg.KEYDOWN:
                if event.key == pg.K_ESCAPE:
                    return 'quit'
                if event.key == pg.K_F1:
                    show_help = True
                    continue
                if event.key == pg.K_F11:
                    app.settings.fullscreen = not app.settings.fullscreen
                    app.apply_fullscreen()
                    continue
            choice = menu.handle(event, app.audio)
            if choice == 'endless':
                return ('endless', 1)
            if choice == 'campaign':
                level = campaign_screen(app, draw_background)
                if level == 'quit':
                    return 'quit'
                if level is not None:
                    return ('campaign', level)
                continue
            if choice == 'quit':
                return 'quit'
            if choice == 'help':
                show_help = True
            elif choice == 'settings':
                if settings_screen(app, draw_background) == 'quit':
                    return 'quit'
        draw_background(t)
        kit.glow_text(app.screen, 'EXPEDITION', (WIDTH // 2, 140), P['cyan'], 'logo', strength=200)
        kit.text(app.screen, 'AN ISOMETRIC ALIEN SHOOTER  //  REACH THE BEACON, SURVIVE THE NESTS',
                 (WIDTH // 2, 198), P['muted'], 'h3', 'center')
        draw_records()
        menu.draw(app.screen, t)
        kit.chips_row(app.screen, [('Up / Down', 'Choose'), ('Enter', 'Select'), ('F1', 'Help'),
                                   ('F11', 'Fullscreen'), ('Esc', 'Quit')], HEIGHT - 44)
        kit.text(app.screen, f'v{__version__}', (WIDTH - 14, HEIGHT - 12), P['dim'], 'tiny', 'bottomright')
        if show_help:
            kit.overlay_help(app.screen, 'HOW TO PLAY', HELP, footer='Any key to close')
        app.flip()
