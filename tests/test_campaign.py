"""The 3-level campaign: tutorial steps, the boss room rule, the gate, the Queen and saved progress."""
import pytest
from expedition.search import solve_grid


# ---- levels ---------------------------------------------------------------------
def test_three_levels_get_harder_and_only_the_last_has_a_boss():
    from expedition.levels import LEVELS
    assert [lv.number for lv in LEVELS] == [1, 2, 3]
    assert LEVELS[0].tutorial and not LEVELS[1].tutorial and not LEVELS[2].tutorial
    assert LEVELS[0].target < LEVELS[1].target < LEVELS[2].target
    assert [lv.boss for lv in LEVELS] == [False, False, True]
    assert len({lv.theme for lv in LEVELS}) == 3


@pytest.mark.parametrize('number', [1, 2, 3])
def test_every_level_builds_a_reachable_map(number):
    from expedition.levels import LEVELS, build_map
    m = build_map(LEVELS[number - 1], seed=11)
    assert m.tile(*m.start) == 'S' and m.tile(*m.exit) == 'E'
    assert solve_grid(m.passable, m.start, m.exit, 'astar').found


def test_tutorial_map_is_the_same_every_time_and_has_a_nest_and_ammo():
    from expedition.levels import LEVELS, build_map
    a = build_map(LEVELS[0], seed=1)
    b = build_map(LEVELS[0], seed=99)
    assert a.tiles == b.tiles
    assert len(a.nests) == 1 and a.count('a') >= 1


# ---- boss room rule and gate ------------------------------------------------------------
def test_boss_map_reaches_the_beacon_only_through_the_lair_and_its_gate():
    from expedition.rooms import generate_map
    for seed in (3, 8, 21):
        m = generate_map(seed=seed, target=0.78, rows=4, cols=5, boss=True).map
        assert m is not None
        exit_room = m.rooms[m.room_index(*m.exit)]
        assert exit_room.template.kind == 'exit' and len(exit_room.doors) == 1
        side = next(iter(exit_room.doors))
        r, c = divmod(m.room_index(*m.exit), m.cols)
        dr, dc = {'N': (-1, 0), 'S': (1, 0), 'E': (0, 1), 'W': (0, -1)}[side]
        assert m.rooms[(r + dr) * m.cols + (c + dc)].template.kind == 'boss'
        assert m.count('G') == 2
        gated = lambda x, y: m.passable(x, y) and m.tile(x, y) != 'G'
        assert not solve_grid(gated, m.start, m.exit, 'bfs').found     # the gate is the only way in
        assert sum(r.template.kind == 'boss' for r in m.rooms) == 1


def _boss_world(seed=3):
    from expedition.rooms import generate_map
    from expedition.world import Expedition
    m = generate_map(seed=seed, target=0.78, rows=4, cols=5, boss=True).map
    return m, Expedition(m, seed=seed, spawning=False, dormant=False)


def _gate_tile(m):
    return next((x, y) for y in range(m.height) for x in range(m.width) if m.tile(x, y) == 'G')


def _stand_near(ex, x, y, distance):
    ex.player.x, ex.player.y = x - distance, y
    while ex.blocked(ex.player.x, ex.player.y):
        ex.player.x += 0.25


def test_queen_guards_the_lair_and_the_gate_opens_when_she_dies():
    m, ex = _boss_world()
    queen = ex.boss
    assert queen is not None and queen.kind == 'queen' and queen.hp == ex.boss_max_hp
    assert m.rooms[m.room_index(queen.x, queen.y)].template.kind == 'boss'
    gx, gy = _gate_tile(m)
    assert ex.solid(gx, gy) and ex.gate_closed
    queen.hp = 1
    queen.frozen = True
    _stand_near(ex, queen.x, queen.y, 2.0)
    events = []
    for _ in range(60):
        events += ex.update(1 / 30, aim=(queen.x - ex.player.x, queen.y - ex.player.y), shoot=True)
        if not ex.gate_closed:
            break
    kinds = [e[0] for e in events]
    assert 'boss_down' in kinds and 'gate_open' in kinds
    assert ex.boss is None and not ex.gate_closed and not ex.solid(gx, gy)


def test_queen_spits_acid_that_hurts_and_summons_skitters():
    m, ex = _boss_world(8)
    queen = ex.boss
    queen.active = True
    _stand_near(ex, queen.x, queen.y, 2.5)
    ex.player.hp = hp0 = 1000.0           # standing still beside her is deadly; survive long enough to see both attacks
    events = []
    for _ in range(30 * 9):
        events += ex.update(1 / 30)
        if ex.dead:
            break
    kinds = [e[0] for e in events]
    assert 'spit' in kinds and 'summon' in kinds
    assert ex.player.hp < hp0


# ---- tutorial ------------------------------------------------------------------------------
def test_tutorial_steps_advance_only_when_done():
    from expedition.levels import LEVELS, build_map
    from expedition.world import Expedition
    from expedition.tutorial import Tutorial, STEPS
    m = build_map(LEVELS[0], seed=1)
    ex = Expedition(m, seed=1, spawning=False, dormant=False)
    tut = Tutorial(ex)
    assert tut.step == 0 and tut.text == STEPS[0][1]
    tut.update([], reload_key=False)
    assert tut.step == 0                                    # standing still does nothing
    for _ in range(40):
        ex.update(1 / 30, move=(1, 0))
    tut.update([], reload_key=False)
    assert tut.step == 1                                    # moved: now shoot the target
    target = tut.target
    ex.aliens.remove(target)
    tut.update([('kill', target.x, target.y, target.kind)], reload_key=False)
    assert tut.step == 2
    tut.update([], reload_key=True)
    assert tut.step == 3                                    # reload done
    tut.update([('pickup', 0, 0, 'ammo')], reload_key=False)
    assert tut.step == 4
    for alien in list(tut.aliens):
        ex.aliens.remove(alien)
    tut.update([], reload_key=False)
    assert tut.step == 5
    for nest in ex.nests:
        nest.hp = 0
    tut.update([], reload_key=False)
    assert tut.step == 6
    ex.won = True
    tut.update([('win', 0, 0)], reload_key=False)
    assert tut.done


# ---- saved progress -------------------------------------------------------------------------
def test_campaign_progress_and_best_time_are_saved():
    from expedition.settings import Records
    r = Records.load()
    assert r.levels_cleared == 0 and r.best_campaign is None
    assert r.level_cleared(1) is True and r.level_cleared(1) is False
    r.level_cleared(2)
    assert r.levels_cleared == 2
    assert r.campaign_finished(312.4) is True and r.campaign_finished(400) is False
    r.save()
    loaded = Records.load()
    assert loaded.levels_cleared == 2 and loaded.best_campaign == 312.4
