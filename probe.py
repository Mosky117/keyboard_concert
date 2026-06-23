#!/usr/bin/env python3
"""Latency probe for PRO X TKL per-key lighting.

Answers the only question that matters before building a reactive effect:
how fast can we push per-key color frames over Lightspeed? Reactive press-echo
needs ~20+ fps to feel smooth.

Run:  python3 probe.py
It will briefly take over the keyboard lighting (violet fill, green flash, fade),
then print timing stats and a verdict.
"""

import statistics
import time

from proxtkl.device import PerKey, open_keyboard, rgb_to_int

VIOLET = rgb_to_int("8A2BE2")
GREEN = rgb_to_int("00FF00")


def bench(label, fn, rounds=40):
    samples = []
    for _ in range(rounds):
        t0 = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - t0) * 1000.0)
    samples.sort()
    med = statistics.median(samples)
    p90 = samples[int(len(samples) * 0.9) - 1]
    print(f"  {label:<34} median {med:6.2f} ms   p90 {p90:6.2f} ms   "
          f"(~{1000.0/med:5.1f} fps)")
    return med


def main():
    print("Opening keyboard…")
    dev = open_keyboard()
    print(f"  connected: {dev.name}  (HID++ {dev.protocol})")
    pk = PerKey(dev)
    keys = pk.keys
    print(f"  valid key indices: {len(keys)}  (range {keys[0]}..{keys[-1]})")
    print()

    # Establish a known background first (a commit needs something staged).
    pk.fill(VIOLET)

    print("Timing primitives:")
    bench("full violet fill + commit", lambda: pk.fill(VIOLET))

    # Reactive frame: background already violet; recolor N 'pressed' keys + commit.
    sample_keys = keys[: min(8, len(keys))]
    def reactive_frame(n):
        pk.stage({k: GREEN for k in sample_keys[:n]})
        pk.commit()
    for n in (1, 4, 8):
        bench(f"recolor {n} key(s) + commit", lambda n=n: reactive_frame(n))
    print()

    # End-to-end fade: one key green -> violet over ~30 steps, see real fps.
    print("Simulated 1-key fade (green->violet, 30 steps):")
    key = keys[len(keys) // 2]
    steps = 30
    t0 = time.perf_counter()
    for i in range(steps + 1):
        t = i / steps
        r = int(0x8A + (0x00 - 0x8A) * 0)  # held by lerp below
        # linear lerp in RGB
        gr = (0x8A, 0x2B, 0xE2)
        gv = (0x00, 0xFF, 0x00)
        col = tuple(int(gv[c] + (gr[c] - gv[c]) * t) for c in range(3))
        pk.set({key: rgb_to_int(col)})
    dur = time.perf_counter() - t0
    fps = (steps + 1) / dur
    print(f"  {steps+1} frames in {dur*1000:.0f} ms  ->  {fps:.1f} fps")
    print()

    # restore violet so we don't leave a stray green key
    pk.fill(VIOLET)

    verdict = "SMOOTH (>=20 fps): reactive echo is viable" if fps >= 20 else (
        "USABLE (10-20 fps): reactive echo will work but may look steppy" if fps >= 10
        else "TOO SLOW (<10 fps): reactive over wireless is marginal — try wired/closer receiver")
    print(f"VERDICT: {verdict}")


if __name__ == "__main__":
    main()
