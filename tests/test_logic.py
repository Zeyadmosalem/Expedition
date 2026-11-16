"""Game logic without Pygame: search, map CSP, simulation, director and saves."""
import json
import pytest
from expedition.search import solve_grid, bfs_distance_field

GRID = ["......",
        ".####.",
        ".#..#.",
        ".#..#.",
        ".####.",
        "......"]          # a walled-off 2x2 pocket at (2..3, 2..3)


def open_cell(x, y):
    return 0 <= y < len(GRID) and 0 <= x < len(GRID[0]) and GRID[y][x] == '.'


# ---- search ---------------------------------------------------------------
def test_grid_search_known_shortest_path():
    for algo in ('bfs', 'dfs', 'astar', 'greedy'):
        r = solve_grid(open_cell, (0, 0), (5, 5), algo)
        assert r.found and r.path[0] == (0, 0) and r.path[-1] == (5, 5)
        assert all(abs(a[0] - b[0]) + abs(a[1] - b[1]) == 1 for a, b in zip(r.path, r.path[1:]))
        assert all(open_cell(*c) for c in r.path)
    assert solve_grid(open_cell, (0, 0), (5, 5), 'bfs').cost == 10
    assert solve_grid(open_cell, (0, 0), (5, 5), 'astar').cost == 10


def test_walled_off_goal_says_no_solution():
    r = solve_grid(open_cell, (0, 0), (2, 2), 'astar')
    assert not r.found and r.reason == 'No solution'


def test_bfs_distance_field():
    field = bfs_distance_field(open_cell, (0, 0), 6, 6)
    assert field[(0, 0)] == 0 and field[(5, 0)] == 5 and field[(5, 5)] == 10
    assert (2, 2) not in field


# ---- map CSP ----------------------------------------------------------------
@pytest.mark.parametrize('fc,ac', [(False, False), (True, False), (False, True), (True, True)])
def test_room_csp_modes_give_consistent_doors(fc, ac):
    from expedition.rooms import RoomCSP
    r = RoomCSP(4, 4, 0.5, seed=7).solve(fc, ac)
    rooms = r.rooms
    assert rooms is not None and r.stats.assignments >= 16
    grid = [rooms[i * 4:(i + 1) * 4] for i in range(4)]
    for y in range(4):
        for x in range(4):
            d = grid[y][x].doors
            assert ('W' in d) == (x > 0 and 'E' in grid[y][x - 1].doors)
            assert ('N' in d) == (y > 0 and 'S' in grid[y - 1][x].doors)
            assert d and (x < 3 or 'E' not in d) and (y < 3 or 'S' not in d)
            if x < 3:
                assert not (grid[y][x].template.kind == 'nest' and grid[y][x + 1].template.kind == 'nest')
    assert grid[0][0].template.kind == 'start' and grid[3][3].template.kind == 'exit'


def test_room_csp_impossible_says_no_solution():
    from expedition.rooms import RoomCSP
    r = RoomCSP(impossible=True).solve()
    assert r.rooms is None and r.reason == 'No solution'


@pytest.mark.parametrize('seed', [1, 2, 3, 4, 5])
def test_generated_maps_are_reachable(seed):
    from expedition.rooms import generate_map
    result = generate_map(seed=seed, target=0.18 * seed)
    m = result.map
    assert m is not None and result.search.found
    assert m.tile(*m.start) == 'S' and m.tile(*m.exit) == 'E'
    assert solve_grid(m.passable, m.start, m.exit, 'bfs').found


