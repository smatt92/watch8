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
def _chunk(tag, data):
    out = struct.pack(">I", len(data)) + tag + data
    return out + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)


def _filter_rows(rows, bpp):
    """Adaptive PNG filtering: per row, pick the filter with the lowest sum of
    absolute signed byte deviations (the heuristic from the PNG spec)."""
    out = bytearray()
    prev = bytearray(len(rows[0]))
    for line in rows:
        n = len(line)
        best, best_score = None, None
        for ftype in range(5):
            cand = bytearray(n)
            for i in range(n):
                a = line[i - bpp] if i >= bpp else 0
                b = prev[i]
                c = prev[i - bpp] if i >= bpp else 0
                x = line[i]
                if ftype == 0:
                    v = x
                elif ftype == 1:
                    v = x - a
                elif ftype == 2:
                    v = x - b
                elif ftype == 3:
                    v = x - ((a + b) >> 1)
                else:
                    pp = a + b - c
                    pa, pb, pc = abs(pp - a), abs(pp - b), abs(pp - c)
                    pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                    v = x - pr
                cand[i] = v & 0xFF
            score = sum(v if v < 128 else 256 - v for v in cand)
            if best_score is None or score < best_score:
                best, best_score, best_type = cand, score, ftype
        out.append(best_type)
        out.extend(best)
        prev = line
    return out


def _encode_palette(width, height, px, palette, depth):
    index = {p: i for i, p in enumerate(palette)}
    per_byte = 8 // depth
    rows = []
    for y in range(height):
        row = bytearray()
        acc = shift = 0
        for x in range(width):
            v = index[px[y * width + x]]
            if depth == 8:
                row.append(v)
            else:
                acc = (acc << depth) | v
                shift += 1
                if shift == per_byte:
                    row.append(acc)
                    acc = shift = 0
        if depth != 8 and shift:
            row.append(acc << (depth * (per_byte - shift)))
        rows.append(row)
    body = _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, depth, 3, 0, 0, 0))
    body += _chunk(b"PLTE", b"".join(bytes(p[:3]) for p in palette))
    alphas = bytes(p[3] for p in palette).rstrip(b"\xff")
    if alphas:
        body += _chunk(b"tRNS", alphas)
    return body, _filter_rows(rows, 1)


def _encode_grey_alpha(width, height, px):
    rows = [
        bytearray(
            b for x in range(width)
            for b in (px[y * width + x][0], px[y * width + x][3])
        )
        for y in range(height)
    ]
    body = _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 4, 0, 0, 0))
    return body, _filter_rows(rows, 2)


def _encode_rgba(width, height, rgba):
    stride = width * 4
    rows = [bytearray(rgba[y * stride : (y + 1) * stride]) for y in range(height)]
    body = _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
    return body, _filter_rows(rows, 4)


def write_png(path, width, height, rgba):
    """Writes the smallest correct PNG for the given RGBA pixels.

    Builds every applicable encoding -- packed palette, 8-bit palette,
    greyscale+alpha, RGBA -- and keeps whichever serialises smallest. On small
    images the PLTE/tRNS chunk overhead can outweigh sub-byte packing, so the
    winner is decided by measurement, not by a rule of thumb.

    Encoding affects APK size only. The memory footprint evaluator charges
    4 * width * height * frames off the decoded bitmap, so none of this moves
    the memcheck numbers.
    """
    px = [bytes(rgba[i : i + 4]) for i in range(0, len(rgba), 4)]
    # Translucent entries first, so the tRNS chunk can be truncated.
    palette = sorted(set(px), key=lambda p: (p[3], p[0], p[1], p[2]))

    candidates = []
    if len(palette) <= 256:
        min_depth = next(d for d in (1, 2, 4, 8) if len(palette) <= (1 << d))
        for depth in {min_depth, 8}:
            candidates.append(("palette %d-bit" % depth,
                               _encode_palette(width, height, px, palette, depth)))
    if all(p[0] == p[1] == p[2] for p in px):
        candidates.append(("grey+alpha 8-bit", _encode_grey_alpha(width, height, px)))
    candidates.append(("RGBA 8-bit", _encode_rgba(width, height, rgba)))

    best = None
    for label, (body, raw) in candidates:
        png = (b"\x89PNG\r\n\x1a\n" + body
               + _chunk(b"IDAT", zlib.compress(bytes(raw), 9))
               + _chunk(b"IEND", b""))
        if best is None or len(png) < len(best[1]):
            best = (label, png)

    with open(path, "wb") as fh:
        fh.write(best[1])
    return best[0], len(best[1])


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
        enc, size = write_png(path, w, h, buf)
        total_px += w * h
        print("wrote %-13s %7sx%-4s %-17s %6d B" % (name + ".png", w, h, enc, size))

    preview = render_preview(images)
    path = os.path.join(OUT_DIR, "preview.png")
    enc, size = write_png(path, CANVAS, CANVAS, preview)
    print("wrote %-13s %7sx%-4s %-17s %6d B" % ("preview.png", CANVAS, CANVAS, enc, size))

    print(
        "\nhand bitmap memory: %d px x 4 B = %.1f KB (preview is not loaded at runtime)"
        % (total_px, total_px * 4 / 1024.0)
    )
    print_layout()


if __name__ == "__main__":
    main()
