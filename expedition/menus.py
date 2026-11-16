"""Menu buttons, the settings screen and the help card, shared by title and game."""
from __future__ import annotations
from math import sin
from expedition import ui
from expedition.ui import WIDTH, HEIGHT, PALETTE as P

HELP = [
    ('MOVE AND FIGHT', [('W A S D', 'Move (arrow keys work too)'), ('Mouse', 'Aim'),
                        ('Click / Space', 'Shoot (hold for auto fire)'), ('R', 'Reload')]),
    ('SURVIVE', [('Beacon', 'Reach it to clear the sector'), ('Armory', 'Ammo and health crates'),
                 ('Acid', 'Green floor hurts'), ('Sidearm', 'Unlimited, slow: used when out of ammo')]),
    ('THE ALIENS', [('Glob', 'Slow; follows a shared BFS map to you'), ('Skitter', 'Fast; replans with Greedy search'),
                    ('Brute', 'Tough; replans with A*, often drops ammo'), ('Nest', 'Spawns aliens; shoot it down'),
                    ('Queen', "Level 3 boss: spits acid; kill her to open the gate")]),
    ('GAME', [('Esc', 'Pause'), ('F1', 'This help'), ('F11', 'Fullscreen'), ('Enter', 'Continue after a sector')]),
]


