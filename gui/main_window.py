"""
GUI Application for STM32 Flasher.
Ultra-lightweight, instant-launch native Windows interface (Pure stdlib tkinter + ttk).
Zero runtime image rendering, zero Pillow/ttkbootstrap overhead.
Features Per-Monitor V2 Live DPI Scaling (bypassing Tcl/Tk's frozen GetDeviceCaps bug).

Hardware Mapping:
- RTS = BOOT (BOOT0 pin on STM32)
- DTR = nRESET (NRST pin on STM32)

Boot Sequences:
- Enter Bootloader: Assert RTS (BOOT) => Pulse DTR (nRESET) 100ms => Release DTR
- Exit Bootloader : Deassert RTS (BOOT) => Pulse DTR (nRESET) 100ms => Release DTR
"""

import os
import sys
import ctypes
import threading
from datetime import datetime
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, filedialog, messagebox

from core import __version__
from core.serial_comm import SerialComm
from core.firmware_file import load_firmware, FirmwareInfo
from core.bootloader import Stm32Bootloader, CommandError, AbortedError
from core.chip_db import get_affected_sectors
from gui.app_icon import apply_app_icon


# Native Color Palette (Zero image generation)
BADGE_COLORS = {
    "primary": ("#0d6efd", "#ffffff"),
    "info": ("#0aa2c0", "#ffffff"),
    "success": ("#198754", "#ffffff"),
    "warning": ("#f59f00", "#ffffff"),
    "danger": ("#dc3545", "#ffffff"),
    "secondary": ("#5c636a", "#ffffff"),
}

# Logical point sizes for named fonts (converted directly to physical pixels via live monitor DPI)
FONT_SPECS = {
    "TkDefaultFont": ("Segoe UI", 10, "normal"),
    "TkTextFont": ("Segoe UI", 10, "normal"),
    "TkMenuFont": ("Segoe UI", 10, "normal"),
    "TkHeadingFont": ("Segoe UI", 10, "bold"),
    "TkFixedFont": ("Consolas", 10, "normal"),
    "AppTitleFont": ("Segoe UI", 13, "bold"),
    "AppBoldFont": ("Segoe UI", 10, "bold"),
    "AppSmallFont": ("Segoe UI", 9, "normal"),
    "AppSmallBoldFont": ("Segoe UI", 9, "bold"),
    "AppMonoFont": ("Consolas", 10, "normal"),
}


def get_live_window_dpi(root: tk.Tk, fallback: float = 96.0) -> float:
    """
    Query the real-time effective DPI of the monitor currently displaying `root`.
    Uses GetDpiForMonitor / GetDpiForWindow on the top-level HWND (GA_ROOT) so changes
    in Windows Display Settings are detected immediately without signing out of Windows.
    """
    if sys.platform != "win32":
        return fallback
    try:
        wid = root.winfo_id()
        if wid:
            hwnd = ctypes.windll.user32.GetAncestor(wid, 2) or wid  # GA_ROOT = 2
            hmon = ctypes.windll.user32.MonitorFromWindow(hwnd, 2)  # MONITOR_DEFAULTTONEAREST = 2
            if hmon:
                dpi_x = ctypes.c_uint(0)
                dpi_y = ctypes.c_uint(0)
                if ctypes.windll.shcore.GetDpiForMonitor(hmon, 0, ctypes.byref(dpi_x), ctypes.byref(dpi_y)) == 0:
                    if dpi_x.value > 0:
                        return float(dpi_x.value)
            win_dpi = ctypes.windll.user32.GetDpiForWindow(hwnd)
            if win_dpi > 0:
                return float(win_dpi)
    except Exception:
        pass
    return fallback


