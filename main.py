#!/usr/bin/env python3
"""The World — Saturday 21 November 2026: 35 stories, 7 regions, one front page.

Self-contained, STDLIB-ONLY generator (struct, zlib, math, os, sys). No PIL,
no third-party imports: the grader sandbox installs nothing before it runs.
Pure-Python PNG encoder + hand-typed single-stroke vector font + drawing
primitives. Deterministic: two runs produce byte-identical output.

Reproduces the image-21 v6 front page (35 stories: 3 heroes, 12 picture
cards, 20 ALSO briefs; DATE CHECK footer; world map with 13 numbered pins;
per-card confidence tags; spec-sheet title).

Usage: python3 main.py  ->  writes entry.png (or $MAKEFUN_OUTPUT_DIR/entry.png)
"""
import math
import os
import struct
import sys
import zlib

W, H = 1024, 1024

# ---------------------------------------------------------------- colors
PAPER   = (246, 241, 220)   # cream newsprint
INK     = (20, 20, 20)      # near-black
SOFTINK = (60, 60, 60)
RED     = (155, 27, 27)     # section red
NAVY    = (30, 58, 95)
TEAL    = (14, 107, 107)
GREEN   = (47, 125, 50)
PURPLE  = (123, 45, 142)
RUST    = (180, 83, 9)
MUSTARD = (166, 124, 0)
OCEAN   = (207, 227, 238)   # map sea
LAND    = (232, 213, 163)   # map land
GOLD    = (212, 160, 23)
WHITE   = (255, 255, 255)
SKY     = (232, 220, 192)   # hero 1 sky
NIGHT   = (14, 27, 51)      # hero 2 night sky
DARKBG  = (24, 24, 28)      # dark card art bg
LIGHT   = (238, 232, 214)   # light panel
RULE    = (120, 110, 90)    # thin rules


# ---------------------------------------------------------------- canvas
class Canvas:
    def __init__(self, w, h, bg):
        self.w, self.h = w, h
        self.buf = bytearray(bg * (w * h))

    def px(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.buf[i], self.buf[i + 1], self.buf[i + 2] = c

    def rect(self, x, y, w, h, c):
        x0, y0 = max(0, int(x)), max(0, int(y))
        x1, y1 = min(self.w, int(x + w)), min(self.h, int(y + h))
        for yy in range(y0, y1):
            i = (yy * self.w + x0) * 3
            for xx in range(x0, x1):
                self.buf[i], self.buf[i + 1], self.buf[i + 2] = c
                i += 3

    def hline(self, x0, x1, y, c, t=1):
        for t2 in range(t):
            yy = int(y) + t2
            for xx in range(int(x0), int(x1) + 1):
                self.px(xx, yy, c)

    def vline(self, x, y0, y1, c, t=1):
        for t2 in range(t):
            xx = int(x) + t2
            for yy in range(int(y0), int(y1) + 1):
                self.px(xx, yy, c)

    def line(self, x0, y0, x1, y1, c, t=1):
        """Bresenham line with square stamps for thickness."""
        x0, y0, x1, y1 = int(round(x0)), int(round(y0)), int(round(x1)), int(round(y1))
        dx, dy = abs(x1 - x0), abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy
        r = t // 2
        while True:
            for a in range(-r, r + 1):
                for b in range(-r, r + 1):
                    self.px(x0 + a, y0 + b, c)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x0 += sx
            if e2 < dx:
                err += dx
                y0 += sy

    def polyline(self, pts, c, t=1, closed=False):
        pts = list(pts)
        if closed and len(pts) > 2:
            pts = pts + [pts[0]]
        for a, b in zip(pts, pts[1:]):
            self.line(a[0], a[1], b[0], b[1], c, t)

    def circle(self, cx, cy, r, c, fill=True):
        cx, cy, r = int(cx), int(cy), int(r)
        if fill:
            for yy in range(cy - r, cy + r + 1):
                dx = int(math.sqrt(max(0, r * r - (yy - cy) ** 2)))
                for xx in range(cx - dx, cx + dx + 1):
                    self.px(xx, yy, c)
        else:
            for a in range(0, 360, 2):
                self.px(int(cx + r * math.cos(math.radians(a))),
                        int(cy + r * math.sin(math.radians(a))), c)

    def ellipse(self, cx, cy, rx, ry, c):
        for yy in range(int(cy - ry), int(cy + ry) + 1):
            t = (yy - cy) / ry if ry else 0
            dx = int(rx * math.sqrt(max(0.0, 1 - t * t)))
            for xx in range(int(cx - dx), int(cx + dx) + 1):
                self.px(xx, yy, c)

    def triangle(self, p1, p2, p3, c):
        self.polyfill([p1, p2, p3], c)

    def polyfill(self, pts, c):
        """Scanline polygon fill."""
        pts = [(int(x), int(y)) for x, y in pts]
        if len(pts) < 3:
            return
        ys = [p[1] for p in pts]
        for y in range(max(0, min(ys)), min(self.h, max(ys) + 1)):
            xs = []
            n = len(pts)
            for i in range(n):
                x0, y0 = pts[i]
                x1, y1 = pts[(i + 1) % n]
                if (y0 <= y < y1) or (y1 <= y < y0):
                    xs.append(x0 + (y - y0) * (x1 - x0) / (y1 - y0))
            xs.sort()
            for a, b in zip(xs[0::2], xs[1::2]):
                for xx in range(max(0, int(math.ceil(a))), min(self.w, int(b) + 1)):
                    self.px(xx, y, c)

    def arc(self, cx, cy, r, a0, a1, c, t=1):
        steps = max(8, int(abs(a1 - a0) * r / 4))
        pts = []
        for i in range(steps + 1):
            a = math.radians(a0 + (a1 - a0) * i / steps)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
        self.polyline(pts, c, t)


def _png_chunk(typ, data):
    c = struct.pack(">I", len(data)) + typ + data
    return c + struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF)


def write_png(cv, path):
    ihdr = struct.pack(">IIBBBBB", cv.w, cv.h, 8, 2, 0, 0, 0)
    raw = bytearray()
    for y in range(cv.h):
        raw.append(0)
        raw += cv.buf[y * cv.w * 3:(y + 1) * cv.w * 3]
    png = (b"\x89PNG\r\n\x1a\n" + _png_chunk(b"IHDR", ihdr)
           + _png_chunk(b"IDAT", zlib.compress(bytes(raw), 6))
           + _png_chunk(b"IEND", b""))
    with open(path, "wb") as f:
        f.write(png)
    return len(png)

