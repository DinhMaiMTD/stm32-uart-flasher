# STM32 UART Bootloader Flasher v1.1.0

A simple, lightweight GUI tool for flashing STM32 microcontrollers via serial UART bootloader (ST AN3155 protocol).

Supports all major STM32 families (**F0, F1, F3, F4, F7, H7, L0, L4, G0...**) with automatic chip detection and smart sector erase.

---

## Features

- **Automated Bootloader Entry/Exit**: Uses `RTS` (`BOOT0`) and `DTR` (`NRST`) control lines—no jumpers or manual buttons needed (optional).
- **Smart Sector-Only Erase**: Only erases flash sectors used by your firmware, preserving all other flash contents.
- **File Format Support**: Accepts Intel HEX (`.hex`) and raw binary (`.bin`) files with CRC32 verification.
- **Auto Chip Detection**: Identifies chip model, Flash size, Bootloader version, and 96-bit Unique ID (UID).
- **Minimalist & Modern UI**: Clean layout, comfortable typography, dark/light theme toggle, and collapsible advanced pin settings.
- **Additional Tools**: Full chip mass erase, flash backup/dump to `.bin`, and Readout Protection (RDP) unprotect.

---

## Hardware Wiring

Connect your USB-UART adapter to the STM32 board:

| USB-UART Adapter | STM32 Target | Note |
| :--- | :--- | :--- |
| **TX** | **RX** (e.g. `PA10`) | Serial receive (Required) |
| **RX** | **TX** (e.g. `PA9`) | Serial transmit (Required) |
| **GND** | **GND** | Common ground (Required) |
| **RTS** | **BOOT0** | Boot mode select *(Optional: for automated mode)* |
| **DTR** | **NRST** | Hardware reset pulse *(Optional: for automated mode)* |

> **Note on Manual Mode**: If RTS and DTR are not wired, you can manually set the `BOOT0` jumper to 3.3V (HIGH), `BOOT1` to GND, and press the physical Reset button on your board before flashing.

---

## How to Run

### From Source
```bash
pip install -r requirements.txt
python main.py
```

### Build Standalone Executable (.exe)
Run `release.bat`. The standalone `STM32_UART_Flasher.exe` will be generated in `dist/`.

