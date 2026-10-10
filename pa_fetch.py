#!/usr/bin/env python3
# -----------------------------------------------------------------
# pa_fetch.py - naked-k-analysis core price-action data/deploy logic
# (c) 2026 William-Trader (https://github.com/William-Trader)
# WM: NKA-FD2C1B22
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Removing this mark violates the license.
# -----------------------------------------------------------------
# -*- coding: utf-8 -*-
"""价格行为分析师 - 数据获取与摘要
数据源: data-api.binance.vision (Binance 公共数据端点)
输出: 紧凑文本摘要, 供 LLM 做价格行为分析
用法: python3 pa_fetch.py [BTCUSDT ETHUSDT ...]
"""
import json, sys, time
from datetime import datetime, timezone, timedelta
from urllib.request import urlopen, Request

BASE = "https://data-api.binance.vision"
CST = timezone(timedelta(hours=8))

def fetch(path, timeout=15):
    req = Request(BASE + path, headers={"User-Agent": "pa-analyst/1.0"})
    with urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())

def fmt_num(x, nd=2):
    return f"{x:,.{nd}f}"

def analyze_symbol(sym):
    lines = [f"===== {sym} ====="]
    t = fetch(f"/api/v3/ticker/24hr?symbol={sym}")
    price = float(t["lastPrice"])
    lines.append(f"现价: {fmt_num(price)} | 24h: {float(t['priceChangePercent']):+.2f}% | 24h高/低: {fmt_num(float(t['highPrice']))} / {fmt_num(float(t['lowPrice']))}")
    lines.append(f"24h成交量: {fmt_num(float(t['volume']), 1)} {sym[:3]} | 24h成交额: {fmt_num(float(t['quoteVolume'])/1e6, 1)}M USDT")

    # 4h K线 42根
    k4 = fetch(f"/api/v3/klines?symbol={sym}&interval=4h&limit=42")
    lines.append("\n--- 4小时K线 (最近42根, 最新在最后) ---")
    lines.append("时间(北京)         开         高         低         收        涨跌%   量(相对均)")
    vols = [float(x[5]) for x in k4]
    avgv = sum(vols) / len(vols)
    prev = None
    lows, highs = [], []
    for x in k4:
        ts = datetime.fromtimestamp(x[0]/1000, CST).strftime("%m-%d %H:%M")
        o, h, l, c, v = float(x[1]), float(x[2]), float(x[3]), float(x[4]), float(x[5])
        chg = (c - o) / o * 100
        vr = v / avgv
        marker = ""
        if vr > 1.5: marker = " 量!"
        lines.append(f"{ts}  {fmt_num(o,1):>10} {fmt_num(h,1):>10} {fmt_num(l,1):>10} {fmt_num(c,1):>10}  {chg:+5.2f}%  {vr:.1f}{marker}")
        prev = c
    # ATR14 (4h)
    trs = []
    for i in range(1, len(k4)):
        h, l, pc = float(k4[i][2]), float(k4[i][3]), float(k4[i-1][4])
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    atr = sum(trs[-14:]) / 14
    # 最近20根区间
    last20 = k4[-20:]
    rhi = max(float(x[2]) for x in last20)
    rlo = min(float(x[3]) for x in last20)
    lines.append(f"\n4h ATR(14): {fmt_num(atr, 1)} ({atr/price*100:.2f}%) | 最近20根(约3.3天)区间: {fmt_num(rlo)} ~ {fmt_num(rhi)} ({(rhi-rlo)/price*100:.1f}%)")

    # 1h K线 24根
    k1 = fetch(f"/api/v3/klines?symbol={sym}&interval=1h&limit=24")
    lines.append("\n--- 1小时K线 (最近24根, 简) ---")
    row = []
    for x in k1:
        ts = datetime.fromtimestamp(x[0]/1000, CST).strftime("%H:%M")
        row.append(f"{ts} O{float(x[1]):.0f} H{float(x[2]):.0f} L{float(x[3]):.0f} C{float(x[4]):.0f}")
    for i in range(0, len(row), 2):
        lines.append("  " + " | ".join(row[i:i+2]))
    return "\n".join(lines)

def main():
    syms = sys.argv[1:] or ["BTCUSDT", "ETHUSDT"]
    now = datetime.now(CST)
    print(f"# 价格行为数据摘要 | {now.strftime('%Y-%m-%d %H:%M')} 北京时间")
    for s in syms:
        try:
            print()
            print(analyze_symbol(s))
        except Exception as e:
            print(f"\n[{s}] 数据获取失败: {e}")
    print("\n# 数据源: Binance 现货 (data-api.binance.vision)")

if __name__ == "__main__":
    main()