class Stm32FlasherApp:
    def __init__(self, root: tk.Tk, initial_dpi: float = 96.0):
        self.root = root
        self.root.withdraw()  # Keep hidden while constructing widgets
        self.root.title(f"STM32 UART Bootloader Flasher v{__version__}")

        self.current_dpi = float(initial_dpi)
        self.named_fonts: dict[str, tkfont.Font] = {}
        self._main_thread_id = threading.get_ident()

        # CRITICAL: Set initial geometry BEFORE any update_idletasks(), winfo_id(), or iconbitmap()
        # so Tcl/Tk's CreateWindowExW creates the Win32 HWND at the exact final full size immediately
        # (preventing Windows DWM from showing a 200x200 window and zooming it out).
        scale = max(1.0, self.current_dpi / 96.0)
        init_w = int(960 * scale)
        init_h = int(680 * scale)
        scr_w = self.root.winfo_screenwidth()
        scr_h = self.root.winfo_screenheight()
        init_w = min(init_w, int(scr_w * 0.94))
        init_h = min(init_h, int(scr_h * 0.90))
        pos_x = max(0, (scr_w - init_w) // 2)
        pos_y = max(0, (scr_h - init_h) // 2 - int(20 * scale))
        self.root.geometry(f"{init_w}x{init_h}+{pos_x}+{pos_y}")
        self.root.minsize(int(860 * scale), int(580 * scale))

        # Configure native Windows theme & DPI-accurate named pixel fonts
        self._init_native_styles_and_fonts(self.current_dpi)

        # State variables
        self.firmware: FirmwareInfo | None = None
        self.is_busy = False
        self.cancel_requested = False
        self.active_comm: SerialComm | None = None

        # Build UI
        self._init_variables()
        self._create_widgets()

        # Populate initial logs and COM ports before showing the window
        self._refresh_com_ports()
        self.log(f"STM32 UART Bootloader Flasher v{__version__} initialized.", "SUCCESS")
        self.log("Default Hardware Pinout: RTS = BOOT0 | DTR = NRST (100ms reset pulse).", "INFO")
        self.log("Ready. Select COM port and firmware file (.hex or .bin) to begin.", "INFO")

        # Flush layout at full geometry, apply icon, and reveal window in one instant frame
        self.root.update_idletasks()
        apply_app_icon(self.root)
        self.root.deiconify()

        self.root.bind("<Configure>", self._on_window_configure, add="+")
        self.root.after(400, self._poll_dpi_change)

    @staticmethod
    def _pt_to_neg_px(pt: float, dpi: float) -> int:
        """
        Convert typographic points (1/72 inch) to negative pixel height for Tcl/Tk.
        Negative font sizes in Tcl/Tk pass pixel height directly to Win32 CreateFontIndirectW,
        bypassing Tcl/Tk's buggy GetDeviceCaps(LOGPIXELSY) which stays frozen at logon DPI.
        """
        return -max(11, int(round(pt * dpi / 72.0)))

    def _init_native_styles_and_fonts(self, dpi: float):
        """Initialize Windows native theme and named fonts scaled to exact live monitor pixels."""
        style = ttk.Style(self.root)
        available = style.theme_names()
        if "vista" in available:
            style.theme_use("vista")
        elif "xpnative" in available:
            style.theme_use("xpnative")

        # Create/configure all named fonts using exact negative pixel heights
        existing_names = set(tkfont.names(self.root))
        for name, (family, pt, weight) in FONT_SPECS.items():
            px_size = self._pt_to_neg_px(pt, dpi)
            try:
                if name in existing_names:
                    f = tkfont.nametofont(name)
                    f.configure(family=family, size=px_size, weight=weight)
                else:
                    f = tkfont.Font(root=self.root, name=name, family=family, size=px_size, weight=weight)
                self.named_fonts[name] = f
            except Exception:
                pass

        # Ensure Combobox dropdown list uses the live-scaled TkTextFont
        self.root.option_add("*TCombobox*Listbox.font", "TkTextFont")

        self._refresh_ttk_styles(dpi)

    def _refresh_ttk_styles(self, dpi: float):
        """Configure ttk styles with DPI-scaled fonts and padding."""
        try:
            self.root.tk.call("tk", "scaling", dpi / 72.0)
        except Exception:
            pass

        style = ttk.Style(self.root)
        style.configure(".", font="TkDefaultFont")
        style.configure("TButton", font="TkDefaultFont")
        style.configure("TCheckbutton", font="TkDefaultFont")
        style.configure("TRadiobutton", font="TkDefaultFont")
        style.configure("TCombobox", font="TkTextFont")
        style.configure("TEntry", font="TkTextFont")
        style.configure("TSpinbox", font="TkTextFont")
        style.configure("TLabelframe.Label", font="AppBoldFont", foreground="#0d6efd")
        style.configure("Bold.TLabel", font="AppBoldFont")
        style.configure("Title.TLabel", font="AppTitleFont")
        style.configure("Muted.TLabel", font="AppSmallFont", foreground="#555555")
        style.configure("Success.TLabel", font="AppSmallBoldFont", foreground="#157347")
        style.configure("Danger.TLabel", font="AppSmallBoldFont", foreground="#bb2d3b")

    def _apply_window_geometry_for_dpi(self, dpi: float, center: bool = False):
        """Scale window dimensions and minimum size proportionally to live monitor DPI."""
        scale = max(1.0, dpi / 96.0)
        self.root.update_idletasks()
        req_w = self.root.winfo_reqwidth()
        req_h = self.root.winfo_reqheight()

        win_w = max(req_w + int(20 * scale), int(960 * scale))
        win_h = max(req_h + int(24 * scale), int(680 * scale))
        min_w = max(req_w, int(860 * scale))
        min_h = max(req_h, int(580 * scale))

        scr_w = self.root.winfo_screenwidth()
        scr_h = self.root.winfo_screenheight()
        win_w = min(win_w, int(scr_w * 0.94))
        win_h = min(win_h, int(scr_h * 0.90))
        min_w = min(min_w, win_w)
        min_h = min(min_h, win_h)

        self.root.minsize(min_w, min_h)
        if center:
            pos_x = max(0, (scr_w - win_w) // 2)
            pos_y = max(0, (scr_h - win_h) // 2 - int(20 * scale))
            self.root.geometry(f"{win_w}x{win_h}+{pos_x}+{pos_y}")
        else:
            self.root.geometry(f"{win_w}x{win_h}")

        # Flush Tcl's queued UpdateGeometryInfo while window is still withdrawn
        # so the Win32 HWND is already at full size before deiconify() maps it.
        self.root.update_idletasks()

    def _apply_live_dpi_update(self, live_dpi: float):
        """Rescale all named fonts, widget paddings, and window geometry when monitor DPI changes."""
        self.current_dpi = live_dpi
        for name, (_family, pt, _weight) in FONT_SPECS.items():
            f = self.named_fonts.get(name)
            if f is not None:
                try:
                    f.configure(size=self._pt_to_neg_px(pt, live_dpi))
                except Exception:
                    pass

        scale = max(1.0, live_dpi / 96.0)
        try:
            self.badge_lbl.configure(padx=int(10 * scale), pady=int(4 * scale))
            self.btn_detect.configure(padx=int(10 * scale), pady=int(3 * scale))
            self.btn_flash.configure(padx=int(18 * scale), pady=int(6 * scale))
            self.btn_cancel.configure(padx=int(14 * scale), pady=int(6 * scale))
        except Exception:
            pass

        self._refresh_ttk_styles(live_dpi)
        self._apply_window_geometry_for_dpi(live_dpi, center=False)

    def _on_window_configure(self, _event=None):
        """Detect cross-monitor DPI changes during window drag/resize."""
        live_dpi = get_live_window_dpi(self.root, self.current_dpi)
        if abs(live_dpi - self.current_dpi) >= 2.0:
            self._apply_live_dpi_update(live_dpi)

    def _poll_dpi_change(self):
        """Lightweight periodic check (0.005ms) to catch in-place Windows Display Scale changes."""
        try:
            if not self.root.winfo_exists():
                return
            live_dpi = get_live_window_dpi(self.root, self.current_dpi)
            if abs(live_dpi - self.current_dpi) >= 2.0:
                self._apply_live_dpi_update(live_dpi)
        except Exception:
            pass
        self.root.after(400, self._poll_dpi_change)

    def _init_variables(self):
        # Connection
        self.var_port = tk.StringVar()
        self.var_baud = tk.StringVar(value="115200")
        self.var_parity = tk.StringVar(value="Even (8E1)")
        self.var_target_family = tk.StringVar(value="AUTO (Auto-Detect)")

        # Hardware sequence config (Explicit RTS=BOOT, DTR=nRESET)
        self.var_pin_mode = tk.StringVar(value="RTS = BOOT, DTR = nRESET (Standard)")
        self.var_invert_boot = tk.BooleanVar(value=False)
        self.var_invert_reset = tk.BooleanVar(value=False)
        self.var_pulse_ms = tk.IntVar(value=100)

        # Firmware file & options
        self.var_file_path = tk.StringVar()
        self.var_flash_address = tk.StringVar(value="0x08000000")
        self.var_erase_before_flash = tk.BooleanVar(value=True)
        self.var_erase_mode = tk.StringVar(value="affected")  # "affected" or "mass"
        self.var_verify_flash = tk.BooleanVar(value=True)
        self.var_auto_run = tk.BooleanVar(value=True)

        # Status
        self.var_status_badge = tk.StringVar(value="READY")
        self.var_progress_info = tk.StringVar(value="Ready.")
        self.var_progress_val = tk.DoubleVar(value=0.0)

    def _make_flat_button(self, parent, text, bg, fg="#ffffff", active_bg=None, font="AppBoldFont", padx=12, pady=5, command=None, state="normal"):
        """Create a fast native Win32 flat color button using named DPI-scaled font."""
        return tk.Button(
            parent,
            text=text,
            bg=bg,
            fg=fg,
            activebackground=active_bg or bg,
            activeforeground=fg,
            disabledforeground="#d0d0d0",
            font=font,
            relief=tk.FLAT,
            bd=0,
            padx=padx,
            pady=pady,
            cursor="hand2",
            state=state,
            command=command,
        )

    def _create_widgets(self):
        main_frame = ttk.Frame(self.root, padding=(12, 10))
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 1. Header
        header = ttk.Frame(main_frame)
        header.pack(fill=tk.X, pady=(0, 8))

        title_frame = ttk.Frame(header)
        title_frame.pack(side=tk.LEFT)

        ttk.Label(
            title_frame,
            text=f"⚡ STM32 UART Bootloader Flasher  v{__version__}",
            style="Title.TLabel",
        ).pack(anchor="w")

        ttk.Label(
            title_frame,
            text="UART ISP  •  RTS = BOOT0  •  DTR = NRST  •  Auto-Detect & Sector Erase",
            style="Muted.TLabel",
        ).pack(anchor="w")

        self.badge_lbl = tk.Label(
            header,
            textvariable=self.var_status_badge,
            font="AppSmallBoldFont",
            bg="#0d6efd",
            fg="#ffffff",
            padx=10,
            pady=4,
        )
        self.badge_lbl.pack(side=tk.RIGHT, padx=(6, 0))

        # 2. Connection & Target Card
        self._create_connection_card(main_frame)

        # 3. Firmware File & Flash Options Card
        self._create_firmware_card(main_frame)

        # 4. Collapsible Advanced Hardware Settings
        self._create_advanced_hardware_section(main_frame)

        # 5. Primary Action Bar & Progress Bar
        self._create_action_bar(main_frame)

        # 6. Activity Log Console
        self._create_log_console(main_frame)

    def _create_connection_card(self, parent):
        card = ttk.LabelFrame(parent, text=" Target & Port ", padding=(10, 6))
        card.pack(fill=tk.X, pady=(0, 6))

        row = ttk.Frame(card)
        row.pack(fill=tk.X)

        ttk.Label(row, text="Port:", style="Bold.TLabel").pack(side=tk.LEFT, padx=(0, 4))
        self.cbo_ports = ttk.Combobox(row, textvariable=self.var_port, state="readonly", width=26, font="TkTextFont")
        self.cbo_ports.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))

        ttk.Button(row, text="Refresh", width=9, command=self._refresh_com_ports).pack(side=tk.LEFT, padx=(0, 10))

        ttk.Label(row, text="Baud:").pack(side=tk.LEFT, padx=(0, 4))
        cbo_baud = ttk.Combobox(
            row,
            textvariable=self.var_baud,
            values=["9600", "19200", "38400", "57600", "115200", "230400", "460800", "921600"],
            width=8,
            state="readonly",
            font="TkTextFont",
        )
        cbo_baud.pack(side=tk.LEFT, padx=(0, 10))

        ttk.Label(row, text="Target:").pack(side=tk.LEFT, padx=(0, 4))
        self.cbo_family = ttk.Combobox(
            row,
            textvariable=self.var_target_family,
            values=[
                "AUTO (Auto-Detect)",
                "STM32F4 (F405, F407...)",
                "STM32F1 (F103, F105...)",
                "STM32F0 (F030, F070...)",
                "STM32F3",
                "STM32F7",
                "STM32H7",
                "STM32L4",
                "STM32L0",
                "STM32G0",
            ],
            state="readonly",
            width=18,
            font="TkTextFont",
        )
        self.cbo_family.pack(side=tk.LEFT, padx=(0, 8))

        self.btn_detect = self._make_flat_button(
            row,
            text="Detect Chip",
            bg="#0aa2c0",
            active_bg="#08849e",
            padx=10,
            pady=3,
            command=self._on_btn_detect_chip,
        )
        self.btn_detect.pack(side=tk.LEFT)

    def _create_firmware_card(self, parent):
        card = ttk.LabelFrame(parent, text=" Firmware & Options ", padding=(10, 6))
        card.pack(fill=tk.X, pady=(0, 6))

        # Row 1: File selection
        r1 = ttk.Frame(card)
        r1.pack(fill=tk.X, pady=(0, 5))

        ttk.Label(r1, text="File:", width=8, style="Bold.TLabel").pack(side=tk.LEFT)
        self.ent_filepath = ttk.Entry(r1, textvariable=self.var_file_path, font="TkTextFont")
        self.ent_filepath.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
        ttk.Button(r1, text="Browse...", width=11, command=self._browse_firmware_file).pack(side=tk.RIGHT)

        # Row 2: Flash Address & File info tag
        r2 = ttk.Frame(card)
        r2.pack(fill=tk.X, pady=(0, 5))

        ttk.Label(r2, text="Address:", width=8).pack(side=tk.LEFT)
        self.ent_addr = ttk.Entry(r2, textvariable=self.var_flash_address, width=13, font="TkTextFont")
        self.ent_addr.pack(side=tk.LEFT, padx=(0, 10))

        self.lbl_file_details = ttk.Label(
            r2,
            text="No file selected (Supports .hex and .bin).",
            style="Muted.TLabel",
        )
        self.lbl_file_details.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Row 3: Flashing Options
        r3 = ttk.Frame(card)
        r3.pack(fill=tk.X)

        ttk.Checkbutton(
            r3,
            text="Erase Flash",
            variable=self.var_erase_before_flash,
            command=self._update_erase_options_state,
        ).pack(side=tk.LEFT, padx=(0, 8))

        self.rb_erase_affected = ttk.Radiobutton(
            r3,
            text="Affected sectors only",
            variable=self.var_erase_mode,
            value="affected",
        )
        self.rb_erase_affected.pack(side=tk.LEFT, padx=(0, 8))

        self.rb_erase_mass = ttk.Radiobutton(
            r3,
            text="Full chip",
            variable=self.var_erase_mode,
            value="mass",
        )
        self.rb_erase_mass.pack(side=tk.LEFT, padx=(0, 16))

        ttk.Checkbutton(
            r3,
            text="Verify after write",
            variable=self.var_verify_flash,
        ).pack(side=tk.LEFT, padx=(0, 14))

        ttk.Checkbutton(
            r3,
            text="Auto-run user code",
            variable=self.var_auto_run,
        ).pack(side=tk.LEFT)

    def _update_erase_options_state(self):
        state = "normal" if self.var_erase_before_flash.get() else "disabled"
        self.rb_erase_affected.config(state=state)
        self.rb_erase_mass.config(state=state)

    def _create_advanced_hardware_section(self, parent):
        self.adv_container = ttk.Frame(parent)
        self.adv_container.pack(fill=tk.X, pady=(0, 4))

        header_row = ttk.Frame(self.adv_container)
        header_row.pack(fill=tk.X)

        self.btn_toggle_adv = tk.Button(
            header_row,
            text="▸ Advanced Pin & Hardware Settings",
            font="AppSmallBoldFont",
            fg="#0d6efd",
            activeforeground="#0a58ca",
            relief=tk.FLAT,
            bd=0,
            cursor="hand2",
            command=self._toggle_advanced_panel,
        )
        self.btn_toggle_adv.pack(side=tk.LEFT)

        self.frame_advanced = ttk.LabelFrame(
            self.adv_container,
            text=" Hardware Sequence & Pins ",
            padding=(10, 6),
        )

        r_pins = ttk.Frame(self.frame_advanced)
        r_pins.pack(fill=tk.X, pady=(0, 5))

        ttk.Label(r_pins, text="Pin Mode:").pack(side=tk.LEFT, padx=(0, 4))
        cbo_pin_mode = ttk.Combobox(
            r_pins,
            textvariable=self.var_pin_mode,
            values=[
                "RTS = BOOT, DTR = nRESET (Standard)",
                "DTR = BOOT, RTS = nRESET (Swapped)",
            ],
            state="readonly",
            width=28,
            font="TkTextFont",
        )
        cbo_pin_mode.pack(side=tk.LEFT, padx=(0, 10))

        ttk.Label(r_pins, text="Pulse:").pack(side=tk.LEFT, padx=(0, 4))
        ttk.Spinbox(
            r_pins,
            from_=20,
            to=1000,
            increment=20,
            textvariable=self.var_pulse_ms,
            width=5,
            font="TkTextFont",
        ).pack(side=tk.LEFT, padx=(0, 2))
        ttk.Label(r_pins, text="ms").pack(side=tk.LEFT, padx=(0, 12))

        ttk.Checkbutton(r_pins, text="Invert RTS (BOOT)", variable=self.var_invert_boot).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Checkbutton(r_pins, text="Invert DTR (nRESET)", variable=self.var_invert_reset).pack(side=tk.LEFT)

        r_btns = ttk.Frame(self.frame_advanced)
        r_btns.pack(fill=tk.X)

        ttk.Button(r_btns, text="Enter Boot Mode", command=self._on_btn_manual_enter_boot).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(r_btns, text="Exit Boot & Run", command=self._on_btn_manual_exit_boot).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(r_btns, text="Pulse Reset", command=self._on_btn_manual_reset).pack(side=tk.LEFT)

    def _toggle_advanced_panel(self):
        if self.frame_advanced.winfo_ismapped():
            self.frame_advanced.pack_forget()
            self.btn_toggle_adv.config(text="▸ Advanced Pin & Hardware Settings")
        else:
            self.frame_advanced.pack(fill=tk.X, pady=(4, 2))
            self.btn_toggle_adv.config(text="▾ Advanced Pin & Hardware Settings")
            self.root.update_idletasks()
            req_h = self.root.winfo_reqheight()
            cur_w = self.root.winfo_width()
            cur_h = self.root.winfo_height()
            if cur_h < req_h:
                self.root.geometry(f"{cur_w}x{req_h}")

    def _create_action_bar(self, parent):
        action_frame = ttk.Frame(parent)
        action_frame.pack(fill=tk.X, pady=(2, 6))

        self.btn_flash = self._make_flat_button(
            action_frame,
            text="⚡ Flash Firmware",
            bg="#198754",
            active_bg="#146c43",
            font="AppBoldFont",
            padx=18,
            pady=6,
            command=self._on_btn_flash,
        )
        self.btn_flash.pack(side=tk.LEFT, padx=(0, 8))

        self.btn_erase = ttk.Button(
            action_frame,
            text="Erase Flash",
            padding=(10, 5),
            command=self._on_btn_erase,
        )
        self.btn_erase.pack(side=tk.LEFT, padx=(0, 6))

        self.btn_dump = ttk.Button(
            action_frame,
            text="Read / Backup",
            padding=(10, 5),
            command=self._on_btn_dump,
        )
        self.btn_dump.pack(side=tk.LEFT, padx=(0, 6))

        self.btn_unprotect = ttk.Button(
            action_frame,
            text="Unprotect RDP",
            padding=(10, 5),
            command=self._on_btn_unprotect,
        )
        self.btn_unprotect.pack(side=tk.LEFT, padx=(0, 6))

        self.btn_cancel = self._make_flat_button(
            action_frame,
            text="Cancel",
            bg="#dc3545",
            active_bg="#b02a37",
            padx=14,
            pady=6,
            state="disabled",
            command=self._on_btn_cancel,
        )
        self.btn_cancel.pack(side=tk.RIGHT)

        # Progress bar & status label
        p_frame = ttk.Frame(parent)
        p_frame.pack(fill=tk.X, pady=(0, 6))

        self.progress_bar = ttk.Progressbar(
            p_frame,
            variable=self.var_progress_val,
            maximum=100.0,
        )
        self.progress_bar.pack(fill=tk.X, pady=(0, 3))

        self.lbl_progress_status = ttk.Label(
            p_frame,
            textvariable=self.var_progress_info,
            style="Muted.TLabel",
        )
        self.lbl_progress_status.pack(side=tk.LEFT)

    def _create_log_console(self, parent):
        log_frame = ttk.Frame(parent)
        log_frame.pack(fill=tk.BOTH, expand=True)

        tool_frame = ttk.Frame(log_frame)
        tool_frame.pack(fill=tk.X, pady=(0, 2))

        ttk.Label(
            tool_frame,
            text="Activity Log",
            style="Bold.TLabel",
        ).pack(side=tk.LEFT)

        ttk.Button(tool_frame, text="Clear", width=7, command=self._clear_log).pack(side=tk.RIGHT)
        ttk.Button(tool_frame, text="Save Log...", width=11, command=self._export_log).pack(side=tk.RIGHT, padx=(0, 4))

        console_box = ttk.Frame(log_frame)
        console_box.pack(fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(console_box, orient=tk.VERTICAL)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.txt_log = tk.Text(
            console_box,
            wrap=tk.WORD,
            height=8,
            font="AppMonoFont",
            bg="#181a1f",
            fg="#e6edf3",
            insertbackground="#ffffff",
            relief=tk.SOLID,
            bd=1,
            padx=8,
            pady=6,
            yscrollcommand=scrollbar.set,
        )
        self.txt_log.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.txt_log.yview)

        # High-contrast syntax colors on dark log terminal
        self.txt_log.tag_config("INFO", foreground="#39c5bb")
        self.txt_log.tag_config("SUCCESS", foreground="#3fb950")
        self.txt_log.tag_config("WARNING", foreground="#d29922")
        self.txt_log.tag_config("ERROR", foreground="#f85149")
        self.txt_log.tag_config("HARDWARE", foreground="#ffa657")
        self.txt_log.tag_config("TIME", foreground="#8b949e")

    # ================= UI Helpers =================
    def _set_badge(self, text: str, style_key: str = "primary"):
        self.var_status_badge.set(text)
        bg, fg = BADGE_COLORS.get(style_key, BADGE_COLORS["primary"])
        self.badge_lbl.configure(bg=bg, fg=fg)

    def _refresh_com_ports(self):
        ports = SerialComm.list_ports()
        values = [p[1] for p in ports]
        self.cbo_ports["values"] = values

        if ports:
            selected = values[0]
            for _, p_lbl in ports:
                if any(x in p_lbl.upper() for x in ("CP210", "CH340", "FTDI", "STM32", "USB-SERIAL")):
                    selected = p_lbl
                    break
            self.var_port.set(selected)
            self.log(f"[Port] Found {len(ports)} serial port(s): {', '.join(p[0] for p in ports)}", "INFO")
        else:
            self.var_port.set("")
            self.log("[Port] No COM ports detected. Please connect your USB-UART bridge.", "WARNING")

    def _get_selected_port_device(self) -> str:
        val = self.var_port.get().strip()
        if not val:
            raise ValueError("Please select a COM port first!")
        return val.split(" - ")[0].strip()

    def _get_parity_char(self) -> str:
        val = self.var_parity.get().upper()
        if "EVEN" in val:
            return "E"
        elif "ODD" in val:
            return "O"
        return "N"

    def _get_pin_config(self):
        mode = self.var_pin_mode.get()
        if "DTR = BOOT" in mode:
            boot_pin, reset_pin = "DTR", "RTS"
        else:
            boot_pin, reset_pin = "RTS", "DTR"

        return {
            "boot_pin": boot_pin,
            "reset_pin": reset_pin,
            "invert_boot": self.var_invert_boot.get(),
            "invert_reset": self.var_invert_reset.get(),
            "pulse_ms": self.var_pulse_ms.get(),
        }

    def _get_target_family(self) -> str:
        val = self.var_target_family.get().upper()
        if "AUTO" in val:
            return "AUTO"
        for fam in ("F4", "F1", "F0", "F3", "F7", "H7", "L4", "L0", "G0"):
            if fam in val:
                return fam
        return "F4"

    def _set_busy(self, busy: bool, badge_text: str = "", badge_style: str = "primary"):
        self.is_busy = busy
        state = "disabled" if busy else "normal"
        self.btn_flash.config(state=state, bg="#6c757d" if busy else "#198754")
        self.btn_detect.config(state=state, bg="#6c757d" if busy else "#0aa2c0")
        self.btn_erase.config(state=state)
        self.btn_dump.config(state=state)
        self.btn_unprotect.config(state=state)
        self.btn_cancel.config(state="normal" if busy else "disabled", bg="#dc3545" if busy else "#a5a5a5")

        if badge_text:
            self._set_badge(badge_text, badge_style)

    def log(self, message: str, level: str = "INFO"):
        def _append():
            now_str = datetime.now().strftime("%H:%M:%S")
            self.txt_log.insert(tk.END, f"[{now_str}] ", "TIME")
            lvl_tag = level.upper()
            if "[Hardware]" in message or ("BOOT" in message and "nRESET" in message):
                lvl_tag = "HARDWARE"
            self.txt_log.insert(tk.END, f"{message}\n", lvl_tag)
            self.txt_log.see(tk.END)

        if threading.get_ident() == self._main_thread_id:
            _append()
        else:
            self.root.after(0, _append)

    def _clear_log(self):
        self.txt_log.delete("1.0", tk.END)

    def _export_log(self):
        f = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text file", "*.txt")])
        if f:
            with open(f, "w", encoding="utf-8") as fp:
                fp.write(self.txt_log.get("1.0", tk.END))
            messagebox.showinfo("Log Saved", f"Log successfully exported to:\n{f}")

    # ================= Firmware File Handling =================
    def _browse_firmware_file(self):
        filetypes = [
            ("All Firmware files (*.hex;*.bin)", "*.hex;*.bin"),
            ("Intel HEX (*.hex)", "*.hex"),
            ("Binary RAW (*.bin)", "*.bin"),
            ("All files (*.*)", "*.*"),
        ]
        chosen = filedialog.askopenfilename(title="Select Firmware File", filetypes=filetypes)
        if not chosen:
            return

        self.var_file_path.set(chosen)
        self._load_and_display_firmware(chosen)

    def _load_and_display_firmware(self, filepath: str):
        try:
            addr = int(self.var_flash_address.get().strip(), 16)
        except Exception:
            addr = 0x08000000

        try:
            self.firmware = load_firmware(filepath, default_bin_address=addr)
            if self.firmware.file_type == "HEX":
                self.var_flash_address.set(f"0x{self.firmware.start_address:08X}")

            family = self._get_target_family()
            if family == "AUTO":
                family = "F4"
            sectors, sec_desc = get_affected_sectors(family, self.firmware.start_address, self.firmware.size_bytes)

            info_text = (
                f"File: {self.firmware.filename} [{self.firmware.file_type}] | "
                f"Size: {self.firmware.size_bytes:,} B ({self.firmware.size_kb:.1f} KB) | "
                f"Addr: 0x{self.firmware.start_address:08X} - 0x{self.firmware.end_address:08X} | "
                f"Sectors: {sectors} | CRC32: {self.firmware.crc32_str}"
            )
            self.lbl_file_details.config(text=info_text, style="Success.TLabel")
            self.log(f"[File] Loaded firmware: {self.firmware.filename} ({self.firmware.size_bytes:,} bytes, {self.firmware.file_type})", "SUCCESS")
            self.log(f"[File] Target Address Range: 0x{self.firmware.start_address:08X} - 0x{self.firmware.end_address:08X}", "INFO")
            self.log(f"[File] Affected Flash Sectors: {sec_desc}", "INFO")
        except Exception as e:
            self.firmware = None
            err_msg = f"Failed to load firmware: {e}"
            self.lbl_file_details.config(text=err_msg, style="Danger.TLabel")
            self.log(f"[File] {err_msg}", "ERROR")

    # ================= Background Execution Helper =================
    def _run_in_thread(self, target, badge_text="PROCESSING..."):
        if self.is_busy:
            return
        self.cancel_requested = False
        self._set_busy(True, badge_text=badge_text, badge_style="warning")

        thread = threading.Thread(target=target, daemon=True)
        thread.start()

    def _on_btn_cancel(self):
        if self.is_busy:
            self.cancel_requested = True
            self.log("[User] Cancel button clicked. Aborting current operation...", "WARNING")
            self.var_progress_info.set("Cancelling...")

    # ================= Worker Implementations =================
    def _open_connection_and_sync(self, enter_boot=True) -> tuple[SerialComm, Stm32Bootloader]:
        port = self._get_selected_port_device()
        baud = int(self.var_baud.get().strip())
        parity = self._get_parity_char()
        pin_cfg = self._get_pin_config()

        comm = SerialComm(port=port, baudrate=baud, parity=parity, timeout=3.0)
        self.active_comm = comm
        self.log(f"[Connect] Opening {port} @ {baud} baud, 8{parity}1...", "INFO")
        comm.connect()

        if enter_boot:
            comm.enter_boot_mode(
                boot_pin=pin_cfg["boot_pin"],
                reset_pin=pin_cfg["reset_pin"],
                invert_boot=pin_cfg["invert_boot"],
                invert_reset=pin_cfg["invert_reset"],
                pulse_ms=pin_cfg["pulse_ms"],
                log_callback=lambda msg, *_: self.log(msg, "HARDWARE"),
            )

        bl = Stm32Bootloader(comm, log_callback=self.log)

        try:
            bl.synchronize()
        except CommandError as sync_err:
            if not pin_cfg["invert_boot"]:
                self.log("[Auto-Sync] Initial sync attempt failed. Testing inverted RTS (BOOT) logic...", "WARNING")
                comm.enter_boot_mode(
                    boot_pin=pin_cfg["boot_pin"],
                    reset_pin=pin_cfg["reset_pin"],
                    invert_boot=True,
                    invert_reset=pin_cfg["invert_reset"],
                    pulse_ms=pin_cfg["pulse_ms"],
                    log_callback=lambda msg, *_: self.log(msg, "HARDWARE"),
                )
                try:
                    bl.synchronize(max_attempts=3)
                    self.log("[Auto-Sync] Synchronized successfully with inverted RTS polarity! Updated configuration.", "SUCCESS")
                    self.root.after(0, lambda: self.var_invert_boot.set(True))
                    return comm, bl
                except Exception:
                    pass
            raise sync_err

        return comm, bl

    def _on_btn_detect_chip(self):
        def worker():
            comm = None
            try:
                self.var_progress_info.set("Connecting and identifying chip...")
                comm, bl = self._open_connection_and_sync(enter_boot=True)

                target_fam = self._get_target_family()
                detected = bl.detect_chip(target_fam)

                self.log("================ CHIP IDENTIFIED ================", "SUCCESS")
                self.log(f"  Chip Model: {detected.name}", "SUCCESS")
                self.log(f"  Chip ID   : 0x{detected.chip_id:04X}", "SUCCESS")
                self.log(f"  Family    : STM32{detected.family} ({detected.description})", "SUCCESS")
                self.log(f"  Flash Size: {detected.flash_size_kb} KB", "SUCCESS")
                self.log(f"  Bootloader: {detected.bootloader_version}", "SUCCESS")
                self.log(f"  Device UID: {detected.uid_str}", "SUCCESS")
                self.log(f"  Ext Erase : {'Supported (0x44)' if detected.has_extended_erase else 'Not supported'}", "INFO")
                self.log("=================================================", "SUCCESS")

                def update_ui():
                    self.var_progress_info.set(f"Detected: {detected.name} ({detected.flash_size_kb} KB Flash)")
                    self._set_badge(f"{detected.family} - 0x{detected.chip_id:03X}", "info")

                self.root.after(0, update_ui)

            except Exception as e:
                self.log(f"[Detect Error] {e}", "ERROR")
                self.log(
                    "[Troubleshooting Tips]\n"
                    "  1. Ensure TX/RX lines are cross-connected (PC TX -> MCU RX, PC RX -> MCU TX).\n"
                    "  2. Verify RTS is connected to BOOT0 and DTR is connected to NRST.\n"
                    "  3. Check 'Invert RTS (BOOT)' or 'Invert DTR (nRESET)' if active level differs.",
                    "WARNING",
                )
                self.root.after(0, lambda: messagebox.showerror("Detection Failed", f"Could not detect STM32 microcontroller:\n{e}"))
            finally:
                if comm:
                    comm.disconnect()
                self.active_comm = None
                self.root.after(0, lambda: self._set_busy(False, "READY", "primary"))

        self._run_in_thread(worker, badge_text="DETECTING CHIP...")

    def _on_btn_flash(self):
        filepath = self.var_file_path.get().strip()
        if not filepath:
            messagebox.showwarning("No File Selected", "Please select a .hex or .bin firmware file first!")
            return

        if not self.firmware or self.firmware.filepath != os.path.abspath(filepath):
            self._load_and_display_firmware(filepath)
            if not self.firmware:
                return

        try:
            write_addr = int(self.var_flash_address.get().strip(), 16)
        except Exception:
            messagebox.showerror("Invalid Address", "Flash address must be a valid hex number (e.g. 0x08000000)!")
            return

        erase_first = self.var_erase_before_flash.get()
        erase_mode = self.var_erase_mode.get()
        verify_after = self.var_verify_flash.get()
        auto_run = self.var_auto_run.get()
        pin_cfg = self._get_pin_config()

        def worker():
            comm = None
            try:
                self.log("[Flash] Starting firmware programming workflow...", "INFO")
                self.log(f"[Flash] Firmware: {self.firmware.filename} ({self.firmware.size_bytes:,} bytes)", "INFO")
                self.log(f"[Flash] Flash Address: 0x{write_addr:08X}", "INFO")

                comm, bl = self._open_connection_and_sync(enter_boot=True)

                target_fam = self._get_target_family()
                detected = bl.detect_chip(target_fam)
                self.log(f"[Flash] Target detected: {detected.name} (Flash: {detected.flash_size_kb} KB)", "SUCCESS")

                if erase_first:
                    self.root.after(0, lambda: self._set_badge("ERASING...", "warning"))

                    if erase_mode == "affected":
                        affected_sectors, sec_desc = get_affected_sectors(
                            detected.family, write_addr, len(self.firmware.data)
                        )
                        self.log(f"[Erase] Erasing only affected sectors: {sec_desc} (preserving all other sectors)...", "INFO")
                        self.var_progress_info.set(f"Erasing sector(s) {affected_sectors}...")
                        bl.erase_flash(
                            global_erase=False,
                            sectors=affected_sectors,
                            progress_callback=lambda msg: self.var_progress_info.set(msg),
                        )
                    else:
                        self.log("[Erase] Full Chip Mass Erase requested...", "INFO")
                        self.var_progress_info.set("Erasing Full Chip Flash (10-25s)...")
                        bl.erase_flash(
                            global_erase=True,
                            progress_callback=lambda msg: self.var_progress_info.set(msg),
                        )

                self.root.after(0, lambda: self._set_badge("PROGRAMMING...", "info"))
                self.log("[Flash] Writing firmware blocks to Flash...", "INFO")

                def on_write_prog(done, total, msg):
                    pct = (done / total) * 100.0
                    self.root.after(0, lambda: self.var_progress_val.set(pct))
                    self.root.after(0, lambda: self.var_progress_info.set(msg))

                bl.write_memory_blocks(
                    address=write_addr,
                    data=self.firmware.data,
                    progress_callback=on_write_prog,
                    cancel_token=lambda: self.cancel_requested,
                )

                self.log("[Flash] Firmware blocks written successfully!", "SUCCESS")

                if verify_after:
                    self.root.after(0, lambda: self._set_badge("VERIFYING...", "info"))
                    self.log("[Flash] Reading back Flash to verify integrity...", "INFO")

                    def on_verify_prog(done, total, _msg):
                        pct = (done / total) * 100.0
                        self.root.after(0, lambda: self.var_progress_val.set(pct))
                        self.root.after(0, lambda: self.var_progress_info.set(f"Verifying: {pct:.1f}% ({done}/{total} bytes)"))

                    bl.verify_memory(
                        address=write_addr,
                        expected_data=self.firmware.data,
                        progress_callback=on_verify_prog,
                        cancel_token=lambda: self.cancel_requested,
                    )
                    self.log("[Flash] Flash verification completed: 100% byte match!", "SUCCESS")

                if auto_run:
                    self.log("[Flash] Exiting bootloader to run user application...", "INFO")
                    comm.exit_boot_mode(
                        boot_pin=pin_cfg["boot_pin"],
                        reset_pin=pin_cfg["reset_pin"],
                        invert_boot=pin_cfg["invert_boot"],
                        invert_reset=pin_cfg["invert_reset"],
                        pulse_ms=pin_cfg["pulse_ms"],
                        log_callback=lambda msg, *_: self.log(msg, "HARDWARE"),
                    )

                self.log("[Flash] FIRMWARE FLASHING COMPLETED SUCCESSFULLY!", "SUCCESS")
                self.root.after(0, lambda: self.var_progress_info.set("Flashing successful! Microcontroller is running."))
                self.root.after(0, lambda: self.var_progress_val.set(100.0))
                self.root.after(0, lambda: messagebox.showinfo("Programming Succeeded", f"Successfully flashed '{self.firmware.filename}' onto STM32!"))

            except AbortedError:
                self.log("[Flash] Flashing operation was cancelled by user.", "WARNING")
                self.root.after(0, lambda: self.var_progress_info.set("Cancelled."))
            except Exception as e:
                self.log(f"[Flash Error] {e}", "ERROR")
                self.root.after(0, lambda: messagebox.showerror("Flashing Failed", f"Flashing process encountered an error:\n{e}"))
            finally:
                if comm:
                    comm.disconnect()
                self.active_comm = None
                self.root.after(0, lambda: self._set_busy(False, "READY", "primary"))

        self._run_in_thread(worker, badge_text="FLASHING...")

    def _on_btn_erase(self):
        if self.firmware:
            res = messagebox.askyesnocancel(
                "Erase Flash",
                f"A firmware file '{self.firmware.filename}' is loaded.\n\n"
                "• Click YES to erase ONLY the sectors used by this firmware (Preserve other sectors).\n"
                "• Click NO to perform a FULL CHIP MASS ERASE.\n"
                "• Click CANCEL to abort.",
            )
            if res is None:
                return
            only_affected = res is True
        else:
            if not messagebox.askyesno("Confirm Flash Erase", "Are you sure you want to perform a FULL CHIP MASS ERASE on STM32?"):
                return
            only_affected = False

        def worker():
            comm = None
            try:
                self.var_progress_info.set("Connecting to erase Flash...")
                comm, bl = self._open_connection_and_sync(enter_boot=True)
                target_fam = self._get_target_family()
                detected = bl.detect_chip(target_fam)

                if only_affected and self.firmware:
                    write_addr = int(self.var_flash_address.get().strip(), 16)
                    sectors, desc = get_affected_sectors(detected.family, write_addr, len(self.firmware.data))
                    self.log(f"[Erase] Erasing only firmware sectors: {desc}...", "INFO")
                    bl.erase_flash(global_erase=False, sectors=sectors, progress_callback=lambda msg: self.var_progress_info.set(msg))
                    self.log(f"[Erase] Sectors {sectors} erased successfully! Other sectors remain intact.", "SUCCESS")
                    self.root.after(0, lambda: messagebox.showinfo("Erase Complete", f"Sectors {sectors} erased successfully!"))
                else:
                    self.log("[Erase] Executing Full Chip Mass Erase...", "INFO")
                    bl.erase_flash(global_erase=True, progress_callback=lambda msg: self.var_progress_info.set(msg))
                    self.log("[Erase] Full chip Flash erase completed successfully!", "SUCCESS")
                    self.root.after(0, lambda: messagebox.showinfo("Erase Complete", "Full chip Flash erase completed successfully!"))
            except Exception as e:
                self.log(f"[Erase Error] {e}", "ERROR")
                self.root.after(0, lambda: messagebox.showerror("Erase Error", f"Failed to erase Flash:\n{e}"))
            finally:
                if comm:
                    comm.disconnect()
                self.active_comm = None
                self.root.after(0, lambda: self._set_busy(False, "READY", "primary"))

        self._run_in_thread(worker, badge_text="ERASING FLASH...")

    def _on_btn_dump(self):
        f = filedialog.asksaveasfilename(
            title="Save Flash Backup",
            defaultextension=".bin",
            filetypes=[("Binary file", "*.bin")],
        )
        if not f:
            return

        try:
            addr = int(self.var_flash_address.get().strip(), 16)
        except Exception:
            addr = 0x08000000

        def worker():
            comm = None
            try:
                self.var_progress_info.set("Connecting to read Flash...")
                comm, bl = self._open_connection_and_sync(enter_boot=True)
                target_fam = self._get_target_family()
                detected = bl.detect_chip(target_fam)

                total_bytes = detected.flash_size_kb * 1024
                self.log(f"[Backup] Reading {detected.flash_size_kb} KB Flash starting from 0x{addr:08X}...", "INFO")

                def on_dump_prog(done, total, msg):
                    pct = (done / total) * 100.0
                    self.root.after(0, lambda: self.var_progress_val.set(pct))
                    self.root.after(0, lambda: self.var_progress_info.set(msg))

                data = bl.read_memory_blocks(
                    address=addr,
                    total_length=total_bytes,
                    progress_callback=on_dump_prog,
                    cancel_token=lambda: self.cancel_requested,
                )

                with open(f, "wb") as fp:
                    fp.write(data)

                self.log(f"[Backup] Successfully saved {len(data):,} bytes to: {f}", "SUCCESS")
                self.root.after(0, lambda: messagebox.showinfo("Backup Succeeded", f"Flash backup saved successfully ({len(data):,} bytes):\n{f}"))
            except AbortedError:
                self.log("[Backup] Flash readout was cancelled.", "WARNING")
            except Exception as e:
                self.log(f"[Backup Error] {e}", "ERROR")
                self.root.after(0, lambda: messagebox.showerror("Readout Error", f"Failed to read Flash:\n{e}"))
            finally:
                if comm:
                    comm.disconnect()
                self.active_comm = None
                self.root.after(0, lambda: self._set_busy(False, "READY", "primary"))

        self._run_in_thread(worker, badge_text="READING FLASH...")

    def _on_btn_unprotect(self):
        if not messagebox.askyesno(
            "Readout Unprotect (RDP) Warning",
            "Disabling Readout Protection will trigger an AUTOMATIC FULL CHIP MASS ERASE of all user Flash and reset the MCU.\n\nDo you wish to proceed?",
        ):
            return

        def worker():
            comm = None
            try:
                self.var_progress_info.set("Connecting to disable RDP...")
                comm, bl = self._open_connection_and_sync(enter_boot=True)
                bl.readout_unprotect()
                self.log("[Unprotect] Readout Unprotect executed. Flash is erased and chip reset.", "SUCCESS")
                self.root.after(0, lambda: messagebox.showinfo("Unprotect Complete", "Readout protection removed. Flash has been fully erased."))
            except Exception as e:
                self.log(f"[Unprotect Error] {e}", "ERROR")
                self.root.after(0, lambda: messagebox.showerror("Unprotect Error", f"Failed to unprotect Flash:\n{e}"))
            finally:
                if comm:
                    comm.disconnect()
                self.active_comm = None
                self.root.after(0, lambda: self._set_busy(False, "READY", "primary"))

        self._run_in_thread(worker, badge_text="UNPROTECTING...")

    # ================= Manual Hardware Sequence Triggers =================
    def _on_btn_manual_enter_boot(self):
        port = self._get_selected_port_device()
        baud = int(self.var_baud.get().strip())
        parity = self._get_parity_char()
        pin_cfg = self._get_pin_config()

        def worker():
            comm = SerialComm(port=port, baudrate=baud, parity=parity)
            try:
                comm.connect()
                comm.enter_boot_mode(
                    boot_pin=pin_cfg["boot_pin"],
                    reset_pin=pin_cfg["reset_pin"],
                    invert_boot=pin_cfg["invert_boot"],
                    invert_reset=pin_cfg["invert_reset"],
                    pulse_ms=pin_cfg["pulse_ms"],
                    log_callback=lambda msg, *_: self.log(msg, "HARDWARE"),
                )
                self.log(f"[Hardware] Enter Boot sequence completed (Assert {pin_cfg['boot_pin']} -> Pulse {pin_cfg['reset_pin']} {pin_cfg['pulse_ms']}ms).", "SUCCESS")
            except Exception as e:
                self.log(f"[Hardware Error] {e}", "ERROR")
            finally:
                comm.disconnect()
                self.root.after(0, lambda: self._set_busy(False, "READY", "primary"))

        self._run_in_thread(worker, badge_text="ENTER BOOT...")

    def _on_btn_manual_exit_boot(self):
        port = self._get_selected_port_device()
        baud = int(self.var_baud.get().strip())
        parity = self._get_parity_char()
        pin_cfg = self._get_pin_config()

        def worker():
            comm = SerialComm(port=port, baudrate=baud, parity=parity)
            try:
                comm.connect()
                comm.exit_boot_mode(
                    boot_pin=pin_cfg["boot_pin"],
                    reset_pin=pin_cfg["reset_pin"],
                    invert_boot=pin_cfg["invert_boot"],
                    invert_reset=pin_cfg["invert_reset"],
                    pulse_ms=pin_cfg["pulse_ms"],
                    log_callback=lambda msg, *_: self.log(msg, "HARDWARE"),
                )
                self.log(f"[Hardware] Exit Boot sequence completed (Release {pin_cfg['boot_pin']} -> Pulse {pin_cfg['reset_pin']} {pin_cfg['pulse_ms']}ms).", "SUCCESS")
            except Exception as e:
                self.log(f"[Hardware Error] {e}", "ERROR")
            finally:
                comm.disconnect()
                self.root.after(0, lambda: self._set_busy(False, "READY", "primary"))

        self._run_in_thread(worker, badge_text="EXIT BOOT...")

    def _on_btn_manual_reset(self):
        port = self._get_selected_port_device()
        baud = int(self.var_baud.get().strip())
        parity = self._get_parity_char()
        pin_cfg = self._get_pin_config()

        def worker():
            comm = SerialComm(port=port, baudrate=baud, parity=parity)
            try:
                comm.connect()
                comm.pulse_reset(
                    reset_pin=pin_cfg["reset_pin"],
                    invert_reset=pin_cfg["invert_reset"],
                    pulse_ms=pin_cfg["pulse_ms"],
                    log_callback=lambda msg, *_: self.log(msg, "HARDWARE"),
                )
                self.log(f"[Hardware] Reset pulse ({pin_cfg['pulse_ms']}ms) sent via {pin_cfg['reset_pin']} (nRESET).", "SUCCESS")
            except Exception as e:
                self.log(f"[Hardware Error] {e}", "ERROR")
            finally:
                comm.disconnect()
                self.root.after(0, lambda: self._set_busy(False, "READY", "primary"))

        self._run_in_thread(worker, badge_text="PULSE RESET...")
