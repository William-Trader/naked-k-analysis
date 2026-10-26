"""Data-driven regime gate (measured 2026-10-26, n=498 scored signals).

Per-cell average return (regime x direction, %):
  transition/long +0.177  range/short +0.121  down/long +0.014
  up/long -0.003  transition/short -0.057  range/long -0.083
  up/short -0.084  down/short -0.193   <- worst: chasing a completed downtrend

Rule: only short in range (fade range highs); only long in transition or down.
This is a measured guardrail, not a claimed edge.
"""

STATS = {
    ("transition", "long"): 0.177,
    ("range", "short"): 0.121,
    ("down", "long"): 0.014,
    ("up", "long"): -0.003,
    ("transition", "short"): -0.057,
    ("range", "long"): -0.083,
    ("up", "short"): -0.084,
    ("down", "short"): -0.193,
}

BLOCK = {k for k, v in STATS.items() if v < 0.0}


def allow(regime, direction):
    if not regime or not direction:
        return True
    return (regime, direction) not in BLOCK


def note(regime, direction):
    return STATS.get((regime, direction))
