"""
STM32 Chip Database: Chip IDs, Families, and Memory Characteristics.
Reference: ST RM0090, AN2606, AN3155, and stm32loader.
"""

CHIP_IDS = {
    # STM32F4
    0x413: {
        "name": "STM32F405xx/407xx & STM32F415xx/417xx (F405RGT6)",
        "family": "F4",
        "description": "High-performance ARM Cortex-M4 with FPU, 168MHz",
        "flash_base": 0x08000000,
        "default_flash_kb": 1024,
    },
    0x419: {
        "name": "STM32F42xxx & STM32F43xxx",
        "family": "F4",
        "description": "High-performance ARM Cortex-M4 with FPU, 180MHz",
        "flash_base": 0x08000000,
        "default_flash_kb": 2048,
    },
    0x423: {
        "name": "STM32F401xB/C",
        "family": "F4",
        "description": "ARM Cortex-M4 with FPU, 84MHz",
        "flash_base": 0x08000000,
        "default_flash_kb": 256,
    },
    0x433: {
        "name": "STM32F401xD/E",
        "family": "F4",
        "description": "ARM Cortex-M4 with FPU, 84MHz",
        "flash_base": 0x08000000,
        "default_flash_kb": 512,
    },
    0x441: {
        "name": "STM32F411xx",
        "family": "F4",
        "description": "ARM Cortex-M4 with FPU, 100MHz",
        "flash_base": 0x08000000,
        "default_flash_kb": 512,
    },
    0x421: {
        "name": "STM32F446xx",
        "family": "F4",
        "description": "ARM Cortex-M4 with FPU, 180MHz",
        "flash_base": 0x08000000,
        "default_flash_kb": 512,
    },
    0x434: {
        "name": "STM32F469xx/479xx",
        "family": "F4",
        "description": "ARM Cortex-M4 with FPU, 180MHz",
        "flash_base": 0x08000000,
        "default_flash_kb": 2048,
    },
    0x458: {
        "name": "STM32F410xx",
        "family": "F4",
        "description": "ARM Cortex-M4 with FPU, 100MHz",
        "flash_base": 0x08000000,
        "default_flash_kb": 128,
    },
    0x463: {
        "name": "STM32F413xx/423xx",
        "family": "F4",
        "description": "ARM Cortex-M4 with FPU, 100MHz",
        "flash_base": 0x08000000,
        "default_flash_kb": 1536,
    },

    # STM32F1
    0x412: {
        "name": "STM32F10x Low-density",
        "family": "F1",
        "description": "ARM Cortex-M3, 16-32KB Flash",
        "flash_base": 0x08000000,
        "default_flash_kb": 32,
    },
    0x410: {
        "name": "STM32F10x Medium-density (F103C8T6...)",
        "family": "F1",
        "description": "ARM Cortex-M3, 64-128KB Flash",
        "flash_base": 0x08000000,
        "default_flash_kb": 64,
    },
    0x414: {
        "name": "STM32F10x High-density (F103RCT6...)",
        "family": "F1",
        "description": "ARM Cortex-M3, 256-512KB Flash",
        "flash_base": 0x08000000,
        "default_flash_kb": 512,
    },
    0x420: {
        "name": "STM32F10x Medium-density value line",
        "family": "F1",
        "description": "ARM Cortex-M3 value line",
        "flash_base": 0x08000000,
        "default_flash_kb": 128,
    },
    0x428: {
        "name": "STM32F10x High-density value line",
        "family": "F1",
        "description": "ARM Cortex-M3 value line",
        "flash_base": 0x08000000,
        "default_flash_kb": 512,
    },
    0x430: {
        "name": "STM32F10x XL-density",
        "family": "F1",
        "description": "ARM Cortex-M3, 768-1024KB Flash",
        "flash_base": 0x08000000,
        "default_flash_kb": 1024,
    },
    0x418: {
        "name": "STM32F105/107 Connectivity line",
        "family": "F1",
        "description": "ARM Cortex-M3 with USB OTG/Ethernet",
        "flash_base": 0x08000000,
        "default_flash_kb": 256,
    },

    # STM32F0
    0x444: {"name": "STM32F03xx4/6", "family": "F0", "description": "ARM Cortex-M0", "flash_base": 0x08000000, "default_flash_kb": 32},
    0x440: {"name": "STM32F030x8 / F05xxx", "family": "F0", "description": "ARM Cortex-M0", "flash_base": 0x08000000, "default_flash_kb": 64},
    0x445: {"name": "STM32F070x6 / F04xxx", "family": "F0", "description": "ARM Cortex-M0", "flash_base": 0x08000000, "default_flash_kb": 32},
    0x448: {"name": "STM32F070xB / F072xx", "family": "F0", "description": "ARM Cortex-M0", "flash_base": 0x08000000, "default_flash_kb": 128},
    0x442: {"name": "STM32F030xC / F09xxx", "family": "F0", "description": "ARM Cortex-M0", "flash_base": 0x08000000, "default_flash_kb": 256},

    # STM32F3
    0x422: {"name": "STM32F302xB(C)/303xB(C)/358xx", "family": "F3", "description": "ARM Cortex-M4", "flash_base": 0x08000000, "default_flash_kb": 256},
    0x432: {"name": "STM32F373xx/378xx", "family": "F3", "description": "ARM Cortex-M4", "flash_base": 0x08000000, "default_flash_kb": 256},
    0x438: {"name": "STM32F303x4(6/8)/334xx/328xx", "family": "F3", "description": "ARM Cortex-M4", "flash_base": 0x08000000, "default_flash_kb": 64},
    0x439: {"name": "STM32F301xx/302x4(6/8)/318xx", "family": "F3", "description": "ARM Cortex-M4", "flash_base": 0x08000000, "default_flash_kb": 64},
    0x446: {"name": "STM32F302xD(E)/303xD(E)/398xx", "family": "F3", "description": "ARM Cortex-M4", "flash_base": 0x08000000, "default_flash_kb": 512},

    # STM32F7
    0x452: {"name": "STM32F72xxx/73xxx", "family": "F7", "description": "ARM Cortex-M7", "flash_base": 0x08000000, "default_flash_kb": 512},
    0x449: {"name": "STM32F74xxx/75xxx", "family": "F7", "description": "ARM Cortex-M7", "flash_base": 0x08000000, "default_flash_kb": 1024},
    0x451: {"name": "STM32F76xxx/77xxx", "family": "F7", "description": "ARM Cortex-M7", "flash_base": 0x08000000, "default_flash_kb": 2048},

    # STM32H7
    0x450: {"name": "STM32H74xxx/75xxx", "family": "H7", "description": "ARM Cortex-M7, up to 480MHz", "flash_base": 0x08000000, "default_flash_kb": 2048},
    0x480: {"name": "STM32H7A3xx/B3xx", "family": "H7", "description": "ARM Cortex-M7, up to 280MHz", "flash_base": 0x08000000, "default_flash_kb": 2048},
    0x483: {"name": "STM32H72xxx/73xxx", "family": "H7", "description": "ARM Cortex-M7, up to 550MHz", "flash_base": 0x08000000, "default_flash_kb": 1024},

    # STM32L4
    0x415: {"name": "STM32L475xx/476xx/486xx", "family": "L4", "description": "Ultra-low-power ARM Cortex-M4", "flash_base": 0x08000000, "default_flash_kb": 1024},
    0x435: {"name": "STM32L43xxx/44xxx", "family": "L4", "description": "Ultra-low-power ARM Cortex-M4", "flash_base": 0x08000000, "default_flash_kb": 256},
    0x462: {"name": "STM32L45xxx/46xxx", "family": "L4", "description": "Ultra-low-power ARM Cortex-M4", "flash_base": 0x08000000, "default_flash_kb": 512},
    0x464: {"name": "STM32L41xxx/42xxx", "family": "L4", "description": "Ultra-low-power ARM Cortex-M4", "flash_base": 0x08000000, "default_flash_kb": 128},
    0x470: {"name": "STM32L4Rxxx/4Sxxx", "family": "L4", "description": "Ultra-low-power ARM Cortex-M4", "flash_base": 0x08000000, "default_flash_kb": 2048},

    # STM32G0 / G4
    0x460: {"name": "STM32G0x1", "family": "G0", "description": "ARM Cortex-M0+ 64MHz", "flash_base": 0x08000000, "default_flash_kb": 128},
    0x466: {"name": "STM32G0x0", "family": "G0", "description": "ARM Cortex-M0+ 64MHz", "flash_base": 0x08000000, "default_flash_kb": 64},
    0x468: {"name": "STM32G43x/44x", "family": "F3", "description": "ARM Cortex-M4 170MHz", "flash_base": 0x08000000, "default_flash_kb": 128},
    0x469: {"name": "STM32G47x/48x", "family": "F3", "description": "ARM Cortex-M4 170MHz", "flash_base": 0x08000000, "default_flash_kb": 512},
}

