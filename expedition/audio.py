"""Sound effects synthesized in code (no audio files to license or ship).

If the computer has no usable audio device the game simply stays silent.
"""
from __future__ import annotations
from array import array
from math import sin, pi, exp
from random import Random
from time import monotonic

RATE = 22050


def _tone(freq0, freq1, seconds, decay=8.0, wave='sine', volume=0.6):
    """A pitch sweep from freq0 to freq1 with an exponential fade."""
    n = int(RATE * seconds)
    out = []
    phase = 0.0
    for i in range(n):
        t = i / n
        f = freq0 + (freq1 - freq0) * t
        phase += 2 * pi * f / RATE
        if wave == 'square':
            v = 1.0 if sin(phase) >= 0 else -1.0
        elif wave == 'tri':
            v = 2 / pi * (abs(((phase / pi) % 2) - 1) * pi) - 1
        else:
            v = sin(phase)
        out.append(v * volume * exp(-decay * t))
    return out


def _noise(seconds, decay=10.0, smooth=0.0, volume=0.6, seed=1):
    """Decaying white noise; `smooth` (0..1) low-passes it into a thud."""
    rng = Random(seed)
    n = int(RATE * seconds)
    out = []
    last = 0.0
    for i in range(n):
        raw = rng.uniform(-1, 1)
        last = last * smooth + raw * (1 - smooth)
        out.append(last * volume * exp(-decay * i / n))
    return out


def _mix(*parts):
    length = max(len(p) for p in parts)
    return [sum(p[i] for p in parts if i < len(p)) for i in range(length)]


def _seq(*parts, gap=0.0):
    out = []
    for p in parts:
        out += p + [0.0] * int(RATE * gap)
    return out


def _ambient():
    n = int(RATE * 4.0)
    return [0.10 * (sin(2 * pi * 55 * i / RATE) + 0.6 * sin(2 * pi * 82.4 * i / RATE))
            * (0.6 + 0.4 * sin(2 * pi * 0.25 * i / RATE)) for i in range(n)]


def build_samples():
    """name -> list of floats in -1..1 (separate from Pygame so it is testable)."""
    return {
        'rifle': _mix(_noise(0.09, decay=9, smooth=0.2, volume=0.55, seed=2), _tone(150, 60, 0.09, 6, volume=0.5)),
        'sidearm': _mix(_tone(620, 180, 0.08, 7, 'square', 0.22), _noise(0.05, 12, 0.1, 0.25, seed=3)),
        'hit': _noise(0.05, decay=14, smooth=0.55, volume=0.45, seed=4),
        'kill': _mix(_noise(0.22, decay=6, smooth=0.7, volume=0.6, seed=5), _tone(240, 50, 0.22, 5, volume=0.4)),
        'hurt': _mix(_tone(170, 70, 0.2, 5, 'tri', 0.55), _noise(0.12, 9, 0.6, 0.3, seed=6)),
        'pickup': _seq(_tone(660, 760, 0.06, 3, volume=0.35), _tone(990, 1100, 0.08, 4, volume=0.35)),
        'drop': _tone(1320, 1500, 0.07, 6, volume=0.25),
        'reload': _seq(_noise(0.025, 20, 0.3, 0.4, seed=7), _noise(0.025, 20, 0.3, 0.45, seed=8), gap=0.12),
        'alert': _seq(_tone(880, 880, 0.05, 2, 'square', 0.14), _tone(1175, 1175, 0.06, 2, 'square', 0.14), gap=0.02),
        'spawn': [v * (0.6 + 0.4 * sin(i / 90)) for i, v in enumerate(_tone(300, 180, 0.2, 4, 'tri', 0.35))],
        'nest_down': _mix(_noise(0.7, decay=4, smooth=0.85, volume=0.8, seed=9), _tone(90, 35, 0.7, 3, volume=0.5)),
        'win': _seq(*[_tone(f, f, 0.11, 3, 'tri', 0.35) for f in (523, 659, 784, 1046)]),
        'lose': _tone(392, 130, 0.7, 2.5, 'tri', 0.45),
        'ui_move': _tone(1200, 1250, 0.03, 5, 'square', 0.12),
        'ui_select': _seq(_tone(900, 900, 0.04, 3, 'square', 0.14), _tone(1400, 1400, 0.06, 3, 'square', 0.14)),
        'ambient': _ambient(),
    }


GAIN = {'rifle': 0.55, 'sidearm': 0.6, 'hit': 0.5, 'kill': 0.8, 'hurt': 0.9, 'pickup': 0.8, 'drop': 0.6,
        'reload': 0.7, 'alert': 0.5, 'spawn': 0.5, 'nest_down': 1.0, 'win': 0.9, 'lose': 0.9,
        'ui_move': 0.6, 'ui_select': 0.7, 'ambient': 0.35}
MIN_GAP = {'hit': 0.03, 'spark': 0.05, 'alert': 0.15, 'spawn': 0.1, 'drop': 0.05}


class Audio:
    def __init__(self, pg, settings):
        self.pg = pg
        self.settings = settings
        self.sounds = {}
        self.enabled = False
        self.last = {}
        self.ambient_channel = None
        try:
            if not pg.mixer.get_init():
                pg.mixer.init(frequency=RATE, size=-16, channels=1, buffer=512)
            freq, size, channels = pg.mixer.get_init()
            pg.mixer.set_num_channels(24)
            for name, samples in build_samples().items():
                self.sounds[name] = pg.mixer.Sound(buffer=self._pcm(samples, freq, channels))
            self.enabled = True
        except Exception:          # no audio device, no driver: play silently
            self.enabled = False
            self.sounds = {}

    @staticmethod
    def _pcm(samples, freq, channels):
        step = RATE / freq
        count = int(len(samples) / step)
        data = array('h')
        for i in range(count):
            v = int(max(-1.0, min(1.0, samples[int(i * step)])) * 32000)
            for _ in range(channels):
                data.append(v)
        return data.tobytes()

    def play(self, name, volume=1.0):
        if not (self.enabled and self.settings.sound) or name not in self.sounds:
            return
        now = monotonic()
        if now - self.last.get(name, -1.0) < MIN_GAP.get(name, 0.0):
            return
        self.last[name] = now
        sound = self.sounds[name]
        sound.set_volume(max(0.0, min(1.0, self.settings.volume * GAIN.get(name, 0.7) * volume)))
        sound.play()

    def ambient(self, on=True):
        """Start or stop the quiet background hum."""
        if not self.enabled:
            return
        if on and self.settings.sound:
            if self.ambient_channel is None or not self.ambient_channel.get_busy():
                self.ambient_channel = self.sounds['ambient'].play(loops=-1)
            self.refresh()
        elif self.ambient_channel is not None:
            self.ambient_channel.stop()
            self.ambient_channel = None

    def refresh(self):
        """Apply volume / mute changes from the settings screen."""
        if not self.enabled:
            return
        if not self.settings.sound:
            self.pg.mixer.stop()
            self.ambient_channel = None
        elif self.ambient_channel is not None:
            self.ambient_channel.set_volume(self.settings.volume * GAIN['ambient'])
