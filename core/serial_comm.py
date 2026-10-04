"""
Serial communication and Hardware Boot/Reset Pin Management.
Hardware Pin Assignment:
- RTS = BOOT (BOOT0 pin on STM32)
- DTR = nRESET (NRST pin on STM32)

Hardware Sequences:
- Enter Bootloader: Assert RTS (BOOT) => Pulse DTR (nRESET) 100ms => Release DTR (nRESET)
- Exit Bootloader : Deassert RTS (BOOT) => Pulse DTR (nRESET) 100ms => Release DTR (nRESET)
"""

import time
import serial
import serial.tools.list_ports


class SerialComm:
    """Manages the UART serial connection and pin toggling for STM32."""

    def __init__(self, port: str, baudrate: int = 115200, parity: str = "E", timeout: float = 3.0):
        self.port = port
        self.baudrate = baudrate
        self.parity = parity
        self._timeout = timeout
        self.ser: serial.Serial | None = None

    @property
    def timeout(self) -> float:
        """Get the current read timeout."""
        if self.ser and self.ser.is_open:
            return self.ser.timeout
        return self._timeout

    @timeout.setter
    def timeout(self, val: float):
        """Set read timeout both internally and on the underlying pyserial instance."""
        self._timeout = val
        if self.ser and self.ser.is_open:
            self.ser.timeout = val

    def connect(self):
        """Open the serial port."""
        if self.ser and self.ser.is_open:
            self.ser.close()

        # STM32 UART Bootloader is 8 data bits, Even parity, 1 stop bit (8E1)
        self.ser = serial.Serial(
            port=self.port,
            baudrate=self.baudrate,
            bytesize=serial.EIGHTBITS,
            parity=self.parity,
            stopbits=serial.STOPBITS_ONE,
            xonxoff=False,
            rtscts=False,
            timeout=self._timeout,
        )

    def disconnect(self):
        """Close the serial port."""
        if self.ser and self.ser.is_open:
            try:
                self.ser.close()
            except Exception:
                pass
        self.ser = None

    @property
    def is_connected(self) -> bool:
        return bool(self.ser and self.ser.is_open)

    def flush_input_buffer(self):
        """Flush stale bytes from input buffer."""
        if self.ser and self.ser.is_open:
            self.ser.reset_input_buffer()

    def write(self, data: bytes):
        """Write raw bytes to serial port."""
        if not self.ser or not self.ser.is_open:
            raise IOError("Serial port is not open.")
        return self.ser.write(data)

    def read(self, length: int = 1) -> bytes:
        """
        Read requested number of bytes, waiting until all bytes arrive or timeout occurs.
        Robustly handles Windows USB packet fragmentation (e.g. CP2102/CH340 64-byte packets).
        """
        if not self.ser or not self.ser.is_open:
            raise IOError("Serial port is not open.")

        result = bytearray()
        cur_timeout = self.timeout if self.timeout else 3.0
        deadline = time.time() + cur_timeout

        while len(result) < length:
            needed = length - len(result)
            chunk = self.ser.read(needed)
            if chunk:
                result.extend(chunk)
                # Keep active deadline alive while data is streaming in
                deadline = time.time() + cur_timeout
            else:
                if time.time() >= deadline:
                    break

        return bytes(result)

    def set_line(self, line_name: str, active: bool, invert: bool = False):
        """
        Set RTS or DTR line.
        :param line_name: 'RTS' (BOOT) or 'DTR' (nRESET)
        :param active: True to assert, False to deassert/release
        :param invert: True if active level is inverted by external circuitry
        """
        if not self.ser or not self.ser.is_open:
            return

        level = not active if invert else active
        if line_name.upper() == "RTS":
            self.ser.rts = level
        elif line_name.upper() == "DTR":
            self.ser.dtr = level

    def enter_boot_mode(
        self,
        boot_pin: str = "RTS",
        reset_pin: str = "DTR",
        invert_boot: bool = False,
        invert_reset: bool = False,
        pulse_ms: int = 100,
        log_callback=None,
    ):
        """
        Switch STM32 into Bootloader mode:
        Hold RTS (BOOT) => Pulse DTR (nRESET) 100ms => Release DTR (nRESET)
        """
        if log_callback:
            log_callback(f"[Hardware] Enter Boot: Assert {boot_pin} (BOOT) => Pulse {reset_pin} (nRESET) {pulse_ms}ms...")

        # 1. Assert RTS (BOOT = 1)
        self.set_line(boot_pin, active=True, invert=invert_boot)
        time.sleep(0.05)

        # 2. Assert DTR for pulse duration (pull nRESET active low)
        self.set_line(reset_pin, active=True, invert=invert_reset)
        time.sleep(pulse_ms / 1000.0)

        # 3. Release DTR (nRESET released so STM32 boots into bootloader)
        self.set_line(reset_pin, active=False, invert=invert_reset)
        
        # Wait for MCU oscillator & system bootloader initialization
        time.sleep(0.12)
        self.flush_input_buffer()

        if log_callback:
            log_callback(f"[Hardware] {boot_pin} (BOOT)=HIGH, {reset_pin} (nRESET)=RELEASED -> STM32 entered Bootloader.")

    def exit_boot_mode(
        self,
        boot_pin: str = "RTS",
        reset_pin: str = "DTR",
        invert_boot: bool = False,
        invert_reset: bool = False,
        pulse_ms: int = 100,
        log_callback=None,
    ):
        """
        Exit Bootloader and run user application:
        Release RTS (BOOT) => Pulse DTR (nRESET) 100ms => Release DTR (nRESET)
        """
        if log_callback:
            log_callback(f"[Hardware] Exit Boot: Release {boot_pin} (BOOT) => Pulse {reset_pin} (nRESET) {pulse_ms}ms...")

        # 1. Release RTS (BOOT = 0 to boot from User Flash)
        self.set_line(boot_pin, active=False, invert=invert_boot)
        time.sleep(0.05)

        # 2. Assert DTR for pulse duration (pulse nRESET)
        self.set_line(reset_pin, active=True, invert=invert_reset)
        time.sleep(pulse_ms / 1000.0)

        # 3. Release DTR (release nRESET)
        self.set_line(reset_pin, active=False, invert=invert_reset)
        
        time.sleep(0.1)

        if log_callback:
            log_callback(f"[Hardware] {boot_pin} (BOOT)=LOW, {reset_pin} (nRESET)=RELEASED -> STM32 running User Application.")

    def pulse_reset(
        self,
        reset_pin: str = "DTR",
        invert_reset: bool = False,
        pulse_ms: int = 100,
        log_callback=None,
    ):
        """Pulse the Reset line via DTR (nRESET)."""
        if log_callback:
            log_callback(f"[Hardware] Pulsing {reset_pin} (nRESET) {pulse_ms}ms...")
        self.set_line(reset_pin, active=True, invert=invert_reset)
        time.sleep(pulse_ms / 1000.0)
        self.set_line(reset_pin, active=False, invert=invert_reset)

    @staticmethod
    def list_ports():
        """
        List all available serial ports with description.
        Returns list of tuples: (port_device, display_label)
        """
        ports = serial.tools.list_ports.comports()
        result = []
        for p in ports:
            label = f"{p.device} - {p.description}"
            result.append((p.device, label))
        return sorted(result, key=lambda x: x[0])
