"""
Firmware file loader supporting both Intel HEX (.hex) and raw Binary (.bin).
Extracts addresses, sizes, fills gaps, and calculates integrity checksums.
"""

from dataclasses import dataclass
from pathlib import Path
import binascii
import hashlib

try:
    from intelhex import IntelHex
except ImportError:
    IntelHex = None


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
        if IntelHex is None:
            raise ImportError("Package 'intelhex' is required to load .hex files. Install it via 'pip install intelhex'.")
        
        ih = IntelHex()
        ih.loadhex(str(path))
        
        start_addr = ih.minaddr()
        end_addr = ih.maxaddr()
        
        if start_addr is None or end_addr is None or start_addr > end_addr:
            raise ValueError("Intel Hex file does not contain valid memory data.")
        
        # Extract binary stream filling any sparse gap with 0xFF (erased flash state)
        data = ih.tobinstr(start=start_addr, end=end_addr)
        file_type = "HEX"

    elif ext in (".bin", ".raw"):
        data = path.read_bytes()
        start_addr = default_bin_address
        end_addr = start_addr + len(data) - 1 if data else start_addr
        file_type = "BIN"

    else:
        # Default fallback: try to detect if it's text (HEX) or raw binary
        with open(path, "rb") as f:
            header = f.read(16)
        if header.startswith(b":") and IntelHex is not None:
            ih = IntelHex()
            ih.loadhex(str(path))
            start_addr = ih.minaddr()
            end_addr = ih.maxaddr()
            data = ih.tobinstr(start=start_addr, end=end_addr)
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
