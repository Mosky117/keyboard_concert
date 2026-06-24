#!/usr/bin/env python3
"""Hardware demo of the echo effect WITHOUT needing real key presses.
Simulates pressing G, T, A, E, S staggered ~0.5s apart and lets them fade.
Watch the keyboard: each should flash green and melt back to violet over 3s.
"""
import time
from keyboard_concert.device import open_keyboard, PerKey
from keyboard_concert.effects import EchoEffect
from keyboard_concert.engine import Engine

dev = open_keyboard()
pk = PerKey(dev)
eff = EchoEffect(background="8A2BE2", press_color="00FF00", fade_seconds=3.0)
eng = Engine(pk, eff, inputs=[], fps=30)

pk.fill(eff.background)
eng._shown.clear()

# letter LED indices: A=1, E=5, G=7, S=19, T=20
schedule = [(0.0, 7), (0.5, 20), (1.0, 1), (1.5, 5), (2.0, 19)]
t0 = time.monotonic()
si = 0
frames = 0
while True:
    now = time.monotonic()
    el = now - t0
    while si < len(schedule) and el >= schedule[si][0]:
        eff.on_press(schedule[si][1], now)
        si += 1
    eng._render(now)
    frames += 1
    if si >= len(schedule) and eff.idle():
        break
    time.sleep(1 / 30)
print(f"demo done ({frames} frames rendered)")
