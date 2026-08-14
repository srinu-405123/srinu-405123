#!/usr/bin/env python3
"""Original Carnatic-inspired bhajan: Srinivasa Govinda.

Public-domain mantras (Om Namo Venkatesaya, Govinda) with an original
Mohanam-raga melody. No copyrighted film or commercial song is used.
"""

from __future__ import annotations

import math
import wave
from pathlib import Path

import numpy as np
from scipy.signal import fftconvolve

SR = 44100
BPM = 70.0
BEAT = 60.0 / BPM

# Mohanam: S R2 G3 P D2  (Sa = D3 for tanpura, melody around D4)
SA = 146.83  # D3
NOTES = {
    "S,": SA,
    "R,": SA * 9 / 8,
    "G,": SA * 5 / 4,
    "P,": SA * 3 / 2,
    "D,": SA * 5 / 3,
    "S": SA * 2,
    "R": SA * 2 * 9 / 8,
    "G": SA * 2 * 5 / 4,
    "P": SA * 2 * 3 / 2,
    "D": SA * 2 * 5 / 3,
    "S'": SA * 4,
    "R'": SA * 4 * 9 / 8,
    "G'": SA * 4 * 5 / 4,
    "P'": SA * 4 * 3 / 2,
}


def midi_like(name: str) -> float:
    return NOTES[name]


def adsr(n: int, a: float, d: float, s: float, r: float) -> np.ndarray:
    na, nd, nr = int(a * n), int(d * n), int(r * n)
    ns = max(0, n - na - nd - nr)
    env = np.concatenate(
        [
            np.linspace(0, 1, max(1, na), endpoint=False),
            np.linspace(1, s, max(1, nd), endpoint=False),
            np.full(max(1, ns), s),
            np.linspace(s, 0, max(1, nr)),
        ]
    )
    if len(env) < n:
        env = np.pad(env, (0, n - len(env)))
    return env[:n]


def tanh_soft(x: np.ndarray, gain: float = 1.0) -> np.ndarray:
    return np.tanh(x * gain)


def mix_at(buf: np.ndarray, sig: np.ndarray, t: float, gain: float = 1.0) -> None:
    i0 = int(t * SR)
    i1 = min(len(buf), i0 + len(sig))
    if i0 >= len(buf) or i1 <= i0:
        return
    buf[i0:i1] += sig[: i1 - i0] * gain


def stereo_pan(mono: np.ndarray, pan: float) -> np.ndarray:
    """pan -1 left, +1 right."""
    left = math.sqrt(0.5 * (1 - pan))
    right = math.sqrt(0.5 * (1 + pan))
    return np.stack([mono * left, mono * right], axis=1)


def reverb(st: np.ndarray, decay: float = 1.6) -> np.ndarray:
    out = st.copy()
    delays = [0.029, 0.037, 0.053, 0.079, 0.107, 0.137]
    gains = [0.42, 0.36, 0.30, 0.24, 0.18, 0.14]
    for d, g in zip(delays, gains):
        n = int(d * SR)
        padded = np.vstack([np.zeros((n, 2)), st * g])
        out += padded[: len(out)]
    # simple tail
    tail_n = int(0.25 * SR)
    kernel = np.exp(-np.linspace(0, decay, tail_n)).astype(np.float64)
    kernel /= kernel.sum()
    for ch in range(2):
        out[:, ch] = fftconvolve(out[:, ch], kernel, mode="same")
    return out


def tanpura_pluck(freq: float, dur: float) -> np.ndarray:
    n = int(dur * SR)
    t = np.arange(n) / SR
    # inharmonic buzzing strings
    sig = np.zeros(n)
    partials = [
        (1.0, 1.00, 1.8),
        (0.45, 2.003, 2.4),
        (0.22, 3.01, 3.0),
        (0.12, 4.02, 3.6),
        (0.07, 5.04, 4.2),
        (0.04, 6.07, 5.0),
        (0.03, 7.1, 5.5),
    ]
    for amp, ratio, decay in partials:
        env = np.exp(-t * decay)
        # slight chorus
        det = 1 + 0.0015 * np.sin(2 * math.pi * 0.7 * t)
        sig += amp * env * np.sin(2 * math.pi * freq * ratio * det * t)
    # jawari buzz
    buzz = 0.04 * np.sign(np.sin(2 * math.pi * freq * t)) * np.exp(-t * 2.5)
    env = adsr(n, 0.002, 0.08, 0.55, 0.55)
    return tanh_soft(sig + buzz) * env


