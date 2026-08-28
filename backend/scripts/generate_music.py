#!/usr/bin/env python3
"""Generate Nagrik's royalty-free background music loops.

All tracks are synthesized procedurally (no copyrighted material) and encoded
to .m4a via ffmpeg. Run once from backend/:

    python3 scripts/generate_music.py
"""
import subprocess
import wave
from pathlib import Path

import numpy as np

SR = 44100
OUT_DIR = Path(__file__).resolve().parent.parent / "app" / "assets" / "music"


def env(t, attack, release, total):
    e = np.ones_like(t)
    a = int(attack * SR)
    r = int(release * SR)
    if a > 0:
        e[:a] = np.linspace(0, 1, a)
    if r > 0:
        e[-r:] *= np.linspace(1, 0, r)
    return e


def sine(freq, dur, amp=0.5):
    t = np.arange(int(dur * SR)) / SR
    return amp * np.sin(2 * np.pi * freq * t)


def noise_burst(dur, decay=0.03, amp=0.3):
    n = int(dur * SR)
    x = np.random.uniform(-1, 1, n)
    envd = np.exp(-np.arange(n) / (decay * SR))
    return amp * x * envd


def kick(dur=0.22, f0=110.0, f1=45.0, amp=0.9):
    n = int(dur * SR)
    t = np.arange(n) / SR
    freq = f1 + (f0 - f1) * np.exp(-t * 30)
    phase = 2 * np.pi * np.cumsum(freq) / SR
    body = np.sin(phase) * np.exp(-t * 18)
    return amp * body


def hat(dur=0.05, amp=0.12):
    return noise_burst(dur, decay=0.006, amp=amp)


def pad_chord(freqs, dur, amp=0.14, detune=0.7):
    n = int(dur * SR)
    t = np.arange(n) / SR
    out = np.zeros(n)
    for f in freqs:
        for d in (-detune, detune):
            vib = 0.15 * np.sin(2 * np.pi * 0.25 * t + np.random.rand() * 6)
            out += np.sin(2 * np.pi * (f + d) * t + vib)
    # slow attack envelope
    a = int(min(1.2, dur * 0.3) * SR)
    e = np.ones(n)
    e[:a] = np.linspace(0, 1, a) ** 2
    e[-a:] = np.minimum(e[-a:], np.linspace(1, 0, a) ** 2)
    return amp * out * e


def pluck(freq, dur, amp=0.25):
    n = int(dur * SR)
    t = np.arange(n) / SR
    x = (np.sin(2 * np.pi * freq * t) + 0.35 * np.sin(2 * np.pi * freq * 2 * t)) * np.exp(-t * 6)
    return amp * x


def place(buf, start_sec, signal):
    i = int(start_sec * SR)
    j = min(len(buf), i + len(signal))
    if i < len(buf):
        buf[i:j] += signal[: j - i]


NOTE = {"C": 261.63, "D": 293.66, "E": 329.63, "F": 349.23, "G": 392.0, "A": 440.0, "B": 493.88}

def nf(note, octave):
    return NOTE[note] / (2 ** (4 - octave))


def render(name: str, builder, duration: float):
    mono = builder(duration)
    peak = np.max(np.abs(mono)) or 1.0
    mono = mono / peak * 0.82
    stereo = np.stack([mono, mono], axis=1)
    pcm = (stereo * 32767).astype(np.int16)
    wav_path = OUT_DIR / f"{name}.wav"
    with wave.open(str(wav_path), "w") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    m4a_path = OUT_DIR / f"{name}.m4a"
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", str(wav_path), "-c:a", "aac", "-b:a", "112k", str(m4a_path)],
        check=True,
    )
    wav_path.unlink()
    print(f"✓ {m4a_path.name}  ({m4a_path.stat().st_size // 1024} KB)")


# ── Track builders ────────────────────────────────────────────

def serious_news(total):
    buf = np.zeros(int(total * SR))
    t = np.arange(len(buf)) / SR
    drone = 0.16 * np.sin(2 * np.pi * 55 * t) + 0.10 * np.sin(2 * np.pi * 110 * t + 0.5)
    swell = 0.04 * np.sin(2 * np.pi * 0.08 * t)
    buf += drone + drone * swell
    for beat in np.arange(0, total, 2.0):           # slow news pulse
        place(buf, beat, kick(0.3, f0=70, f1=40, amp=0.28))
    for hit in np.arange(0, total, 8.0):            # periodic low sting
        place(buf, hit, sine(65.4, 1.6, amp=0.10) * env(np.arange(int(1.6*SR))/SR, 0.02, 0.8, 1.6))
    return buf


