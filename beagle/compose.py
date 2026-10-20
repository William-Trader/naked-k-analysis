"""Top-tier message composition: one screen, actionable, source-stamped."""
from __future__ import annotations

MAX_CHARS = 900
DISCLAIMER = "非投资建议"
NL = chr(10)


def _fmt(x, nd=2):
    if x is None:
        return "—"
    return f"{x:,.{nd}f}"


def plan(signal: dict, price: float, atr: float, risk_pct: float = 0.5,
         ttl_h: int = 8):
    side = signal.get("direction")
    if side not in ("long", "short") or not price or not atr:
        return None
    entry = float(signal.get("entry") or price)
    stop = float(signal.get("stop") or (entry - 1.5 * atr if side == "long"
                                        else entry + 1.5 * atr))
    target = float(signal.get("target") or (entry + 2.0 * atr if side == "long"
                                            else entry - 2.0 * atr))
    risk = abs(entry - stop)
    if risk <= 0:
        return None
    rr = abs(target - entry) / risk
    if rr < 1.5:
        return None
    stop_pct = risk / entry * 100.0
    notional = min(200.0, risk_pct / stop_pct * 100.0) if stop_pct else 0.0
    return {"side": side, "entry": round(entry, 2), "stop": round(stop, 2),
            "target": round(target, 2), "rr": round(rr, 2),
            "stop_pct": round(stop_pct, 2), "risk_pct": risk_pct,
            "notional_pct": round(notional, 1), "ttl_h": ttl_h,
            "invalidate": "4h收盘" + ("<" if side == "long" else ">") + f" {round(stop, 2)}"}


def compose_signal(symbol: str, data: dict, stamp: str = "") -> str:
    base = symbol.replace("USDT", "")
    price = data.get("price")
    dirn = (data.get("direction") or "neutral").lower()
    label = {"long": "偏多", "short": "偏空", "neutral": "中性"}.get(dirn, dirn)
    conf = data.get("confidence")
    struct_state = data.get("structure_state")
    conflict = ((dirn == "long" and struct_state == "down")
                or (dirn == "short" and struct_state == "up"))
    if conflict and isinstance(conf, int):
        conf = min(59, conf)
    lines = [f"{base} · 4h" + (f" · {stamp}" if stamp else ""),
             f"结论：{label}" + (f" · 置信 {conf}" if conf is not None else "")]
    if conflict:
        lines.append("注意：结构与大周期方向冲突，置信上限 59，等 BOS 确认")
    p = data.get("plan")
    if p:
        stop_txt = -p["stop_pct"] if p["side"] == "long" else p["stop_pct"]
        lines += [
            (f"触发：现价 {_fmt(p['entry'])}（即时）"
             if price and abs(p['entry'] - price) / price < 0.001
             else f"触发：{_fmt(p['entry'])}（现价 {_fmt(price)}）"),
            f"止损：{_fmt(p['stop'])}（{stop_txt:+.2f}%）",
            f"目标：{_fmt(p['target'])}（R:R {p['rr']} · {p.get('basis', 'structure')}）",
            f"仓位：风险 {p['risk_pct']}% · 名义 {p['notional_pct']}%",
            f"失效：{p['invalidate']}",
        ]
    else:
        lines.append("计划：R:R 不足 1.5 或方向中性，不出手")
    ev = data.get("evidence") or []
    if ev:
        lines.append("依据：" + " · ".join(ev))
    src = data.get("source") or "Binance"
    ts = data.get("data_time") or stamp
    lines.append(f"数据：{src}" + (f" · {ts}" if ts else "") + f" · {DISCLAIMER}")
    text = NL.join(lines)
    return text if len(text) <= MAX_CHARS else text[:MAX_CHARS - 1] + "…"


def compose_event(event: dict) -> str:
    p = event.get("payload") or {}
    symbol = (event.get("symbol") or "").replace("USDT", "")
    kind = event.get("kind")
    sev = event.get("severity", "P1")
    price = event.get("price")
    bits = []
    for key, label in (("move_pct", "1m变动"), ("atr_ratio", "ATR倍数"),
                       ("vol_z", "量能z"), ("funding", "资金费率")):
        if p.get(key) is not None:
            val = p[key]
            bits.append(label + " " + (f"{val:+.2f}" if isinstance(val, float) else str(val)))
    lines = [f"[{sev}] {symbol} · {kind}",
             " ".join(bits) if bits else f"现价 {_fmt(price)}"]
    if kind == "price_shock_extreme":
        lines += ["含义：单根1m冲击超过2倍ATR，多为清算或大单",
                  "建议：不追单，等 5m 收盘确认；插针极值外侧再考虑止损"]
    elif kind == "price_shock":
        lines += ["含义：短线推进，需成交量与5m收盘确认",
                  "建议：站稳再跟；回落至事件起点下方视为假突破"]
    elif kind == "volume_spike":
        lines += ["含义：量能异常，可能为吸筹或派发",
                  "建议：看下一根K线收盘位置；无跟随则不参与"]
    elif kind == "range_break":
        lines += ["含义：区间边缘突破，需回踩确认",
                  "建议：回踩不破再进；直接追突破的失败率高"]
    elif kind == "state_shift":
        lines += [f"含义：结构由 {p.get('prev_state')} 切到 {p.get('state')}",
                  "建议：等新结构的第一次回踩，不猜顶底"]
    else:
        lines.append("含义：需结合 4h 结构判断")
    lines.append(f"数据：Binance · {DISCLAIMER}")
    return NL.join(lines)[:MAX_CHARS]


def validate_message(text: str) -> dict:
    issues = []
    if len(text) > MAX_CHARS:
        issues.append(f"超长 {len(text)}>{MAX_CHARS}")
    for line in text.splitlines():
        if line.startswith("|") and line.count("|") >= 2:
            issues.append("包含 Markdown 表格")
            break
    for must in ("结论", "数据", DISCLAIMER):
        if must not in text:
            issues.append("缺少" + must)
    return {"ok": not issues, "issues": issues, "chars": len(text)}
