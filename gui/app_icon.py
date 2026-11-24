"""
Zero-Overhead Application Icon Loader.
Loads the pre-built multi-resolution app_icon.ico directly via Win32 and Tkinter
with zero runtime image rendering and zero Pillow dependency.
"""

import os
import sys
import ctypes


def get_resource_path(relative_path: str) -> str:
    """Resolve resource path for both normal Python execution and PyInstaller bundles."""
    base_dir = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base_dir, relative_path)


def apply_app_icon(root) -> list:
    """
    Apply pre-built app_icon.ico directly to Window Titlebar and Windows Taskbar.
    Zero runtime rendering overhead.
    """
    ico_path = get_resource_path("app_icon.ico")
    if not os.path.exists(ico_path):
        return []

    try:
        root.iconbitmap(default=ico_path)
        root.iconbitmap(ico_path)
    except Exception:
        pass

    if sys.platform == "win32":
        def _set_win32_icon():
            try:
                # WM_SETICON = 0x0080, ICON_SMALL = 0, ICON_BIG = 1
                # IMAGE_ICON = 1, LR_LOADFROMFILE = 0x0010, LR_DEFAULTSIZE = 0x0040
                hicon_big = ctypes.windll.user32.LoadImageW(0, ico_path, 1, 0, 0, 0x0010 | 0x0040)
                hicon_small = ctypes.windll.user32.LoadImageW(0, ico_path, 1, 16, 16, 0x0010)
                hwnd = root.winfo_id()
                if hwnd:
                    if hicon_big:
                        ctypes.windll.user32.SendMessageW(hwnd, 0x0080, 1, hicon_big)
                    if hicon_small:
                        ctypes.windll.user32.SendMessageW(hwnd, 0x0080, 0, hicon_small)
            except Exception:
                pass

        _set_win32_icon()

    return []
