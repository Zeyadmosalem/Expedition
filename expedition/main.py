"""Start Expedition: one window shared by the title screen and the game.

`--smoke LOGFILE` runs a short scripted session (title -> play -> pause ->
help -> quit) in a throwaway save folder and writes 'ok' to LOGFILE; the build
script uses it to check the packaged app really starts.
"""
from __future__ import annotations
import os
import sys
import tempfile
import time
import traceback
from expedition import __version__


class App:
    """Everything the screens share: window, clock, fonts, sprites, sound, saves."""

    def __init__(self, pg, seed=None):
        from expedition import ui, pixel_art
        from expedition.audio import Audio
        from expedition.paths import resource
        from expedition.settings import Settings, Records
        self.pg = pg
        self.settings = Settings.load()
        self.records = Records.load()
        self.seed = seed if seed is not None else int(time.time() * 1000) % 1_000_000
        icon = None
        try:
            icon = pg.transform.smoothscale(pg.image.load(str(resource('assets', 'hero_skull.png'))), (64, 64))
        except (FileNotFoundError, pg.error):
            pass
        self.screen = ui.open_window(pg, f'Expedition  v{__version__}', self.settings.fullscreen, icon)
        self.clock = pg.time.Clock()
        self.kit = ui.Kit(pg)
        self.backdrop = ui.Backdrop(pg)
        self.sprites = pixel_art.Sprites(pg)
        self.audio = Audio(pg, self.settings)
        self._start = time.monotonic()
        self.visited = []          # screens shown, in order (the self-check reports them)

    def now(self):
        return time.monotonic() - self._start

    def flip(self):
        self.pg.display.flip()

    def apply_fullscreen(self):
        from expedition import ui
        ui.set_fullscreen(self.pg, self.settings.fullscreen)
        self.settings.save()


def run(seed=None, on_start=None):
    import pygame as pg
    from expedition import title, game
    pg.init()
    try:
        app = App(pg, seed)
        if on_start is not None:
            on_start(app)
        screen = 'title'
        while screen != 'quit':
            app.visited.append(screen)
            if screen == 'title':
                screen = 'game' if title.run(app) == 'play' else 'quit'
            else:
                screen = game.run(app)
        app.settings.save()
        app.records.save()
    finally:
        pg.quit()
    return app.visited


def smoke(logfile):
    """Scripted self-check for the packaged app (hidden from players)."""
    os.environ['EXPEDITION_HOME'] = tempfile.mkdtemp(prefix='expedition-smoke-')
    import pygame as pg
    frames = [0]
    script = {10: pg.K_RETURN, 40: pg.K_SPACE, 120: pg.K_ESCAPE, 130: pg.K_ESCAPE,
              140: pg.K_F1, 150: pg.K_F1, 170: pg.K_ESCAPE, 175: pg.K_DOWN, 176: pg.K_DOWN, 178: pg.K_RETURN}
    real_flip = pg.display.flip

    def flip():
        frames[0] += 1
        key = script.get(frames[0])
        if key is not None:
            pg.event.post(pg.event.Event(pg.KEYDOWN, key=key, mod=0, unicode='', scancode=0))
        if frames[0] >= 400:
            pg.event.post(pg.event.Event(pg.QUIT))
        return real_flip()

    def no_mouse(app):
        # The real cursor may hover a menu button and change the selection:
        # the scripted session must not depend on where the mouse happens to be.
        pg.event.set_blocked([pg.MOUSEMOTION, pg.MOUSEBUTTONDOWN, pg.MOUSEBUTTONUP])
        pg.event.clear()           # drop the mouse events already queued when the window opened

    pg.display.flip = flip
    try:
        visited = run(seed=1234, on_start=no_mouse)
        if 'game' in visited and frames[0] >= 400:
            result = f'ok frames={frames[0]} screens={",".join(visited)}'
        else:
            result = f'error: session ended early, frames={frames[0]} screens={",".join(visited)}'
    except Exception:
        result = 'error\n' + traceback.format_exc()
    finally:
        pg.display.flip = real_flip
    with open(logfile, 'w', encoding='utf8') as f:
        f.write(result)
    return 0 if result.startswith('ok') else 1


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if '--smoke' in argv:
        index = argv.index('--smoke')
        logfile = argv[index + 1] if index + 1 < len(argv) else 'smoke.log'
        return smoke(logfile)
    try:
        run()
        return 0
    except Exception:
        # Leave a note friends can send back, then let the error surface.
        try:
            from expedition.paths import save_dir
            (save_dir() / 'crash.log').write_text(traceback.format_exc(), encoding='utf8')
        except OSError:
            pass
        raise


if __name__ == '__main__':
    sys.exit(main())
