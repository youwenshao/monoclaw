"""QR code and A4 bilingual sign generation for customer queue joining."""

from __future__ import annotations

from pathlib import Path

import qrcode
from PIL import Image, ImageDraw, ImageFont

A4_WIDTH = 2480
A4_HEIGHT = 3508


def _load_fonts(
    title_size: int = 120,
    body_size: int = 72,
    small_size: int = 48,
) -> tuple[ImageFont.FreeTypeFont | ImageFont.ImageFont, ...]:
    """Best-effort font loading with multiple fallback paths."""
    candidates = [
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ]
    for path in candidates:
        try:
            return (
                ImageFont.truetype(path, title_size),
                ImageFont.truetype(path, body_size),
                ImageFont.truetype(path, small_size),
            )
        except (OSError, IOError):
            continue
    default = ImageFont.load_default()
    return default, default, default


def generate_qr(base_url: str, output_path: str | Path) -> Path:
    """Generate a QR code image pointing to /queue-bot/join."""
    url = f"{base_url.rstrip('/')}/queue-bot/join"
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(out))
    return out


def generate_sign(
    base_url: str,
    restaurant_name: str,
    output_path: str | Path,
) -> Path:
    """Generate an A4-sized bilingual sign with QR code and instructions.

    The sign includes the restaurant name, a scannable QR code, and
    step-by-step instructions in Chinese and English.
    """
    bg_color = (255, 255, 255)
    text_color = (33, 33, 33)
    accent_color = (212, 168, 67)
    muted_color = (128, 128, 128)

    img = Image.new("RGB", (A4_WIDTH, A4_HEIGHT), bg_color)
    draw = ImageDraw.Draw(img)
    title_font, body_font, small_font = _load_fonts()

    y = 200

    draw.text(
        (A4_WIDTH // 2, y), restaurant_name,
        fill=accent_color, font=title_font, anchor="mt",
    )
    y += 200

    draw.line([(300, y), (A4_WIDTH - 300, y)], fill=accent_color, width=4)
    y += 80

    for line in ["掃描 QR Code 加入排隊", "Scan QR Code to Join Queue"]:
        draw.text(
            (A4_WIDTH // 2, y), line,
            fill=text_color, font=body_font, anchor="mt",
        )
        y += 120

    y += 60

    url = f"{base_url.rstrip('/')}/queue-bot/join"
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=20,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    qr_size = min(1200, A4_WIDTH - 600)
    qr_img = qr_img.resize((qr_size, qr_size), Image.LANCZOS)
    img.paste(qr_img, ((A4_WIDTH - qr_size) // 2, y))
    y += qr_size + 80

    steps = [
        ("1. 掃描二維碼", "1. Scan QR code"),
        ("2. 填寫人數及電話", "2. Enter party size & phone"),
        ("3. 等候通知入座", "3. Wait for notification"),
    ]
    for zh, en in steps:
        draw.text(
            (A4_WIDTH // 2, y), zh,
            fill=text_color, font=small_font, anchor="mt",
        )
        y += 70
        draw.text(
            (A4_WIDTH // 2, y), en,
            fill=muted_color, font=small_font, anchor="mt",
        )
        y += 90

    draw.text(
        (A4_WIDTH // 2, A4_HEIGHT - 200), url,
        fill=(160, 160, 160), font=small_font, anchor="mt",
    )

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(out), quality=95)
    return out