def test_start_and_beacon_sit_in_opposite_corners_that_vary():
    from expedition.rooms import generate_map, ROOM
    corners = set()
    for seed in range(12):
        m = generate_map(seed=seed, target=0.4).map
        s = (m.start[0] // ROOM, m.start[1] // ROOM)
        e = (m.exit[0] // ROOM, m.exit[1] // ROOM)
        assert s in {(0, 0), (3, 0), (0, 3), (3, 3)}
        assert e == (3 - s[0], 3 - s[1])
        corners.add(s)
    assert len(corners) >= 3


# ---- simulation ----------------------------------------------------------------
def _world(seed=5, target=0.3):
    from expedition.rooms import generate_map
    from expedition.world import Expedition
    m = generate_map(seed=seed, target=target).map
    return m, Expedition(m, seed=seed, spawning=False)


def test_aliens_close_the_distance():
    m, ex = _world(3, 0.4)
    route = solve_grid(m.passable, m.start, m.exit, 'bfs').path
    for kind, cell in zip(('glob', 'skitter', 'brute'), (route[7], route[9], route[11])):
        ex.spawn(kind, cell[0] + 0.5, cell[1] + 0.5)
    before = [abs(a.x - ex.player.x) + abs(a.y - ex.player.y) for a in ex.aliens]
    for _ in range(45):
        ex.update(1 / 30)
    after = [abs(a.x - ex.player.x) + abs(a.y - ex.player.y) for a in ex.aliens]
    assert len(after) == 3 and all(b < a for a, b in zip(before, after))
    assert {a.kind: a.algorithm for a in ex.aliens} == {'glob': 'bfs', 'skitter': 'greedy', 'brute': 'astar'}


def test_walking_the_route_reaches_the_beacon():
    m, ex = _world()
    events = []
    for cx, cy in solve_grid(m.passable, m.start, m.exit, 'astar').path:
        for _ in range(60):
            dx, dy = cx + 0.5 - ex.player.x, cy + 0.5 - ex.player.y
            if abs(dx) + abs(dy) < 0.15 or ex.won:
                break
            events += ex.update(1 / 30, move=(dx, dy))
    assert ex.won and not ex.dead and any(e[0] == 'win' for e in events)


def _free_direction(ex, distance=2.5):
    """A direction from the player with open floor for `distance` tiles."""
    for dx, dy in ((1, 0), (0, 1), (-1, 0), (0, -1)):
        if all(not ex.blocked(ex.player.x + dx * k / 4, ex.player.y + dy * k / 4) for k in range(int(distance * 4) + 1)):
            return dx, dy
    raise AssertionError('no open direction next to the start')


def test_shooting_kills_an_alien():
    m, ex = _world()
    dx, dy = _free_direction(ex)
    ex.spawn('skitter', ex.player.x + dx * 2.5, ex.player.y + dy * 2.5).frozen = True
    events = []
    for _ in range(60):
        events += ex.update(1 / 30, aim=(dx, dy), shoot=True)
    assert ex.kills == 1 and ex.hits >= 1 and ex.shots >= ex.hits
    assert any(e[0] == 'kill' for e in events)


def test_killed_alien_can_drop_ammo_that_is_picked_up(monkeypatch):
    from expedition import world
    monkeypatch.setitem(world.DROP_CHANCE, 'brute', 1.0)
    m, ex = _world()
    dx, dy = _free_direction(ex)
    brute = ex.spawn('brute', ex.player.x + dx * 2.5, ex.player.y + dy * 2.5)
    brute.frozen = True
    brute.hp = 1
    events = []
    for _ in range(30):
        events += ex.update(1 / 30, aim=(dx, dy), shoot=True)
    drops = [p for p in ex.pickups if p.kind == 'ammo' and p.amount == world.DROP_AMMO]
    assert any(e[0] == 'drop' for e in events) and len(drops) == 1
    before = ex.player.ammo
    for _ in range(90):
        if drops[0].taken:
            break
        ex.update(1 / 30, move=(drops[0].x - ex.player.x, drops[0].y - ex.player.y))
    assert drops[0].taken and ex.player.ammo == before + world.DROP_AMMO


def test_empty_gun_switches_to_the_sidearm_and_still_kills():
    m, ex = _world()
    dx, dy = _free_direction(ex)
    ex.player.ammo = 0
    ex.player.mag = 0
    assert ex.player.sidearm
    ex.spawn('skitter', ex.player.x + dx * 2.5, ex.player.y + dy * 2.5).frozen = True
    events = []
    for _ in range(90):
        events += ex.update(1 / 30, aim=(dx, dy), shoot=True)
    shots = [e for e in events if e[0] == 'shot']
    assert ex.kills == 1 and shots and all(e[3] == 'sidearm' for e in shots)
    assert ex.player.ammo == 0 and ex.player.mag == 0


# ---- director ---------------------------------------------------------------------
def test_director_adapts_both_ways_and_follows_the_challenge():
    from expedition.director import Director
    d = Director(seed=9, challenge=0.4)
    result = d.next_map()
    assert result.map is not None and abs(result.map.difficulty - 0.4) < 0.3
    d.record(won=True)
    assert d.challenge > 0.4
    high = d.challenge
    d.record(won=False)
    assert d.challenge < high
    for _ in range(40):
        d.record(won=False)
    assert d.challenge >= 0.08


# ---- saves ------------------------------------------------------------------------
def test_settings_and_records_round_trip(tmp_path, monkeypatch):
    monkeypatch.setenv('EXPEDITION_HOME', str(tmp_path))
    from expedition.settings import Settings, Records
    s = Settings.load()
    assert s.volume == 0.7 and s.sound and not s.fullscreen
    s.volume = 0.3; s.fullscreen = True; s.seen_tips = True; s.save()
    again = Settings.load()
    assert again.volume == 0.3 and again.fullscreen and again.seen_tips
    r = Records.load()
    assert r.sector_cleared(41.5) is True and r.sector_cleared(50.0) is False
    new = r.finish_run(sectors_cleared=3, kills=17)
    assert set(new) == {'best_run', 'most_kills'} and r.total_kills == 17 and r.runs == 1
    assert r.finish_run(sectors_cleared=1, kills=2) == []
    r.save()
    loaded = Records.load()
    assert (loaded.best_run, loaded.most_kills, loaded.fastest_clear, loaded.total_kills) == (3, 17, 41.5, 19)


def test_corrupt_save_files_fall_back_to_defaults(tmp_path, monkeypatch):
    monkeypatch.setenv('EXPEDITION_HOME', str(tmp_path))
    (tmp_path / 'settings.json').write_text('{not json', encoding='utf8')
    (tmp_path / 'records.json').write_text(json.dumps({'best_run': 'lots', 'total_kills': 4}), encoding='utf8')
    from expedition.settings import Settings, Records
    assert Settings.load().volume == 0.7
    r = Records.load()
    assert r.best_run == 0 and r.total_kills == 4
