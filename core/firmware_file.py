"""
Firmware file loader supporting both Intel HEX (.hex) and raw Binary (.bin).
Pure Python standard library implementation (zero external dependencies).
Extracts addresses, sizes, fills gaps with 0xFF, and calculates integrity checksums.
"""

from dataclasses import dataclass
from pathlib import Path
import binascii
import hashlib


@dataclass
class FirmwareInfo:
    filepath: str
    filename: str
    file_type: str  # 'HEX' or 'BIN'
    data: bytes
    size_bytes: int
    start_address: int
    end_address: int
    crc32_str: str
    md5_str: str

    @property
    def size_kb(self) -> float:
        return self.size_bytes / 1024.0


def _parse_intel_hex(file_path: Path) -> tuple[int, int, bytes]:
    """
    Parse an Intel HEX (.hex) file using pure Python standard library.
    Returns (start_address, end_address, binary_data_with_0xFF_gaps).
    """
    segments: list[tuple[int, bytes]] = []
    upper_addr = 0
    min_addr: int | None = None
    max_addr: int | None = None

    with open(file_path, "r", encoding="ascii", errors="ignore") as f:
        for line_num, raw_line in enumerate(f, 1):
            line = raw_line.strip()
            if not line:
                continue
            if not line.startswith(":"):
                raise ValueError(f"Invalid Intel HEX record at line {line_num}: missing ':' prefix.")

            raw_bytes = bytes.fromhex(line[1:])
            if len(raw_bytes) < 5:
                raise ValueError(f"Truncated Intel HEX record at line {line_num}.")

            byte_count = raw_bytes[0]
            addr_offset = (raw_bytes[1] << 8) | raw_bytes[2]
            record_type = raw_bytes[3]
            if len(raw_bytes) != byte_count + 5:
                raise ValueError(f"Byte count mismatch in Intel HEX at line {line_num}.")

            if (sum(raw_bytes) & 0xFF) != 0:
                raise ValueError(f"Checksum error in Intel HEX at line {line_num}.")

            payload = raw_bytes[4 : 4 + byte_count]

            if record_type == 0x00:  # Data Record
                if byte_count > 0:
                    abs_addr = upper_addr + addr_offset
                    segments.append((abs_addr, payload))
                    seg_end = abs_addr + byte_count - 1
                    if min_addr is None or abs_addr < min_addr:
                        min_addr = abs_addr
                    if max_addr is None or seg_end > max_addr:
                        max_addr = seg_end
            elif record_type == 0x01:  # End of File
                break
            elif record_type == 0x02:  # Extended Segment Address
                if byte_count != 2:
                    raise ValueError(f"Invalid Extended Segment Address record at line {line_num}.")
                upper_addr = ((payload[0] << 8) | payload[1]) << 4
            elif record_type == 0x04:  # Extended Linear Address
                if byte_count != 2:
                    raise ValueError(f"Invalid Extended Linear Address record at line {line_num}.")
                upper_addr = ((payload[0] << 8) | payload[1]) << 16
            elif record_type in (0x03, 0x05):  # Start Segment / Linear Address
                continue

    if min_addr is None or max_addr is None or min_addr > max_addr:
        raise ValueError("Intel HEX file does not contain valid memory data.")

    total_len = max_addr - min_addr + 1
    buf = bytearray(b"\xFF" * total_len)
    for seg_addr, seg_data in segments:
        offset = seg_addr - min_addr
        buf[offset : offset + len(seg_data)] = seg_data

    return min_addr, max_addr, bytes(buf)


def load_firmware(file_path: str, default_bin_address: int = 0x08000000) -> FirmwareInfo:
    """
    Load a firmware file (.hex or .bin).

    :param file_path: Path to the firmware file.
    :param default_bin_address: Base flash address to use for .bin files (default 0x08000000).
    :return: FirmwareInfo object.
    """
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"File not found: {file_path}")

    ext = path.suffix.lower()

    if ext == ".hex":
        start_addr, end_addr, data = _parse_intel_hex(path)
        file_type = "HEX"
    elif ext in (".bin", ".raw"):
        data = path.read_bytes()
        start_addr = default_bin_address
        end_addr = start_addr + len(data) - 1 if data else start_addr
        file_type = "BIN"
    else:
        with open(path, "rb") as f:
            header = f.read(16)
        if header.startswith(b":"):
            start_addr, end_addr, data = _parse_intel_hex(path)
            file_type = "HEX"
        else:
            data = path.read_bytes()
            start_addr = default_bin_address
            end_addr = start_addr + len(data) - 1 if data else start_addr
            file_type = "BIN"

    if not data:
        raise ValueError("Firmware file is empty.")

    crc = binascii.crc32(data) & 0xFFFFFFFF
    crc_str = f"0x{crc:08X}"
    md5_str = hashlib.md5(data).hexdigest()

    return FirmwareInfo(
        filepath=str(path.resolve()),
        filename=path.name,
        file_type=file_type,
        data=data,
        size_bytes=len(data),
        start_address=start_addr,
        end_address=end_addr,
        crc32_str=crc_str,
        md5_str=md5_str,
    )
