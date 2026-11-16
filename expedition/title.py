"""Title screen: play, settings, help, quit, and the player's records."""
from __future__ import annotations
from math import sin
from expedition import __version__
from expedition.levels import LEVELS
from expedition.menus import Menu, settings_screen, HELP
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

    def draw_background(t):
        app.backdrop.draw(app.screen, t, camera=t * 38)
        ground = HEIGHT - 70
        pg.draw.rect(app.screen, (40, 40, 80), (0, ground, WIDTH, 70))
        pg.draw.rect(app.screen, (72, 210, 188), (0, ground, WIDTH, 6))
        pg.draw.rect(app.screen, (30, 118, 124), (0, ground + 6, WIDTH, 4))
        # the skull hero runs from a pack of aliens along the bottom
        lead = (t * 140) % (WIDTH + 600) - 300
        hero = scaled(sprites.hero[('r', int(t * 10) % 4)])
        app.screen.blit(hero, (lead, ground - hero.get_height() + 3))
        for n, kind in enumerate(('skitter', 'glob', 'brute')):
            img = scaled(sprites.aliens[(kind, int(t * 6 + n) % 2, 'r')])
            x = lead - 160 - n * 120
            app.screen.blit(img, (x, ground - img.get_height() + 3 - abs(sin(t * 6 + n)) * 6))

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
