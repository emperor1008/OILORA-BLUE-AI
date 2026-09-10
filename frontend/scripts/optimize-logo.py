"""
Oilora Blue AI — brand-asset optimizer

Reads D:\oilora logo.jpeg and produces:
  frontend/public/brand/oilora-blue-ai-logo.webp      (full logo)
  frontend/public/brand/oilora-blue-ai-mark.webp       (compass mark only)
  frontend/public/icon-192.png
  frontend/public/icon-512.png
  frontend/public/apple-touch-icon.png

Preserve aspect ratio and fine line art. Crop the mark using a centered square
region that fits inside the outer compass ring; never redesign or recolor.
"""

from __future__ import annotations

import pathlib
import sys
from PIL import Image, ImageOps

SRC = pathlib.Path(r"D:\oilora logo.jpeg")
OUT = pathlib.Path(__file__).resolve().parent.parent / "frontend" / "public"

MARK_SIDE = 1132  # px margin-left of outer ring to crop


def shrink_to_max(im: Image.Image, max_side: int) -> Image.Image:
    w, h = im.size
    if max(w, h) <= max_side:
        return im
    ratio = max_side / max(w, h)
    return im.resize((int(round(w * ratio)), int(round(h * ratio))), Image.LANCZOS)


def png_bytes(im: Image.Image, optimize: bool = True) -> bytes:
    buf = pathlib.Path(__file__).parent / "_tmp.png"
    im.save(buf, "PNG", optimize=optimize)
    data = buf.read_bytes()
    buf.unlink(missing_ok=True)
    return data


def main() -> None:
    src = Image.open(SRC).convert("RGBA")
    if src.mode != "RGBA":
        src = ImageOps.expand(src.convert("RGB"), border=0)

    # ─── 1. Full logo (keep original composition) ─────────────────────────
    logo = shrink_to_max(src, 900)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "brand").mkdir(parents=True, exist_ok=True)

    logo_webp = logo.copy()
   ception = logo_webp
    logo_webp.save(OUT / "brand" / "oilora-blue-ai-logo.webp", "WEBP", quality=92, method=6)
    print("wrote", (OUT / "brand" / "oilora-blue-ai-logo.webp").relative_to(OUT.parent))

    # ─── 2. Compass mark crop (centered square, inside outer ring) ────────
    w, h = src.size
    center = w // 2
    left = center - MARK_SIDE
    top = center - MARK_SIDE
    right = center + MARK_SIDE
    bottom = center + MARK_SIDE
    mark = src.crop((left, top, right, bottom))
    # shrink a touch so it fits nicely in a 52-56px container
    mark = shrink_to_max(mark, 760)
    mark.save(OUT / "brand" / "oilora-blue-ai-mark.webp", "WEBP", quality=92, method=6)
    print("wrote", (OUT / "brand" / "oilora-blue-ai-mark.webp").relative_to(OUT.parent))

    # ─── 3. Favicons & app icons ──────────────────────────────────────────
    def icns_square(im: Image.Image, side: int) -> bytes:
        square = im.resize((side, side), Image.LANCZOS)
        return png_bytes(square)

    icon_512 = shrink_to_max(src, 512)
    (OUT / "icon-512.png").write_bytes(png_bytes(icon_512))
    (OUT / "apple-touch-icon.png").write_bytes(png_bytes(icon_512))
    print("wrote", (OUT / "icon-512.png").relative_to(OUT.parent))
    print("wrote", (OUT / "apple-touch-icon.png").relative_to(OUT.parent))

    icon_192 = shrink_to_max(src, 192)
    (OUT / "icon-192.png").write_bytes(png_bytes(icon_192))
    print("wrote", (OUT / "icon-192.png").relative_to(OUT.parent))

    # favicon.ico from the same source at small size
    fav = shrink_to_max(src, 64)
    fav_path = OUT / "favicon.ico"
    fav.save(fav_path, "ICO", sizes=[(16, 16), (32, 32), (48, 48), (64, 64)])
    print("wrote", fav_path.relative_to(OUT.parent))


if __name__ == "__main__":
    main()