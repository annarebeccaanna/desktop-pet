"""Erzeugt kurze, eigene 8-Bit-Sounds (keine Windows-Systemklänge).

Aufruf:  python tools/make_sounds.py
Schreibt WAV-Dateien (22,05 kHz, 8 Bit, mono) nach desktop_pets/assets/sounds/.
"""

from __future__ import annotations

import math
import random
import wave
from pathlib import Path

RATE = 22050
OUT = Path(__file__).resolve().parent.parent / "desktop_pets" / "assets" / "sounds"


def square(freq: float, t: float, duty: float = 0.5) -> float:
    return 1.0 if (t * freq) % 1.0 < duty else -1.0


def tone(f0: float, f1: float, dur: float, vol: float = 0.5, duty: float = 0.5,
         vibrato: float = 0.0, attack: float = 0.01, release: float = 0.05) -> list[float]:
    out = []
    n = int(dur * RATE)
    phase = 0.0
    for i in range(n):
        t = i / RATE
        k = i / max(n - 1, 1)
        f = f0 + (f1 - f0) * k
        if vibrato:
            f *= 1 + 0.03 * math.sin(2 * math.pi * vibrato * t)
        phase += f / RATE
        env = min(1.0, t / attack) if attack else 1.0
        env *= min(1.0, (dur - t) / release) if release else 1.0
        out.append((1.0 if phase % 1.0 < duty else -1.0) * vol * env)
    return out


def noise(dur: float, vol: float = 0.4, lowpass: float = 0.3, seed: int = 1) -> list[float]:
    rng = random.Random(seed)
    out, prev = [], 0.0
    n = int(dur * RATE)
    for i in range(n):
        prev = prev + lowpass * (rng.uniform(-1, 1) - prev)
        env = min(1.0, (n - i) / (0.05 * RATE))
        out.append(prev * vol * env * 2)
    return out


def silence(dur: float) -> list[float]:
    return [0.0] * int(dur * RATE)


def write(name: str, samples: list[float]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with wave.open(str(OUT / name), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(1)
        w.setframerate(RATE)
        w.writeframes(bytes(max(0, min(255, int(128 + s * 127))) for s in samples))


def main() -> None:
    write("meow.wav", tone(500, 900, 0.12, duty=0.3) + tone(900, 420, 0.25, duty=0.3, vibrato=8))
    purr = []
    for _ in range(6):
        purr += tone(55, 60, 0.08, vol=0.35, duty=0.2, release=0.03) + silence(0.03)
    write("purr.wav", purr)
    write("hiss.wav", noise(0.45, vol=0.35, lowpass=0.8))
    write("growl.wav", tone(90, 70, 0.4, vol=0.45, duty=0.25, vibrato=25))
    write("woof.wav", tone(260, 180, 0.09, vol=0.6, duty=0.4) + silence(0.06) + tone(260, 170, 0.11, vol=0.6, duty=0.4))
    write("pant.wav", (noise(0.08, 0.25, 0.6, 2) + silence(0.06)) * 4)
    write("chirp.wav", tone(900, 1500, 0.07, duty=0.25) + tone(1500, 1100, 0.08, duty=0.25))
    write("roar.wav", tone(160, 90, 0.35, vol=0.5, duty=0.3, vibrato=30) + noise(0.2, 0.2, 0.5, 3))
    write("blub.wav", tone(300, 700, 0.06, vol=0.4, duty=0.5) + silence(0.05) + tone(350, 800, 0.06, vol=0.4))
    write("munch.wav", (noise(0.05, 0.35, 0.5, 4) + silence(0.07)) * 3)
    write("pling.wav", tone(1318, 1318, 0.09, vol=0.4, duty=0.5) + tone(1760, 1760, 0.22, vol=0.35, duty=0.5, release=0.18))
    write("jump.wav", tone(300, 900, 0.14, vol=0.35, duty=0.5))
    print("Sounds geschrieben nach", OUT)


if __name__ == "__main__":
    main()
