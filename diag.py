#!/usr/bin/env python3
"""Minimal diagnostic: can we stage one color + commit? Reports per-step result."""
import sys
from proxtkl.device import PerKey, open_keyboard, rgb_to_int

dev = open_keyboard()
pk = PerKey(dev)
print(f"connected {dev.name}, {len(pk.keys)} keys")

def try_call(label, fn):
    try:
        fn()
        print(f"  OK   {label}")
    except Exception as e:
        print(f"  FAIL {label}: {type(e).__name__} {e}")

# 1) stage a full violet fill (no_reply, should not raise)
try_call("stage_fill(violet)", lambda: pk.stage_fill(rgb_to_int('8A2BE2')))
# 2) commit it
try_call("commit", pk.commit)
# 3) stage a single green key + commit
try_call("stage 1 key green", lambda: pk.stage({pk.keys[len(pk.keys)//2]: rgb_to_int('00FF00')}))
try_call("commit", pk.commit)
print("done")
