"""
Dynamic Application Icon Generator.
Draws a high-resolution, professional STM32 microcontroller chip icon with an electric flash emblem
entirely via code (Pillow / ImageDraw) without requiring any external .ico file.
Applies the icon seamlessly to both the Window Titlebar and the Windows Taskbar.
"""

import os
import sys
import ctypes
import tempfile
from PIL import Image, ImageDraw, ImageFont, ImageTk


def generate_stm32_chip_image(size: int = 256) -> Image.Image:
    """
    Draw a clean, modern STM32 MCU chip icon with metal leads and glowing cyan flash emblem.
    Optimized dynamically for both tiny (16x16 / 32x32) and large (64x64 / 256x256) displays.
    """
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(im)
    s = size / 256.0

    # 1. Pins (5 metallic leads per side, centered)
    body_min = int(44 * s)
    body_max = int(212 * s)
    pin_len = max(2, int(22 * s))
    pin_w = max(1, int(10 * s))
    pin_color = (210, 222, 238, 255)
    pin_tip = (245, 250, 255, 255)

    pin_positions = [int(body_min + (body_max - body_min) * (i / 6.0)) for i in range(1, 6)]

    for pos in pin_positions:
        # Top
        draw.rectangle([pos - pin_w // 2, body_min - pin_len, pos + pin_w // 2, body_min], fill=pin_color)
        draw.rectangle([pos - pin_w // 2, body_min - pin_len, pos + pin_w // 2, body_min - pin_len + max(1, int(4 * s))], fill=pin_tip)
        # Bottom
        draw.rectangle([pos - pin_w // 2, body_max, pos + pin_w // 2, body_max + pin_len], fill=pin_color)
        draw.rectangle([pos - pin_w // 2, body_max + pin_len - max(1, int(4 * s)), pos + pin_w // 2, body_max + pin_len], fill=pin_tip)
        # Left
        draw.rectangle([body_min - pin_len, pos - pin_w // 2, body_min, pos + pin_w // 2], fill=pin_color)
        draw.rectangle([body_min - pin_len, pos - pin_w // 2, body_min - pin_len + max(1, int(4 * s)), pos + pin_w // 2], fill=pin_tip)
        # Right
        draw.rectangle([body_max, pos - pin_w // 2, body_max + pin_len, pos + pin_w // 2], fill=pin_color)
        draw.rectangle([body_max + pin_len - max(1, int(4 * s)), pos - pin_w // 2, body_max + pin_len, pos + pin_w // 2], fill=pin_tip)

    # 2. Chip Body (Matte charcoal with beveled border)
    radius = max(2, int(20 * s))
    chip_rect = [body_min, body_min, body_max, body_max]
    draw.rounded_rectangle(
        chip_rect,
        radius=radius,
        fill=(20, 24, 32, 255),
        outline=(75, 88, 108, 255),
        width=max(1, int(4 * s)),
    )

    # Inner beveled chamfer & Pin 1 dot
    if size >= 32:
        inset = max(1, int(7 * s))
        draw.rounded_rectangle(
            [body_min + inset, body_min + inset, body_max - inset, body_max - inset],
            radius=max(1, radius - inset // 2),
            outline=(38, 46, 60, 255),
            width=max(1, int(2 * s)),
        )

        # Pin 1 orientation dot (top-left)
        dot_c = (body_min + int(18 * s), body_min + int(18 * s))
        dot_r = max(2, int(6 * s))
        draw.ellipse(
            [dot_c[0] - dot_r, dot_c[1] - dot_r, dot_c[0] + dot_r, dot_c[1] + dot_r],
            fill=(45, 55, 72, 255),
            outline=(100, 120, 145, 255),
            width=max(1, int(2 * s)),
        )

    # 3. Flash Lightning Bolt in center
    if size < 64:
        # High-contrast, larger centered bolt for small taskbar/titlebar icons
        bolt = [
            (145 * s, 55 * s),
            (95 * s, 135 * s),
            (125 * s, 135 * s),
            (110 * s, 205 * s),
            (165 * s, 125 * s),
            (135 * s, 125 * s),
        ]
        draw.polygon(bolt, fill=(0, 225, 255, 255))
        core = [
            (143 * s, 65 * s),
            (105 * s, 133 * s),
            (127 * s, 133 * s),
            (120 * s, 175 * s),
            (155 * s, 127 * s),
            (137 * s, 127 * s),
        ]
        draw.polygon(core, fill=(230, 250, 255, 255))
    else:
        # Detailed bolt with cyan glow and engraved 'STM32' text
        bolt = [
            (138 * s, 58 * s),
            (100 * s, 122 * s),
            (125 * s, 122 * s),
            (114 * s, 175 * s),
            (156 * s, 114 * s),
            (131 * s, 114 * s),
        ]
        glow = [
            (138 * s, 54 * s),
            (94 * s, 124 * s),
            (122 * s, 124 * s),
            (110 * s, 180 * s),
            (162 * s, 112 * s),
            (133 * s, 112 * s),
        ]
        draw.polygon(glow, fill=(0, 210, 255, 80))
        draw.polygon(bolt, fill=(0, 225, 255, 255))

        core = [
            (135 * s, 66 * s),
            (108 * s, 118 * s),
            (127 * s, 118 * s),
            (120 * s, 148 * s),
            (146 * s, 116 * s),
            (133 * s, 116 * s),
        ]
        draw.polygon(core, fill=(230, 250, 255, 255))

        # 4. Text 'STM32' engraved in bright metallic white/silver
        try:
            font = ImageFont.truetype("segoeui.ttf", int(24 * s))
        except Exception:
            try:
                font = ImageFont.truetype("arial.ttf", int(24 * s))
            except Exception:
                font = ImageFont.load_default()

        bbox = draw.textbbox((0, 0), "STM32", font=font)
        tw = bbox[2] - bbox[0]
        draw.text(((size - tw) // 2, int(178 * s)), "STM32", fill=(235, 242, 250, 240), font=font)

    return im


def apply_app_icon(root) -> list:
    """
    Generate and apply custom STM32 icon to both Window Titlebar and Windows Taskbar.
    Returns the list of PhotoImage references to prevent Python garbage collection.
    """
    # 1. Set explicit Windows AppUserModelID so Taskbar uses our custom window icon
    if sys.platform == "win32":
        try:
            app_id = "antigravity.stm32.uart.flasher.app.2.0"
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
        except Exception:
            pass

    # 2. Generate multi-resolution images
    sizes = [16, 24, 32, 48, 64, 128, 256]
    images_by_size = {sz: generate_stm32_chip_image(sz) for sz in sizes}

    photo_images = []
    for sz in sizes:
        photo = ImageTk.PhotoImage(images_by_size[sz])
        photo_images.append(photo)

    try:
        # iconphoto(True, ...) applies to root and all future toplevel dialogs
        root.iconphoto(True, *photo_images)
    except Exception:
        pass

    # 3. For native Windows taskbar & shell crispness, save multi-res ICO to temp directory
    temp_ico_path = None
    if sys.platform == "win32":
        try:
            temp_ico_path = os.path.join(tempfile.gettempdir(), "stm32_flasher_app_icon.ico")
            # Save master 256 image with multi-res sub-images
            ico_sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
            images_by_size[256].save(temp_ico_path, format="ICO", sizes=ico_sizes)
            root.iconbitmap(temp_ico_path)
            root.iconbitmap(default=temp_ico_path)
        except Exception:
            pass

    # 4. Direct Win32 WM_SETICON injection to ensure Taskbar button updates immediately
    def _apply_win32_wm_seticon():
        if sys.platform == "win32" and temp_ico_path and os.path.exists(temp_ico_path):
            try:
                # WM_SETICON = 0x0080, ICON_SMALL = 0, ICON_BIG = 1
                # IMAGE_ICON = 1, LR_LOADFROMFILE = 0x0010, LR_DEFAULTSIZE = 0x0040
                hicon_big = ctypes.windll.user32.LoadImageW(
                    0, temp_ico_path, 1, 0, 0, 0x0010 | 0x0040
                )
                hicon_small = ctypes.windll.user32.LoadImageW(
                    0, temp_ico_path, 1, 16, 16, 0x0010
                )
                hwnd = root.winfo_id()
                if hwnd:
                    ctypes.windll.user32.SendMessageW(hwnd, 0x0080, 1, hicon_big)
                    ctypes.windll.user32.SendMessageW(hwnd, 0x0080, 0, hicon_small)
            except Exception:
                pass

    _apply_win32_wm_seticon()
    # Re-trigger after window mapping to guarantee Windows Taskbar picks up the icon
    root.after(150, _apply_win32_wm_seticon)

    return photo_images


def ensure_app_icon_ico(target_path: str = "app_icon.ico") -> str:
    """
    Ensure that a multi-resolution .ico file exists on disk.
    If it doesn't exist, it is generated dynamically from code.
    """
    if not os.path.exists(target_path):
        img = generate_stm32_chip_image(256)
        ico_sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
        img.save(target_path, format="ICO", sizes=ico_sizes)
    return target_path