class Menu:
    """A vertical stack of buttons driven by keyboard or mouse."""

    def __init__(self, kit, items, center_y, width=360, height=46, gap=54):
        self.kit = kit
        self.items = list(items)          # (label, key)
        self.selected = 0
        self.rects = []
        pg = kit.pg
        for n in range(len(self.items)):
            rect = pg.Rect(0, 0, width, height)
            rect.center = (WIDTH // 2, center_y + n * gap)
            self.rects.append(rect)

    def set_labels(self, items):
        self.items = list(items)

    def handle(self, event, audio=None):
        """Returns the chosen item's key, ('left', key) / ('right', key) for
        adjustments, or None."""
        pg = self.kit.pg
        if event.type == pg.KEYDOWN:
            if event.key in (pg.K_UP, pg.K_w):
                self.selected = (self.selected - 1) % len(self.items)
                audio and audio.play('ui_move')
            elif event.key in (pg.K_DOWN, pg.K_s, pg.K_TAB):
                self.selected = (self.selected + 1) % len(self.items)
                audio and audio.play('ui_move')
            elif event.key in (pg.K_LEFT, pg.K_a):
                return ('left', self.items[self.selected][1])
            elif event.key in (pg.K_RIGHT, pg.K_d):
                return ('right', self.items[self.selected][1])
            elif event.key in (pg.K_RETURN, pg.K_KP_ENTER, pg.K_SPACE):
                audio and audio.play('ui_select')
                return self.items[self.selected][1]
        elif event.type == pg.MOUSEMOTION:
            for n, rect in enumerate(self.rects):
                if rect.collidepoint(event.pos) and n != self.selected:
                    self.selected = n
                    audio and audio.play('ui_move')
        elif event.type == pg.MOUSEBUTTONDOWN and event.button == 1:
            for n, rect in enumerate(self.rects):
                if rect.collidepoint(event.pos):
                    self.selected = n
                    audio and audio.play('ui_select')
                    return self.items[n][1]
        return None

    def draw(self, dest, t):
        pg = self.kit.pg
        for n, (label, _) in enumerate(self.items):
            rect = self.rects[n]
            active = n == self.selected
            if active:
                pulse = 0.5 + 0.5 * sin(t * 4)
                halo = rect.inflate(10 + 4 * pulse, 10 + 4 * pulse)
                layer = pg.Surface(halo.size, pg.SRCALPHA)
                pg.draw.rect(layer, (*P['cyan'], 40), layer.get_rect(), border_radius=18)
                dest.blit(layer, halo.topleft)
            self.kit.panel(dest, rect, fill=P['panel_hi'] if active else P['panel'],
                           border=P['cyan'] if active else P['line'], radius=14,
                           alpha=245 if active else 215, border_width=2 if active else 1)
            self.kit.text(dest, label, rect.center, P['text'] if active else P['muted'], 'menu', 'center')
            if active:
                self.kit.text(dest, '>', (rect.left + 22, rect.centery), P['cyan'], 'menu', 'midleft')


def settings_screen(app, draw_background):
    """Volume, sound, fullscreen and screen shake. Returns 'back' or 'quit'."""
    pg = app.pg
    s = app.settings

    def labels():
        return [(f'VOLUME  {round(s.volume * 100)}%', 'volume'),
                (f'SOUND  {"ON" if s.sound else "OFF"}', 'sound'),
                (f'FULLSCREEN  {"ON" if s.fullscreen else "OFF"}', 'fullscreen'),
                (f'SCREEN SHAKE  {"ON" if s.shake else "OFF"}', 'shake'),
                (f'CHARACTER  {"PHOTO" if s.character == "photo" else "SKULL"}', 'character'),
                ('BACK', 'back')]

    def choose_photo():
        """Open the file picker and turn the chosen picture into the hero's head."""
        from expedition import photo
        was_full = s.fullscreen
        if was_full:
            ui.set_fullscreen(pg, False)          # the Windows file window cannot sit over fullscreen
        try:
            path = app.pick_photo()
        finally:
            if was_full:
                ui.set_fullscreen(pg, True)
        if not path:
            return 'No picture chosen.'
        try:
            head = photo.head_from_image(pg, path)
        except photo.PhotoError as ex:
            return str(ex)
        photo.save_head(pg, head)
        s.character = 'photo'
        app.sprites.use_head(head)
        return 'Your photo is now your character (in the game).'

    def use_skull():
        s.character = 'skull'
        app.sprites.use_head(None)
        return 'Back to the skull.'

    message = 'Character: Enter picks a photo, Left goes back to the skull.'
    menu = Menu(app.kit, labels(), 220, width=420)
    while True:
        app.clock.tick(60)
        t = app.now()
        for event in pg.event.get():
            if event.type == pg.QUIT:
                return 'quit'
            if event.type == pg.KEYDOWN and event.key in (pg.K_ESCAPE, pg.K_F1):
                s.save()
                return 'back'
            choice = menu.handle(event, app.audio)
            if choice is None:
                continue
            direction, key = choice if isinstance(choice, tuple) else ('right', choice)
            if key == 'back':
                s.save()
                return 'back'
            if key == 'volume':
                step = 0.1 if direction == 'right' else -0.1
                value = round(s.volume + step, 1)
                if isinstance(choice, str):           # Enter / click cycles round
                    value = 0.0 if s.volume >= 0.99 else value
                s.volume = max(0.0, min(1.0, value))
            elif key == 'sound':
                s.sound = not s.sound
            elif key == 'fullscreen':
                s.fullscreen = not s.fullscreen
                ui.set_fullscreen(pg, s.fullscreen)
            elif key == 'shake':
                s.shake = not s.shake
            elif key == 'character':
                from expedition import photo
                if direction == 'left':
                    message = use_skull()
                elif isinstance(choice, tuple) and photo.load_head(pg) is not None:
                    s.character = 'photo'                      # Right: back to the saved photo
                    app.sprites.use_head(photo.load_head(pg))
                    message = 'Using your saved photo.'
                else:
                    message = choose_photo()
            s.save()
            app.audio.refresh()
            app.audio.play('ui_move')
            menu.set_labels(labels())
        draw_background(t)
        app.kit.shade(app.screen, 150)
        app.kit.glow_text(app.screen, 'SETTINGS', (WIDTH // 2, 140), P['cyan'], 'title', strength=140)
        menu.draw(app.screen, t)
        # live preview of the in-game hero next to the CHARACTER row
        hero = app.sprites.player[('r', int(t * 8) % 4)]
        big = pg.transform.scale(hero, (hero.get_width() * 4, hero.get_height() * 4))
        row = menu.rects[4]
        app.screen.blit(big, big.get_rect(midleft=(row.right + 30, row.centery)))
        app.kit.text(app.screen, message, (WIDTH // 2, menu.rects[-1].bottom + 28), P['muted'], 'small', 'center')
        app.kit.chips_row(app.screen, [('Up / Down', 'Choose'), ('Left / Right', 'Change'), ('Esc', 'Back')],
                          HEIGHT - 60)
        app.flip()
