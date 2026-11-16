# PyInstaller spec for Expedition: one folder, no console window, skull icon.
# Build with build/build.ps1 (it also runs the --smoke self-check and zips the result).
from pathlib import Path

root = Path(SPECPATH).parent

a = Analysis(
    [str(root / 'run_game.py')],
    pathex=[str(root)],
    datas=[(str(root / 'assets' / 'hero_skull.png'), 'assets')],
    excludes=['tkinter', 'numpy', 'pytest', 'matplotlib', 'PIL', 'unittest', 'pydoc'],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Expedition',
    console=False,
    icon=str(root / 'build' / 'expedition.ico'),
)
coll = COLLECT(exe, a.binaries, a.datas, name='Expedition')
