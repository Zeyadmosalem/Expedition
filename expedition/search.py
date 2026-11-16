"""Graph search on the tile grid: BFS, DFS, A* and Greedy best-first.

All four share one loop: FIFO / LIFO / f = g + h / f = h frontiers, FIFO
tie-breaking, A* relaxation with stale heap records skipped, and the same
counters (nodes expanded, generated, largest frontier).
"""
from __future__ import annotations
from collections import deque
from dataclasses import dataclass
from heapq import heappop, heappush
from time import perf_counter

ALGORITHMS = ('bfs', 'dfs', 'astar', 'greedy')
GRID_MOVES = (('E', 1, 0), ('S', 0, 1), ('W', -1, 0), ('N', 0, -1))


@dataclass
class SearchResult:
    algorithm: str
    found: bool
    actions: list
    path: list
    expanded: int
    generated: int
    frontier_max: int
    elapsed_ms: float
    trace: list
    reason: str = ''

    @property
    def cost(self):
        return len(self.actions) if self.found else None


def _reconstruct(end, parents):
    path = [end]; actions = []
    while path[-1] in parents:
        prev, act = parents[path[-1]]
        actions.append(act); path.append(prev)
    path.reverse(); actions.reverse()
    return actions, path


def graph_search(start, is_goal, successors, h, algorithm='astar', max_expansions=18000,
                 trace_limit=3500) -> SearchResult:
    """`successors(s)` yields (action, next_state); `h(s)` estimates the cost to the goal."""
    if algorithm not in ALGORITHMS:
        raise ValueError('Select bfs, dfs, astar or greedy')
    begun = perf_counter()
    parents = {}; seen = {start}; trace = []
    expanded = 0; generated = 1; frontier_max = 1
    bfs = algorithm == 'bfs'; dfs = algorithm == 'dfs'; astar = algorithm == 'astar'
    uninformed = bfs or dfs
    infinity = float('inf')
    if uninformed:
        frontier = deque([start]) if bfs else [start]
    else:
        frontier = [(h(start), 0, 0, start)]
        best_g = {start: 0}; sequence = 0
    while frontier and expanded < max_expansions:
        if bfs:
            cur = frontier.popleft()
        elif dfs:
            cur = frontier.pop()
        else:
            _, _, g, cur = heappop(frontier)
            if astar and g != best_g[cur]:
                continue                      # stale record: a cheaper path was found later
        expanded += 1
        if len(trace) < trace_limit:
            trace.append(cur)
        if is_goal(cur):
            actions, path = _reconstruct(cur, parents)
            return SearchResult(algorithm, True, actions, path, expanded, generated, frontier_max,
                                round((perf_counter() - begun) * 1000, 3), trace)
        if not uninformed and not astar:
            g = best_g[cur]
        for action, nxt in successors(cur):
            if nxt is None or nxt == cur:
                continue
            if astar:
                new_g = g + 1
                if new_g >= best_g.get(nxt, infinity):
                    continue
                best_g[nxt] = new_g
                parents[nxt] = (cur, action); generated += 1; sequence += 1
                heappush(frontier, (new_g + h(nxt), sequence, new_g, nxt))
            else:
                if nxt in seen:
                    continue
                seen.add(nxt); parents[nxt] = (cur, action); generated += 1
                if uninformed:
                    frontier.append(nxt)
                else:
                    new_g = g + 1; best_g[nxt] = new_g; sequence += 1
                    heappush(frontier, (h(nxt), sequence, new_g, nxt))
        if len(frontier) > frontier_max:
            frontier_max = len(frontier)
    return SearchResult(algorithm, False, [], [], expanded, generated, frontier_max,
                        round((perf_counter() - begun) * 1000, 3), trace,
                        'expansion limit' if frontier else 'No solution')


def solve_grid(passable, start, goal, algorithm='astar', max_expansions=20000, trace_limit=3500) -> SearchResult:
    """Four-neighbour path on a tile grid; states are (x, y) tuples.

    Manhattan distance is admissible and consistent for unit-cost moves, so
    A* (like BFS) returns a shortest path.
    """
    start = tuple(start); goal = tuple(goal)
    gx, gy = goal

    def successors(cell):
        x, y = cell
        for action, dx, dy in GRID_MOVES:
            if passable(x + dx, y + dy):
                yield action, (x + dx, y + dy)

    return graph_search(start, lambda c: c == goal, successors,
                        lambda c: abs(c[0] - gx) + abs(c[1] - gy), algorithm, max_expansions, trace_limit)


def bfs_distance_field(passable, source, width, height) -> dict:
    """Step distance from `source` to every reachable cell: one BFS that every
    Glob can follow downhill ("flow field"), instead of one search per alien."""
    source = tuple(source)
    dist = {source: 0}; queue = deque([source])
    while queue:
        x, y = queue.popleft(); d = dist[(x, y)] + 1
        for _, dx, dy in GRID_MOVES:
            nx, ny = x + dx, y + dy
            if 0 <= nx < width and 0 <= ny < height and (nx, ny) not in dist and passable(nx, ny):
                dist[(nx, ny)] = d; queue.append((nx, ny))
    return dist
