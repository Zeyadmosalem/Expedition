"""A player's photo can replace the skull as the hero's head, in gameplay only."""
import pytest

pg = pytest.importorskip('pygame')


@pytest.fixture
def screen():
    pg.init()
    yield pg.display.set_mode((320, 200))
    pg.quit()


def make_photo(tmp_path, name='me.png'):
    """A 120x80 test 'photo': warm left half, cool right half."""
    img = pg.Surface((120, 80))
    img.fill((230, 160, 120))
    pg.draw.rect(img, (40, 90, 200), (60, 0, 60, 80))
    path = tmp_path / name
    pg.image.save(img, str(path))
    return path


def test_photo_becomes_a_round_pixel_head(screen, tmp_path):
    from expedition.photo import head_from_image, HEAD_SIZE
    head = head_from_image(pg, make_photo(tmp_path))
    assert head.get_size() == (HEAD_SIZE + 2, HEAD_SIZE + 2)       # head plus a 1 px outline
    assert head.get_at((0, 0)).a == 0                               # round: corners stay clear
    assert head.get_at((HEAD_SIZE // 2, HEAD_SIZE // 2)).a == 255
    colours = {tuple(head.get_at((x, y)))[:3] for x in range(head.get_width())
               for y in range(head.get_height()) if head.get_at((x, y)).a}
    assert len(colours) <= 16                                       # posterized to a small palette


def test_not_an_image_is_refused(screen, tmp_path):
    from expedition.photo import head_from_image, PhotoError
    bad = tmp_path / 'notes.png'
    bad.write_text('not really a picture', encoding='utf8')
    with pytest.raises(PhotoError):
        head_from_image(pg, bad)


def test_head_is_saved_and_loaded_from_the_save_folder(screen, tmp_path):
    from expedition.photo import head_from_image, save_head, load_head
    from expedition.paths import save_dir
    assert load_head(pg) is None
    save_head(pg, head_from_image(pg, make_photo(tmp_path)))
    assert (save_dir() / 'character.png').exists()
    loaded = load_head(pg)
    assert loaded is not None and loaded.get_width() > 10


def test_custom_head_changes_the_player_but_not_the_title_hero(screen, tmp_path):
    from expedition.pixel_art import Sprites
    from expedition.photo import head_from_image
    sprites = Sprites(pg)
    assert sprites.player is sprites.hero
    sprites.use_head(head_from_image(pg, make_photo(tmp_path)))
    assert sprites.player is not sprites.hero
    assert set(sprites.player) == set(sprites.hero)                 # same facings and walk frames
    sprites.use_head(None)
    assert sprites.player is sprites.hero


def _drive(monkeypatch, frames, keys):
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


ROW_CHARACTER = {3: pg.K_DOWN, 4: pg.K_DOWN, 5: pg.K_DOWN, 6: pg.K_DOWN}


def test_settings_character_row_picks_a_photo_and_switches_back(monkeypatch, tmp_path):
    from expedition.main import App
    from expedition.menus import settings_screen
    from expedition.settings import Settings
    pg.init()
    app = App(pg, seed=3)
    photo = make_photo(tmp_path)
    app.pick_photo = lambda: str(photo)
    _drive(monkeypatch, 40, {**ROW_CHARACTER, 8: pg.K_RETURN, 15: pg.K_ESCAPE})
    assert settings_screen(app, lambda t: None) == 'back'
    assert Settings.load().character == 'photo' and app.sprites.player is not app.sprites.hero
    _drive(monkeypatch, 40, {**ROW_CHARACTER, 8: pg.K_LEFT, 15: pg.K_ESCAPE})
    assert settings_screen(app, lambda t: None) == 'back'
    assert Settings.load().character == 'skull' and app.sprites.player is app.sprites.hero
    pg.quit()


def test_bad_file_keeps_the_skull(monkeypatch, tmp_path):
    from expedition.main import App
    from expedition.menus import settings_screen
    from expedition.settings import Settings
    pg.init()
    app = App(pg, seed=3)
    bad = tmp_path / 'oops.jpg'
    bad.write_text('nope', encoding='utf8')
    app.pick_photo = lambda: str(bad)
    _drive(monkeypatch, 40, {**ROW_CHARACTER, 8: pg.K_RETURN, 15: pg.K_ESCAPE})
    assert settings_screen(app, lambda t: None) == 'back'
    assert Settings.load().character == 'skull' and app.sprites.player is app.sprites.hero
    pg.quit()


def test_saved_photo_is_used_again_on_the_next_launch(tmp_path):
    from expedition.main import App
    from expedition.photo import head_from_image, save_head
    from expedition.settings import Settings
    pg.init()
    pg.display.set_mode((64, 64))
    save_head(pg, head_from_image(pg, make_photo(tmp_path)))
    s = Settings.load(); s.character = 'photo'; s.save()
    pg.quit()
    pg.init()
    app = App(pg, seed=1)
    assert app.sprites.player is not app.sprites.hero
    pg.quit()