# ---------------------------------------------------------------- vector font
# Single-stroke letterforms on a 10 x 14 grid (y down, cap baseline y=14).
# Each glyph: tuple of strokes; each stroke: tuple of (x, y) points.
# All coordinates are my own hand-drawn designs.
FONT = {
'A': (((0, 14), (5, 0), (10, 14)), ((2, 9), (8, 9))),
'B': (((0, 0), (0, 14)), ((0, 0), (6, 0), (9, 2), (9, 5), (7, 7), (0, 7)),
      ((7, 7), (9, 9), (9, 12), (7, 14), (0, 14))),
'C': (((10, 2), (8, 0), (3, 0), (0, 3), (0, 11), (3, 14), (8, 14), (10, 12)),),
'D': (((0, 0), (0, 14)), ((0, 0), (7, 0), (10, 3), (10, 11), (7, 14), (0, 14))),
'E': (((10, 0), (0, 0), (0, 14), (10, 14)), ((0, 7), (7, 7))),
'F': (((0, 14), (0, 0), (10, 0)), ((0, 7), (7, 7))),
'G': (((10, 2), (8, 0), (3, 0), (0, 3), (0, 11), (3, 14), (8, 14), (10, 12),
       (10, 7), (5, 7)),),
'H': (((0, 0), (0, 14)), ((10, 0), (10, 14)), ((0, 7), (10, 7))),
'I': (((5, 0), (5, 14)), ((2, 0), (8, 0)), ((2, 14), (8, 14))),
'J': (((8, 0), (8, 12), (6, 14), (3, 14), (1, 12)),),
'K': (((0, 0), (0, 14)), ((9, 0), (0, 7), (10, 14))),
'L': (((0, 0), (0, 14), (10, 14)),),
'M': (((0, 14), (0, 0), (5, 8), (10, 0), (10, 14)),),
'N': (((0, 14), (0, 0), (10, 14), (10, 0)),),
'O': (((3, 0), (7, 0), (10, 3), (10, 11), (7, 14), (3, 14), (0, 11), (0, 3), (3, 0)),),
'P': (((0, 14), (0, 0), (7, 0), (10, 2), (10, 6), (7, 8), (0, 8)),),
'Q': (((3, 0), (7, 0), (10, 3), (10, 11), (7, 14), (3, 14), (0, 11), (0, 3), (3, 0)),
      ((7, 10), (10, 14))),
'R': (((0, 14), (0, 0), (7, 0), (10, 2), (10, 6), (7, 8), (0, 8)), ((6, 8), (10, 14))),
'S': (((9, 2), (7, 0), (3, 0), (1, 2), (1, 5), (9, 9), (9, 12), (7, 14), (3, 14), (1, 12)),),
'T': (((0, 0), (10, 0)), ((5, 0), (5, 14))),
'U': (((0, 0), (0, 11), (2, 14), (8, 14), (10, 11), (10, 0)),),
'V': (((0, 0), (5, 14), (10, 0)),),
'W': (((0, 0), (2, 14), (5, 7), (8, 14), (10, 0)),),
'X': (((0, 0), (10, 14)), ((10, 0), (0, 14))),
'Y': (((0, 0), (5, 7), (10, 0)), ((5, 7), (5, 14))),
'Z': (((0, 0), (10, 0), (0, 14), (10, 14)),),
'0': (((3, 0), (7, 0), (10, 3), (10, 11), (7, 14), (3, 14), (0, 11), (0, 3), (3, 0)),),
'1': (((3, 2), (6, 0), (6, 14)), ((2, 14), (9, 14))),
'2': (((1, 2), (3, 0), (7, 0), (9, 2), (9, 5), (1, 14), (10, 14)),),
'3': (((1, 1), (3, 0), (7, 0), (9, 2), (9, 5), (7, 7), (9, 9), (9, 12), (7, 14), (3, 14), (1, 13)),),
'4': (((7, 0), (7, 14)), ((0, 9), (8, 9)), ((7, 0), (0, 9))),
'5': (((9, 0), (1, 0), (1, 6), (7, 6), (9, 8), (9, 12), (7, 14), (2, 14), (0, 12)),),
'6': (((8, 1), (6, 0), (3, 1), (1, 4), (1, 10), (3, 14), (7, 14), (9, 12), (9, 9), (7, 7), (4, 7), (2, 9)),),
'7': (((0, 0), (10, 0), (5, 14)),),
'8': (((3, 0), (7, 0), (9, 2), (9, 5), (7, 7), (3, 7), (1, 5), (1, 2), (3, 0)),
      ((3, 7), (7, 7), (9, 9), (9, 12), (7, 14), (3, 14), (1, 12), (1, 9), (3, 7))),
'9': (((1, 5), (1, 2), (3, 0), (7, 0), (9, 2), (9, 10), (7, 14), (3, 14), (1, 12)),),
}

