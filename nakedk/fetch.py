# -----------------------------------------------------------------
# nakedk/fetch.py - naked-k-analysis core price-action engine
# (c) 2026 William-Trader (https://github.com/William-Trader)
# WM: NKA-771AC70B
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Removing this mark violates the license.
# -----------------------------------------------------------------
"""Binance public-data fetcher and text summariser (stdlib only)."""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from urllib.request import Request, urlopen

from .features import features_from_klines
from .trend import trend_score
from .patterns import arbitrate, detect as detect_patterns
from .pattern_tracker import states as pattern_states, track as track_patterns
from .derivs import derivatives
from .calibration import table_from_db
from .bars import profile_series, closed_bars
from .structure import structure as structure_of
from .mtf import alignment as mtf_alignment
from .volume import vpoc, effort_result, divergence
from .location import atr_distance, edge_zone, session_levels
from .signalbar import score as signalbar_score

BASE = "https://data-api.binance.vision"
CST = timezone(timedelta(hours=8))


def get_json(path: str, timeout: int = 15):
    req = Request(BASE + path, headers={"User-Agent": "naked-k-analysis/2.0"})
    with urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def ticker(symbol: str) -> dict:
    return get_json(f"/api/v3/ticker/24hr?symbol={symbol}")


def klines(symbol: str, interval: str = "4h", limit: int = 200):
    return get_json(f"/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}")


def fmt(x, nd=2) -> str:
    if x is None:
        return "n/a"
    return f"{x:,.{nd}f}"


