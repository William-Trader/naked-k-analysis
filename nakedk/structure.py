"""Swing structure: ATR ZigZag, HH/HL/LH/LL, BOS and CHoCH."""
from __future__ import annotations


def _f(x):
    return float(x)


def zigzag(highs, lows, atr: float, mult: float = 0.5) -> list:
    """Pivot list [{"i","p","kind"}] using an ATR retracement threshold."""
    n = len(highs)
    if n < 3:
        return []
    if not atr:
        atr = sum(h - l for h, l in zip(highs, lows)) / n or 1.0
    th = max(1e-9, mult * atr)
    piv = []
    dirn = 1 if highs[1] >= highs[0] else -1
    ext_i = 0
    ext = highs[0] if dirn == 1 else lows[0]
    for i in range(1, n):
        if dirn == 1:
            if highs[i] >= ext:
                ext_i, ext = i, highs[i]
            elif ext - lows[i] >= th:
                piv.append({"i": ext_i, "p": ext, "kind": "H"})
                dirn, ext_i, ext = -1, i, lows[i]
        else:
            if lows[i] <= ext:
                ext_i, ext = i, lows[i]
            elif highs[i] - ext >= th:
                piv.append({"i": ext_i, "p": ext, "kind": "L"})
                dirn, ext_i, ext = 1, i, highs[i]
    piv.append({"i": ext_i, "p": ext, "kind": "H" if dirn == 1 else "L"})
    return piv


def label(pivots: list) -> list:
    """Attach HH/HL/LH/LL by comparing consecutive same-kind pivots."""
    out = []
    last_h = last_l = None
    for p in pivots:
        q = dict(p)
        if q["kind"] == "H":
            q["label"] = ("HH" if last_h is not None and q["p"] > last_h
                          else "LH" if last_h is not None else "H")
            last_h = q["p"]
        else:
            q["label"] = ("HL" if last_l is not None and q["p"] > last_l
                          else "LL" if last_l is not None else "L")
            last_l = q["p"]
        out.append(q)
    return out


def _state(labels: list) -> str:
    hs = [p["label"] for p in labels if p["kind"] == "H"][-2:]
    ls = [p["label"] for p in labels if p["kind"] == "L"][-2:]
    up = hs == ["HH"] or (hs and hs[-1] == "HH")
    down = ls and ls[-1] == "LL"
    if up and not down:
        return "up"
    if down and not up:
        return "down"
    if not up and not down:
        return "range"
    return "transition"


def structure(ks, atr=None, mult: float = 0.5) -> dict:
    """Return structure state, labelled swings, BOS/CHoCH and key levels."""
    if len(ks) < 10:
        return {"state": "unknown", "swings": [], "levels": {}}
    highs = [_f(k[2]) for k in ks]
    lows = [_f(k[3]) for k in ks]
    closes = [_f(k[4]) for k in ks]
    if atr is None:
        trs = [max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]),
                   abs(lows[i] - closes[i - 1])) for i in range(1, len(ks))]
        atr = (sum(trs[-14:]) / len(trs[-14:])) if trs else 1.0
    labels = label(zigzag(highs, lows, atr, mult))
    last_h = next((p for p in reversed(labels) if p["kind"] == "H"), None)
    last_l = next((p for p in reversed(labels) if p["kind"] == "L"), None)
    close = closes[-1]
    prior = _state(labels[:-1]) if len(labels) > 2 else "unknown"
    bos = None
    if last_h and close > last_h["p"]:
        bos = {"kind": "bullish", "level": round(last_h["p"], 4),
               "from_state": prior, "i": last_h["i"]}
    elif last_l and close < last_l["p"]:
        bos = {"kind": "bearish", "level": round(last_l["p"], 4),
               "from_state": prior, "i": last_l["i"]}
    choch = None
    if bos and prior in ("up", "down"):
        if (bos["kind"] == "bullish" and prior == "down") or (bos["kind"] == "bearish" and prior == "up"):
            choch = {"kind": bos["kind"], "level": bos["level"], "from_state": prior}
    levels = {}
    if last_h:
        levels["swing_high"] = round(last_h["p"], 4)
    if last_l:
        levels["swing_low"] = round(last_l["p"], 4)
    if bos:
        levels["bos_level"] = bos["level"]
    return {
        "state": _state(labels),
        "prior_state": prior,
        "swings": labels[-6:],
        "last_h": last_h,
        "last_l": last_l,
        "bos": bos,
        "choch": choch,
        "levels": levels,
        "atr": round(atr, 4),
    }