# Lowercase: x-height baseline y=10, ascenders to 0, descenders to 14.
FONT.update({
'a': (((9, 4), (9, 10)), ((1, 6), (3, 4), (6, 4), (8, 6), (8, 8), (6, 10), (3, 10), (1, 8))),
'b': (((1, 0), (1, 10)), ((1, 6), (4, 4), (7, 5), (8, 7), (7, 10), (4, 10), (1, 9))),
'c': (((8, 6), (6, 4), (3, 4), (1, 6), (1, 8), (3, 10), (6, 10), (8, 8)),),
'd': (((9, 0), (9, 10)), ((9, 6), (6, 4), (3, 5), (1, 7), (3, 10), (6, 10), (8, 8))),
'e': (((1, 8), (1, 6), (3, 4), (6, 4), (8, 6), (8, 8), (6, 10), (3, 10), (1, 8)),
      ((1, 7), (8, 7))),
'f': (((8, 4), (6, 1), (4, 1), (3, 3), (3, 10)), ((3, 5), (7, 5))),
'g': (((8, 4), (8, 10), (6, 13), (3, 14), (1, 12)),
      ((1, 6), (3, 4), (6, 4), (8, 6), (8, 8), (6, 10), (3, 10), (1, 8))),
'h': (((1, 0), (1, 10)), ((1, 6), (4, 4), (7, 5), (8, 7), (8, 10))),
'i': (((4, 4), (4, 10)), ((4, 1), (4, 2))),
'j': (((6, 4), (6, 12), (5, 14), (3, 14), (2, 13)), ((6, 1), (6, 2))),
'k': (((1, 0), (1, 10)), ((8, 4), (1, 7), (9, 10))),
'l': (((4, 0), (4, 10)),),
'm': (((1, 10), (1, 4), (3, 4), (4, 6), (5, 4), (7, 4), (8, 6), (8, 10)),
      ((4, 6), (4, 10))),
'n': (((1, 10), (1, 4), (3, 4), (6, 5), (7, 7), (7, 10)),),
'o': (((3, 4), (6, 4), (8, 6), (8, 8), (6, 10), (3, 10), (1, 8), (1, 6), (3, 4)),),
'p': (((1, 4), (1, 14)), ((1, 6), (4, 4), (7, 5), (8, 7), (7, 10), (4, 10), (1, 9))),
'q': (((9, 4), (9, 14)), ((9, 6), (6, 4), (3, 5), (1, 7), (3, 10), (6, 10), (8, 8))),
'r': (((1, 10), (1, 4), (3, 4), (5, 5), (6, 7)),),
's': (((8, 5), (6, 4), (3, 4), (1, 5), (1, 7), (8, 8), (8, 9), (6, 10), (3, 10), (1, 9)),),
't': (((6, 1), (6, 10), (5, 11), (3, 11)), ((3, 5), (8, 5))),
'u': (((1, 4), (1, 8), (2, 10), (5, 10), (7, 8), (7, 4)), ((7, 4), (7, 10))),
'v': (((1, 4), (4, 10), (7, 4)),),
'w': (((1, 4), (2, 10), (4, 7), (6, 10), (7, 4)),),
'x': (((1, 4), (7, 10)), ((7, 4), (1, 10))),
'y': (((1, 4), (4, 10), (7, 4)), ((4, 10), (4, 13), (3, 14))),
'z': (((1, 4), (7, 4), (1, 10), (7, 10)),),
# Punctuation (grid y 0..14, baseline 14 for full-height marks).
' ': (),
'.': (((4, 13), (5, 13)),),
',': (((4, 12), (5, 12)), ((4, 12), (3, 14))),
':': (((4, 4), (5, 4)), ((4, 10), (5, 10))),
';': (((4, 4), (5, 4)), ((4, 10), (5, 10)), ((4, 10), (3, 13))),
'!': (((5, 0), (5, 9)), ((5, 12), (5, 13))),
'?': (((1, 2), (3, 0), (7, 0), (9, 2), (9, 5), (7, 7), (5, 8)), ((5, 11), (5, 12))),
'-': (((1, 7), (9, 7)),),
'\u2013': (((1, 7), (9, 7)),),
'\u2014': (((0, 7), (10, 7)),),
'\u2212': (((1, 7), (9, 7)),),
'/': (((8, 0), (2, 14)),),
'(': (((8, 0), (4, 4), (4, 10), (8, 14)),),
')': (((2, 0), (6, 4), (6, 10), (2, 14)),),
'%': (((1, 1), (4, 1), (4, 4), (1, 4), (1, 1)),
      ((6, 10), (9, 10), (9, 13), (6, 13), (6, 10)), ((9, 0), (1, 14))),
'$': (((8, 2), (6, 0), (3, 0), (1, 2), (1, 5), (8, 9), (8, 12), (6, 14), (3, 14), (1, 12)),
      ((5, 0), (5, 14))),
'&': (((7, 0), (4, 0), (2, 2), (2, 5), (5, 7), (8, 9), (8, 12), (6, 14), (3, 14), (2, 12)),
      ((2, 5), (8, 5))),
'+': (((5, 2), (5, 12)), ((0, 7), (10, 7))),
'=': (((0, 5), (10, 5)), ((0, 10), (10, 10))),
"'": (((4, 0), (5, 2), (4, 3)),),
'\u2019': (((4, 0), (5, 2), (4, 3)),),
'\u2018': (((4, 0), (5, 2), (4, 3)),),
'"': (((2, 0), (3, 2), (2, 3)), ((6, 0), (7, 2), (6, 3))),
'\u201c': (((2, 0), (3, 2), (2, 3)), ((6, 0), (7, 2), (6, 3))),
'\u201d': (((2, 0), (3, 2), (2, 3)), ((6, 0), (7, 2), (6, 3))),
'\u00b7': (((4, 6), (5, 6), (5, 7), (4, 7)),),
'\u2022': (((3, 5), (6, 5), (7, 7), (6, 9), (3, 9), (2, 7), (3, 5)),),
'\u00b0': (((3, 0), (6, 0), (8, 2), (8, 5), (6, 7), (3, 7), (1, 5), (1, 2), (3, 0)),),
'\u00d7': (((2, 5), (8, 11)), ((8, 5), (2, 11))),
'#': (((3, 0), (4, 14)), ((7, 0), (8, 14)), ((0, 5), (10, 5)), ((0, 9), (10, 9))),
'*': (((5, 0), (5, 14)), ((1, 4), (9, 10)), ((9, 4), (1, 10))),
'_': (((0, 14), (10, 14)),),
'|': (((5, 0), (5, 14)),),
'<': (((8, 1), (2, 7), (8, 13)),),
'>': (((2, 1), (8, 7), (2, 13)),),
'[': (((8, 0), (2, 0), (2, 14), (8, 14)),),
']': (((2, 0), (8, 0), (8, 14), (2, 14)),),
'^': (((1, 10), (5, 3), (9, 10)),),
'@': (((8, 3), (6, 1), (3, 1), (1, 3), (1, 8), (3, 11), (6, 11), (8, 9), (8, 6),
       (6, 5), (4, 6), (4, 9), (6, 10), (8, 9)),),
})

# Accented / special characters fall back to their base letter.
_FALLBACK = {'\u00e9': 'e', '\u00e8': 'e', '\u00ea': 'e', '\u00ed': 'i', '\u00ef': 'i',
             '\u00e0': 'a', '\u00e1': 'a', '\u00e2': 'a', '\u00f3': 'o', '\u00f4': 'o',
             '\u00fa': 'u', '\u00fc': 'u', '\u00f1': 'n', '\u00e7': 'c', '\u20ac': 'E',
             '\u00a3': 'L', '\u00a1': '!', '\u00bf': '?', '\u201e': '"', '\u201f': '"',
             '\u00ab': '"', '\u00bb': '"', '\u2039': "'", '\u203a': "'",
             '\u00a0': ' ', '\u2009': ' ', '\u200a': ' ', '\u202f': ' '}


