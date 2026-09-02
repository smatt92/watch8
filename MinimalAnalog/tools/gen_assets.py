#!/usr/bin/env python3
"""Generates the drawable assets for the Minimal Analog watch face.

The hands are plain white rounded shapes; colour is applied declaratively in
watchface.xml via `tintColor`, so the PNGs stay reusable and cheap. Each PNG is
authored at exactly the size it is drawn at on the 450x450 canvas, which is why
they live in res/drawable-nodpi/ -- the platform must not rescale them, and the
memory footprint evaluator charges 4 bytes per pixel of the decoded bitmap.

Run: python3 tools/gen_assets.py
"""

import math
import os
import struct
import zlib

CANVAS = 450
CENTER = CANVAS / 2.0

OUT_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..",
    "watchface",
    "src",
    "main",
    "res",
    "drawable-nodpi",
)

# Hand geometry. `length` is the distance from the watch centre to the tip,
# `tail` the distance from the centre to the blunt end. These drive both the
# PNG dimensions and the x/y/pivotY attributes in watchface.xml, so the two
# stay consistent; print_layout() emits the values to paste into the XML.
HANDS = {
    "hour": dict(w=22, length=120, tail=30, radius=11),
    "minute": dict(w=16, length=175, tail=25, radius=8),
    "second": dict(w=14, length=190, tail=40, radius=2, shaft=4, weight_r=7),
}

# Preview render time, must match the PREVIEW_TIME metadata in watchface.xml.
PREVIEW_H, PREVIEW_M, PREVIEW_S = 10, 8, 32
PREVIEW_DATE = "MON 15"
PREVIEW_STEPS = "8432 STEPS"

SS = 4  # supersampling factor for anti-aliasing


# --------------------------------------------------------------------------
# PNG output
# --------------------------------------------------------------------------
def write_png(path, width, height, rgba):
    """Writes an 8-bit RGBA PNG. `rgba` is a bytearray of width*height*4."""
    raw = bytearray()
    stride = width * 4
    for y in range(height):
        raw.append(0)  # filter type 0 (None)
        raw.extend(rgba[y * stride : (y + 1) * stride])

    def chunk(tag, data):
        out = struct.pack(">I", len(data)) + tag + data
        return out + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    png += chunk(b"IEND", b"")
    with open(path, "wb") as fh:
        fh.write(png)


# --------------------------------------------------------------------------
# Coverage helpers (signed distance fields, sampled at SSxSS per pixel)
# --------------------------------------------------------------------------
def sd_round_rect(px, py, cx, cy, w, h, r):
    """Signed distance to a rounded rectangle centred on (cx, cy)."""
    dx = abs(px - cx) - (w / 2.0 - r)
    dy = abs(py - cy) - (h / 2.0 - r)
    ax, ay = max(dx, 0.0), max(dy, 0.0)
    return math.hypot(ax, ay) + min(max(dx, dy), 0.0) - r


def sd_circle(px, py, cx, cy, r):
    return math.hypot(px - cx, py - cy) - r


def coverage(x, y, shapes):
    """Fraction of pixel (x, y) covered by any of `shapes` (SSxSS samples)."""
    hits = 0
    for sy in range(SS):
        py = y + (sy + 0.5) / SS
        for sx in range(SS):
            px = x + (sx + 0.5) / SS
            # A sample counts once, however many shapes cover it.
            if any(fn(px, py) < 0.0 for fn in shapes):
                hits += 1
    return hits / float(SS * SS)


def render_mask(width, height, shapes):
    """Renders `shapes` as a white image with coverage in the alpha channel."""
    buf = bytearray(width * height * 4)
    for y in range(height):
        for x in range(width):
            a = coverage(x, y, shapes)
            if a <= 0.0:
                continue
            i = (y * width + x) * 4
            buf[i] = 255
            buf[i + 1] = 255
            buf[i + 2] = 255
            buf[i + 3] = int(round(a * 255))
    return buf