def investigative(total):
    buf = np.zeros(int(total * SR))
    t = np.arange(len(buf)) / SR
    buf += 0.13 * np.sin(2 * np.pi * 73.42 * t) + 0.07 * np.sin(2 * np.pi * 87.31 * t)
    rng = np.random.default_rng(7)
    tick_times = sorted(rng.uniform(0, total, int(total / 1.1)))
    prev = -9
    for tt in tick_times:
        if tt - prev > 0.55:
            place(buf, tt, hat(0.035, amp=0.10 + rng.uniform(0, 0.06)))
            prev = tt
    for beat in np.arange(0, total, 4.0):
        place(buf, beat, kick(0.4, f0=80, f1=38, amp=0.20))
    return buf


def energetic(total):
    buf = np.zeros(int(total * SR))
    bpm = 104
    beat = 60 / bpm
    step = 0.0
    bar_i = 0
    while step < total:
        pos_in_bar = bar_i % 4
        if pos_in_bar in (0, 2):
            place(buf, step, kick())
        elif pos_in_bar == 3:
            place(buf, step, kick(0.18, amp=0.6))
        place(buf, step + beat / 2, hat(amp=0.09))
        if pos_in_bar == 0:
            root = [nf("A", 1), nf("F", 1), nf("C", 2), nf("G", 1)][(bar_i // 4) % 4]
            place(buf, step, sine(root, beat * 2, amp=0.16))
        step += beat
        bar_i += 1
    return buf * 0.85


EMOTIONAL_PROG = [("A", ["A", "C", "E"]), ("F", ["F", "A", "C"]), ("C", ["C", "E", "G"]), ("G", ["G", "B", "D"])]

def emotional(total):
    buf = np.zeros(int(total * SR))
    chord_dur = 4.0
    i = 0
    t0 = 0.0
    while t0 < total:
        root, chord = EMOTIONAL_PROG[i % len(EMOTIONAL_PROG)]
        freqs = [nf(n, 3) for n in chord]
        place(buf, t0, pad_chord(freqs, min(chord_dur + 1.2, total - t0 + 1.2)))
        place(buf, t0, sine(nf(root, 1), chord_dur, amp=0.10))
        t0 += chord_dur
        i += 1
    return buf


CIVIC_SCALE = ["C", "D", "E", "G", "A"]

def civic(total):
    buf = np.zeros(int(total * SR))
    bpm = 92
    beat = 60 / bpm
    step = 0.0
    k = 0
    while step < total:
        note = CIVIC_SCALE[(k * 3 + (k % 2)) % len(CIVIC_SCALE)]
        octv = 4 if k % 3 else 5
        place(buf, step, pluck(nf(note, octv), 0.9, amp=0.16))
        if k % 4 == 0:
            place(buf, step, kick(0.24, amp=0.32))
            place(buf, step, sine(nf(CIVIC_SCALE[0], 1), 0.8, amp=0.12))
        if k % 2 == 1:
            place(buf, step + beat / 2, hat(amp=0.05))
        step += beat
        k += 1
    t = np.arange(len(buf)) / SR
    buf += 0.05 * np.sin(2 * np.pi * nf("C", 2) * t)
    return buf


def modern(total):
    buf = np.zeros(int(total * SR))
    bpm = 96
    beat = 60 / bpm
    step = 0.0
    k = 0
    while step < total:
        if k % 4 == 0:
            place(buf, step, kick(f0=90, f1=42, amp=0.5))
            place(buf, step, sine(55, 0.5, amp=0.2))
        if k % 8 == 6:
            place(buf, step, kick(0.16, amp=0.35))
        if k % 2 == 1:
            place(buf, step, hat(amp=0.06))
        if k % 16 == 12:
            place(buf, step, pluck(nf("E", 4), 0.7, amp=0.10))
            place(buf, step + beat, pluck(nf("G", 4), 0.7, amp=0.09))
        step += beat
        k += 1
    return buf


def minimal(total):
    buf = np.zeros(int(total * SR))
    place(buf, 0, pad_chord([nf("A", 3), nf("E", 4)], total, amp=0.09))
    place(buf, 0, sine(110, total, amp=0.06))
    t = np.arange(len(buf)) / SR
    buf *= 1 + 0.08 * np.sin(2 * np.pi * 0.05 * t)
    return buf


TRACKS = {
    "serious_news": ("Serious News", serious_news),
    "investigative": ("Investigative", investigative),
    "energetic": ("Energetic", energetic),
    "emotional": ("Emotional", emotional),
    "civic": ("Civic", civic),
    "modern": ("Modern", modern),
    "minimal": ("Minimal", minimal),
}


if __name__ == "__main__":
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print("Synthesizing royalty-free music beds…")
    for key, (_, fn) in TRACKS.items():
        render(key, fn, 48.0)
    print("Done.")