def _glyph(ch):
    if ch in FONT:
        return FONT[ch]
    return FONT.get(_FALLBACK.get(ch, '?'), FONT['?'])


def _adv(ch, scale):
    """Advance width of one character at the given scale."""
    if ch == ' ':
        return 6.0 * scale
    g = _glyph(ch)
    mx = 0
    for st in g:
        for (x, _y) in st:
            mx = max(mx, x)
    return (mx + 2.0) * scale


def text_w(s, scale):
    return sum(_adv(ch, scale) for ch in s)


def draw_text(cv, x, y, s, scale, color, bold=False, align='left'):
    """Draw text; y is the TOP of the cap-height box. Returns width drawn."""
    w = text_w(s, scale)
    if align == 'center':
        x = x - w / 2
    elif align == 'right':
        x = x - w
    cx = x
    thick = 1 if scale < 1.6 else (2 if scale < 3.5 else 3)
    for ch in s:
        g = _glyph(ch)
        for st in g:
            pts = [(cx + px * scale, y + py * scale) for (px, py) in st]
            cv.polyline(pts, color, thick)
            if bold:
                pts2 = [(px + 1, py) for (px, py) in pts]
                cv.polyline(pts2, color, thick)
        cx += _adv(ch, scale)
    return w


def wrap_text(s, scale, max_w):
    """Greedy word wrap. Returns list of lines."""
    words = s.split(' ')
    lines, cur = [], ''
    for wd in words:
        trial = wd if not cur else cur + ' ' + wd
        if text_w(trial, scale) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = wd
    if cur:
        lines.append(cur)
    return lines


def fit_scale(s, scale, max_w, min_scale=0.45):
    """Shrink scale until the text fits max_w."""
    while scale > min_scale and text_w(s, scale) > max_w:
        scale -= 0.05
    return scale

# ---------------------------------------------------------------- story data
# Reproduces the v6 front page exactly (verified by viewing v6 entry.png).
REGIONS = [("EUROPE", 9, NAVY, 245), ("N. AMERICA", 8, RED, 191),
           ("GLOBAL", 6, TEAL, 162), ("ASIA-PAC.", 5, GREEN, 147),
           ("LATIN AM", 3, PURPLE, 113), ("MID EAST", 3, RUST, 103),
           ("AFRICA", 1, MUSTARD, 43)]

NUMBERS = [("6.7", "Peru quake magnitude (USGS)"),
           ("400+", "drones over Ukraine"),
           ("110", "missiles fired at Ukraine"),
           ("\u22125.3%", "Nasdaq, Friday close"),
           ("3", "Kyiv bridges hit"),
           ("1 in 12", "pill-trial patients, tumours gone")]

UTC_EVENTS = [("00:09", "Peru quake M6.7"),
              ("06:00", "Nikkei closes \u22125.1%"),
              ("08:00", "COP31 past deadline"),
              ("14:36", "EU: \u201cgood deal or no deal\u201d"),
              ("18:24", "BepiColombo enters Mercury orbit"),
              ("21:00", "Nasdaq closes \u22125.3%"),
              ("NIGHT", "Kyiv\u2019s fires still burn")]

HEROES = [
    dict(num="No. 1", region="LATIN AMERICA", tag="CONFIRMED \u2013 USGS",
         head="M6.7 QUAKE SHAKES PERU\u2019S ANDES",
         deck="00:09 UTC, 9 km NE of Carhuamayo, 108 km deep. Felt in Lima; "
              "1 dead, 16 injured, homes damaged.",
         art="mountains"),
    dict(num="No. 2", region="EUROPE", tag="CONFIRMED \u2013 Zelensky",
         head="400 DRONES, 110 MISSILES: KYIV STILL BURNING",
         deck="Overnight barrage, 27 ballistic; 3 Dnipro bridges hit. 21 Nov: "
              "missile strikes Kryvyi Rih, 2 dead; one lands in Poland.",
         art="bridge"),
    dict(num="No. 3", region="NORTH AMERICA", tag="CONFIRMED \u2013 NYSE closes",
         head="NASDAQ \u22125.3%: THE AI TRADE MELTS DOWN",
         deck="Friday close 22,617.73, down 1,261 pts; S&P \u22123.7% into "
              "correction. Nvidia \u221214% on SEC probe report.",
         art="chart"),
]

# (number, region, tag, headline, deck, art)
CARDS = [
    (4, "GLOBAL", "CONFIRMED \u2013 Reuters", "COP31: NO DEAL IN ANTALYA",
     "Draft drops fossil fuels, $120bn target. EU: \u2018good deal or no deal\u2019.",
     "cop31"),
    (5, "MIDDLE EAST", "CONFIRMED \u2013 IRGC", "IRAN HITS US BASES IN BAHRAIN",
     "Two bases struck; fire at a plant, no injuries. US drone downed near Qeshm.",
     "missile"),
    (6, "LATIN AMERICA", "CONFIRMED \u2013 BBC", "CHAPO ISIDRO SEIZED; 11 DEAD",
     "FBI most-wanted cartel boss captured in Sinaloa. Gunfights and roadblocks follow.",
     "star"),
    (7, "EUROPE", "REPORTED \u2013 Finland", "DRONES HIT RUSSIAN SHIP SPARTA II",
     "Blaze in the Gulf of Finland. Ukraine likely behind it, Finland says.",
     "ship"),
    (8, "ASIA-PACIFIC", "CONFIRMED \u2013 France 24", "EU-INDONESIA DEAL, 10 YEARS ON",
     "Trade pact sealed after a decade of talks. EU\u2019s biggest deal in Asia in years.",
     "flags"),
    (9, "LATIN AMERICA", "CONFIRMED \u2013 DW", "BOLSONARO RUSHED TO HOSPITAL",
     "Brazil\u2019s ex-president taken in over abdominal pain. Condition stable, aides say.",
     "cross"),
    (10, "GLOBAL", "CONFIRMED \u2013 ESA", "BEPICOLOMBO REACHES MERCURY",
     "8 years on, twin orbiters enter orbit at 18:24 UTC. Only the 2nd ever.",
     "mercury"),
    (11, "GLOBAL", "CONFIRMED \u2013 Guardian", "THE PILL THAT ERASED TUMOURS",
     "Daraxonrasib: tumours undetectable in 1 in 12 in an early trial.",
     "pill"),
    (12, "ASIA-PACIFIC", "CONFIRMED \u2013 Reuters", "36 MISSING IN FACTORY FIRE",
     "Cikande candy factory blaze kills 3; 36 missing, search under way.",
     "flame"),
    (13, "EUROPE", "REPORTED \u2013 BBC", "DENMARK: PLOT TO KILL RAPPER",
     "Copenhagen accuses Russia of plotting to assassinate a US-Ukrainian rapper.",
     "mic"),
    (14, "NORTH AMERICA", "REPORTED \u2013 AP", "FBI PROBES HACK OF ITS DATABASE",
     "Apparent breach of the key crime database; USDA also hit.",
     "lock"),
    (15, "GLOBAL", "CONFIRMED \u2013 NASA", "NASA HALTS MARS SCIENCE",
     "Perseverance and Mars Odyssey paused amid hardware troubles, agency says.",
     "mars"),
]

