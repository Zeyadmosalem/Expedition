"""Settings and records, saved as small JSON files in the player's save folder.

Damaged or hand-edited files never stop the game: unreadable files fall back to
defaults, and values of the wrong type are ignored field by field.
"""
from __future__ import annotations
import json
from dataclasses import dataclass, asdict, fields
from expedition.paths import save_dir


def _load(cls, filename):
    obj = cls()
    try:
        data = json.loads((save_dir() / filename).read_text(encoding='utf8'))
    except (OSError, ValueError):
        return obj
    if not isinstance(data, dict):
        return obj
    for f in fields(cls):
        if f.name not in data:
            continue
        value = data[f.name]
        default = getattr(obj, f.name)
        if default is None:
            ok = value is None or isinstance(value, (int, float))
        elif isinstance(default, bool):
            ok = isinstance(value, bool)
        elif isinstance(default, (int, float)):
            ok = isinstance(value, (int, float)) and not isinstance(value, bool)
        else:
            ok = isinstance(value, type(default))
        if ok:
            setattr(obj, f.name, type(default)(value) if default is not None and not isinstance(default, bool) else value)
    return obj


def _save(obj, filename):
    path = save_dir() / filename
    tmp = path.with_suffix('.tmp')
    try:
        tmp.write_text(json.dumps(asdict(obj), indent=2), encoding='utf8')
        tmp.replace(path)
    except OSError:
        pass                      # a failed save must never crash the game


@dataclass
class Settings:
    volume: float = 0.7
    sound: bool = True
    fullscreen: bool = False
    shake: bool = True
    seen_tips: bool = False
    character: str = 'skull'      # 'skull' or 'photo' (the in-game hero's head)
    challenge: float = 0.3        # the director's difficulty, carried between runs

    @classmethod
    def load(cls):
        s = _load(cls, 'settings.json')
        s.volume = max(0.0, min(1.0, s.volume))
        return s

    def save(self):
        _save(self, 'settings.json')


@dataclass
class Records:
    best_run: int = 0              # most sectors cleared in one run
    most_kills: int = 0            # most kills in one run
    fastest_clear: float | None = None
    total_kills: int = 0
    runs: int = 0
    levels_cleared: int = 0        # campaign: the highest level beaten (unlocks the next)
    best_campaign: float | None = None

    def level_cleared(self, number) -> bool:
        """Returns True when this unlocks a new level."""
        if number > self.levels_cleared:
            self.levels_cleared = number
            return True
        return False

    def campaign_finished(self, seconds) -> bool:
        """Returns True when this is a new best campaign time."""
        if self.best_campaign is None or seconds < self.best_campaign:
            self.best_campaign = round(float(seconds), 1)
            return True
        return False

    @classmethod
    def load(cls):
        return _load(cls, 'records.json')

    def save(self):
        _save(self, 'records.json')

    def sector_cleared(self, seconds) -> bool:
        """Returns True when this clear is a new fastest time."""
        if self.fastest_clear is None or seconds < self.fastest_clear:
            self.fastest_clear = round(float(seconds), 1)
            return True
        return False

    def finish_run(self, sectors_cleared, kills) -> list:
        """Close a run and return the names of the records it broke."""
        self.runs += 1
        self.total_kills += kills
        broken = []
        if sectors_cleared > self.best_run:
            self.best_run = sectors_cleared; broken.append('best_run')
        if kills > self.most_kills:
            self.most_kills = kills; broken.append('most_kills')
        return broken
