"""Entry point used by PyInstaller (and handy for `python run_game.py`)."""
import os
import sys

os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT', '1')

from expedition.main import main  # noqa: E402

if __name__ == '__main__':
    sys.exit(main())