FAMILY_DEFAULTS = {
    "F4": {
        "flash_page_size": 1024,
        "transfer_size": 256,
        "flash_size_address": 0x1FFF7A22,
        "uid_address": 0x1FFF7A10,
        "special_f4_reading": True,
    },
    "F1": {
        "flash_page_size": 1024,
        "transfer_size": 256,
        "flash_size_address": 0x1FFFF7E0,
        "uid_address": 0x1FFFF7E8,
        "special_f4_reading": False,
    },
    "F0": {
        "flash_page_size": 1024,
        "transfer_size": 256,
        "flash_size_address": 0x1FFFF7CC,
        "uid_address": None,
        "special_f4_reading": False,
    },
    "F3": {
        "flash_page_size": 2048,
        "transfer_size": 256,
        "flash_size_address": 0x1FFFF7CC,
        "uid_address": 0x1FFFF7AC,
        "special_f4_reading": False,
    },
    "F7": {
        "flash_page_size": 1024,
        "transfer_size": 256,
        "flash_size_address": 0x1FF0F442,
        "uid_address": 0x1FF0F420,
        "special_f4_reading": False,
    },
    "H7": {
        "flash_page_size": 128 * 1024,
        "transfer_size": 256,
        "flash_size_address": 0x1FF1E880,
        "uid_address": 0x1FF1E800,
        "special_f4_reading": False,
    },
    "L4": {
        "flash_page_size": 1024,
        "flash_page_size": 2048,
        "transfer_size": 256,
        "flash_size_address": 0x1FFF75E0,
        "uid_address": 0x1FFF7590,
        "special_f4_reading": False,
    },
    "L0": {
        "flash_page_size": 128,
        "transfer_size": 128,
        "flash_size_address": 0x1FF8007C,
        "uid_address": 0x1FF80050,
        "special_f4_reading": True,
    },
    "G0": {
        "flash_page_size": 1024,
        "flash_page_size": 2048,
        "transfer_size": 256,
        "flash_size_address": 0x1FFF75E0,
        "uid_address": 0x1FFF7590,
        "special_f4_reading": False,
    },
}


