# Expedition — standalone game design

*Approved 16 November 2026. Split out of the NEUROFORGE course project to become a game friends can download and play on Windows.*

## Goal

An isometric pixel-art top-down alien shooter. The hero is a pixel version of the author's skull logo. Maps are built by a constraint solver; aliens hunt with graph search. No machine-learning model ships with the game.

## Player experience

- **Runs:** clear sectors in a row; each clear raises the difficulty; death ends the run and shows the score (sectors cleared, kills, time). Difficulty carries over between runs, adjusted to how the player did.
- **Records:** best run, most kills in a run, fastest clear, total kills; shown on the title screen.
- **Combat:** WASD move, mouse aim, click / hold to shoot, R reload. Aliens drop ammo (Brutes often, others sometimes). With no ammo left the player switches to a slow sidearm with unlimited ammo.
- **Maps:** a 4×4 grid of rooms; start and beacon in random opposite corners.
- **Sound:** effects synthesized in code; volume and sound on / off settings; silent (not crashing) when no audio device exists.
- **Menus:** Esc pauses (Resume / Settings / Quit to menu). Settings: volume, sound, fullscreen, screen shake; saved between launches.
- **HUD:** threat level, sector, kills, time, health, ammo, minimap. First run only: a short controls card.

## How the AI works

| Part | Module | Role |
|---|---|---|
| Constraint satisfaction | `expedition/rooms.py` | Rooms are variables, (template, doors) values. Matching doors, no adjacent nests, a difficulty budget, a minimum number of nests and full connectivity. Backtracking with Forward Checking and AC-3; A* then confirms the beacon is reachable. |
| Graph search | `expedition/search.py` | BFS / DFS / A* / Greedy on the tile grid. Globs follow one shared BFS distance field, Skitters replan with Greedy, Brutes with A*. |
| Adaptive difficulty | `expedition/director.py` | Rule based: a challenge level rises after clears and falls after deaths; the director picks the candidate map closest to it. |

## Files and saves

- Bundled read-only files (sprites) are found through `expedition/paths.py`, which works both from source and inside the packaged app.
- Saves go to `%APPDATA%\Expedition` (`settings.json`, `records.json`). `EXPEDITION_HOME` overrides the folder (tests use a temporary one).

## Packaging

PyInstaller, one-folder, windowed, skull icon. `build/build.ps1` builds `dist/Expedition/Expedition.exe`, runs its `--smoke` self-check and zips it as `Expedition-v1.0-windows.zip`.

## Tests

Map CSP (door consistency, four FC/AC-3 settings, impossible case, reachability, random corners); grid search with known answers; aliens chase; shooting kills; ammo drops and the sidearm; director adapts; settings and records round-trip in a temporary folder; hidden-window smoke tests for title, settings, game, pause and help; a bot playtest finishes every run without a zero-ammo dead end.
