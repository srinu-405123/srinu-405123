#!/usr/bin/env python3
"""Cinematic 9:16 Lord Venkateshwara video with Ken Burns stills and lyrics."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

ROOT = Path("/workspace")
STILLS = ROOT / "assets" / "stills"
OUT = ROOT / "output" / "venkateshwara-swami.mp4"
AUDIO = ROOT / "output" / "srinivasa-govinda.wav"

W, H = 1080, 1920
FPS = 30
DURATION = 88.0

FONT_SERIF = "/usr/share/fonts/truetype/noto/NotoSerif-Regular.ttf"
FONT_SERIF_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"
FONT_DEV = "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Bold.ttf"
FONT_TE = "/usr/share/fonts/truetype/noto/NotoSerifTelugu-Bold.ttf"

GOLD = (232, 196, 106, 255)
CREAM = (255, 248, 230, 255)
SOFT = (255, 236, 200, 230)


def font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)


def load_cover(path: Path, overscan: float = 1.22) -> np.ndarray:
    im = Image.open(path).convert("RGB")
    im = ImageEnhance.Color(im).enhance(1.12)
    im = ImageEnhance.Contrast(im).enhance(1.08)
    im = ImageEnhance.Brightness(im).enhance(1.04)
    tw, th = int(W * overscan), int(H * overscan)
    scale = max(tw / im.width, th / im.height)
    nw, nh = int(im.width * scale), int(im.height * scale)
    im = im.resize((nw, nh), Image.Resampling.LANCZOS)
    return np.asarray(im, dtype=np.uint8)


def ken_burns(img: np.ndarray, t: float, duration: float, mode: str) -> np.ndarray:
    """t in 0..1 through the clip. Returns WxH uint8."""
    ih, iw = img.shape[:2]
    z0, z1 = 1.0, 1.16
    if mode == "out":
        z0, z1 = 1.16, 1.0
    if mode == "right":
        z0 = z1 = 1.08
    zoom = z0 + (z1 - z0) * t
    cw, ch = int(W * zoom), int(H * zoom)
    cw = min(cw, iw)
    ch = min(ch, ih)
    if mode == "right":
        x = int((iw - cw) * t)
        y = (ih - ch) // 2
    elif mode == "left":
        x = int((iw - cw) * (1 - t))
        y = (ih - ch) // 2
    elif mode == "up":
        x = (iw - cw) // 2
        y = int((ih - ch) * (1 - t))
    else:
        x = (iw - cw) // 2
        y = (ih - ch) // 2
    x = max(0, min(x, iw - cw))
    y = max(0, min(y, ih - ch))
    crop = img[y : y + ch, x : x + cw]
    frame = np.array(
        Image.fromarray(crop).resize((W, H), Image.Resampling.BILINEAR),
        dtype=np.uint8,
    )
    return frame


def vignette_mask() -> np.ndarray:
    ys, xs = np.mgrid[0:H, 0:W]
    cx, cy = W / 2, H / 2
    r = np.sqrt(((xs - cx) / (W * 0.72)) ** 2 + ((ys - cy) / (H * 0.72)) ** 2)
    v = np.clip(1.15 - 0.55 * r, 0.35, 1.0)
    return v.astype(np.float32)


VIGNETTE = None  # filled in main


def apply_vignette(frame: np.ndarray) -> np.ndarray:
    f = frame.astype(np.float32) * VIGNETTE[:, :, None]
    return np.clip(f, 0, 255).astype(np.uint8)


def text_size(draw: ImageDraw.ImageDraw, text: str, fnt) -> tuple[int, int]:
    b = draw.textbbox((0, 0), text, font=fnt)
    return b[2] - b[0], b[3] - b[1]


def draw_centered(draw, y, text, fnt, fill, stroke=2, stroke_fill=(20, 12, 0, 200)):
    dummy = draw
    tw, th = text_size(dummy, text, fnt)
    x = (W - tw) // 2
    draw.text(
        (x, y),
        text,
        font=fnt,
        fill=fill,
        stroke_width=stroke,
        stroke_fill=stroke_fill,
    )
    return th


def make_overlay(kind: str, lines: list[tuple[str, str, int]]) -> Image.Image:
    """lines: (font_key, text, size)"""
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(ov)
    fonts = {
        "serif": lambda s: font(FONT_SERIF, s),
        "bold": lambda s: font(FONT_SERIF_BOLD, s),
        "dev": lambda s: font(FONT_DEV, s),
        "te": lambda s: font(FONT_TE, s),
    }

    if kind == "title":
        # top sacred mark + title block in lower third
        draw_centered(draw, 220, "ॐ", fonts["dev"](140), GOLD, stroke=1)
        draw_centered(draw, 420, "Śrī Venkateśvara", fonts["bold"](64), CREAM, stroke=3)
        draw_centered(draw, 510, "Om Namo Venkatesaya", fonts["serif"](40), GOLD, stroke=2)
        # bottom caption
        bar_y = H - 280
        draw.rectangle([(80, bar_y), (W - 80, bar_y + 3)], fill=GOLD)
        draw_centered(draw, bar_y + 24, "Srinivasa Govinda", fonts["bold"](42), CREAM)
        draw_centered(draw, bar_y + 84, "an original bhajan", fonts["serif"](28), SOFT, stroke=1)
        return ov

    # lyric card in lower third
    block_h = 280
    y0 = H - 420
    shade = Image.new("RGBA", (W, block_h + 80), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shade)
    for i in range(block_h + 80):
        a = int(150 * (i / (block_h + 80)) ** 0.7)
        sd.line([(0, i), (W, i)], fill=(8, 4, 0, a))
    ov.alpha_composite(shade, (0, y0 - 40))
    draw = ImageDraw.Draw(ov)
    draw.rectangle([(160, y0), (W - 160, y0 + 3)], fill=GOLD)

    y = y0 + 28
    for key, text, size in lines:
        th = draw_centered(draw, y, text, fonts[key](size), CREAM if key != "te" else GOLD, stroke=2)
        y += th + 10
    return ov


def overlay_alpha(frame: np.ndarray, overlay: Image.Image, opacity: float) -> np.ndarray:
    if opacity <= 0:
        return frame
    if opacity < 1:
        ov = overlay.copy()
        a = np.array(ov.split()[-1], dtype=np.float32) * opacity
        ov.putalpha(Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)))
    else:
        ov = overlay
    base = Image.fromarray(frame).convert("RGBA")
    base.alpha_composite(ov)
    return np.array(base.convert("RGB"), dtype=np.uint8)


SCENES = [
    # start, end, file, ken-burns mode
    (0.0, 8.5, "05-celestial-symbols.png", "in"),
    (7.5, 17.0, "04-deity-close.png", "in"),
    (16.0, 25.5, "01-shrine-night.png", "out"),
    (24.5, 34.0, "02-tirumala-mural.png", "right"),
    (33.0, 42.5, "06-golden-path.png", "left"),
    (41.5, 51.0, "03-gopuram-night.png", "up"),
    (50.0, 59.0, "10-deity-pavilion.png", "in"),
    (58.0, 67.0, "09-gopuram-low-angle.png", "out"),
    (66.0, 75.0, "07-temple-courtyard.png", "in"),
    (74.0, 88.0, "08-lotus-om.png", "out"),
]

# Lyrics windows: (start, end, overlay kind, lines)
LYRICS = [
    (0.0, 7.2, "title", []),
    (
        8.0,
        15.6,
        "lyric",
        [("dev", "ॐ नमो वेङ्कटेशाय", 52), ("serif", "Om Namo Venkatesaya", 36)],
    ),
    (
        16.0,
        23.6,
        "lyric",
        [("te", "గోవిందా గోవిందా", 48), ("serif", "Govinda   Govinda", 36)],
    ),
    (
        24.0,
        31.6,
        "lyric",
        [("te", "శ్రీనివాస గోవిందా", 48), ("serif", "Srinivasa Govinda", 36)],
    ),
    (
        32.0,
        39.6,
        "lyric",
        [("serif", "Tirumala giri vaasa", 40), ("serif", "Jyothi swaroopa", 34)],
    ),
    (
        40.0,
        47.6,
        "lyric",
        [("dev", "ॐ नमो वेङ्कटेशाय", 52), ("serif", "Om Namo Venkatesaya", 36)],
    ),
    (
        48.0,
        55.6,
        "lyric",
        [("serif", "Shankha chakra dhara", 40), ("serif", "Bhakta vatsala", 34)],
    ),
    (
        56.0,
        63.6,
        "lyric",
        [("te", "గోవిందా గోవిందా", 48), ("serif", "Govinda   Govinda", 36)],
    ),
    (
        64.0,
        71.6,
        "lyric",
        [("te", "శ్రీనివాస గోవిందా", 48), ("serif", "Srinivasa Govinda", 36)],
    ),
    (
        72.5,
        80.0,
        "lyric",
        [("dev", "गोविन्द गोविन्द", 52), ("serif", "Govinda Govinda", 36)],
    ),
    (
        81.0,
        88.0,
        "lyric",
        [("dev", "ॐ", 90), ("serif", "Hari Om", 40)],
    ),
]


def fade_weight(t: float, start: float, end: float, fade: float = 0.7) -> float:
    if t < start or t > end:
        return 0.0
    if t < start + fade:
        return (t - start) / fade
    if t > end - fade:
        return (end - t) / fade
    return 1.0


def main() -> None:
    global VIGNETTE
    VIGNETTE = vignette_mask()

    if not AUDIO.exists():
        sys.exit(f"Missing audio: {AUDIO}")

    print("Loading stills...")
    cache: dict[str, np.ndarray] = {}
    for _, _, name, _ in SCENES:
        if name not in cache:
            path = STILLS / name
            if not path.exists():
                sys.exit(f"Missing still: {path}")
            print(f"  {name}")
            cache[name] = load_cover(path)

    print("Baking lyric overlays...")
    baked: list[tuple[float, float, Image.Image]] = []
    for start, end, kind, lines in LYRICS:
        ov = make_overlay(kind, lines)
        baked.append((start, end, ov))

    nframes = int(DURATION * FPS)
    OUT.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-s",
        f"{W}x{H}",
        "-r",
        str(FPS),
        "-i",
        "pipe:0",
        "-i",
        str(AUDIO),
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-crf",
        "17",
        "-preset",
        "medium",
        "-tune",
        "film",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-shortest",
        "-movflags",
        "+faststart",
        str(OUT),
    ]
    print("Encoding", OUT)
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    assert proc.stdin is not None

    try:
        for i in range(nframes):
            t = i / FPS
            acc = np.zeros((H, W, 3), dtype=np.float32)
            wsum = 0.0
            for s0, s1, name, mode in SCENES:
                w = fade_weight(t, s0, s1, fade=1.05)
                if w <= 0:
                    continue
                local = (t - s0) / max(0.001, s1 - s0)
                fr = ken_burns(cache[name], local, s1 - s0, mode)
                acc += fr.astype(np.float32) * w
                wsum += w
            if wsum <= 0:
                frame = np.zeros((H, W, 3), dtype=np.uint8)
            else:
                frame = np.clip(acc / wsum, 0, 255).astype(np.uint8)
            frame = apply_vignette(frame)

            # global fade in/out
            g = 1.0
            if t < 1.2:
                g = t / 1.2
            elif t > DURATION - 2.8:
                g = max(0.0, (DURATION - t) / 2.8)
            if g < 1:
                frame = (frame.astype(np.float32) * g).astype(np.uint8)

            for s0, s1, ov in baked:
                ow = fade_weight(t, s0, s1, fade=0.55)
                if ow > 0:
                    frame = overlay_alpha(frame, ov, ow)

            proc.stdin.write(frame.tobytes())
            if i % 90 == 0:
                print(f"  {t:5.1f}s / {DURATION:.0f}s", flush=True)
        proc.stdin.close()
        stderr = proc.stderr.read().decode("utf-8", errors="replace") if proc.stderr else ""
        code = proc.wait()
        if code != 0:
            print(stderr[-4000:])
            sys.exit(code)
        print("Done:", OUT, "size", OUT.stat().st_size)
    except BrokenPipeError:
        stderr = proc.stderr.read().decode("utf-8", errors="replace") if proc.stderr else ""
        print(stderr[-4000:])
        raise


if __name__ == "__main__":
    main()
