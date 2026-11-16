"""Hidden-window smoke tests: every screen draws frames and its keys lead where they should."""
import pytest

pg = pytest.importorskip('pygame')


def drive(monkeypatch, frames, keys=None):
    """Press `keys` ({frame: key}) and close the window after `frames` frames."""
    keys = keys or {}
    count = [0]
    real_flip = pg.display.flip

    def flip():
        count[0] += 1
        if count[0] in keys:
            pg.event.post(pg.event.Event(pg.KEYDOWN, key=keys[count[0]], mod=0, unicode='', scancode=0))
        if count[0] >= frames:
            pg.event.post(pg.event.Event(pg.QUIT))
        return real_flip()

    monkeypatch.setattr(pg.display, 'flip', flip)
    return count


def make_app():
    from expedition.main import App
    pg.init()
    return App(pg, seed=7)


def test_audio_builds_every_sound_or_stays_silent():
    from expedition.audio import Audio, build_samples
    from expedition.settings import Settings
    samples = build_samples()
    assert {'rifle', 'sidearm', 'kill', 'win', 'lose', 'ambient'} <= set(samples)
    assert all(-1.01 <= v <= 1.01 for s in samples.values() for v in s[::50])
    pg.init()
    audio = Audio(pg, Settings())
    audio.play('rifle'); audio.play('nope'); audio.ambient(True); audio.ambient(False)
    pg.quit()


def test_title_menu_settings_and_quit(monkeypatch):
    from expedition import title
    from expedition.settings import Settings
    app = make_app()
    # down to SETTINGS, enter, raise volume, toggle shake, back out, quit with Esc
    drive(monkeypatch, 200, {4: pg.K_DOWN, 5: pg.K_DOWN, 6: pg.K_RETURN, 10: pg.K_RIGHT, 12: pg.K_DOWN, 13: pg.K_DOWN,
                             14: pg.K_DOWN, 15: pg.K_RETURN, 18: pg.K_ESCAPE, 22: pg.K_F1, 25: pg.K_F1,
                             30: pg.K_ESCAPE})
    assert title.run(app) == 'quit'
    saved = Settings.load()
    assert saved.volume == 0.8 and saved.shake is False
    pg.quit()


def test_title_campaign_starts_level_one_and_endless_is_second(monkeypatch):
    from expedition import title
    app = make_app()
    drive(monkeypatch, 60, {5: pg.K_RETURN, 10: pg.K_RETURN})
    assert title.run(app) == ('campaign', 1)
    drive(monkeypatch, 60, {5: pg.K_DOWN, 8: pg.K_RETURN})
    assert title.run(app) == ('endless', 1)
    pg.quit()


def test_locked_levels_cannot_be_started(monkeypatch):
    from expedition import title
    app = make_app()
    # only level 1 is open: moving right to level 2 and pressing Enter does nothing, Esc goes back
    drive(monkeypatch, 80, {5: pg.K_RETURN, 10: pg.K_RIGHT, 12: pg.K_RETURN, 20: pg.K_ESCAPE, 30: pg.K_ESCAPE})
    assert title.run(app) == 'quit'
    pg.quit()


def test_campaign_tutorial_draws_and_pause_quits_to_menu(monkeypatch):
    from expedition import game
    app = make_app()
    drive(monkeypatch, 90, {20: pg.K_r, 60: pg.K_ESCAPE, 62: pg.K_DOWN, 63: pg.K_DOWN, 65: pg.K_RETURN})
    assert game.run(app, 'campaign', 1) == 'title'
    pg.quit()


def test_boss_level_draws(monkeypatch):
    from expedition import game
    app = make_app()
    count = drive(monkeypatch, 90)
    assert game.run(app, 'campaign', 3) == 'quit' and count[0] >= 90
    pg.quit()


def test_game_tips_pause_help_and_quit_to_menu(monkeypatch):
    from expedition import game
    from expedition.settings import Settings, Records
    app = make_app()
    drive(monkeypatch, 300, {5: pg.K_SPACE, 40: pg.K_ESCAPE, 45: pg.K_ESCAPE, 50: pg.K_F1, 55: pg.K_F1,
                             60: pg.K_ESCAPE, 62: pg.K_DOWN, 63: pg.K_DOWN, 65: pg.K_RETURN})
    assert game.run(app) == 'title'
    assert Settings.load().seen_tips is True
    assert Records.load().runs == 1          # leaving mid-run still counts the run
    pg.quit()


def test_window_close_during_play_quits(monkeypatch):
    from expedition import game
    app = make_app()
    count = drive(monkeypatch, 120, {5: pg.K_SPACE, 20: pg.K_r})
    assert game.run(app) == 'quit' and count[0] >= 120
    pg.quit()


def test_smoke_self_check_writes_ok(tmp_path):
    from expedition.main import main
    log = tmp_path / 'smoke.log'
    assert main(['--smoke', str(log)]) == 0
    text = log.read_text(encoding='utf8')
    assert text.startswith('ok') and 'game' in text