def flute_note(freq: float, dur: float, vol: float = 0.22) -> np.ndarray:
    n = int(dur * SR)
    t = np.arange(n) / SR
    env = adsr(n, 0.06, 0.12, 0.72, min(0.28, dur * 0.35 / dur if dur else 0.2))
    # longer release for lyrical phrases
    env = adsr(n, 0.07, 0.14, 0.7, 0.22)
    vib = 1 + 0.011 * np.sin(2 * math.pi * 5.1 * t) * np.clip(t / 0.25, 0, 1)
    # gentle portamento from 3% below
    slide = 1 - 0.03 * np.exp(-t * 18)
    f = freq * vib * slide
    sig = (
        1.00 * np.sin(2 * math.pi * f * t)
        + 0.22 * np.sin(2 * math.pi * 2 * f * t)
        + 0.07 * np.sin(2 * math.pi * 3 * f * t)
        + 0.03 * np.sin(2 * math.pi * 4 * f * t)
    )
    breath = 0.035 * np.random.default_rng(int(freq * 10)).standard_normal(n)
    breath *= env
    # air-band shimmer
    shimmer = 0.02 * np.sin(2 * math.pi * (1800 + freq) * t) * env
    return (sig + breath + shimmer) * env * vol


def bell(freq: float, dur: float, vol: float = 0.35) -> np.ndarray:
    n = int(dur * SR)
    t = np.arange(n) / SR
    ratios = [1.0, 2.0, 2.4, 3.0, 4.2, 5.4]
    amps = [1.0, 0.55, 0.4, 0.22, 0.12, 0.08]
    decays = [1.2, 1.8, 2.2, 2.8, 3.5, 4.2]
    sig = np.zeros(n)
    for r, a, d in zip(ratios, amps, decays):
        sig += a * np.sin(2 * math.pi * freq * r * t) * np.exp(-t * d)
    click = np.exp(-t * 80) * 0.15 * np.sin(2 * math.pi * freq * 6 * t)
    return tanh_soft(sig + click, 1.3) * vol


def mridangam(kind: str, dur: float = 0.28) -> np.ndarray:
    n = int(dur * SR)
    t = np.arange(n) / SR
    rng = np.random.default_rng(7 if kind == "tha" else 11)
    if kind == "tha":
        tone = np.sin(2 * math.pi * 82 * t) * np.exp(-t * 14)
        noise = rng.standard_normal(n) * np.exp(-t * 40)
        return tanh_soft(0.9 * tone + 0.25 * noise) * 0.45
    if kind == "dhin":
        tone = np.sin(2 * math.pi * 130 * t) * np.exp(-t * 10)
        return tone * 0.38
    # thi
    noise = rng.standard_normal(n) * np.exp(-t * 28)
    ring = np.sin(2 * math.pi * 220 * t) * np.exp(-t * 18)
    return (0.55 * noise + 0.2 * ring) * 0.32


def choir_om(dur: float, freq: float, vol: float = 0.12) -> np.ndarray:
    n = int(dur * SR)
    t = np.arange(n) / SR
    env = adsr(n, 0.35, 0.2, 0.8, 0.35)
    sig = np.zeros(n)
    for det, amp in [(-0.012, 0.7), (0.0, 1.0), (0.011, 0.7), (0.023, 0.4)]:
        f = freq * (1 + det)
        # formant-ish vowels for Om (O -> M)
        o = np.sin(2 * math.pi * f * t) + 0.3 * np.sin(2 * math.pi * 2 * f * t)
        m = np.sin(2 * math.pi * (f * 0.5) * t) * 0.6
        morph = np.clip((t / dur - 0.55) * 3, 0, 1)
        sig += amp * ((1 - morph) * o + morph * m)
    return sig * env * vol / 2.4


def lowpass(x: np.ndarray, cutoff: float) -> np.ndarray:
    # one-pole
    rc = 1 / (2 * math.pi * cutoff)
    a = 1 / (rc * SR + 1)
    y = np.empty_like(x)
    acc = 0.0
    for i, s in enumerate(x):
        acc += a * (s - acc)
        y[i] = acc
    return y


def render_score(melody: list[tuple[str | None, float]], start: float, buf: np.ndarray, vol=0.22, octave=1.0):
    t = start
    for name, beats in melody:
        dur = beats * BEAT
        if name:
            mix_at(buf, flute_note(midi_like(name) * octave, dur * 0.98, vol), t)
        t += dur
    return t


