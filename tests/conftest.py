"""Every test gets its own save folder, so the player's real saves are never touched."""
import pytest


@pytest.fixture(autouse=True)
def isolated_saves(tmp_path, monkeypatch):
    monkeypatch.setenv('EXPEDITION_HOME', str(tmp_path / 'saves'))
    monkeypatch.setenv('SDL_VIDEODRIVER', 'dummy')
    monkeypatch.setenv('SDL_AUDIODRIVER', 'dummy')
