"""Level 1's lessons: each step is done only when the player has really done it."""
from __future__ import annotations
from math import hypot

STEPS = (
    ('move', 'Move with W A S D'),
    ('target', 'Aim with the mouse and click to shoot the practice target'),
    ('reload', 'Press R to reload'),
    ('ammo', 'Walk over the ammo crate to pick it up'),
    ('aliens', 'Aliens wake up when you get close: clear the next room'),
    ('nest', 'Shoot the nest until it breaks: it keeps spawning aliens'),
    ('beacon', 'Reach the glowing beacon to finish training'),
)


class Tutorial:
    def __init__(self, world):
        self.world = world
        self.step = 0
        p = world.player
        self.start = (p.x, p.y)
        self.reloaded = False
        self.got_ammo = False
        # A sleeping practice target in the second room, two aliens in the fourth.
        self.target = world.spawn('glob', 14.5, 4.5, active=False)
        self.target.frozen = True
        self.aliens = [world.spawn('glob', 33.5, 4.5, active=False), world.spawn('glob', 35.5, 5.5, active=False)]

    @property
    def done(self):
        return self.step >= len(STEPS)

    @property
    def text(self):
        return '' if self.done else STEPS[self.step][1]

    def update(self, events, reload_key=False):
        """Feed one frame of game events; returns True when a step was completed."""
        for e in events:
            if e[0] in ('reload', 'reloaded'):
                self.reloaded = True
            elif e[0] == 'pickup' and e[3] == 'ammo':
                self.got_ammo = True
        if reload_key:
            self.reloaded = True
        before = self.step
        while not self.done and self._satisfied(STEPS[self.step][0]):
            self.step += 1
        return self.step != before

    def _satisfied(self, key):
        w = self.world
        if key == 'move':
            return hypot(w.player.x - self.start[0], w.player.y - self.start[1]) > 2.5
        if key == 'target':
            return self.target not in w.aliens
        if key == 'reload':
            return self.reloaded
        if key == 'ammo':
            return self.got_ammo
        if key == 'aliens':
            return all(a not in w.aliens for a in self.aliens)
        if key == 'nest':
            return all(n.dead for n in w.nests)
        return w.won
