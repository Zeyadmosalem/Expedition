"""Use a photo as the hero's head (gameplay only).

The photo is cropped to a centred square, shrunk to a 16 px round head,
posterized to a small palette and outlined, so it matches the pixel art. Only
that tiny head is kept (in the save folder); the original photo is not copied.
"""
from __future__ import annotations
import sys
from expedition.paths import save_dir
from expedition.pixel_art import add_outline

HEAD_SIZE = 16
STEP = 64                    # posterize each colour channel to 4 levels
HEAD_FILE = 'character.png'


class PhotoError(Exception):
    """The chosen file could not be turned into a head."""


def head_from_image(pg, path):
    try:
        img = pg.image.load(str(path)).convert_alpha()
    except (pg.error, OSError, ValueError) as ex:
        raise PhotoError('That file is not a picture the game can read.') from ex
    w, h = img.get_size()
    if w < 4 or h < 4:
        raise PhotoError('That picture is too small.')
    side = min(w, h)
    square = img.subsurface(((w - side) // 2, (h - side) // 2, side, side)).copy()
    small = pg.transform.smoothscale(square, (HEAD_SIZE, HEAD_SIZE))
    head = pg.Surface((HEAD_SIZE + 2, HEAD_SIZE + 2), pg.SRCALPHA)
    centre = (HEAD_SIZE - 1) / 2
    for y in range(HEAD_SIZE):
        for x in range(HEAD_SIZE):
            if (x - centre) ** 2 + (y - centre) ** 2 > (HEAD_SIZE / 2) ** 2:
                continue                                  # round head: leave the corners clear
            c = small.get_at((x, y))
            if c.a < 110:
                continue
            r, g, b = (min(255, (v // STEP) * STEP + STEP // 2) for v in (c.r, c.g, c.b))
            head.set_at((x + 1, y + 1), (r, g, b, 255))
    return add_outline(pg, head)


def save_head(pg, head):
    pg.image.save(head, str(save_dir() / HEAD_FILE))


def load_head(pg):
    path = save_dir() / HEAD_FILE
    if not path.exists():
        return None
    try:
        return pg.image.load(str(path)).convert_alpha()
    except (pg.error, OSError, ValueError):
        return None


def pick_image_file(pg=None):
    """The standard Windows 'Open' window, filtered to pictures. Returns a path or None."""
    if sys.platform != 'win32':
        return None
    import ctypes
    from ctypes import wintypes

    class OPENFILENAMEW(ctypes.Structure):
        _fields_ = [('lStructSize', wintypes.DWORD), ('hwndOwner', wintypes.HWND),
                    ('hInstance', wintypes.HINSTANCE), ('lpstrFilter', wintypes.LPCWSTR),
                    ('lpstrCustomFilter', wintypes.LPWSTR), ('nMaxCustFilter', wintypes.DWORD),
                    ('nFilterIndex', wintypes.DWORD), ('lpstrFile', wintypes.LPWSTR),
                    ('nMaxFile', wintypes.DWORD), ('lpstrFileTitle', wintypes.LPWSTR),
                    ('nMaxFileTitle', wintypes.DWORD), ('lpstrInitialDir', wintypes.LPCWSTR),
                    ('lpstrTitle', wintypes.LPCWSTR), ('Flags', wintypes.DWORD),
                    ('nFileOffset', wintypes.WORD), ('nFileExtension', wintypes.WORD),
                    ('lpstrDefExt', wintypes.LPCWSTR), ('lCustData', wintypes.LPARAM),
                    ('lpfnHook', ctypes.c_void_p), ('lpTemplateName', wintypes.LPCWSTR),
                    ('pvReserved', ctypes.c_void_p), ('dwReserved', wintypes.DWORD),
                    ('FlagsEx', wintypes.DWORD)]

    buffer = ctypes.create_unicode_buffer(1024)
    ofn = OPENFILENAMEW()
    ofn.lStructSize = ctypes.sizeof(OPENFILENAMEW)
    try:
        ofn.hwndOwner = pg.display.get_wm_info().get('window') if pg else None
    except Exception:
        ofn.hwndOwner = None
    ofn.lpstrFilter = 'Pictures (*.png;*.jpg;*.jpeg;*.bmp;*.webp)\0*.png;*.jpg;*.jpeg;*.bmp;*.webp\0All files\0*.*\0\0'
    ofn.lpstrFile = ctypes.cast(buffer, wintypes.LPWSTR)
    ofn.nMaxFile = 1024
    ofn.lpstrTitle = 'Choose a photo for your character'
    ofn.Flags = 0x00001000 | 0x00000800 | 0x00080000 | 0x00000008   # must exist, path must exist, explorer, keep cwd
    try:
        if ctypes.windll.comdlg32.GetOpenFileNameW(ctypes.byref(ofn)):
            return buffer.value
    except (OSError, AttributeError):
        pass
    return None