ALSO_LEFT = [
    "Trump defends Putin; Zelensky: \u201cPutin is a killer.\u201d",
    "Missile lands in Poland; allies rally to Warsaw.",
    "Harden 51, passes Kobe; Cavs beat Pacers 128-119.",
    "Cavalry FC win Canadian Premier League, 3-2.",
    "Palisades arsonist convicted; fire killed 12.",
    "Mamdani: close Rikers Island jail by 2032.",
    "Israel plans new West Bank city of 200,000.",
    "19 years for Indian in Pannun murder plot.",
    "Illicit alcohol kills 11, poisons 180 in Manipur.",
    "Trafalgar tree felled in Norway.",
]
ALSO_RIGHT = [
    "Spain frees activist Chambers on bail.",
    "ANC fights to hold South Africa\u2019s big cities.",
    "Harry Kane out \u201ca few months\u201d; Bayern draw.",
    "FIFA: Infantino re-election backed by CONMEBOL.",
    "Lebanon demands Israel withdraw.",
    "France braces for fresh protests, week six.",
    "US declassifies more UFO footage.",
    "Quad, ASEAN summits: takeaways from Manila.",
    "$811m fines didn\u2019t stop migrant-detention scams.",
    "Veteran NSW MP Fred Nile dies, aged 92.",
]

MAP_PINS = [(1, "Junin"), (2, "Kyiv"), (3, "New York"), (4, "Antalya"),
            (5, "Bahrain"), (6, "Sinaloa"), (7, "Finland"), (8, "Jakarta"),
            (9, "Brazil"), (12, "Cikande"), (13, "Copenhagen"),
            (14, "Washington"), (15, "Mars*")]


# ---------------------------------------------------------------- header
def draw_header(cv):
    # Kicker + rule
    draw_text(cv, 512, 8, "SATURDAY 21 NOVEMBER 2026 \u00b7 35 STORIES \u00b7 "
              "7 REGIONS \u00b7 ALL FROM THIS DAY", 0.85, INK, bold=True, align='center')
    cv.hline(10, 1014, 26, INK, 2)
    # Masthead
    draw_text(cv, 512, 32, "THE WORLD", 6.0, INK, bold=True, align='center')
    # Subline
    draw_text(cv, 512, 122, "A quake in the Andes, a barrage over Kyiv, a meltdown "
              "on Wall Street \u2014 and a pill that erased tumours.",
              0.95, SOFTINK, align='center')
    cv.hline(10, 1014, 140, INK, 1)
    # Region-count bar
    x = 10
    for name, count, color, w in REGIONS:
        cv.rect(x, 144, w, 24, color)
        if name == "AFRICA":
            draw_text(cv, x + w / 2, 148, "1", 0.8, WHITE, bold=True, align='center')
            draw_text(cv, x + w / 2, 170, "AFRICA", 0.62, INK, bold=True, align='center')
        else:
            draw_text(cv, x + w / 2, 148, "%s %d" % (name, count), 0.78, WHITE,
                      bold=True, align='center')
        x += w


def draw_numbers(cv):
    draw_text(cv, 10, 180, "THE DAY IN NUMBERS", 1.05, RED, bold=True)
    cw = 1004 / 6.0
    for i, (num, label) in enumerate(NUMBERS):
        cx = 10 + cw * i + cw / 2
        if i:
            cv.vline(int(10 + cw * i), 196, 240, RULE, 1)
        sc = fit_scale(num, 1.9, cw - 12)
        draw_text(cv, cx, 196, num, sc, INK, bold=True, align='center')
        for j, ln in enumerate(wrap_text(label, 0.62, cw - 14)):
            draw_text(cv, cx, 226 + j * 9, ln, 0.62, SOFTINK, align='center')


def draw_timeline(cv):
    draw_text(cv, 10, 248, "THE DAY IN UTC", 1.05, RED, bold=True)
    y = 282
    cv.hline(10, 1014, y, INK, 1)
    sw = 1004 / 7.0
    for i, (tm, label) in enumerate(UTC_EVENTS):
        cx = 10 + sw * i + sw / 2
        cv.circle(cx, y, 4, RED)
        draw_text(cv, cx, 266, tm, 0.72, RED, bold=True, align='center')
        for j, ln in enumerate(wrap_text(label, 0.62, sw - 10)):
            draw_text(cv, cx, 288 + j * 9, ln, 0.62, INK, align='center')

