# Expedition implementation plan

> Executed inline (task by task, tests first). Design: `docs/design.md`.

**Global constraints:** Python 3.14, pygame-ce 2.5.8 is the only runtime dependency; game logic modules (`search`, `rooms`, `world`, `director`, `paths`, `settings`) import no Pygame; logical screen 1280×720, world canvas 640×360 scaled ×2; saves only under `paths.save_dir()`.

1. **Search** — `search.py`: `SearchResult`, `graph_search`, `solve_grid(passable, start, goal, algorithm, max_expansions, trace_limit)`, `bfs_distance_field(passable, source, width, height)`. Tests: known shortest path on a ring grid for all four algorithms, walled-off goal → `No solution`, distance field values.
2. **Rooms** — `rooms.py`: `RoomCSP(rows, cols, target, seed, impossible, start_cell, exit_cell)`, `compile_rooms`, `generate_map(seed, target, ..., corner)` returning `MapResult(map, csp, search, candidates, reason, target, csp_seed)`; corners chosen from the seed when `corner is None`. Tests: four modes give consistent doors, impossible → `No solution`, five seeds reachable, start and exit in opposite corners and varying across seeds.
3. **World** — `world.py`: `Expedition(map, seed, spawning)` with `update(dt, move, aim, shoot, reload) -> events`; ammo drops (`DROP_CHANCE` per kind) and a sidearm when `ammo + mag == 0`. Tests: aliens close distance, route walker reaches the beacon, shooting kills, a killed Brute can drop ammo that can be picked up, empty gun switches to the sidearm and still kills.
4. **Director** — `director.py`: `Director(seed, challenge)` with `next_map()`, `record(won)`; challenge up after clears, down after deaths, clamped. Tests: adapts both ways; map difficulty follows challenge.
5. **Saves** — `paths.py` (`resource(*parts)`, `save_dir()` honouring `EXPEDITION_HOME`), `settings.py` (`Settings`, `Records` load / save JSON, tolerate corrupt files). Tests: round-trip in `tmp_path`, corrupt file falls back to defaults, records update rules.
6. **Audio** — `audio.py`: `Audio(settings)` builds sounds from synthesized samples; `play(name)`; silent when the mixer cannot start. Test: builds every sound with a dummy audio driver or degrades to silent without raising.
7. **Screens** — `ui.py`, `pixel_art.py`, `title.py`, `game.py`, `main.py` (`--smoke`). Smoke tests drive title → settings → game → pause → help with posted key events in a hidden window.
8. **Packaging** — `build/expedition.spec`, `build/build.ps1`; build, run `Expedition.exe --smoke`, zip.
