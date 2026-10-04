"""
STM32 UART Bootloader Flasher Application.
Main Entry Point.
"""

import sys
import ctypes
import ttkbootstrap as tb
from core import __version__
from gui.main_window import Stm32FlasherApp


def enable_high_dpi_awareness():
    """Enable High-DPI scaling on Windows for ultra-sharp UI rendering."""
    if sys.platform == "win32":
        try:
            # Per-monitor DPI awareness (Windows 10/11)
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            try:
                # Fallback to system DPI awareness (Windows Vista/7/8)
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass


def main():
    enable_high_dpi_awareness()
    
    # Set Windows AppUserModelID early so Taskbar binds correctly to our custom icon
    if sys.platform == "win32":
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(f"antigravity.stm32.uart.flasher.app.{__version__}")
        except Exception:
            pass

    # Initialize modern themed window (disable default ttkbootstrap icon)
    root = tb.Window(
        title=f"STM32 UART Bootloader Flasher v{__version__}",
        themename="darkly",
        scaling=1.0,
        iconphoto=None,
    )
    
    app = Stm32FlasherApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
