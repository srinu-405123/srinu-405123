#!/usr/bin/env python3
"""Natural photo finish: keep the original scene, make it look clean and rich."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter
from scipy.ndimage import gaussian_filter

SRC = Path("/opt/cursor/artifacts/assets")
OUT = Path("/workspace/assets/originals")
ART = Path("/opt/cursor/artifacts")


def f32(im: Image.Image) -> np.ndarray:
    return np.asarray(im.convert("RGB"), dtype=np.float32) / 255.0


def img(arr: np.ndarray) -> Image.Image:
    return Image.fromarray(np.clip(arr * 255.0, 0, 255).astype(np.uint8), "RGB")


def luma(rgb: np.ndarray) -> np.ndarray:
    return 0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]


def denoise_darks(rgb: np.ndarray) -> np.ndarray:
    y = luma(rgb)
    w = np.clip((0.16 - y) / 0.16, 0, 1)[..., None]
    blur = np.empty_like(rgb)
    for c in range(3):
        blur[..., c] = gaussian_filter(rgb[..., c], sigma=1.35)
    # pull noisy sky toward deep night, keep structure
    night = np.array([0.01, 0.012, 0.02], dtype=np.float32)
    cleaned = rgb * (1 - w * 0.55) + blur * (w * 0.35) + night * (w * 0.20)
    return np.clip(cleaned, 0, 1)


def recover_highlights(rgb: np.ndarray) -> np.ndarray:
    y = luma(rgb)
    h = np.clip((y - 0.78) / 0.22, 0, 1)[..., None]
    return np.clip(rgb * (1 - h * 0.22) + np.power(np.maximum(rgb, 1e-6), 1.12) * h * 0.22, 0, 1)


def gentle_curve(rgb: np.ndarray) -> np.ndarray:
    x = np.clip(rgb, 0, 1)
    # mild S-curve
    return np.clip(x + 0.10 * (x - 0.5) * (1 - (2 * x - 1) ** 2), 0, 1)


def lift_shadows(rgb: np.ndarray) -> np.ndarray:
    y = luma(rgb)
    s = np.clip((0.28 - y) / 0.28, 0, 1)[..., None]
    return np.clip(rgb + 0.035 * s, 0, 1)


def warm_lights(rgb: np.ndarray) -> np.ndarray:
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    y = luma(rgb)
    gold = np.clip((r - b) * 1.8, 0, 1) * np.clip(y * 1.2, 0, 1)
    gold = gold[..., None]
    boost = rgb.copy()
    boost[..., 0] = np.clip(boost[..., 0] * 1.08, 0, 1)
    boost[..., 1] = np.clip(boost[..., 1] * 1.02, 0, 1)
    boost[..., 2] = np.clip(boost[..., 2] * 0.90, 0, 1)
    return np.clip(rgb * (1 - gold * 0.28) + boost * (gold * 0.28), 0, 1)


def unsharp(rgb: np.ndarray, radius=0.9, amount=0.55) -> np.ndarray:
    blur = np.empty_like(rgb)
    for c in range(3):
        blur[..., c] = gaussian_filter(rgb[..., c], sigma=radius)
    detail = rgb - blur
    y = luma(rgb)
    w = np.clip((y - 0.07) / 0.22, 0, 1)[..., None]
    return np.clip(rgb + detail * amount * w, 0, 1)


def light_bloom(rgb: np.ndarray) -> np.ndarray:
    y = luma(rgb)
    mask = np.clip((y - 0.78) / 0.22, 0, 1)[..., None]
    glow = np.empty_like(rgb)
    for c in range(3):
        glow[..., c] = gaussian_filter((rgb * mask)[..., c], sigma=5.5)
    return np.clip(1 - (1 - rgb) * (1 - glow * 0.16), 0, 1)


def enhance(path: Path, scale: float = 2.0) -> Image.Image:
    im = Image.open(path).convert("RGB")
    nw, nh = int(im.width * scale), int(im.height * scale)
    nw -= nw % 2
    nh -= nh % 2
    im = im.resize((nw, nh), Image.Resampling.LANCZOS)
    im = im.filter(ImageFilter.MedianFilter(size=3))
    rgb = f32(im)
    rgb = denoise_darks(rgb)
    rgb = recover_highlights(rgb)
    rgb = lift_shadows(rgb)
    rgb = warm_lights(rgb)
    rgb = gentle_curve(rgb)
    rgb = light_bloom(rgb)
    rgb = unsharp(rgb)
    out = img(rgb)
    out = ImageEnhance.Color(out).enhance(1.10)
    out = ImageEnhance.Contrast(out).enhance(1.05)
    out = ImageEnhance.Sharpness(out).enhance(1.10)
    out = ImageEnhance.Brightness(out).enhance(1.03)
    return out


def save(im: Image.Image, stem: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    png = OUT / f"{stem}.png"
    jpg = OUT / f"{stem}.jpg"
    im.save(png, "PNG", optimize=True)
    im.save(jpg, "JPEG", quality=94, subsampling=0, optimize=True)
    im.save(ART / f"{stem}.png", "PNG", optimize=True)
    im.save(ART / f"{stem}.jpg", "JPEG", quality=94, subsampling=0, optimize=True)
    print(f"wrote {png.name} {im.size}")


def main() -> None:
    jobs = [
        ("original-shrine-pond-night.png", "my-shrine-original", "my-shrine-edited"),
        ("original-gopuram-night.png", "my-gopuram-original", "my-gopuram-edited"),
        ("original-gopuram-courtyard.png", "my-courtyard-original", "my-courtyard-edited"),
    ]
    for src_name, orig_stem, edit_stem in jobs:
        src = SRC / src_name
        raw = Image.open(src).convert("RGB")
        # keep a true original copy (as shot)
        OUT.mkdir(parents=True, exist_ok=True)
        raw.save(OUT / f"{orig_stem}.jpg", "JPEG", quality=94, subsampling=0)
        raw.save(ART / f"{orig_stem}.jpg", "JPEG", quality=94, subsampling=0)
        print("enhancing", src_name)
        save(enhance(src), edit_stem)


if __name__ == "__main__":
    main()
