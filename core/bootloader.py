"""
STM32 Bootloader Protocol Engine (ST AN3155 / AN2606).
Handles USART synchronization, device detection, reading, writing, sector-based erasing, and verification.
Specifically optimized for STM32F405 and all major STM32 families.
"""

import time
import struct
import operator
from functools import reduce
from dataclasses import dataclass
from typing import Callable, Optional

from core.chip_db import lookup_chip_info, FAMILY_DEFAULTS, get_affected_sectors


class BootloaderError(Exception):
    """Base exception for bootloader errors."""
    pass


class CommandError(BootloaderError):
    """Raised when a bootloader command fails or returns NACK."""
    pass


class DataMismatchError(BootloaderError):
    """Raised when verification fails."""
    pass


class AbortedError(BootloaderError):
    """Raised when the operation is cancelled by the user."""
    pass


@dataclass
class DetectedChip:
    chip_id: int
    name: str
    family: str
    description: str
    bootloader_version: str
    flash_size_kb: int
    uid_str: str
    has_extended_erase: bool
    supported_commands: list[int]


class Stm32Bootloader:
    """Implements the STM32 UART Bootloader Protocol."""

    CMD_GET = 0x00
    CMD_GET_VERSION = 0x01
    CMD_GET_ID = 0x02
    CMD_READ_MEMORY = 0x11
    CMD_GO = 0x21
    CMD_WRITE_MEMORY = 0x31
    CMD_ERASE = 0x43
    CMD_EXTENDED_ERASE = 0x44
    CMD_WRITE_PROTECT = 0x63
    CMD_WRITE_UNPROTECT = 0x73
    CMD_READOUT_PROTECT = 0x82
    CMD_READOUT_UNPROTECT = 0x92
    CMD_SYNCHRONIZE = 0x7F

    ACK = 0x79
    NACK = 0x1F

    def __init__(self, comm, log_callback: Optional[Callable[..., None]] = None):
        """
        :param comm: An instance of SerialComm.
        :param log_callback: Function to report log strings.
        """
        self.comm = comm
        self._log_cb = log_callback
        self.supported_commands: list[int] = []
        self.boot_version: int = 0
        self.has_extended_erase: bool = False
        self.family: str = "F4"
        self.transfer_size: int = 256

    def log(self, message: str, level: str = "INFO") -> None:
        """Report log message to callback with signature compatibility."""
        if not self._log_cb:
            return
        try:
            self._log_cb(message, level)
        except TypeError:
            try:
                self._log_cb(message)
            except Exception:
                pass

    def _wait_ack(self, context: str = "") -> None:
        """Wait for ACK (0x79) from MCU."""
        reply = self.comm.read(1)
        if not reply:
            raise CommandError(f"Timeout waiting for STM32 response ({context}).")
        byte_val = reply[0]
        if byte_val == self.ACK:
            return
        elif byte_val == self.NACK:
            raise CommandError(
                f"STM32 returned NACK (command rejected) ({context}). "
                f"If Readout Protection (RDP) is enabled, please use 'Unlock RDP' to erase and unprotect the chip."
            )
        else:
            raise CommandError(f"Unexpected response from STM32: 0x{byte_val:02X} ({context}).")

    def _send_command(self, cmd: int, context: str = "") -> None:
        """Send command byte and its XOR complement, then wait for ACK."""
        self.comm.write(bytes([cmd, cmd ^ 0xFF]))
        self._wait_ack(f"Command 0x{cmd:02X} - {context}")

    @staticmethod
    def _encode_address(address: int) -> bytes:
        """Encode 32-bit address in big-endian + XOR checksum byte."""
        addr_bytes = struct.pack(">I", address)
        checksum = reduce(operator.xor, addr_bytes)
        return addr_bytes + bytes([checksum])

    def synchronize(self, max_attempts: int = 6) -> bool:
        """
        Send 0x7F to activate USART bootloader and auto-baud.
        Returns True if synchronized successfully.
        """
        self.comm.flush_input_buffer()
        for attempt in range(1, max_attempts + 1):
            self.log(f"[Sync] Synchronizing baudrate with STM32 (Attempt {attempt}/{max_attempts})...")
            self.comm.write(bytes([self.CMD_SYNCHRONIZE]))
            reply = self.comm.read(1)
            if reply and reply[0] in (self.ACK, self.NACK):
                self.log(f"[Sync] Synchronized successfully! (Response: 0x{reply[0]:02X})")
                return True
            time.sleep(0.08)

        raise CommandError("No ACK response from STM32 Bootloader. Please verify wiring and Boot mode pin levels.")

    def get_supported_commands(self) -> tuple[int, list[int]]:
        """Query bootloader version and list of supported commands."""
        self._send_command(self.CMD_GET, "GET Commands")
        len_byte = self.comm.read(1)
        if not len_byte:
            raise CommandError("Failed to read command count from STM32.")
        length = len_byte[0]

        ver_byte = self.comm.read(1)
        if not ver_byte:
            raise CommandError("Failed to read Bootloader version byte.")
        self.boot_version = ver_byte[0]

        cmds = self.comm.read(length)
        self._wait_ack("GET Commands completion")

        self.supported_commands = list(cmds)
        self.has_extended_erase = self.CMD_EXTENDED_ERASE in self.supported_commands
        return self.boot_version, self.supported_commands

    def get_chip_id(self) -> int:
        """Query STM32 Device Chip ID (PID)."""
        self._send_command(self.CMD_GET_ID, "GET ID")
        len_byte = self.comm.read(1)
        if not len_byte:
            raise CommandError("Failed to read Chip ID length.")
        length = len_byte[0] + 1  # ST AN3155: length is count - 1

        id_data = self.comm.read(length)
        self._wait_ack("GET ID completion")

        if len(id_data) < 2:
            raise CommandError("Chip ID data length less than 2 bytes.")
        
        chip_id = (id_data[0] << 8) | id_data[1]
        return chip_id

    def read_memory(self, address: int, length: int) -> bytes:
        """Read up to 256 bytes from flash/system memory."""
        if length <= 0 or length > self.transfer_size:
            raise ValueError(f"Read length must be between 1 and {self.transfer_size} bytes.")

        self._send_command(self.CMD_READ_MEMORY, f"Read Memory at 0x{address:08X}")
        self.comm.write(self._encode_address(address))
        self._wait_ack(f"Send read address 0x{address:08X}")

        # Send number of bytes to read (N-1) and XOR checksum ( (N-1) ^ 0xFF )
        nr_byte = (length - 1) & 0xFF
        checksum = nr_byte ^ 0xFF
        self.comm.write(bytes([nr_byte, checksum]))
        self._wait_ack(f"Confirm read count {length}")

        data = self.comm.read(length)
        if len(data) != length:
            raise CommandError(f"Only received {len(data)}/{length} bytes at 0x{address:08X}.")
        return data

    def read_memory_blocks(
        self,
        address: int,
        total_length: int,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        cancel_token: Optional[Callable[[], bool]] = None,
    ) -> bytes:
        """Read a large memory block with progress reporting."""
        data = bytearray()
        remaining = total_length
        current_addr = address
        start_time = time.time()

        while remaining > 0:
            if cancel_token and cancel_token():
                raise AbortedError("Operation cancelled by user.")

            chunk_len = min(remaining, self.transfer_size)
            chunk = self.read_memory(current_addr, chunk_len)
            data.extend(chunk)

            remaining -= chunk_len
            current_addr += chunk_len

            if progress_callback:
                done = total_length - remaining
                elapsed = max(0.001, time.time() - start_time)
                speed_kb = (done / 1024.0) / elapsed
                progress_callback(done, total_length, f"Reading: {done}/{total_length} bytes ({speed_kb:.1f} KB/s)")

        return bytes(data)

    def write_memory_chunk(self, address: int, data: bytes) -> None:
        """Write up to 256 bytes to flash memory at address."""
        length = len(data)
        if length == 0 or length > self.transfer_size:
            raise ValueError(f"Write chunk length must be between 1 and {self.transfer_size} bytes.")

        # STM32 flash programming requires data aligned to 4 bytes. Pad with 0xFF.
        chunk = bytearray(data)
        pad = (4 - (len(chunk) % 4)) % 4
        if pad > 0:
            chunk.extend([0xFF] * pad)

        chunk_len = len(chunk)
        self._send_command(self.CMD_WRITE_MEMORY, f"Write at 0x{address:08X}")
        self.comm.write(self._encode_address(address))
        self._wait_ack(f"Send write address 0x{address:08X}")

        # Byte count (N-1)
        count_byte = (chunk_len - 1) & 0xFF
        checksum = reduce(operator.xor, chunk, count_byte)

        payload = bytes([count_byte]) + bytes(chunk) + bytes([checksum])
        self.comm.write(payload)
        self._wait_ack(f"Programming Flash at 0x{address:08X}")

    def write_memory_blocks(
        self,
        address: int,
        data: bytes,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        cancel_token: Optional[Callable[[], bool]] = None,
    ) -> None:
        """Write entire binary payload to flash in chunks with progress reporting."""
        total_length = len(data)
        remaining = total_length
        current_addr = address
        offset = 0
        start_time = time.time()

        while remaining > 0:
            if cancel_token and cancel_token():
                raise AbortedError("Operation cancelled by user.")

            chunk_len = min(remaining, self.transfer_size)
            chunk = data[offset : offset + chunk_len]
            self.write_memory_chunk(current_addr, chunk)

            remaining -= chunk_len
            current_addr += chunk_len
            offset += chunk_len

            if progress_callback:
                done = total_length - remaining
                elapsed = max(0.001, time.time() - start_time)
                speed_kb = (done / 1024.0) / elapsed
                percent = (done / total_length) * 100.0
                progress_callback(done, total_length, f"Programming: {percent:.1f}% ({done}/{total_length} bytes, {speed_kb:.1f} KB/s)")

    def erase_flash(
        self,
        global_erase: bool = False,
        sectors: Optional[list[int]] = None,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> None:
        """
        Erase flash memory.
        If global_erase is True: performs full chip mass erase (0xFFFF).
        If sectors is provided: erases ONLY the specified sectors/pages, leaving all other sectors untouched.
        """
        prev_timeout = self.comm.timeout

        try:
            if self.has_extended_erase:
                # Extended Erase (0x44) for STM32F4/F7/H7/L4
                self.log("[Erase] Using Extended Erase command (0x44)...")
                self._send_command(self.CMD_EXTENDED_ERASE, "Extended Erase")

                if global_erase or not sectors:
                    # Full chip mass erase: 0xFFFF with checksum 0x00
                    self.comm.timeout = 60.0
                    self.log("[Erase] Executing Full Chip Mass Erase (please wait 10 - 25s)...", "INFO")
                    if progress_callback:
                        progress_callback("Erasing Full Chip Flash (10-25s)...")
                    self.comm.write(b"\xFF\xFF\x00")
                else:
                    # Sector erase: erase only specific sectors
                    count = len(sectors) - 1
                    count_bytes = struct.pack(">H", count)
                    sector_bytes = bytearray()
                    for s in sectors:
                        sector_bytes.extend(struct.pack(">H", s))
                    chk = reduce(operator.xor, count_bytes)
                    chk = reduce(operator.xor, sector_bytes, chk)
                    
                    # Sector erase timeout: ~2-3s per sector
                    self.comm.timeout = max(15.0, len(sectors) * 4.0)
                    self.log(f"[Erase] Erasing only specified sector(s): {sectors} (preserving other sectors)...", "INFO")
                    if progress_callback:
                        progress_callback(f"Erasing sector(s) {sectors}...")
                    self.comm.write(count_bytes + sector_bytes + bytes([chk]))

                self._wait_ack("Executing Extended Erase")

            else:
                # Standard Erase (0x43) for STM32F1/F0/F3
                self.log("[Erase] Using Standard Erase command (0x43)...")
                self._send_command(self.CMD_ERASE, "Standard Erase")

                if global_erase or not sectors:
                    self.comm.timeout = 40.0
                    self.log("[Erase] Executing Full Chip Erase...", "INFO")
                    if progress_callback:
                        progress_callback("Erasing Full Chip Flash...")
                    self.comm.write(b"\xFF\x00")
                else:
                    count = len(sectors) - 1
                    page_bytes = bytearray(sectors)
                    chk = reduce(operator.xor, page_bytes, count)
                    self.comm.timeout = max(10.0, len(sectors) * 2.0)
                    self.log(f"[Erase] Erasing only specified page(s): {sectors}...", "INFO")
                    if progress_callback:
                        progress_callback(f"Erasing page(s) {sectors}...")
                    self.comm.write(bytes([count]) + page_bytes + bytes([chk]))

                self._wait_ack("Executing Standard Erase")

            self.log("[Erase] Flash erase completed successfully!", "SUCCESS")
            if progress_callback:
                progress_callback("Flash erase completed successfully!")
        finally:
            self.comm.timeout = prev_timeout

    def verify_memory(
        self,
        address: int,
        expected_data: bytes,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        cancel_token: Optional[Callable[[], bool]] = None,
    ) -> None:
        """Read back flash and verify against expected data byte-by-byte."""
        total_length = len(expected_data)
        read_data = self.read_memory_blocks(address, total_length, progress_callback, cancel_token)

        if read_data == expected_data:
            self.log("[Verify] Verification successful: Flash data matches reference 100%!", "SUCCESS")
            return

        # Find first mismatch
        for idx, (exp, act) in enumerate(zip(expected_data, read_data)):
            if exp != act:
                mismatch_addr = address + idx
                raise DataMismatchError(
                    f"Verification failed at address 0x{mismatch_addr:08X}: "
                    f"Expected 0x{exp:02X}, read 0x{act:02X}."
                )

    def go_to_address(self, address: int = 0x08000000) -> None:
        """Send GO command to jump to user code address."""
        self._send_command(self.CMD_GO, f"Go to 0x{address:08X}")
        self.comm.write(self._encode_address(address))
        self._wait_ack(f"Run program at 0x{address:08X}")
        self.log(f"[Go] Jumped to program address 0x{address:08X}!")

    def readout_unprotect(self) -> None:
        """Disable readout protection (will trigger chip mass erase and hardware reset)."""
        self._send_command(self.CMD_READOUT_UNPROTECT, "Readout Unprotect")
        self._wait_ack("Readout Unprotect")
        self.log("[Unprotect] Sent Readout Unprotect command. MCU is mass-erasing and resetting...")
        time.sleep(15.0)

    def detect_chip(self, specified_family: Optional[str] = None) -> DetectedChip:
        """
        Query chip ID, bootloader version, read Flash size and 96-bit UID.
        Auto-detects family (or uses specified family).
        """
        ver, cmds = self.get_supported_commands()
        chip_id = self.get_chip_id()
        chip_info = lookup_chip_info(chip_id)

        family = specified_family if specified_family and specified_family != "AUTO" else chip_info["family"]
        self.family = family

        fam_config = FAMILY_DEFAULTS.get(family, FAMILY_DEFAULTS["F4"])
        self.transfer_size = fam_config["transfer_size"]

        # Read Flash Size & UID
        flash_size_kb = chip_info.get("default_flash_kb", 512)
        uid_str = "N/A"

        try:
            flash_addr = fam_config["flash_size_address"]
            uid_addr = fam_config["uid_address"]

            if fam_config["special_f4_reading"]:
                # F4 & L0: Read 256 bytes from 256-byte aligned base
                data_base = uid_addr & 0xFFFFFF00
                data_block = self.read_memory(data_base, 256)
                
                flash_offset = flash_addr - data_base
                uid_offset = uid_addr - data_base

                size_val = data_block[flash_offset] | (data_block[flash_offset + 1] << 8)
                if 16 <= size_val <= 4096:
                    flash_size_kb = size_val

                uid_bytes = data_block[uid_offset : uid_offset + 12]
                uid_parts = [
                    f"{uid_bytes[1]:02X}{uid_bytes[0]:02X}",
                    f"{uid_bytes[3]:02X}{uid_bytes[2]:02X}",
                    f"{uid_bytes[7]:02X}{uid_bytes[6]:02X}{uid_bytes[5]:02X}{uid_bytes[4]:02X}",
                    f"{uid_bytes[11]:02X}{uid_bytes[10]:02X}{uid_bytes[9]:02X}{uid_bytes[8]:02X}",
                ]
                uid_str = "-".join(uid_parts)
            else:
                if flash_addr:
                    sz_data = self.read_memory(flash_addr, 2)
                    sz_val = sz_data[0] | (sz_data[1] << 8)
                    if 16 <= sz_val <= 4096:
                        flash_size_kb = sz_val
                if uid_addr:
                    uid_bytes = self.read_memory(uid_addr, 12)
                    uid_str = "-".join(f"{b:02X}" for b in uid_bytes)
        except Exception as e:
            self.log(f"[Info] UID/Flash register readout notice: {e}")

        ver_str = f"v{(ver >> 4) & 0x0F}.{ver & 0x0F}"

        return DetectedChip(
            chip_id=chip_id,
            name=chip_info["name"],
            family=family,
            description=chip_info["description"],
            bootloader_version=ver_str,
            flash_size_kb=flash_size_kb,
            uid_str=uid_str,
            has_extended_erase=self.has_extended_erase,
            supported_commands=self.supported_commands,
        )

