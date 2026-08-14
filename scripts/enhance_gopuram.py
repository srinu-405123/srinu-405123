#!/usr/bin/env python3
"""Museum-grade night-photo finish for the Tirumala gopuram stills."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter
from scipy.ndimage import gaussian_filter

ROOT = Path("/workspace")
SRC_DIR = Path("/opt/cursor/artifacts/assets")
OUT_DIR = ROOT / "assets" / "enhanced"
ART = Path("/opt/cursor/artifacts")


def to_f(im: Image.Image) -> np.ndarray:
    return np.asarray(im.convert("RGB"), dtype=np.float32) / 255.0


def to_img(arr: np.ndarray) -> Image.Image:
    return Image.fromarray(np.clip(arr * 255.0, 0, 255).astype(np.uint8), "RGB")


def luma(rgb: np.ndarray) -> np.ndarray:
    return 0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]


def s_curve(x: np.ndarray, contrast: float = 1.18) -> np.ndarray:
    # contrast around mid-gray via smoothstep-ish power
    x = np.clip(x, 0, 1)
    return np.clip(0.5 + (x - 0.5) * contrast, 0, 1)


def crush_blacks(rgb: np.ndarray, floor: float = 0.018, gamma: float = 0.92) -> np.ndarray:
    y = luma(rgb)
    sky = np.clip((0.12 - y) / 0.12, 0, 1)[..., None]
    # near-black sky: denoise toward pure night
    night = np.array([0.004, 0.006, 0.012], dtype=np.float32)
    rgb = rgb * (1 - sky * 0.92) + night * (sky * 0.92)
    rgb = np.clip(rgb, 0, 1)
    rgb = np.power(np.maximum(rgb, 1e-6), gamma)
    rgb = np.clip((rgb - floor) / (1 - floor), 0, 1)
    return rgb


def warm_golds(rgb: np.ndarray) -> np.ndarray:
    y = luma(rgb)
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    gold = np.clip((r - b) * 2.2, 0, 1) * np.clip(y * 1.4, 0, 1)
    gold = gold[..., None]
    boost = np.array([1.10, 0.98, 0.72], dtype=np.float32)
    rgb = rgb * (1 - gold * 0.35) + (rgb * boost) * (gold * 0.35)
    return np.clip(rgb, 0, 1)


def cool_stone(rgb: np.ndarray) -> np.ndarray:
    y = luma(rgb)
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    # bright near-neutral stone -> slightly cooler, cleaner white
    sat = np.maximum(np.maximum(r, g), b) - np.minimum(np.minimum(r, g), b)
    stone = np.clip((y - 0.35) * 2.4, 0, 1) * np.clip(1.0 - sat * 3.5, 0, 1)
    stone = stone[..., None]
    cool = rgb.copy()
    cool[..., 0] *= 0.97
    cool[..., 2] = np.clip(cool[..., 2] * 1.06, 0, 1)
    return np.clip(rgb * (1 - stone * 0.45) + cool * (stone * 0.45), 0, 1)


def bloom(rgb: np.ndarray, thresh: float = 0.72, sigma: float = 9.0, amount: float = 0.28) -> np.ndarray:
    y = luma(rgb)
    mask = np.clip((y - thresh) / (1 - thresh), 0, 1)[..., None]
    lights = rgb * mask
    glow = np.empty_like(rgb)
    for c in range(3):
        glow[..., c] = gaussian_filter(lights[..., c], sigma=sigma)
    # screen
    out = 1 - (1 - rgb) * (1 - glow * amount)
    return np.clip(out, 0, 1)


def unsharp(rgb: np.ndarray, radius: float = 1.15, amount: float = 0.85, threshold: float = 0.012) -> np.ndarray:
    blur = np.empty_like(rgb)
    for c in range(3):
        blur[..., c] = gaussian_filter(rgb[..., c], sigma=radius)
    detail = rgb - blur
    y = luma(rgb)
    # less sharpening in the sky
    w = np.clip((y - 0.08) / 0.25, 0, 1)[..., None]
    apply = (np.abs(detail).mean(axis=2, keepdims=True) > threshold).astype(np.float32)
    return np.clip(rgb + detail * amount * w * apply, 0, 1)


def vignette(rgb: np.ndarray, strength: float = 0.22) -> np.ndarray:
    h, w = rgb.shape[:2]
    ys, xs = np.mgrid[0:h, 0:w]
    cy, cx = h / 2.05, w / 2.0
    r = np.sqrt(((xs - cx) / (w * 0.78)) ** 2 + ((ys - cy) / (h * 0.82)) ** 2)
    v = np.clip(1.0 - strength * np.clip(r - 0.55, 0, 1) ** 1.4, 0.62, 1.0)
    return np.clip(rgb * v[..., None], 0, 1)


def enhance(path: Path, scale: float = 2.25) -> Image.Image:
    im = Image.open(path).convert("RGB")
    nw, nh = int(im.width * scale), int(im.height * scale)
    # even dimensions for video-friendly stills
    nw -= nw % 2
    nh -= nh % 2
    im = im.resize((nw, nh), Image.Resampling.LANCZOS)
    im = im.filter(ImageFilter.MedianFilter(size=3))
    rgb = to_f(im)
    rgb = crush_blacks(rgb)
    rgb = cool_stone(rgb)
    rgb = warm_golds(rgb)
    rgb = s_curve(rgb, 1.16)
    rgb = bloom(rgb, thresh=0.68, sigma=max(6.0, nw / 220), amount=0.32)
    rgb = unsharp(rgb, radius=1.05, amount=0.78)
    rgb = vignette(rgb, 0.18)
    out = to_img(rgb)
    out = ImageEnhance.Color(out).enhance(1.08)
    out = ImageEnhance.Contrast(out).enhance(1.04)
    out = ImageEnhance.Sharpness(out).enhance(1.12)
    return out


def save(im: Image.Image, stem: str) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    png = OUT_DIR / f"{stem}.png"
    jpg = OUT_DIR / f"{stem}.jpg"
    im.save(png, "PNG", optimize=True)
    im.save(jpg, "JPEG", quality=95, subsampling=0, optimize=True)
    im.save(ART / f"{stem}.png", "PNG", optimize=True)
    im.save(ART / f"{stem}.jpg", "JPEG", quality=95, subsampling=0, optimize=True)
    print(f"wrote {png} {im.size}  jpg={jpg.stat().st_size/1e6:.1f}MB")


def main() -> None:
    pairs = [
        (SRC_DIR / "gopuram-hq-hero.png", "tirumala-gopuram-night-enhanced"),
        (SRC_DIR / "gopuram-hq-cinematic.png", "tirumala-gopuram-lowangle-enhanced"),
    ]
    for src, stem in pairs:
        print("enhancing", src.name)
        save(enhance(src), stem)


if __name__ == "__main__":
    main()