def lookup_chip_info(chip_id: int):
    """Return dictionary of chip info or default unknown dictionary."""
    if chip_id in CHIP_IDS:
        return CHIP_IDS[chip_id]
    return {
        "name": f"Unknown STM32 (ID: 0x{chip_id:03X})",
        "family": "F4",
        "description": "Standard STM32 device",
        "flash_base": 0x08000000,
        "default_flash_kb": 512,
    }


STM32F4_SECTOR_MAP = [
    # (sector_num, start_addr, size_bytes)
    (0, 0x08000000, 16 * 1024),
    (1, 0x08004000, 16 * 1024),
    (2, 0x08008000, 16 * 1024),
    (3, 0x0800C000, 16 * 1024),
    (4, 0x08010000, 64 * 1024),
    (5, 0x08020000, 128 * 1024),
    (6, 0x08040000, 128 * 1024),
    (7, 0x08060000, 128 * 1024),
    (8, 0x08080000, 128 * 1024),
    (9, 0x080A0000, 128 * 1024),
    (10, 0x080C0000, 128 * 1024),
    (11, 0x080E0000, 128 * 1024),
    # Dual-bank 2MB devices
    (12, 0x08100000, 16 * 1024),
    (13, 0x08104000, 16 * 1024),
    (14, 0x08108000, 16 * 1024),
    (15, 0x0810C000, 16 * 1024),
    (16, 0x08110000, 64 * 1024),
    (17, 0x08120000, 128 * 1024),
    (18, 0x08140000, 128 * 1024),
    (19, 0x08160000, 128 * 1024),
    (20, 0x08180000, 128 * 1024),
    (21, 0x081A0000, 128 * 1024),
    (22, 0x081C0000, 128 * 1024),
    (23, 0x081E0000, 128 * 1024),
]

STM32F7_SECTOR_MAP = [
    # STM32F7 single bank: 4x32KB, 1x128KB, 3x256KB
    (0, 0x08000000, 32 * 1024),
    (1, 0x08008000, 32 * 1024),
    (2, 0x08010000, 32 * 1024),
    (3, 0x08018000, 32 * 1024),
    (4, 0x08020000, 128 * 1024),
    (5, 0x08040000, 256 * 1024),
    (6, 0x08080000, 256 * 1024),
    (7, 0x080C0000, 256 * 1024),
]


def get_affected_sectors(family: str, start_addr: int, length: int) -> tuple[list[int], str]:
    """
    Calculate which sectors or pages need to be erased for a given address range.
    Returns (list_of_sector_or_page_indices, human_readable_description).
    """
    if length <= 0:
        return [0], "Sector 0 (0 bytes)"

    end_addr = start_addr + length - 1

    # Sector-based STM32 devices (F4, F2, F7)
    if family in ("F4", "F2"):
        sector_map = STM32F4_SECTOR_MAP
    elif family == "F7":
        sector_map = STM32F7_SECTOR_MAP
    else:
        sector_map = None

    if sector_map:
        affected = []
        for sec_num, sec_start, sec_size in sector_map:
            sec_end = sec_start + sec_size - 1
            if max(start_addr, sec_start) <= min(end_addr, sec_end):
                affected.append(sec_num)

        if not affected:
            # Fallback if start_addr is outside standard mapping (e.g. higher bank)
            affected = [0]

        desc = f"Sector{'s' if len(affected) > 1 else ''} {affected} (0x{start_addr:08X} - 0x{end_addr:08X}, {len(affected)} sector{'s' if len(affected) > 1 else ''})"
        return affected, desc

    # Uniform page-based MCU (F1, F0, F3, L4, G0, L0, H7, etc.)
    page_size = FAMILY_DEFAULTS.get(family, {}).get("flash_page_size", 1024)
    base = 0x08000000
    p_start = max(0, (start_addr - base) // page_size)
    p_end = max(0, (end_addr - base) // page_size)
    affected = list(range(p_start, p_end + 1))
    desc = f"Page{'s' if len(affected) > 1 else ''} {p_start}..{p_end} ({len(affected)} page{'s' if len(affected) > 1 else ''}, {page_size}B each)"
    return affected, desc