# --------------------------------------------------------------------------
# Hands
# --------------------------------------------------------------------------
def hand_shapes(name):
    """Returns (width, height, shapes) for a hand drawn tip-up in its own PNG."""
    g = HANDS[name]
    w, h = g["w"], g["length"] + g["tail"]
    if name == "second":
        # Thin shaft plus a round counterweight behind the pivot.
        shaft = g["shaft"]
        shapes = [
            lambda px, py, w=w, h=h, s=shaft: sd_round_rect(
                px, py, w / 2.0, (h - 25) / 2.0, s, h - 25, s / 2.0
            ),
            lambda px, py, w=w, g=g: sd_circle(
                px, py, w / 2.0, g["length"] + 7, g["weight_r"]
            ),
        ]
    else:
        shapes = [
            lambda px, py, w=w, h=h, r=g["radius"]: sd_round_rect(
                px, py, w / 2.0, h / 2.0, w, h, r
            )
        ]
    return w, h, shapes


def hand_layout(name):
    """x, y, width, height, pivotY for the hand as placed on the 450 canvas."""
    g = HANDS[name]
    w, h, _ = hand_shapes(name)
    return dict(
        x=int(round(CENTER - w / 2.0)),
        y=int(round(CENTER - g["length"])),
        width=w,
        height=h,
        pivotY=g["length"] / float(h),
    )


