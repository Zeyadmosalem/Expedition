"""Adaptive difficulty: a challenge level that follows how the player is doing.

Clearing a sector raises the challenge (more after a streak of clears); dying
lowers it. Each new sector is chosen from a few CSP candidate maps generated
around the challenge level: the one whose real difficulty is closest wins.
"""
from __future__ import annotations
from expedition.rooms import generate_map, MapResult

MIN_CHALLENGE, MAX_CHALLENGE = 0.08, 0.98


def clamp(value):
    return max(MIN_CHALLENGE, min(MAX_CHALLENGE, float(value)))


class Director:
    def __init__(self, seed=42, challenge=0.3):
        self.seed = seed
        self.challenge = clamp(challenge)
        self.streak = 0

    def next_map(self, n_candidates=3) -> MapResult:
        options = []
        for k in range(n_candidates):
            target = clamp(self.challenge + (k - (n_candidates - 1) / 2) * 0.1)
            result = generate_map(seed=self.seed + k * 101, target=target)
            if result.map is not None:
                options.append((abs(result.map.difficulty - self.challenge), k, result))
        self.seed += 1009
        if not options:
            raise RuntimeError('No reachable map could be generated')
        return min(options, key=lambda o: (o[0], o[1]))[2]

    def record(self, won):
        if won:
            self.streak += 1
            self.challenge = clamp(self.challenge + 0.065 + 0.018 * min(self.streak, 4))
        else:
            self.streak = 0
            self.challenge = clamp(self.challenge - 0.08)
        return self.challenge
