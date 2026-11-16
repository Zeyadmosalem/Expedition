"""Where the game finds its bundled files and where it saves.

Bundled read-only files (sprites) come from the project folder when running
from source, or from PyInstaller's unpack folder (sys._MEIPASS) in the app.
Saves always go to a per-user folder, never next to the game: the packaged app
may live in a read-only place.
"""
from __future__ import annotations
import os
import sys
from pathlib import Path

APP_NAME = 'Expedition'


def resource(*parts) -> Path:
    base = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[1]))
    return base.joinpath(*parts)


def save_dir() -> Path:
    """%APPDATA%\\Expedition on Windows (~/.expedition elsewhere); EXPEDITION_HOME overrides."""
    override = os.environ.get('EXPEDITION_HOME')
    if override:
        folder = Path(override)
    elif os.environ.get('APPDATA'):
        folder = Path(os.environ['APPDATA']) / APP_NAME
    else:
        folder = Path.home() / '.expedition'
    folder.mkdir(parents=True, exist_ok=True)
    return folder
