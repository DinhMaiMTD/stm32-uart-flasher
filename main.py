"""
STM32 UART Bootloader Flasher Application.
Ultra-lightweight Pure Native Tkinter/TTK Entry Point (Zero External UI Dependencies).
Supports Per-Monitor V2 Live DPI Scaling on Windows 10/11.
"""

import sys
import ctypes
from ctypes import wintypes
import tkinter as tk
from core import __version__
from gui.main_window import Stm32FlasherApp


def init_win32_dpi_and_get_live_dpi() -> float:
    """
    Enable Per-Monitor V2 High-DPI awareness and query the live monitor DPI via GetDpiForMonitor.
    Unlike GetDpiForSystem()/GetDeviceCaps(), GetDpiForMonitor immediately reflects Windows Display Scale
    changes without requiring the user to sign out of Windows.
    """
    if sys.platform != "win32":
        return 96.0

    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            f"stm32.uart.bootloader.flasher.{__version__}"
        )
    except Exception:
        pass

    # Enable Per-Monitor V2 DPI Awareness (-4 = DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2)
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except Exception:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass

    # Query live effective DPI of the active monitor
    try:
        pt = wintypes.POINT(0, 0)
        ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
        hmon = ctypes.windll.user32.MonitorFromPoint(pt, 2)  # MONITOR_DEFAULTTONEAREST = 2
        dpi_x = ctypes.c_uint(96)
        dpi_y = ctypes.c_uint(96)
        res = ctypes.windll.shcore.GetDpiForMonitor(hmon, 0, ctypes.byref(dpi_x), ctypes.byref(dpi_y))
        if res == 0 and dpi_x.value > 0:
            return float(dpi_x.value)
    except Exception:
        pass

    try:
        return float(ctypes.windll.user32.GetDpiForSystem())
    except Exception:
        return 96.0


def main():
    live_dpi = init_win32_dpi_and_get_live_dpi()

    root = tk.Tk()
    root.withdraw()  # Hide initial 200x200 frame until full UI and geometry are ready
    app = Stm32FlasherApp(root, initial_dpi=live_dpi)
    root.mainloop()


if __name__ == "__main__":
    main()