def compose(out_path: Path) -> float:
    duration = 88.0
    n = int(duration * SR)
    left = np.zeros(n)
    right = np.zeros(n)

    # --- Tanpura loop ---
    cycle = [("P,", 1.15), ("S'", 1.05), ("S", 1.25), ("S,", 1.35)]
    t = 0.4
    while t < duration - 2:
        for name, dur in cycle:
            pl = tanpura_pluck(midi_like(name), dur + 1.8)
            # slight stereo
            mix_at(left, pl, t, 0.16)
            mix_at(right, pl * 0.92, t + 0.012, 0.16)
            t += dur

    # --- Choir pads on Sa / Pa ---
    for t0, freq, dur in [
        (2.0, midi_like("S"), 10.0),
        (12.0, midi_like("P"), 10.0),
        (24.0, midi_like("S"), 12.0),
        (40.0, midi_like("P,"), 12.0),
        (56.0, midi_like("S"), 14.0),
        (72.0, midi_like("S,"), 12.0),
    ]:
        ch = choir_om(dur, freq, 0.10)
        mix_at(left, ch, t0, 1.0)
        mix_at(right, ch * 0.9, t0 + 0.02, 1.0)

    # --- Temple bells ---
    bell_times = [0.2, 8.0, 16.0, 24.0, 32.0, 40.0, 48.0, 56.0, 64.0, 72.0, 80.0, 84.5]
    for i, bt in enumerate(bell_times):
        b = bell(392 if i % 2 == 0 else 523.25, 3.2, 0.22 if i else 0.32)
        mix_at(left, b, bt, 1.0)
        mix_at(right, b * 0.85, bt + 0.01, 1.0)
        if i == 0:
            mix_at(left, bell(784, 2.4, 0.12), bt + 0.18)
            mix_at(right, bell(784, 2.4, 0.12), bt + 0.22)

    # --- Original flute melody (Mohanam) ---
    # Phrase A: Om Namo Venkatesaya
    A = [
        ("S", 1), ("S", 0.5), ("R", 0.5), ("G", 1), ("P", 1),
        ("G", 1), ("R", 1), ("S", 2),
    ]
    # Phrase B: Govinda Govinda
    B = [
        ("P", 0.5), ("D", 0.5), ("S'", 1), ("D", 1), ("P", 1),
        ("G", 1), ("R", 1), ("S", 2),
    ]
    # Phrase C: Srinivasa Govinda
    C = [
        ("S", 0.5), ("R", 0.5), ("G", 1), ("P", 1), ("D", 1),
        ("P", 1), ("G", 1), ("R", 0.5), ("S", 1.5),
    ]
    # Phrase D: Tirumala giri vaasa
    Dph = [
        ("G", 1), ("P", 1), ("D", 1), ("S'", 1),
        ("R'", 1), ("S'", 1), ("D", 1), ("P", 1),
    ]
    # Phrase E: Shankha chakra dhara
    E = [
        ("P", 0.5), ("D", 0.5), ("S'", 1.5), ("D", 0.5), ("P", 1),
        ("G", 1), ("P", 1), ("G", 0.5), ("R", 0.5), ("S", 1),
    ]
    # Closing
    F = [
        ("S", 1), ("G", 1), ("P", 2),
        ("D", 1), ("P", 1), ("G", 1), ("S", 3),
    ]

    render_score(A, 8.0, left, 0.24)
    render_score(A, 8.04, right, 0.20)
    render_score(B, 16.0, left, 0.24)
    render_score(B, 16.05, right, 0.20)
    render_score(C, 24.0, left, 0.25)
    render_score(C, 24.04, right, 0.21)
    render_score(Dph, 32.0, left, 0.23)
    render_score(Dph, 32.05, right, 0.20)
    render_score(A, 40.0, left, 0.26)
    render_score(A, 40.04, right, 0.22)
    render_score(E, 48.0, left, 0.24)
    render_score(E, 48.05, right, 0.20)
    render_score(B, 56.0, left, 0.26)
    render_score(B, 56.04, right, 0.22)
    render_score(C, 64.0, left, 0.25)
    render_score(C, 64.05, right, 0.21)
    render_score(F, 72.0, left, 0.22)
    render_score(F, 72.04, right, 0.19)
    # octave echo on last chorus
    render_score(A, 40.0, left, 0.10, octave=0.5)
    render_score(B, 56.0, right, 0.10, octave=0.5)

    # --- Soft mridangam from bar ~16 ---
    t = 16.0
    pattern = ["tha", "thi", "dhin", "thi", "tha", None, "dhin", "thi"]
    while t < 76:
        for k in pattern:
            if k:
                hit = mridangam(k)
                mix_at(left, hit, t, 0.55)
                mix_at(right, hit, t + 0.004, 0.5)
            t += 0.5 * BEAT

    st = np.stack([left, right], axis=1)
    st = reverb(st, decay=1.8)

    # fade in/out
    fade_in = int(0.8 * SR)
    fade_out = int(3.5 * SR)
    st[:fade_in] *= np.linspace(0, 1, fade_in)[:, None]
    st[-fade_out:] *= np.linspace(1, 0, fade_out)[:, None]

    peak = np.max(np.abs(st))
    st = st / peak * 0.89

    pcm = np.clip(st * 32767, -32767, 32767).astype(np.int16)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(out_path), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(pcm.tobytes())
    return duration


if __name__ == "__main__":
    path = Path("/workspace/output/srinivasa-govinda.wav")
    dur = compose(path)
    print(f"Wrote {path} ({dur:.1f}s)")
