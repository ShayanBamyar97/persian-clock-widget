# -*- coding: utf-8 -*-
"""
تولیدکننده آیکون اختصاصی ساعت و تقویم فارسی (assets/icons/app_icon.ico و app_icon.png)
با کیفیت بالا و سایزهای استاندارد ویندوز (16 تا 256 پیکسل)
"""

import os
from PIL import Image, ImageDraw, ImageFont


def generate_persian_calendar_clock_icon(output_dir: str) -> str:
    os.makedirs(output_dir, exist_ok=True)
    size = 256
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 1. پس‌زمینه اصلی کارت تقویم (گرد و مدرن)
    draw.rounded_rectangle(
        (16, 28, 224, 236),
        radius=42,
        fill=(15, 23, 42, 255),
        outline=(56, 189, 248, 255),
        width=6,
    )

    # 2. هدر بالای تقویم
    draw.rounded_rectangle(
        (22, 34, 218, 92),
        radius=36,
        fill=(225, 29, 72, 255),
    )
    draw.rectangle((22, 68, 218, 92), fill=(225, 29, 72, 255))

    # 3. حلقه‌های بالای تقویم
    for x in (68, 120, 172):
        draw.rounded_rectangle(
            (x - 8, 16, x + 8, 48),
            radius=8,
            fill=(248, 250, 252, 255),
            outline=(15, 23, 42, 255),
            width=3,
        )

    # 4. نوشتن عدد فارسی در مرکز تقویم
    font_day = None
    for font_name in ["Tahoma", "Segoe UI", "Arial"]:
        try:
            font_day = ImageFont.truetype(f"{font_name}bd.ttf", 84)
            break
        except Exception:
            try:
                font_day = ImageFont.truetype(f"{font_name}.ttf", 84)
                break
            except Exception:
                continue

    if font_day is None:
        font_day = ImageFont.load_default()

    draw.ellipse((52, 56, 64, 68), fill=(255, 255, 255, 220))
    draw.ellipse((176, 56, 188, 68), fill=(255, 255, 255, 220))
    draw.rounded_rectangle((84, 58, 156, 66), radius=4, fill=(255, 255, 255, 230))

    persian_num = "۱۸"
    bbox = draw.textbbox((0, 0), persian_num, font=font_day)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    draw.text(
        (120 - tw // 2, 146 - th // 2 - 12),
        persian_num,
        fill=(248, 250, 252, 255),
        font=font_day,
    )

    # 5. دایره ساعت در گوشه پایین-راست
    cx, cy, r = 190, 190, 54
    draw.ellipse((cx - r - 4, cy - r - 4, cx + r + 4, cy + r + 4), fill=(15, 23, 42, 255))
    draw.ellipse(
        (cx - r, cy - r, cx + r, cy + r),
        fill=(14, 165, 233, 255),
        outline=(248, 250, 252, 255),
        width=6,
    )
    draw.ellipse((cx - r + 8, cy - r + 8, cx + r - 8, cy + r - 8), fill=(15, 23, 42, 255))

    draw.line((cx, cy, cx, cy - 26), fill=(56, 189, 248, 255), width=6)
    draw.line((cx, cy, cx + 24, cy + 10), fill=(251, 191, 36, 255), width=5)
    draw.ellipse((cx - 5, cy - 5, cx + 5, cy + 5), fill=(248, 250, 252, 255))

    ico_path = os.path.join(output_dir, "app_icon.ico")
    png_path = os.path.join(output_dir, "app_icon.png")

    img.save(png_path, format="PNG")
    img.save(
        ico_path,
        format="ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    return ico_path


if __name__ == "__main__":
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    icons_dir = os.path.join(root_dir, "assets", "icons")
    path = generate_persian_calendar_clock_icon(icons_dir)
    print("Generated icon:", path)