# --------------------------------------------------------------------------
# 5x7 bitmap font, just enough for the preview render
# --------------------------------------------------------------------------
FONT = {
    "0": ("01110", "10001", "10011", "10101", "11001", "10001", "01110"),
    "1": ("00100", "01100", "00100", "00100", "00100", "00100", "01110"),
    "2": ("01110", "10001", "00001", "00010", "00100", "01000", "11111"),
    "3": ("11111", "00010", "00100", "00010", "00001", "10001", "01110"),
    "4": ("00010", "00110", "01010", "10010", "11111", "00010", "00010"),
    "5": ("11111", "10000", "11110", "00001", "00001", "10001", "01110"),
    "6": ("00110", "01000", "10000", "11110", "10001", "10001", "01110"),
    "7": ("11111", "00001", "00010", "00100", "01000", "01000", "01000"),
    "8": ("01110", "10001", "10001", "01110", "10001", "10001", "01110"),
    "9": ("01110", "10001", "10001", "01111", "00001", "00010", "01100"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "M": ("10001", "11011", "10101", "10001", "10001", "10001", "10001"),
    "N": ("10001", "11001", "10101", "10101", "10011", "10001", "10001"),
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    " ": ("00000",) * 7,
}


def draw_text(buf, text, cx, cy, scale, color):
    """Draws `text` centred on (cx, cy) into an opaque RGB buffer."""
    gw, gh = 5 * scale, 7 * scale
    gap = scale
    total = len(text) * gw + (len(text) - 1) * gap
    x0 = int(round(cx - total / 2.0))
    y0 = int(round(cy - gh / 2.0))
    for idx, ch in enumerate(text):
        rows = FONT.get(ch.upper())
        if rows is None:
            continue
        gx = x0 + idx * (gw + gap)
        for ry, row in enumerate(rows):
            for rx, bit in enumerate(row):
                if bit != "1":
                    continue
                for py in range(gh // 7):
                    for px in range(gw // 5):
                        X, Y = gx + rx * scale + px, y0 + ry * scale + py
                        if 0 <= X < CANVAS and 0 <= Y < CANVAS:
                            i = (Y * CANVAS + X) * 4
                            buf[i], buf[i + 1], buf[i + 2] = color
                            buf[i + 3] = 255


# --------------------------------------------------------------------------
# Preview render
# --------------------------------------------------------------------------
def blend(buf, x, y, color, alpha):
    if alpha <= 0.0 or not (0 <= x < CANVAS and 0 <= y < CANVAS):
        return
    i = (y * CANVAS + x) * 4
    for c in range(3):
        buf[i + c] = int(round(buf[i + c] * (1.0 - alpha) + color[c] * alpha))


def stamp_rotated(buf, src, sw, sh, layout, angle_deg, color):
    """Composites a hand PNG rotated clockwise about the watch centre."""
    th = math.radians(angle_deg)
    cos_t, sin_t = math.cos(-th), math.sin(-th)
    # Bounding box of the rotated hand, padded.
    reach = int(math.hypot(sw, sh)) + 2
    x0, y0 = int(CENTER - reach), int(CENTER - reach)
    x1, y1 = int(CENTER + reach), int(CENTER + reach)
    px_off = layout["x"]
    py_off = layout["y"]
    piv_x, piv_y = CENTER, CENTER
    for dy in range(max(0, y0), min(CANVAS, y1)):
        for dx in range(max(0, x0), min(CANVAS, x1)):
            rx, ry = dx + 0.5 - piv_x, dy + 0.5 - piv_y
            ux = rx * cos_t - ry * sin_t + piv_x - px_off
            uy = rx * sin_t + ry * cos_t + piv_y - py_off
            sx, sy = int(ux), int(uy)
            if not (0 <= sx < sw and 0 <= sy < sh):
                continue
            a = src[(sy * sw + sx) * 4 + 3] / 255.0
            blend(buf, dx, dy, color, a)


def render_preview(hand_images):
    buf = bytearray(CANVAS * CANVAS * 4)
    for i in range(0, len(buf), 4):
        buf[i + 3] = 255  # opaque black

    # Hour ticks, matching the ticks group in watchface.xml.
    for i in range(12):
        ang = math.radians(i * 30)
        long_tick = i % 3 == 0
        outer, inner = 208.0, 208.0 - (26.0 if long_tick else 14.0)
        half_w = 4.0 if long_tick else 2.0
        ux, uy = math.sin(ang), -math.cos(ang)
        for y in range(CANVAS):
            for x in range(CANVAS):
                px, py = x + 0.5 - CENTER, y + 0.5 - CENTER
                along = px * ux + py * uy
                across = px * (-uy) + py * ux
                if inner <= along <= outer and abs(across) <= half_w:
                    blend(buf, x, y, (150, 150, 150), 1.0)

    draw_text(buf, PREVIEW_DATE, CENTER, 114, 4, (170, 170, 170))
    draw_text(buf, PREVIEW_STEPS, CENTER, 336, 4, (170, 170, 170))

    frac_h = (PREVIEW_H % 12) + PREVIEW_M / 60.0 + PREVIEW_S / 3600.0
    angles = {
        "hour": frac_h / 12.0 * 360.0,
        "minute": (PREVIEW_M + PREVIEW_S / 60.0) / 60.0 * 360.0,
        "second": PREVIEW_S / 60.0 * 360.0,
    }
    colors = {
        "hour": (255, 255, 255),
        "minute": (255, 255, 255),
        "second": (255, 68, 56),
    }
    for name in ("hour", "minute", "second"):
        src, sw, sh = hand_images[name]
        stamp_rotated(buf, src, sw, sh, hand_layout(name), angles[name], colors[name])

    # Centre cap.
    for y in range(int(CENTER) - 10, int(CENTER) + 10):
        for x in range(int(CENTER) - 10, int(CENTER) + 10):
            a = coverage(x, y, [lambda px, py: sd_circle(px, py, CENTER, CENTER, 7.0)])
            blend(buf, x, y, (255, 68, 56), a)
    return buf


def print_layout():
    print("\nwatchface.xml hand attributes (canvas %dx%d):" % (CANVAS, CANVAS))
    for name in ("hour", "minute", "second"):
        lay = hand_layout(name)
        print(
            '  %-7s x="%d" y="%d" width="%d" height="%d" pivotX="0.5" pivotY="%.10f"'
            % (name, lay["x"], lay["y"], lay["width"], lay["height"], lay["pivotY"])
        )


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    images = {}
    total_px = 0
    for name in ("hour", "minute", "second"):
        w, h, shapes = hand_shapes(name)
        buf = render_mask(w, h, shapes)
        images[name] = (buf, w, h)
        path = os.path.join(OUT_DIR, name + ".png")
        write_png(path, w, h, buf)
        total_px += w * h
        print("wrote %s (%dx%d)" % (path, w, h))

    preview = render_preview(images)
    path = os.path.join(OUT_DIR, "preview.png")
    write_png(path, CANVAS, CANVAS, preview)
    print("wrote %s (%dx%d)" % (path, CANVAS, CANVAS))

    print(
        "\nhand bitmap memory: %d px x 4 B = %.1f KB (preview is not loaded at runtime)"
        % (total_px, total_px * 4 / 1024.0)
    )
    print_layout()


if __name__ == "__main__":
    main()
