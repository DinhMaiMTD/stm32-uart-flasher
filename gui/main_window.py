"""
GUI Application for STM32 Flasher.
Modern, responsive, extra-large interface built with ttkbootstrap.
Hardware Mapping:
- RTS = BOOT (BOOT0 pin on STM32)
- DTR = nRESET (NRST pin on STM32)

Boot Sequences:
- Enter Bootloader: Assert RTS (BOOT) => Pulse DTR (nRESET) 100ms => Release DTR
- Exit Bootloader : Deassert RTS (BOOT) => Pulse DTR (nRESET) 100ms => Release DTR
"""

import os
import sys
import time
import threading
from datetime import datetime
import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog, messagebox
import ttkbootstrap as tb
from ttkbootstrap.constants import *
from ttkbootstrap.scrolled import ScrolledText

from core import __version__
from core.serial_comm import SerialComm
from core.firmware_file import load_firmware, FirmwareInfo
from core.bootloader import Stm32Bootloader, BootloaderError, CommandError, DataMismatchError, AbortedError
from core.chip_db import lookup_chip_info, get_affected_sectors
from gui.app_icon import apply_app_icon


class Stm32FlasherApp:
    def __init__(self, root: tb.Window):
        self.root = root
        self.root.title(f"STM32 UART Bootloader Flasher v{__version__}")
        self.root.geometry("980x740")
        self.root.minsize(860, 640)

        # Apply programmatic STM32 chip icon to Titlebar & Windows Taskbar
        self.app_icons = apply_app_icon(self.root)

        # Apply ergonomic typography & clean styling (+2 font size)
        self._apply_custom_styles()

        # State variables
        self.firmware: FirmwareInfo | None = None
        self.is_busy = False
        self.cancel_requested = False
        self.active_comm: SerialComm | None = None

        # Build UI
        self._init_variables()
        self._create_widgets()
        self._refresh_com_ports()

        self.log(f"STM32 UART Bootloader Flasher v{__version__} initialized.", "SUCCESS")
        self.log("Default Hardware Pinout: RTS = BOOT0 | DTR = NRST (100ms reset pulse).", "INFO")
        self.log("Ready. Select COM port and firmware file (.hex or .bin) to begin.", "INFO")

    def _apply_custom_styles(self):
        """Configure ergonomic typography and minimalist component spacing (+2 font sizes)."""
        try:
            for font_name in ("TkDefaultFont", "TkTextFont", "TkMenuFont"):
                f = tkfont.nametofont(font_name)
                f.configure(family="Segoe UI", size=12)
            
            f_fixed = tkfont.nametofont("TkFixedFont")
            f_fixed.configure(family="Consolas", size=12)
        except Exception:
            pass

        # Configure ttk styles with balanced sizing (+2 sizes)
        style = self.root.style
        style.configure(".", font=("Segoe UI", 12))
        style.configure("TLabelframe.Label", font=("Segoe UI", 12, "bold"))
        style.configure("TCombobox", font=("Segoe UI", 12))
        style.configure("TEntry", font=("Segoe UI", 12))
        style.configure("TCheckbutton", font=("Segoe UI", 12))
        style.configure("TRadiobutton", font=("Segoe UI", 12))
        style.configure("TButton", font=("Segoe UI", 12))

        # Specialized button styles
        style.configure("Flash.TButton", font=("Segoe UI", 13, "bold"))
        style.configure("Action.TButton", font=("Segoe UI", 12, "bold"))

    def _init_variables(self):
        # Connection
        self.var_port = tk.StringVar()
        self.var_baud = tk.StringVar(value="115200")
        self.var_parity = tk.StringVar(value="Even (8E1)")
        self.var_target_family = tk.StringVar(value="AUTO")

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

    def _create_widgets(self):
        # Main container with clean 12px padding
        main_frame = tb.Frame(self.root, padding=12)
        main_frame.pack(fill=BOTH, expand=YES)

        # 1. Header (Minimalist & Sleek)
        header = tb.Frame(main_frame)
        header.pack(fill=X, pady=(0, 8))

        title_frame = tb.Frame(header)
        title_frame.pack(side=LEFT)

        title_lbl = tb.Label(
            title_frame,
            text=f"⚡ STM32 Bootloader Flasher  v{__version__}",
            font=("Segoe UI", 15, "bold"),
            bootstyle="default",
        )
        title_lbl.pack(anchor="w")

        sub_lbl = tb.Label(
            title_frame,
            text="UART ISP  •  RTS = BOOT0  •  DTR = NRST  •  Auto-Detect & Sector Erase",
            font=("Segoe UI", 11),
            bootstyle="secondary",
        )
        sub_lbl.pack(anchor="w", pady=(1, 0))

        # Status badge & Theme toggle on top right
        self.badge_lbl = tb.Label(
            header,
            textvariable=self.var_status_badge,
            font=("Segoe UI", 11, "bold"),
            bootstyle="secondary-inverse",
            padding=(10, 3),
        )
        self.badge_lbl.pack(side=RIGHT, padx=(6, 0))

        theme_btn = tb.Button(
            header,
            text="🌓 Theme",
            bootstyle="outline-secondary",
            padding=(8, 3),
            command=self._toggle_theme,
        )
        theme_btn.pack(side=RIGHT)

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
        card = tb.Labelframe(parent, text=" Target & Port ", padding=(10, 6))
        card.pack(fill=X, pady=(0, 6))

        row = tb.Frame(card)
        row.pack(fill=X)

        # Port selection
        tb.Label(row, text="Port:", font=("Segoe UI", 11, "bold")).pack(side=LEFT, padx=(0, 4))
        self.cbo_ports = tb.Combobox(row, textvariable=self.var_port, state="readonly", width=22)
        self.cbo_ports.pack(side=LEFT, fill=X, expand=YES, padx=(0, 4))

        tb.Button(row, text="Refresh", padding=(6, 2), bootstyle="outline-secondary", command=self._refresh_com_ports).pack(side=LEFT, padx=(0, 10))

        # Baudrate
        tb.Label(row, text="Baud:").pack(side=LEFT, padx=(0, 4))
        cbo_baud = tb.Combobox(
            row,
            textvariable=self.var_baud,
            values=["9600", "19200", "38400", "57600", "115200", "230400", "460800", "921600"],
            width=8,
            state="readonly",
        )
        cbo_baud.pack(side=LEFT, padx=(0, 10))

        # Target Chip
        tb.Label(row, text="Target:").pack(side=LEFT, padx=(0, 4))
        self.cbo_family = tb.Combobox(
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
        )
        self.cbo_family.pack(side=LEFT, padx=(0, 6))

        btn_detect = tb.Button(
            row,
            text="Detect Chip",
            padding=(8, 2),
            bootstyle="info",
            command=self._on_btn_detect_chip,
        )
        btn_detect.pack(side=LEFT)

    def _create_firmware_card(self, parent):
        card = tb.Labelframe(parent, text=" Firmware & Options ", padding=(10, 6))
        card.pack(fill=X, pady=(0, 6))

        # Row 1: File selection
        r1 = tb.Frame(card)
        r1.pack(fill=X, pady=(0, 4))

        tb.Label(r1, text="File:", width=8, font=("Segoe UI", 11, "bold")).pack(side=LEFT)
        self.ent_filepath = tb.Entry(r1, textvariable=self.var_file_path)
        self.ent_filepath.pack(side=LEFT, fill=X, expand=YES, padx=(0, 6))
        tb.Button(r1, text="Browse...", padding=(10, 2), bootstyle="secondary", command=self._browse_firmware_file).pack(side=RIGHT)

        # Row 2: Flash Address & File info tag
        r2 = tb.Frame(card)
        r2.pack(fill=X, pady=(0, 5))

        tb.Label(r2, text="Address:", width=8).pack(side=LEFT)
        self.ent_addr = tb.Entry(r2, textvariable=self.var_flash_address, width=12)
        self.ent_addr.pack(side=LEFT, padx=(0, 10))

        self.lbl_file_details = tb.Label(
            r2,
            text="No file selected (Supports .hex and .bin).",
            font=("Segoe UI", 11),
            bootstyle="secondary",
        )
        self.lbl_file_details.pack(side=LEFT, fill=X, expand=YES)

        # Row 3: Flashing Options (Tidy inline layout)
        r3 = tb.Frame(card)
        r3.pack(fill=X)

        tb.Checkbutton(
            r3,
            text="Erase Flash",
            variable=self.var_erase_before_flash,
            command=self._update_erase_options_state,
        ).pack(side=LEFT, padx=(0, 6))

        self.rb_erase_affected = tb.Radiobutton(
            r3,
            text="Affected sectors only",
            variable=self.var_erase_mode,
            value="affected",
        )
        self.rb_erase_affected.pack(side=LEFT, padx=(0, 6))

        self.rb_erase_mass = tb.Radiobutton(
            r3,
            text="Full chip",
            variable=self.var_erase_mode,
            value="mass",
        )
        self.rb_erase_mass.pack(side=LEFT, padx=(0, 14))

        tb.Checkbutton(
            r3,
            text="Verify after write",
            variable=self.var_verify_flash,
        ).pack(side=LEFT, padx=(0, 12))

        tb.Checkbutton(
            r3,
            text="Auto-run user code",
            variable=self.var_auto_run,
        ).pack(side=LEFT)

    def _update_erase_options_state(self):
        state = "normal" if self.var_erase_before_flash.get() else "disabled"
        self.rb_erase_affected.config(state=state)
        self.rb_erase_mass.config(state=state)

    def _create_advanced_hardware_section(self, parent):
        self.adv_container = tb.Frame(parent)
        self.adv_container.pack(fill=X, pady=(0, 4))

        # Toggle Button / Header
        header_row = tb.Frame(self.adv_container)
        header_row.pack(fill=X)

        self.btn_toggle_adv = tb.Button(
            header_row,
            text="▸ Advanced Pin & Hardware Settings",
            bootstyle="link",
            padding=(0, 2),
            command=self._toggle_advanced_panel,
        )
        self.btn_toggle_adv.pack(side=LEFT)

        # The collapsible content frame (initially hidden)
        self.frame_advanced = tb.Labelframe(self.adv_container, text=" Hardware Sequence & Pins ", padding=(10, 6))

        r_pins = tb.Frame(self.frame_advanced)
        r_pins.pack(fill=X, pady=(0, 4))

        tb.Label(r_pins, text="Pin Mode:").pack(side=LEFT, padx=(0, 4))
        cbo_pin_mode = tb.Combobox(
            r_pins,
            textvariable=self.var_pin_mode,
            values=[
                "RTS = BOOT, DTR = nRESET (Standard)",
                "DTR = BOOT, RTS = nRESET (Swapped)",
            ],
            state="readonly",
            width=26,
        )
        cbo_pin_mode.pack(side=LEFT, padx=(0, 8))

        tb.Label(r_pins, text="Pulse:").pack(side=LEFT, padx=(0, 4))
        tb.Spinbox(
            r_pins,
            from_=20,
            to=1000,
            increment=20,
            textvariable=self.var_pulse_ms,
            width=5,
        ).pack(side=LEFT, padx=(0, 2))
        tb.Label(r_pins, text="ms").pack(side=LEFT, padx=(0, 10))

        tb.Checkbutton(r_pins, text="Invert RTS (BOOT)", variable=self.var_invert_boot).pack(side=LEFT, padx=(0, 8))
        tb.Checkbutton(r_pins, text="Invert DTR (nRESET)", variable=self.var_invert_reset).pack(side=LEFT)

        # Manual test triggers
        r_btns = tb.Frame(self.frame_advanced)
        r_btns.pack(fill=X, pady=(2, 0))

        tb.Button(
            r_btns,
            text="Enter Boot Mode",
            padding=(8, 2),
            bootstyle="outline-secondary",
            command=self._on_btn_manual_enter_boot,
        ).pack(side=LEFT, padx=(0, 6))

        tb.Button(
            r_btns,
            text="Exit Boot & Run",
            padding=(8, 2),
            bootstyle="outline-secondary",
            command=self._on_btn_manual_exit_boot,
        ).pack(side=LEFT, padx=(0, 6))

        tb.Button(
            r_btns,
            text="Pulse Reset",
            padding=(8, 2),
            bootstyle="outline-secondary",
            command=self._on_btn_manual_reset,
        ).pack(side=LEFT)

    def _toggle_advanced_panel(self):
        if self.frame_advanced.winfo_ismapped():
            self.frame_advanced.pack_forget()
            self.btn_toggle_adv.config(text="▸ Advanced Pin & Hardware Settings")
        else:
            self.frame_advanced.pack(fill=X, pady=(3, 0))
            self.btn_toggle_adv.config(text="▾ Advanced Pin & Hardware Settings")

    def _create_action_bar(self, parent):
        action_frame = tb.Frame(parent)
        action_frame.pack(fill=X, pady=(2, 6))

        # Primary Action Buttons
        self.btn_flash = tb.Button(
            action_frame,
            text="⚡ Flash Firmware",
            bootstyle="success",
            style="Flash.TButton",
            padding=(20, 8),
            command=self._on_btn_flash,
        )
        self.btn_flash.pack(side=LEFT, padx=(0, 6))

        self.btn_erase = tb.Button(
            action_frame,
            text="Erase Flash",
            bootstyle="outline-warning",
            padding=(10, 8),
            command=self._on_btn_erase,
        )
        self.btn_erase.pack(side=LEFT, padx=(0, 6))

        self.btn_dump = tb.Button(
            action_frame,
            text="Read / Backup",
            bootstyle="outline-info",
            padding=(10, 8),
            command=self._on_btn_dump,
        )
        self.btn_dump.pack(side=LEFT, padx=(0, 6))

        self.btn_unprotect = tb.Button(
            action_frame,
            text="Unprotect RDP",
            bootstyle="outline-danger",
            padding=(10, 8),
            command=self._on_btn_unprotect,
        )
        self.btn_unprotect.pack(side=LEFT, padx=(0, 6))

        self.btn_cancel = tb.Button(
            action_frame,
            text="Cancel",
            bootstyle="danger",
            padding=(12, 8),
            state="disabled",
            command=self._on_btn_cancel,
        )
        self.btn_cancel.pack(side=RIGHT)

        # Progress bar & status label
        p_frame = tb.Frame(parent)
        p_frame.pack(fill=X, pady=(0, 6))

        self.progress_bar = tb.Progressbar(
            p_frame,
            variable=self.var_progress_val,
            maximum=100.0,
            bootstyle="success-striped",
        )
        self.progress_bar.pack(fill=X, pady=(0, 2))

        self.lbl_progress_status = tb.Label(
            p_frame,
            textvariable=self.var_progress_info,
            font=("Segoe UI", 11),
            bootstyle="secondary",
        )
        self.lbl_progress_status.pack(side=LEFT)

    def _create_log_console(self, parent):
        log_frame = tb.Frame(parent)
        log_frame.pack(fill=BOTH, expand=YES)

        # Log toolbar
        tool_frame = tb.Frame(log_frame)
        tool_frame.pack(fill=X, pady=(0, 2))

        tb.Label(
            tool_frame,
            text="Activity Log",
            font=("Segoe UI", 11, "bold"),
            bootstyle="secondary",
        ).pack(side=LEFT)

        tb.Button(
            tool_frame,
            text="Clear",
            padding=(6, 1),
            bootstyle="link",
            command=self._clear_log,
        ).pack(side=RIGHT)

        tb.Button(
            tool_frame,
            text="Save Log...",
            padding=(6, 1),
            bootstyle="link",
            command=self._export_log,
        ).pack(side=RIGHT, padx=(0, 4))

        # Scrolled Text Box with comfortable monospace font (+2 size)
        self.txt_log = ScrolledText(
            log_frame,
            wrap=tk.WORD,
            height=7,
            autohide=True,
            font=("Consolas", 12),
        )
        self.txt_log.pack(fill=BOTH, expand=YES)

        # Setup Pleasant Tag Colors for Log Levels
        self.txt_log.tag_config("INFO", foreground="#0dcaf0")
        self.txt_log.tag_config("SUCCESS", foreground="#20c997")
        self.txt_log.tag_config("WARNING", foreground="#ffc107")
        self.txt_log.tag_config("ERROR", foreground="#e63946")
        self.txt_log.tag_config("HARDWARE", foreground="#fd7e14")
        self.txt_log.tag_config("TIME", foreground="#6c757d")

    # ================= UI Helpers =================
    def _toggle_theme(self):
        current_theme = self.root.style.theme.name
        new_theme = "flatly" if current_theme in ("darkly", "superhero", "cyborg") else "darkly"
        self.root.style.theme_use(new_theme)
        self._apply_custom_styles()

    def _refresh_com_ports(self):
        ports = SerialComm.list_ports()
        values = [p[1] for p in ports]
        self.cbo_ports["values"] = values

        if ports:
            # Prefer CP210x, CH340, FTDI, STM32 if found
            selected = values[0]
            for p_dev, p_lbl in ports:
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
        self.btn_flash.config(state=state)
        self.btn_erase.config(state=state)
        self.btn_dump.config(state=state)
        self.btn_unprotect.config(state=state)
        self.btn_cancel.config(state="normal" if busy else "disabled")

        if badge_text:
            self.var_status_badge.set(badge_text)
            self.badge_lbl.configure(bootstyle=f"{badge_style}-inverse")

    def log(self, message: str, level: str = "INFO"):
        def _append():
            now_str = datetime.now().strftime("%H:%M:%S")
            self.txt_log.insert(tk.END, f"[{now_str}] ", "TIME")
            lvl_tag = level.upper()
            if "[Hardware]" in message or ("BOOT" in message and "nRESET" in message):
                lvl_tag = "HARDWARE"
            self.txt_log.insert(tk.END, f"{message}\n", lvl_tag)
            self.txt_log.see(tk.END)

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
                # Auto-set address field from HEX file's starting address
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
            self.lbl_file_details.config(text=info_text, bootstyle="success")
            self.log(f"[File] Loaded firmware: {self.firmware.filename} ({self.firmware.size_bytes:,} bytes, {self.firmware.file_type})", "SUCCESS")
            self.log(f"[File] Target Address Range: 0x{self.firmware.start_address:08X} - 0x{self.firmware.end_address:08X}", "INFO")
            self.log(f"[File] Affected Flash Sectors: {sec_desc}", "INFO")
        except Exception as e:
            self.firmware = None
            err_msg = f"Failed to load firmware: {e}"
            self.lbl_file_details.config(text=err_msg, bootstyle="danger")
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
            # Trigger custom boot sequence: Assert RTS (BOOT) => Pulse DTR (nRESET) 100ms => Release DTR
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
            # Auto-recovery: If sync failed and user hasn't inverted BOOT, test inverted RTS logic once
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
            # If still fails, re-raise original sync error
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

                # Report detected info
                self.log("================ CHIP IDENTIFIED ================", "SUCCESS")
                self.log(f"  Chip Model: {detected.name}", "SUCCESS")
                self.log(f"  Chip ID   : 0x{detected.chip_id:04X}", "SUCCESS")
                self.log(f"  Family    : STM32{detected.family} ({detected.description})", "SUCCESS")
                self.log(f"  Flash Size: {detected.flash_size_kb} KB", "SUCCESS")
                self.log(f"  Bootloader: {detected.bootloader_version}", "SUCCESS")
                self.log(f"  Device UID: {detected.uid_str}", "SUCCESS")
                self.log(f"  Ext Erase : {'Supported (0x44)' if detected.has_extended_erase else 'Not supported'}", "INFO")
                self.log("=================================================", "SUCCESS")

                # Update UI
                def update_ui():
                    self.var_progress_info.set(f"Detected: {detected.name} ({detected.flash_size_kb} KB Flash)")
                    self.var_status_badge.set(f"{detected.family} - 0x{detected.chip_id:03X}")
                    self.badge_lbl.configure(bootstyle="info-inverse")

                self.root.after(0, update_ui)

            except Exception as e:
                self.log(f"[Detect Error] {e}", "ERROR")
                self.log("[Troubleshooting Tips]\n"
                         "  1. Ensure TX/RX lines are cross-connected (PC TX -> MCU RX, PC RX -> MCU TX).\n"
                         "  2. Verify RTS is connected to BOOT0 and DTR is connected to NRST.\n"
                         "  3. Check 'Invert RTS (BOOT)' or 'Invert DTR (nRESET)' if active level differs.", "WARNING")
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

        # Ensure firmware is loaded
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

                # Chip detection & family auto-setup
                target_fam = self._get_target_family()
                detected = bl.detect_chip(target_fam)
                self.log(f"[Flash] Target detected: {detected.name} (Flash: {detected.flash_size_kb} KB)", "SUCCESS")

                # Erase Flash if requested
                if erase_first:
                    self.var_status_badge.set("ERASING...")
                    
                    if erase_mode == "affected":
                        # Only erase sectors touched by the firmware
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
                        # Full chip mass erase
                        self.log("[Erase] Full Chip Mass Erase requested...", "INFO")
                        self.var_progress_info.set("Erasing Full Chip Flash (10-25s)...")
                        bl.erase_flash(
                            global_erase=True,
                            progress_callback=lambda msg: self.var_progress_info.set(msg),
                        )

                # Write Flash
                self.var_status_badge.set("PROGRAMMING...")
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

                # Verify Flash
                if verify_after:
                    self.var_status_badge.set("VERIFYING...")
                    self.log("[Flash] Reading back Flash to verify integrity...", "INFO")

                    def on_verify_prog(done, total, msg):
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

                # Auto Exit Boot & Run User Code
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

                self.log("[Flash] FIRMWARE FLASHING COMPLETED SUCCESSFULLY! 🎉", "SUCCESS")
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
        # Choose erase scope
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
            only_affected = (res is True)
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