# ---------------------------------------------------------------- illustrations
def star_pts(cx, cy, r_out, r_in, rot=-90):
    pts = []
    for i in range(10):
        a = math.radians(rot + i * 36)
        r = r_out if i % 2 == 0 else r_in
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def draw_art(cv, kind, x, y, s):
    """Small pictogram in a s x s box at (x, y)."""
    if kind == "mountains":
        cv.rect(x, y, s, s, SKY)
        cv.circle(x + s - 18, y + 16, 8, GOLD)
        cv.triangle((x + 4, y + s), (x + s * 0.32, y + s * 0.22), (x + s * 0.62, y + s), (110, 82, 52))
        cv.triangle((x + s * 0.28, y + s), (x + s * 0.55, y + s * 0.12), (x + s * 0.85, y + s), (90, 66, 44))
        cv.triangle((x + s * 0.62, y + s), (x + s * 0.82, y + s * 0.30), (x + s - 4, y + s), (120, 92, 60))
        cv.line(x + s * 0.55, y + s * 0.12, x + s * 0.58, y + s * 0.45, (40, 26, 18), 2)
        cv.line(x + s * 0.58, y + s * 0.45, x + s * 0.52, y + s * 0.62, (40, 26, 18), 2)
        cv.rect(x + s * 0.42, y + s - 14, 12, 14, RED)
    elif kind == "bridge":
        cv.rect(x, y, s, s, NIGHT)
        for (sx, sy) in [(12, 12), (30, 22), (52, 10), (70, 26), (88, 14), (44, 34), (64, 40)]:
            cv.px(x + sx * s // 100, y + sy * s // 100, WHITE)
        cv.arc(x + s // 2, y + s, s // 2, 200, 340, (150, 150, 150), 3)
        cv.line(x + 8, y + s - 22, x + s - 8, y + s - 22, (150, 150, 150), 2)
        cv.triangle((x + s * 0.30, y + s - 22), (x + s * 0.38, y + s - 44), (x + s * 0.46, y + s - 22), (255, 140, 0))
        cv.triangle((x + s * 0.58, y + s - 22), (x + s * 0.66, y + s - 40), (x + s * 0.74, y + s - 22), (255, 180, 40))
        cv.circle(x + s * 0.20, y + s * 0.30, 2, (255, 220, 80))
        cv.circle(x + s * 0.75, y + s * 0.22, 2, (255, 220, 80))
        cv.line(x + s * 0.20, y + s * 0.30, x + s * 0.30, y + s * 0.36, (255, 220, 80), 1)
    elif kind == "chart":
        cv.rect(x, y, s, s, WHITE)
        for gx in range(1, 5):
            cv.vline(x + gx * s // 5, y + 6, y + s - 6, (220, 220, 220), 1)
        for gy in range(1, 4):
            cv.hline(x + 6, x + s - 6, y + gy * s // 4, (220, 220, 220), 1)
        pts = [(x + 8, y + 18), (x + 30, y + 24), (x + 48, y + 22), (x + 66, y + 38),
               (x + 84, y + 34), (x + 104, y + 52), (x + 128, y + 48), (x + 152, y + 66),
               (x + 176, y + 62), (x + 200, y + 84), (x + 230, y + 78), (x + 258, y + 100)]
        cv.polyline(pts, RED, 3)
        cv.line(x + 258, y + 100, x + 252, y + 96, RED, 2)
        cv.line(x + 258, y + 100, x + 252, y + 102, RED, 2)
    elif kind == "cop31":
        cv.rect(x, y, s, s, LIGHT)
        cv.circle(x + s // 2 - 4, y + s // 2, 18, (40, 110, 180))
        cv.polyfill([(x + 14, y + 18), (x + 24, y + 14), (x + 30, y + 22), (x + 20, y + 28)], (60, 160, 80))
        cv.polyfill([(x + 28, y + 34), (x + 36, y + 30), (x + 40, y + 38), (x + 30, y + 42)], (60, 160, 80))
        cv.rect(x + s - 20, y + 8, 14, 18, WHITE)
        cv.hline(x + s - 18, x + s - 8, y + 13, INK, 1)
        cv.hline(x + s - 18, x + s - 8, y + 17, INK, 1)
        cv.hline(x + s - 18, x + s - 8, y + 21, INK, 1)
    elif kind == "missile":
        cv.rect(x, y, s, s, (210, 190, 150))
        cv.line(x + 8, y + s - 10, x + s - 14, y + 12, (50, 50, 50), 3)
        cv.triangle((x + s - 14, y + 12), (x + s - 26, y + 10), (x + s - 16, y + 24), (50, 50, 50))
        cv.circle(x + 12, y + s - 14, 5, (150, 150, 150))
        cv.circle(x + 20, y + s - 20, 7, (170, 170, 170))
    elif kind == "star":
        cv.rect(x, y, s, s, DARKBG)
        cv.polyfill(star_pts(x + s // 2, y + s // 2, 20, 8), GOLD)
    elif kind == "ship":
        cv.rect(x, y, s, s, (16, 40, 70))
        cv.polyfill([(x + 8, y + 30), (x + s - 8, y + 30), (x + s - 14, y + 42), (x + 14, y + 42)], (120, 120, 120))
        cv.rect(x + 20, y + 22, 10, 8, (90, 90, 90))
        cv.circle(x + 16, y + 16, 5, (60, 60, 60))
        cv.circle(x + 24, y + 12, 6, (80, 80, 80))
        cv.triangle((x + 30, y + 30), (x + 36, y + 16), (x + 42, y + 30), (255, 140, 0))
    elif kind == "flags":
        cv.rect(x, y, s, s, LIGHT)
        cv.rect(x + 4, y + 10, 22, 16, (20, 60, 160))
        for a in range(12):
            ang = math.radians(a * 30)
            cv.px(int(x + 15 + 7 * math.cos(ang)), int(y + 18 + 6 * math.sin(ang)), GOLD)
        cv.rect(x + 28, y + 10, 20, 8, (200, 40, 40))
        cv.rect(x + 28, y + 18, 20, 8, WHITE)
        cv.rect(x + 4, y + 32, 44, 14, (200, 40, 40))
        cv.rect(x + 4, y + 32, 44, 4, (160, 20, 20))
    elif kind == "cross":
        cv.rect(x, y, s, s, WHITE)
        cv.rect(x + s // 2 - 6, y + 8, 12, 36, (200, 30, 30))
        cv.rect(x + 8, y + s // 2 - 6, 36, 12, (200, 30, 30))
    elif kind == "mercury":
        cv.rect(x, y, s, s, DARKBG)
        cv.circle(x + s // 2, y + s // 2 + 2, 16, (150, 120, 90))
        cv.circle(x + s // 2 - 5, y + s // 2 - 3, 3, (120, 95, 70))
        cv.circle(x + s // 2 + 6, y + s // 2 + 6, 2, (120, 95, 70))
        cv.rect(x + s - 16, y + 8, 8, 5, (200, 200, 200))
        cv.line(x + s - 16, y + 10, x + s // 2 + 12, y + s // 2 - 4, (200, 200, 200), 1)
    elif kind == "pill":
        cv.rect(x, y, s, s, WHITE)
        cx, cy = x + s // 2, y + s // 2
        cv.line(cx - 16, cy + 16, cx + 16, cy - 16, (200, 30, 30), 10)
        cv.line(cx - 16, cy + 16, cx, cy, (200, 30, 30), 10)
        cv.line(cx, cy, cx + 16, cy - 16, (240, 240, 240), 10)
        cv.line(cx - 16, cy + 16, cx + 16, cy - 16, INK, 1)
    elif kind == "flame":
        cv.rect(x, y, s, s, LIGHT)
        cv.polyfill([(x + s // 2, y + 6), (x + s - 10, y + 30), (x + s - 14, y + 44),
                     (x + 10, y + 44), (x + 6, y + 28)], (255, 120, 0))
        cv.polyfill([(x + s // 2, y + 22), (x + s - 14, y + 36), (x + s - 16, y + 44),
                     (x + 14, y + 44), (x + 12, y + 34)], (255, 200, 40))
    elif kind == "mic":
        cv.rect(x, y, s, s, DARKBG)
        cv.circle(x + s // 2, y + 18, 10, (220, 220, 220))
        cv.vline(x + s // 2, y + 28, y + 44, (200, 200, 200), 2)
        cv.arc(x + s // 2, y + 44, 8, 0, 180, (200, 200, 200), 2)
    elif kind == "lock":
        cv.rect(x, y, s, s, DARKBG)
        cv.arc(x + s // 2, y + 22, 9, 180, 360, GOLD, 3)
        cv.rect(x + s // 2 - 11, y + 22, 22, 18, GOLD)
        cv.circle(x + s // 2, y + 30, 3, DARKBG)
        cv.vline(x + s // 2, y + 30, y + 36, DARKBG, 2)
    elif kind == "mars":
        cv.rect(x, y, s, s, DARKBG)
        cv.circle(x + s // 2, y + s // 2 + 2, 16, (200, 90, 50))
        cv.circle(x + s // 2 - 5, y + s // 2 - 2, 4, (170, 70, 40))
        cv.circle(x + s // 2 + 6, y + s // 2 + 7, 3, (170, 70, 40))
        cv.rect(x + 8, y + s - 12, 12, 6, (180, 180, 180))


# ---------------------------------------------------------------- heroes + cards
def draw_heroes(cv):
    for i, h in enumerate(HEROES):
        x = 10 + i * 338
        w = 328
        # illustration box (scaled art: draw into a 328x104 area)
        _hero_art(cv, h["art"], x, 312, w, 104)
        draw_text(cv, x, 422, "%s \u00b7 %s" % (h["num"], h["region"]), 0.68, RED, bold=True)
        tw = text_w(h["tag"], 0.62)
        draw_text(cv, x + w - tw, 422, h["tag"], 0.62, INK)
        lines = wrap_text(h["head"], 1.3, w)
        yy = 436
        for ln in lines[:3]:
            draw_text(cv, x, yy, ln, 1.3, INK, bold=True)
            yy += 19
        for j, ln in enumerate(wrap_text(h["deck"], 0.62, w)[:3]):
            draw_text(cv, x, 496 + j * 10, ln, 0.62, SOFTINK)


def _hero_art(cv, kind, x, y, w, h):
    """Large hero illustration (328 x 112)."""
    if kind == "mountains":
        cv.rect(x, y, w, h, SKY)
        cv.circle(x + w - 40, y + 18, 10, GOLD)
        cv.triangle((x + 6, y + h), (x + 100, y + 20), (x + 200, y + h), (110, 82, 52))
        cv.triangle((x + 110, y + h), (x + 190, y + 8), (x + 290, y + h), (90, 66, 44))
        cv.triangle((x + 220, y + h), (x + 280, y + 34), (x + w - 6, y + h), (120, 92, 60))
        cv.line(x + 190, y + 8, x + 196, y + 52, (40, 26, 18), 2)
        cv.line(x + 196, y + 52, x + 184, y + 78, (40, 26, 18), 2)
        cv.rect(x + 140, y + h - 18, 16, 18, RED)
        cv.rect(x + 158, y + h - 12, 12, 12, (150, 40, 40))
    elif kind == "bridge":
        cv.rect(x, y, w, h, NIGHT)
        for (sx, sy) in [(20, 14), (60, 26), (110, 10), (160, 30), (210, 12), (260, 24), (300, 16), (90, 40), (180, 44)]:
            cv.px(x + sx, y + sy, WHITE)
        cv.arc(x + w // 2, y + h + 30, 150, 205, 335, (150, 150, 150), 3)
        cv.line(x + 10, y + h - 26, x + w - 10, y + h - 26, (150, 150, 150), 2)
        cv.triangle((x + 110, y + h - 26), (x + 122, y + h - 58), (x + 134, y + h - 26), (255, 140, 0))
        cv.triangle((x + 200, y + h - 26), (x + 212, y + h - 50), (x + 224, y + h - 26), (255, 180, 40))
        for (dx, dy) in [(70, 40), (150, 28), (250, 36), (290, 24)]:
            cv.circle(x + dx, y + dy, 2, (255, 220, 80))
            cv.line(x + dx, y + dy, x + dx + 12, y + dy + 6, (255, 220, 80), 1)
    elif kind == "chart":
        cv.rect(x, y, w, h, WHITE)
        for gx in range(1, 6):
            cv.vline(x + gx * w // 6, y + 8, y + h - 8, (225, 225, 225), 1)
        for gy in range(1, 4):
            cv.hline(x + 8, x + w - 8, y + gy * h // 4, (225, 225, 225), 1)
        pts = [(x + 10, y + 22), (x + 45, y + 28), (x + 75, y + 24), (x + 105, y + 44),
               (x + 135, y + 38), (x + 165, y + 58), (x + 195, y + 52), (x + 225, y + 74),
               (x + 255, y + 68), (x + 285, y + 90), (x + 315, y + 84)]
        cv.polyline(pts, RED, 3)
        cv.line(x + 315, y + 84, x + 306, y + 79, RED, 2)
        cv.line(x + 315, y + 84, x + 306, y + 88, RED, 2)


def draw_cards(cv):
    for idx, (num, region, tag, head, deck, art) in enumerate(CARDS):
        row, col = divmod(idx, 4)
        x = 10 + col * 253
        yy = 526 + row * 82
        draw_text(cv, x, yy, "%d. %s" % (num, region), 0.62, RED, bold=True)
        tw = text_w(tag, 0.58)
        draw_text(cv, x + 245 - tw, yy, tag, 0.58, INK)
        draw_art(cv, art, x, yy + 14, 52)
        tx = x + 60
        for j, ln in enumerate(wrap_text(head, 0.95, 185)[:2]):
            draw_text(cv, tx, yy + 16 + j * 13, ln, 0.95, INK, bold=True)
        for j, ln in enumerate(wrap_text(deck, 0.66, 185)[:2]):
            draw_text(cv, tx, yy + 44 + j * 10, ln, 0.66, SOFTINK)

# ---------------------------------------------------------------- map + also + footer
CONTINENTS = [
    # North America
    [(20, 15), (60, 5), (110, 10), (130, 20), (120, 35), (90, 45), (60, 50), (30, 40), (15, 28)],
    # Greenland
    [(135, 6), (150, 4), (155, 12), (142, 16), (134, 12)],
    # South America
    [(85, 55), (115, 52), (125, 65), (110, 85), (95, 80), (85, 65)],
    # Europe
    [(225, 15), (250, 8), (270, 15), (265, 30), (245, 32), (230, 25)],
    # Africa
    [(235, 40), (260, 38), (275, 48), (265, 70), (245, 72), (232, 55)],
    # Asia
    [(275, 10), (340, 5), (420, 12), (460, 25), (440, 45), (380, 50), (320, 45), (290, 30), (275, 20)],
    # SE Asia islands
    [(390, 60), (400, 58), (404, 64), (394, 66)],
    [(408, 64), (418, 62), (422, 68), (410, 70)],
    # Australia
    [(410, 72), (445, 70), (455, 78), (430, 86), (410, 82)],
]

PIN_XY = {1: (95, 62), 2: (258, 20), 3: (118, 28), 4: (268, 30), 5: (292, 42),
          6: (58, 42), 7: (252, 10), 8: (392, 64), 9: (108, 70), 12: (408, 74),
          13: (246, 14), 14: (122, 32), 15: (468, 88)}


def draw_map(cv):
    draw_text(cv, 10, 770, "WHERE IT HAPPENED \u2014 13 PINS", 0.95, RED, bold=True)
    ox, oy, mw, mh = 10, 790, 490, 94
    cv.rect(ox, oy, mw, mh, OCEAN)
    for poly in CONTINENTS:
        cv.polyfill([(ox + px, oy + py) for (px, py) in poly], LAND)
    for num, _name in MAP_PINS:
        px, py = PIN_XY[num]
        cv.circle(ox + px, oy + py, 7, RED)
        draw_text(cv, ox + px, oy + py - 4, str(num), 0.58, WHITE, bold=True, align='center')
    lines = ["1 Junin \u00b7 2 Kyiv \u00b7 3 New York \u00b7 4 Antalya \u00b7 5 Bahrain \u00b7 "
             "6 Sinaloa \u00b7 7 Finland \u00b7 8 Jakarta",
             "9 Brazil \u00b7 12 Cikande \u00b7 13 Copenhagen \u00b7 14 Washington \u00b7 15 Mars*",
             "* off-world \u00b7 10 BepiColombo + 11 pill trial are global, no pin."]
    for j, ln in enumerate(lines):
        draw_text(cv, 10, 888 + j * 9, ln, 0.58, SOFTINK)


def draw_also(cv):
    draw_text(cv, 510, 770, "ALSO \u2014 20 MORE STORIES", 0.95, RED, bold=True)
    for col, items in ((0, ALSO_LEFT), (1, ALSO_RIGHT)):
        x = 510 + col * 255
        for i, item in enumerate(items):
            y = 790 + i * 11
            cv.circle(x + 3, y + 4, 2, RED)
            sc = fit_scale(item, 0.66, 240)
            draw_text(cv, x + 9, y, item, sc, INK)


def draw_datecheck(cv):
    cv.rect(10, 916, 1004, 68, RED)  # border via filled rects below is simpler
    cv.rect(12, 918, 1000, 64, PAPER)
    draw_text(cv, 20, 924, "DATE CHECK \u2014 WHAT WE LEFT OUT ON PURPOSE", 0.95, RED, bold=True)
    draw_text(cv, 20, 944, "NOT 21 NOV: PIF strike (19 Nov) \u00b7 Nvidia results (17 Nov) \u00b7 "
              "Voyager 1 light-day (18 Nov) \u00b7 Anthropic $81.3bn IPO (19 Nov) \u00b7 "
              "EU \u20ac45bn Ukraine loan (19 Nov).", 0.7, INK)
    draw_text(cv, 20, 962, "NOT YET: COP31 final deal (talks run on) \u00b7 Spain votes 29 Nov.",
              0.7, INK)


def draw_footer(cv):
    draw_text(cv, 512, 988, "Sources: Reuters, AP, AFP, BBC, USGS, ESA, NYSE, France 24, "
              "DW, Guardian, NASA.", 0.58, SOFTINK, align='center')
    draw_text(cv, 512, 998, "CONFIRMED = reported by the named source \u00b7 REPORTED = one "
              "side\u2019s account, not yet confirmed \u00b7 CLAIM = an unverified claim.",
              0.58, SOFTINK, align='center')
    draw_text(cv, 512, 1008, "Drawn in code \u00b7 35 stories \u00b7 3 leads, 12 pictures, "
              "20 briefs \u00b7 7 regions \u00b7 UTC timeline \u00b7 date-checked",
              0.58, SOFTINK, align='center')


def main():
    cv = Canvas(W, H, PAPER)
    draw_header(cv)
    draw_numbers(cv)
    draw_timeline(cv)
    draw_heroes(cv)
    draw_cards(cv)
    draw_map(cv)
    draw_also(cv)
    draw_datecheck(cv)
    draw_footer(cv)
    outdir = os.environ.get("MAKEFUN_OUTPUT_DIR", "")
    path = os.path.join(outdir, "entry.png") if outdir else "entry.png"
    try:
        n = write_png(cv, path)
    except OSError:
        path = "entry.png"
        n = write_png(cv, path)
    print("wrote %s %d bytes" % (path, n))


if __name__ == "__main__":
    main()
