"""Title screen: play, settings, help, quit, and the player's records."""
from __future__ import annotations
from math import sin
from expedition import __version__
from expedition.menus import Menu, settings_screen, HELP
from expedition.ui import WIDTH, HEIGHT, PALETTE as P


def run(app):
    """Returns 'play' or 'quit'."""
    pg = app.pg
    kit = app.kit
    menu = Menu(kit, [('PLAY', 'play'), ('SETTINGS', 'settings'), ('HELP', 'help'), ('QUIT', 'quit')], 392)
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
        stats = (('BEST RUN', f'{r.best_run} sector{"s" if r.best_run != 1 else ""}'),
                 ('MOST KILLS', str(r.most_kills)),
                 ('FASTEST CLEAR', '--' if r.fastest_clear is None else f'{r.fastest_clear:.1f}s'),
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
            if choice == 'play':
                return 'play'
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
