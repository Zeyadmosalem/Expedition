"""The three campaign levels and how each one's map is built."""
from __future__ import annotations
from dataclasses import dataclass
from expedition.rooms import BY_NAME, Room, compile_rooms, generate_map


@dataclass(frozen=True)
class Level:
    number: int
    key: str
    name: str
    subtitle: str
    theme: str
    rows: int
    cols: int
    target: float               # CSP difficulty target
    boss: bool = False
    tutorial: bool = False


LEVELS = (
    Level(1, 'outpost', 'TRAINING OUTPOST', 'Learn to move, shoot and survive', 'outpost', 1, 6, 0.1, tutorial=True),
    Level(2, 'hive', 'HIVE CAVES', 'The infestation spreads', 'hive', 4, 4, 0.5),
    Level(3, 'lair', "QUEEN'S LAIR", 'Kill the Queen to open the gate', 'lair', 4, 5, 0.78, boss=True),
)


def tutorial_map():
    """A fixed, straight run of six rooms: the same every time, so the lessons line up."""
    names = ('landing', 'hall', 'armory', 'hall', 'nest', 'beacon')
    rooms = []
    for i, name in enumerate(names):
        doors = {'E', 'W'}
        if i == 0:
            doors = {'E'}
        elif i == len(names) - 1:
            doors = {'W'}
        rooms.append(Room(BY_NAME[name], frozenset(doors)))
    return compile_rooms(rooms, 1, len(names), seed=7)


def build_map(level, seed):
    if level.tutorial:
        return tutorial_map()
    for attempt in range(6):
        result = generate_map(seed=seed + attempt * 7919, target=level.target, rows=level.rows, cols=level.cols,
                              boss=level.boss)
        if result.map is not None:
            return result.map
    raise RuntimeError(f'Could not build a map for level {level.number}')
