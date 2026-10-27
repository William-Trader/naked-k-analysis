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
from .calibration import table_from_db, load_multipliers
from .bars import profile_series, closed_bars
from .structure import structure as structure_of
from .mtf import alignment as mtf_alignment
from .volume import vpoc, effort_result, divergence
from .location import atr_distance, edge_zone, session_levels, plan_from_context
from .flow import analyse as flow_analyse, classify as flow_classify
from .regime import arbitrate as arbitrate_regime
from .policy import allow as policy_allow, note as policy_note
from .pattern_mtf import confluence as mtf_confluence, apply as apply_confluence
from .analogs import build as analogs_build, bucket as analogs_bucket
from .analogs import bucket_regime as analogs_regime
from .events import failed_break, follow_through
from .micro import analyse as micro_analyse
from .volstruct import analyse as volstruct_analyse
from .cross import analyse as cross_analyse
from .trades import trades as trades_analyse, book as book_analyse
from .sources import aggregate as sources_aggregate
from . import always_in as ai_state
from .legs import decompose as leg_decompose, maturity as leg_maturity, exhaustion as leg_exhaustion
from .quality import gates as data_gates
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


def _analogs_cached(symbol: str, k4):
    """Cache the analog table per (symbol, bar) so repeated calls skip the scan."""
    path = os.environ.get("NK_ANALOGS_CACHE") or os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "state", "analogs_cache.json")
    key = f"{symbol}:{int(k4[-1][0])}"
    try:
        with open(path, encoding="utf-8") as fh:
            cache = json.load(fh)
    except Exception:
        cache = {}
    if key in cache:
        return cache[key]
    table = analogs_build(k4, horizon=1)
    cache[key] = table
    if len(cache) > 40:
        for k in list(cache)[:-40]:
            cache.pop(k, None)
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(cache, fh)
    except Exception:
        pass
    return table


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
    try:
        mx = sources_aggregate(symbol)
        if mx:
            src = ",".join(
                f"{r['source']}:{r['price']}" for r in mx["sources"]
            )
            lines.append(
                f"MULTI|{base}|n={mx['n']}|weighted={mx['weighted']}"
                f"|median={mx['median']}|dev={mx['max_dev_pct']}%|{src}"
            )
            if mx["max_dev_pct"] > 0.5:
                lines.append(f"DATA_WARN|{base}|source_dev={mx['max_dev_pct']}%")
            try:
                import time as _time
                log_path = os.environ.get("NK_MULTI_LOG") or os.path.join(
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "state", "multi_log.jsonl")
                rec = {"ts": int(_time.time() * 1000), "symbol": symbol,
                       "n": mx["n"], "weighted": mx["weighted"],
                       "dev": mx["max_dev_pct"], "conf": mx["confidence"],
                       "eff_n": mx["effective_n"],
                       "prices": {r["source"]: r["price"] for r in mx["sources"]}}
                os.makedirs(os.path.dirname(log_path) or ".", exist_ok=True)
                with open(log_path, "a", encoding="utf-8") as fh:
                    fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            except Exception:
                pass
    except Exception:
        pass
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
    try:
        here = os.path.dirname(os.path.abspath(__file__))
        cands = []
        if os.environ.get("NK_ADAPTIVE"):
            cands.append(os.environ["NK_ADAPTIVE"])
        for env in ("NK_CALIB_DB", "BEAGLE_DB"):
            if os.environ.get(env):
                cands.append(os.path.join(os.path.dirname(os.environ[env]),
                                          "state", "adaptive.json"))
        cands.append(os.path.join(here, "..", "state", "adaptive.json"))
        cands.append(os.path.join(here, "..", "..", "beagle-app", "state", "adaptive.json"))
        mults = {}
        for path in cands:
            mults = load_multipliers(path)
            if mults:
                break
        if mults:
            f["adapt_mult"] = mults
            lines.append("ADAPT|" + base + "|" + "|".join(
                f"{k}={v}" for k, v in sorted(mults.items())))
    except Exception:
        pass
    try:
        from .pattern_calibration import load as load_pcal
        cands = []
        if os.environ.get("NK_PATTERN_QUALITY"):
            cands.append(os.environ["NK_PATTERN_QUALITY"])
        for env in ("NK_CALIB_DB", "BEAGLE_DB"):
            if os.environ.get(env):
                cands.append(os.path.join(os.path.dirname(os.environ[env]),
                                          "state", "pattern_quality.json"))
        here = os.path.dirname(os.path.abspath(__file__))
        cands += [os.path.join(here, "..", "state", "pattern_quality.json"),
                  os.path.join(here, "..", "..", "beagle-app", "state", "pattern_quality.json")]
        mults = {}
        for path in cands:
            mults = load_pcal(path)
            if mults:
                break
        f["pattern_mult"] = mults
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
        pdir0 = ("long" if prim.get("direction") == "bullish"
                 else "short" if prim.get("direction") == "bearish" else None)
        if pdir0:
            pstate = stc.get("state")
            lines.append(
                f"POLICY|{base}|regime={pstate}|dir={pdir0}"
                f"|action={'allow' if policy_allow(pstate, pdir0) else 'block'}"
                f"|basis={policy_note(pstate, pdir0)}"
            )
        reg = arbitrate_regime(stc.get("state"), (mtf.get("by_state") or {}).get("1d"),
                               mtf.get("alignment"), f.get("adx14"),
                               f.get("adx_slope"), f.get("overlap"))
        lines.append(
            f"REGIME|{base}|regime={reg['regime']}|conf={reg['confidence']}"
            f"|conflict={int(reg['conflict'])}|notes={';'.join(reg['notes']) or 'none'}"
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
        fl = flow_analyse(k4)
        if fl:
            shape = flow_classify(bar, fl.get("delta", 0.0))
            lines.append(
                f"FLOW|{base}|delta={fl['delta']}|cum20={fl['cum_delta']}"
                f"|pchg={fl['price_chg']}|div={fl['divergence']}|shape={shape}"
            )
        try:
            m5 = closed_bars(klines(symbol, "5m", 200), "5m")
            m1 = closed_bars(klines(symbol, "1m", 60), "1m")
            mi = micro_analyse(m5, m1)
            if mi:
                lines.append(
                    f"MICRO|{base}|state5m={mi.get('state5m')}|bos5m={mi.get('bos5m')}"
                    f"|sign5m={mi.get('sign5m')}|impulse1m={mi.get('impulse_1m')}"
                )
        except Exception:
            pass
        try:
            vs = volstruct_analyse([float(x[2]) for x in k4],
                                   [float(x[3]) for x in k4],
                                   [float(x[4]) for x in k4])
            if vs:
                lines.append(
                    f"VOLS|{base}|atr_pct={vs['atr_percentile']}|ratio={vs['ratio']}"
                    f"|state={vs['state']}|rv={vs['rv']}"
                )
        except Exception:
            pass
        try:
            cr = cross_analyse(closed_bars(klines("BTCUSDT", "1d", 40), "1d"),
                               closed_bars(klines("ETHUSDT", "1d", 40), "1d"),
                               closed_bars(klines("ETHBTC", "1d", 80), "1d"))
            if cr:
                lines.append(
                    f"CROSS|{base}|corr30={cr.get('corr_30d')}|btc30={cr.get('btc_30d')}"
                    f"|eth30={cr.get('eth_30d')}|rs={cr.get('relative_strength')}"
                    f"|ethbtc={cr.get('ethbtc_trend', 'NA')}"
                )
        except Exception:
            pass
        try:
            d1_ks = closed_bars(klines(symbol, "1d", 160), "1d")
            d1_f = features_from_klines(d1_ks)
            d1_arb = arbitrate(detect_patterns(d1_ks, d1_f), d1_f)
            conf = mtf_confluence(prim, d1_arb.get("primary"), reg.get("regime"))
            apply_confluence(prim, conf)
            lines.append(
                f"PATTERN_MTF|{base}|h4={prim.get('type', 'NONE')}"
                f"|d1={(d1_arb.get('primary') or {}).get('type', 'NONE')}"
                f"|align={conf['align']}|score={conf['score']}"
            )
        except Exception:
            pass
        try:
            key = analogs_bucket(f)
            row = _analogs_cached(symbol, k4).get(key)
            source = "full"
            if not row or row["n"] < 100:
                pkey = analogs_regime(f)
                row = analogs_build(k4, horizon=1, mode="regime").get(pkey)
                key, source = pkey, "pooled"
            if row and row["n"] >= 100:
                lines.append(
                    f"PROB|{base}|bucket={key}|n={row['n']}|source={source}"
                    f"|up={row['p_up']}|down={row['p_down']}|flat={row['p_flat']}"
                    f"|wilson_up={row['wilson_up'][0]}-{row['wilson_up'][1]}"
                )
            else:
                lines.append(
                    f"PROB|{base}|bucket={key}|n={row['n'] if row else 0}"
                    f"|status=insufficient"
                )
        except Exception:
            pass
        try:
            tr = trades_analyse(symbol, atr_value=stc.get("atr"),
                                bar_range=(bar or {}).get("range"))
            if tr:
                lines.append(
                    f"TRADES|{base}|n={tr['n']}|delta={tr['delta']}|avg={tr['avg']}"
                    f"|max={tr['max']}|big={tr['big']}"
                )
                for sw in (tr.get("sweeps") or [])[-2:]:
                    lines.append(
                        f"SWEEP|{base}|side={sw['side']}|trades={sw['trades']}"
                        f"|move_atr={sw['move_atr']}|quote={sw['quote']}"
                    )
                ab = tr.get("absorb")
                if ab:
                    lines.append(f"ABSORB|{base}|count={ab['count']}|quote={ab['quote']}")
        except Exception:
            pass
        try:
            bk = book_analyse(symbol)
            if bk:
                lines.append(
                    f"BOOK|{base}|imb={bk['imbalance']}|bid={bk['bid_q']}"
                    f"|ask={bk['ask_q']}|spread_bp={bk['spread_bp']}"
                )
        except Exception:
            pass
        fb = failed_break(k4, stc.get("atr"))
        if fb:
            lines.append(
                f"FAILED|{base}|kind={fb['kind']}|level={fb['level']}|bars_since={fb['bars_since']}"
            )
        pdir0 = ("long" if prim.get("direction") == "bullish"
                 else "short" if prim.get("direction") == "bearish" else None)
        if pdir0:
            ft = follow_through(k4, pdir0)
            if ft:
                lines.append(
                    f"FOLLOW|{base}|dir={pdir0}|ok={int(ft['ok'])}|close_pos={ft['close_pos']}"
                )
        try:
            ai_path = os.environ.get("NK_AI_DB") or os.path.join(
                os.path.dirname(os.environ.get("NK_PATTERN_DB") or
                               os.path.join(os.path.dirname(__file__), "..", "patterns.db")),
                "ai_state.db")
            ai = ai_state.update(ai_path, symbol, (stc.get("bos") or {}).get("kind"),
                                 bool((ft or {}).get("ok")), f["price"], f.get("ema20"),
                                 int(k4[-1][0]))
            lines.append(
                f"AI|{base}|state={ai['state']}|prev={ai['prev']}|since={ai['since_ts']}"
                f"|reason={ai['reason']}"
            )
        except Exception:
            pass
        try:
            legs = leg_decompose([float(x[2]) for x in k4], [float(x[3]) for x in k4],
                                 stc.get("atr"))
            if legs:
                lines.append(
                    f"LEGS|{base}|count={len(legs)}|maturity={leg_maturity(legs)}"
                    f"|exhaustion={int(leg_exhaustion(legs))}"
                    f"|last_atr={legs[-1]['delta_atr']}|dir={legs[-1]['dir']}"
                )
        except Exception:
            pass
        try:
            dq = data_gates(k4, 14_400_000, int(__import__("time").time() * 1000))
            lines.append(f"DATA|{base}|ok={int(dq['ok'])}|issues={';'.join(dq['issues']) or 'none'}")
        except Exception:
            pass
        plan = plan_from_context(f["price"], prim.get("direction"), stc,
                                 stc.get("atr"), pattern=prim)
        if plan:
            lines.append("PLAN|" + base + "|" + "|".join(
                f"{k}={v}" for k, v in plan.items()))
        elif prim.get("direction") in ("bullish", "bearish"):
            lines.append(f"PLAN|{base}|status=reject|reason=rr_below_1.5")
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