def summarise(symbol: str) -> tuple[str, dict]:
    """Return (human text, features) for one symbol."""
    t = ticker(symbol)
    k4 = closed_bars(klines(symbol, "4h", 200), "4h")
    f = features_from_klines(k4)
    try:
        mtf = mtf_alignment(symbol)
        f["mtf_alignment"] = mtf["alignment"]
        f["mtf_label"] = mtf["label"]
    except Exception:
        mtf = {"by_tf": {"1d": 0, "4h": 0, "1h": 0}, "alignment": 0, "label": "unknown"}
    base = symbol[:-4] if symbol.endswith("USDT") else symbol

    lines = [f"===== {symbol} ====="]
    lines.append(
        f"price: {fmt(f['price'])} | 24h: {float(t['priceChangePercent']):+.2f}% "
        f"| 24h high/low: {fmt(float(t['highPrice']))} / {fmt(float(t['lowPrice']))}"
    )
    lines.append(
        f"24h volume: {fmt(float(t['volume']), 1)} {base} "
        f"| 24h quote: {fmt(float(t['quoteVolume']) / 1e6, 1)}M USDT"
    )
    lines.append("")
    lines.append("--- structure (4h) ---")
    lines.append(
        f"EMA20={fmt(f['ema20'], 1)} EMA50={fmt(f['ema50'], 1)} price={fmt(f['price'], 1)} ({f['trend']})"
    )
    lines.append(
        f"ADX14={fmt(f['adx14'], 1)} | RSI14={fmt(f['rsi14'], 1)} "
        f"| ATR14={fmt(f['atr14'], 1)} ({fmt(f['atr_pct'], 2)}%)"
    )
    lines.append(
        f"volume z={f['vol_z']:+.2f} | range20 {fmt(f['r20_lo'])}~{fmt(f['r20_hi'])} "
        f"pos={f['pos20'] * 100:.0f}% | range40 {fmt(f['r40_lo'])}~{fmt(f['r40_hi'])} "
        f"pos={f['pos40'] * 100:.0f}%"
    )
    lines.append(
        "swing highs: " + ", ".join(fmt(x) for x in f["swing_highs"])
        + " | swing lows: " + ", ".join(fmt(x) for x in f["swing_lows"])
    )
    lines.append(
        f"returns: 4h {f['ret4h']:+.2f}% | 24h {f['ret24h']:+.2f}% | 72h {f['ret72h']:+.2f}%"
    )
    try:
        dv = derivatives(symbol)
    except Exception:
        dv = {}
    for k, v in dv.items():
        if v is not None:
            f[k] = v
    if any(v is not None for v in dv.values()):
        rate = dv.get("funding_rate")
        lines.append(
            f"FUNDING|{base}|src={dv.get('source', 'none')}"
            f"|rate={fmt(rate * 100, 4) if rate is not None else 'NA'}%"
            f"|oi={fmt(dv.get('open_interest'), 0) if dv.get('open_interest') is not None else 'NA'}"
            f"|oi_chg_24h={fmt(dv.get('oi_change_24h'), 2) if dv.get('oi_change_24h') is not None else 'NA'}%"
        )
    lines.append("SIG|" + "|".join(
        f"{k}={v:.2f}" if isinstance(v, float) else f"{k}={v}"
        for k, v in [
            ("close", f["price"]), ("ema20", f["ema20"]), ("ema50", f["ema50"]),
            ("adx", f["adx14"] or 0), ("rsi", f["rsi14"] or 50),
            ("atr_pct", f["atr_pct"] or 0), ("vol_z", f["vol_z"]),
            ("r20_lo", f["r20_lo"]), ("r20_hi", f["r20_hi"]), ("pos20", f["pos20"]),
            ("r40_lo", f["r40_lo"]), ("r40_hi", f["r40_hi"]), ("pos40", f["pos40"]),
            ("ret4h", f["ret4h"]), ("ret24h", f["ret24h"]), ("ret72h", f["ret72h"]),
        ]
    ))
    ts = trend_score(f)
    lines.append(f"TREND|{base}|score={ts['score']}|label={ts['label']}|always_in={ts['always_in']}|ema={ts['components']['ema']}|adx={ts['components']['adx']}|pos={ts['components']['pos']}|mom={ts['components']['mom']}")
    lines.append(f"trend: {ts['score']}/100 ({ts['label']}, Always-In={ts['always_in']})")
    try:
        cdb = os.environ.get("NK_CALIB_DB") or os.path.join(os.path.dirname(__file__), "..", "beagle.db")
        tbl = table_from_db(cdb)
        if tbl.get("n"):
            parts = " ".join(
                f"{k}:{v['p'] * 100:.0f}%(n={v['n']})" for k, v in tbl["buckets"].items()
            )
            lines.append(f"CALIB|{base}|n={tbl['n']}|base={tbl['base_rate']}%|{parts}")
    except Exception:
        pass
    arb = arbitrate(detect_patterns(k4, f), f)
    prim = arb["primary"] or {}
    sec = arb["secondary"] or {}
    lines.append(f"PATTERN_CTX|{base}|context={arb['context']}|primary={prim.get('type','NONE')}|secondary={sec.get('type','NONE')}")
    for pp in arb["patterns"]:
        lines.append(f"PATTERN|{base}|{pp['type']}|{pp['direction']}|{pp['label']}|price={pp['price']:.2f}|quality={pp['quality']}|score={pp['score']}|role={pp['role']}|rr={pp.get('rr','')}|{pp.get('note','')}")
    if not arb["patterns"]:
        lines.append(f"PATTERN|{base}|NONE|neutral|无标准形态|")
    try:
        pdb = os.environ.get("NK_PATTERN_DB") or os.path.join(os.path.dirname(__file__), "..", "patterns.db")
        track_patterns(symbol, arb["patterns"], pdb, f.get("price"))
        for stt in pattern_states(symbol, pdb, 6):
            lines.append(f"PATTERN_STATE|{base}|{stt['type']}|{stt['direction']}|{stt['status']}|quality={stt['quality']}")
    except Exception:
        pass
    try:
        profiles = profile_series(k4)
        bar = profiles[-1] if profiles else {}
        prev_bar = profiles[-2] if len(profiles) > 1 else None
        if bar:
            lines.append(
                f"BAR|{base}|type={bar['type']}|q={bar['quality']}|body={bar['body_ratio']}"
                f"|close_pos={bar['close_pos']}|upper={bar['upper_tail']}|lower={bar['lower_tail']}"
                f"|range_atr={bar['range_atr']}|vol_z={bar['vol_z']}"
            )
        stc = structure_of(k4)
        lv = stc.get("levels", {})
        bos = stc.get("bos") or {}
        choch = stc.get("choch") or {}
        lines.append(
            f"STRUCT|{base}|state={stc.get('state')}|prior={stc.get('prior_state')}"
            f"|swing_high={lv.get('swing_high', 'NA')}|swing_low={lv.get('swing_low', 'NA')}"
            f"|bos={bos.get('kind', 'none')}@{bos.get('level', 'NA')}"
            f"|choch={choch.get('kind', 'none')}@{choch.get('level', 'NA')}"
        )
        lines.append(
            f"MTF|{base}|d1={mtf['by_tf']['1d']:+d}|h4={mtf['by_tf']['4h']:+d}"
            f"|h1={mtf['by_tf']['1h']:+d}|alignment={mtf['alignment']:+d}|label={mtf['label']}"
        )
        sess = session_levels(closed_bars(klines(symbol, "1d", 5), "1d"))
        atr_val = stc.get("atr")
        lines.append(
            f"LOC|{base}|edge={edge_zone(f.get('pos20'))}"
            f"|to_swing_hi={atr_distance(f['price'], lv.get('swing_high'), atr_val)}"
            f"|to_swing_lo={atr_distance(f['price'], lv.get('swing_low'), atr_val)}"
            f"|to_prev_day={atr_distance(f['price'], sess.get('prev_day_high'), atr_val)}"
            f"|prev_day={sess.get('prev_day_low', 'NA')}-{sess.get('prev_day_high', 'NA')}"
        )
        vp = vpoc(k4)
        va = vp.get("value_area") or [None, None]
        lines.append(
            f"VOLP|{base}|poc={vp.get('poc', 'NA')}|va={va[0]}-{va[1]}"
            f"|effort={effort_result(bar)}|div={divergence(profiles) or 'none'}"
        )
        pdir = ("long" if prim.get("direction") == "bullish"
                else "short" if prim.get("direction") == "bearish" else None)
        if bar and pdir:
            sbs = signalbar_score(bar, prev_bar, pdir, f.get("pos20"))
            parts_s = " ".join(k + "=" + str(v) for k, v in sbs["parts"].items())
            miss_s = ",".join(sbs["missing"]) or "none"
            lines.append(
                f"SIGBAR|{base}|dir={pdir}|score={sbs['score']}|{parts_s}|missing={miss_s}"
            )
    except Exception as e:
        lines.append(f"BAR_ERR|{base}|{str(e)[:80]}")
    lines.append("")
    lines.append("--- 4h candles (last 42, newest last) ---")
    lines.append("time (CST)        open       high       low        close      chg%    vol z")
    k42 = k4[-42:]
    vols = [float(x[5]) for x in k42]
    mu = sum(vols) / len(vols)
    var = sum((v - mu) ** 2 for v in vols) / len(vols)
    sd = var ** 0.5 or 1.0
    for row in k42:
        ts = datetime.fromtimestamp(row[0] / 1000, CST).strftime("%m-%d %H:%M")
        o, h, l, c, v = (float(row[1]), float(row[2]), float(row[3]),
                         float(row[4]), float(row[5]))
        lines.append(
            f"{ts}  {fmt(o,1):>10} {fmt(h,1):>10} {fmt(l,1):>10} {fmt(c,1):>10}"
            f"  {(c - o) / o * 100:+5.2f}%  {(v - mu) / sd:+.1f}"
        )
    return "\n".join(lines), f
