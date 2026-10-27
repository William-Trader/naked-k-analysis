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


def _state_cn(s):
    return {"up": "上涨", "down": "下跌", "range": "区间",
            "transition": "过渡"}.get(s or "", s or "未知")


def compose_event(event: dict) -> str:
    """Plain-language trading hint. Say what happened, what to do, where it fails."""
    p = event.get("payload") or {}
    symbol = (event.get("symbol") or "").replace("USDT", "")
    kind = event.get("kind")
    sev = event.get("severity", "P1")
    price = event.get("price") or 0.0
    tag = {"P0": "需要立刻看", "P1": "值得留意", "P2": "仅供观察"}.get(sev, "值得留意")
    lines = [f"{symbol} · {tag}"]

    move = p.get("move_pct")
    ratio = p.get("atr_ratio") or 0.0
    implied_atr = (price * abs(move) / 100.0 / ratio) if (move and ratio) else 0.0

    if kind in ("price_shock", "price_shock_extreme"):
        word = "急跌" if (move or 0) < 0 else "急拉"
        speed = "非常快" if kind == "price_shock_extreme" else "偏快"
        lines.append(f"1分钟{word} {abs(move or 0):.2f}%，速度{speed}"
                     + (f"（约 {ratio:.1f} 倍日常波动）" if ratio else ""))
        lines.append(f"现价 {price:,.2f}")
        if kind == "price_shock_extreme":
            lines.append("发生了什么：这种速度多半是爆仓或大单扫单，不是正常波动。")
        else:
            lines.append("发生了什么：可能是大单推动，也可能只是短线情绪，先别急着定性。")
        lines.append("现在怎么做：先别追。等 5 分钟收盘确认，站稳再跟；站不稳就是插针。")
        if implied_atr:
            if (move or 0) < 0:
                lines.append(f"关键位：回到 {price + 0.5 * implied_atr:,.0f} 上方算假摔；"
                             f"跌破 {price - 0.5 * implied_atr:,.0f} 才算真正转弱。")
            else:
                lines.append(f"关键位：站上 {price + 0.5 * implied_atr:,.0f} 才算真突破；"
                             f"跌回 {price - 0.5 * implied_atr:,.0f} 下方就是假突破。")
    elif kind == "volume_spike":
        ratio = p.get("vol_ratio")
        if ratio:
            lines.append(f"成交量突然放大（约 {ratio:.1f} 倍平时），价格几乎没动")
        else:
            lines.append("成交量突然放大，价格几乎没动")
        lines.append(f"现价 {price:,.2f}")
        lines.append("含义：有人在大量换手，但方向还没定，别把放量当成方向。")
        lines.append("现在怎么做：等这一根 K 线收盘。收在高位偏多，收在低位偏空，不猜。")
    elif kind == "range_break":
        lo, hi = p.get("r20_lo"), p.get("r20_hi")
        side = "上沿" if event.get("direction") == "up" else "下沿"
        lines.append(f"价格突破最近 20 根 K 线的{side}")
        if lo and hi:
            lines.append(f"区间 {lo:,.2f} - {hi:,.2f}，现价 {price:,.2f}")
        else:
            lines.append(f"现价 {price:,.2f}")
        lines.append("现在怎么做：等回踩确认。回踩不破再进；直接追突破，假突破概率高。")
        if lo and hi:
            lines.append(f"参考：跌回 {hi if side == '上沿' else lo:,.2f} 区间内，说明突破失败。")
    elif kind == "state_shift":
        prev, now = _state_cn(p.get("prev_state")), _state_cn(p.get("state"))
        lines.append(f"走势结构变了：{prev} → {now}")
        lines.append(f"现价 {price:,.2f}")
        lines.append("含义：高低点关系变了，方向可能切换，但还没走完确认。")
        lines.append("现在怎么做：等第一次回踩不破，再顺新方向做；别在切换瞬间追。")
    elif kind == "funding_extreme":
        rate = p.get("funding") or 0.0
        crowd = "多头拥挤" if rate > 0 else "空头拥挤"
        lines.append(f"资金费率 {rate * 100:+.4f}%，{crowd}")
        lines.append(f"现价 {price:,.2f}")
        lines.append("含义：一边持仓太挤，容易出现快速反向清算。")
        lines.append("现在怎么做：不在拥挤方向追单；已有仓位考虑减一半，等费率回落。")
    else:
        lines.append(f"现价 {price:,.2f}" if price else "市场出现异常")
        lines.append("现在怎么做：先观察，等 5 分钟收盘确认方向再动手。")

    lines.append(f"数据：Binance · 非投资建议")
    return "\n".join(lines)[:MAX_CHARS]



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
