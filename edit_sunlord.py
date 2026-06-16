#!/usr/bin/env python3
"""Edit 顺络电子 row on the original holdings screenshot."""

from PIL import Image, ImageDraw, ImageFont
import sys
import os

# Colors from Chinese stock apps
RED = (230, 67, 64)      # profit
GRAY = (153, 153, 153)   # secondary text
BLACK = (51, 51, 51)     # primary text
WHITE = (255, 255, 255)

# Edits for 顺络电子 row (3rd stock row)
EDITS = [
    # (x, y, width, height, text, color, align)
    # Column 1: market value under stock name
    {"box": (0.52, 0.585, 0.46, 0.018), "text": "233,142.00", "color": BLACK, "align": "right"},
    # Column 2: P/L and rate
    {"box": (0.52, 0.565, 0.22, 0.018), "text": "+15,756.00", "color": RED, "align": "right"},
    {"box": (0.52, 0.585, 0.22, 0.018), "text": "7.25%", "color": GRAY, "align": "right"},
    # Column 3: holdings/available
    {"box": (0.68, 0.565, 0.14, 0.018), "text": "3900", "color": BLACK, "align": "right"},
    {"box": (0.68, 0.585, 0.14, 0.018), "text": "3900", "color": BLACK, "align": "right"},
    # Column 4: cost/current price
    {"box": (0.78, 0.565, 0.20, 0.018), "text": "55.74", "color": BLACK, "align": "right"},
    {"box": (0.78, 0.585, 0.20, 0.018), "text": "59.78", "color": BLACK, "align": "right"},
]


def get_font(size):
    candidates = [
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/opt/cursor/ansible/files/fonts/PublicSans-Regular.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def cover_and_draw(draw, img_w, img_h, box_frac, text, color, align, font):
    x1 = int(box_frac[0] * img_w)
    y1 = int(box_frac[1] * img_h)
    x2 = int((box_frac[0] + box_frac[2]) * img_w)
    y2 = int((box_frac[1] + box_frac[3]) * img_h)

    # Sample background color from left edge of box
    sample_x = max(0, x1 - 5)
    sample_y = (y1 + y2) // 2
  # extend cover slightly
    pad = 4
    draw.rectangle([x1 - pad, y1 - 2, x2 + pad, y2 + 2], fill=WHITE)

    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]

    if align == "right":
        tx = x2 - tw
    else:
        tx = x1
    ty = y1 + (y2 - y1 - th) // 2 - bbox[1]
    draw.text((tx, ty), text, fill=color, font=font)


def edit_image(input_path, output_path):
    img = Image.open(input_path).convert("RGB")
    w, h = img.size
    draw = ImageDraw.Draw(img)

    # Font size relative to image height
    font_size = max(18, int(h * 0.014))
    font = get_font(font_size)

    for edit in EDITS:
        cover_and_draw(
            draw, w, h,
            edit["box"], edit["text"], edit["color"], edit["align"], font
        )

    img.save(output_path, quality=95)
    print(f"Saved: {output_path} ({w}x{h})")


if __name__ == "__main__":
    inp = sys.argv[1] if len(sys.argv) > 1 else "original.png"
    out = sys.argv[2] if len(sys.argv) > 2 else "holdings_modified.png"
    if not os.path.exists(inp):
        print(f"Error: {inp} not found", file=sys.stderr)
        sys.exit(1)
    edit_image(inp, out)
