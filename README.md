# naked-k-analysis

**Zero-dependency price-action analysis and multi-frequency monitoring for crypto markets.**

[![ci](https://github.com/William-Trader/naked-k-analysis/actions/workflows/ci.yml/badge.svg)](https://github.com/William-Trader/naked-k-analysis/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![dependencies](https://img.shields.io/badge/dependencies-0-brightgreen.svg)](#zero-dependencies)
[![License: PolyForm Noncommercial 1.0.0](https://img.shields.io/badge/License-PolyForm%20Noncommercial%201.0.0-blue.svg)](LICENSE)
[![Watermarked](https://img.shields.io/badge/code-watermarked%20(NKA)-orange.svg)](WATERMARK.md)

## Overview

naked-k-analysis is a self-contained toolkit for reading price action (naked K), producing deterministic signals, monitoring market events, and delivering structured briefings.

It is organised in three layers:

- **`nakedk`** — deterministic analysis engine: features, stance, levels, signal ledger, scoring, walk-forward replay.
- **`beagle`** — multi-frequency monitor: 1m/5m event detection, SQLite state, cooldowns, rate limits, push bridge.
- **`knowledge`** — distilled price-action playbooks (Al Brooks, YTC, Wyckoff, chip distribution, and Chinese naked-K authors).

## Features

- **Deterministic first.** State, guards and events are computed with rules; an LLM is optional and only narrates.
- **Price-action native.** Market cycle, always-in, signal bars, H1-H4/L1-L4, DB/DT, wedges, final flags, MTR, BLSHS.
- **Multi-frequency.** 1m/5m detection, 4h briefings, daily review.
- **Closed loop.** Every signal carries a machine-readable `SIGNAL|...` line; `nakedk score` replays it against real prices for internal review.
- **Zero dependencies.** Python standard library only; SQLite for state.
- **Production-ready.** 33 unit tests, GitHub Actions (3.10/3.12/3.13), Dockerfile, Makefile, systemd units.

## Components

| Path | Purpose |
|---|---|
| `nakedk/features.py` | EMA, ADX, RSI, ATR, volume z-score, swing points, range position |
| `nakedk/signals.py` | Deterministic stance engine with guards and levels |
| `nakedk/fetch.py` | Binance public-data fetcher and text summariser |
| `nakedk/score.py` | Signal-ledger outcome scoring |
| `nakedk/backtest.py` | Walk-forward replay of the deterministic engine |
| `nakedk/cli.py` | `fetch`, `signal`, `score`, `backtest` |
| `beagle/detect.py` | Price-shock, volume-spike, range-break, state-shift, funding detectors |
| `beagle/monitor.py` | Snapshot -> features -> events -> SQLite |
| `beagle/push.py` | Pending-alert push bridge |
| `beagle/replay.py` | Historical event calibration |
| `beagle/store.py` | SQLite schema and state |
| `knowledge/` | Price-action playbooks and output template |
| `dashboard/server.py` | Zero-dependency dashboard API (`/api/overview`) |
| `dashboard/index.html` | Dark terminal UI (trend score, levels, stance, events) |
| `deploy/` | systemd units for monitor, push timer and dashboard |

## Quickstart

```bash
git clone https://github.com/William-Trader/naked-k-analysis.git
cd naked-k-analysis
python3 -m unittest discover -s tests
python3 -m nakedk fetch BTCUSDT ETHUSDT
python3 -m nakedk signal BTCUSDT ETHUSDT
```

Docker:

```bash
docker build -t nakedk .
docker run --rm nakedk fetch BTCUSDT ETHUSDT
```

## CLI

| Command | Purpose |
|---|---|
| `python3 -m nakedk fetch SYMBOL...` | 4h structure: EMA/ADX/RSI/ATR/volume/range/swings |
| `python3 -m nakedk signal SYMBOL...` | Deterministic direction, confidence, stop, target, SIGNAL line |
| `python3 -m nakedk score LEDGER.jsonl` | Replay signals against real prices |
| `python3 -m nakedk backtest SYMBOL... --days 365` | Walk-forward replay of the engine |
| `python3 -m beagle once` | One monitoring scan |
| `python3 -m beagle monitor` | Continuous 60s monitor |
| `python3 -m beagle replay --days 1` | Historical event calibration |
| `python3 -m beagle push --dry-run` | Preview pending alerts |
| `python3 -m beagle status` | Heartbeat, queue depth, last event |

## Monitoring

`beagle` polls a watchlist and writes normalised events to SQLite:

| Event | Severity | Trigger |
|---|---|---|
| `price_shock` | P1 | abs(1m move) >= 0.5% or 0.8x ATR |
| `price_shock_extreme` | P0 | abs(1m move) >= 1.5% or 2.0x ATR |
| `volume_spike` | P1 | volume z-score >= 4 with a price move |
| `range_break` | P1 | close beyond the 20-bar range with volume |
| `state_shift` | P2 | trend state changes |
| `funding_extreme` | P2 | abs(funding) >= 0.1% per 8h |

Delivery policy:

- P0 -> group + direct; P1 -> group; P2 -> only in the 4h briefing.
- Cooldowns: P0 60 min, P1 120 min, P2 360 min.
- Quiet hours: 23:00-08:00, P0 only.
- Rate limits: 6 per hour, 20 per day.

Configuration: `config/beagle.json`. The push target is read from `BEAGLE_QQ_TARGET` (environment file), never committed.

## Knowledge base

| File | Content |
|---|---|
| `01-market-structure.md` | Market cycle, trend/range/channel, state machine |
| `02-bar-reading.md` | Signal/entry bars, bar types, buying/selling pressure, order flow |
| `03-setups.md` | H1-H4/L1-L4, DB/DT, wedges, final flags, MTR, head-and-shoulders, BLSHS |
| `04-smart-money.md` | Accumulation/distribution, chip patterns, stop runs, absorption, divergence |
| `05-decision-tree.md` | 9-step decision flow, confidence scoring, hard guards |
| `06-output-template.md` | Briefing template and example |
| `07-ocr-distilled.md` | OCR-distilled rules from scanned Chinese naked-K books |
| `08-albrooks-deep.md` | Deep Al Brooks framework: cycle, always-in, setups, probability, management, 12 questions |
| `09-review-rubric.md` | 12-criterion output review rubric (0-60) |

## Architecture

```
L0 Data      Binance public 1m/5m/15m/1h/4h/1d + optional funding/FGI
L1 Features  EMA20/50, ADX14, RSI14, ATR%, volume z, range 20/40, swings
L2 Events    price shock, volume spike, range break, state shift, funding
L3 Analysis  deterministic stance + optional LLM narration (knowledge/05, 08)
L4 Decision  severity, entry/stop/target, confidence
L5 Delivery  OpenClaw/qqbot or any webhook; cooldowns, quiet hours, rate limits
L6 Feedback  SIGNAL ledger -> outcome scoring -> calibration
```

Full design: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Dashboard

`dashboard/` ships a zero-dependency dark terminal UI:

```bash
PYTHONPATH=. PORT=8080 python3 dashboard/server.py
```

It exposes `/api/overview` and renders BTC/ETH trend scores, key levels, stance and event feed. The page refreshes every 60 seconds.

## Deployment

```bash
rsync -az --exclude .git ./ user@host:/opt/naked-k-analysis/
sudo cp deploy/beagle-monitor.service /etc/systemd/system/
sudo cp deploy/beagle-push.service deploy/beagle-push.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now beagle-monitor beagle-push.timer
sudo cp deploy/nakedk-dashboard.service /etc/systemd/system/
sudo systemctl enable --now nakedk-dashboard
```

## Data

Binance public endpoints (`data-api.binance.vision`). No API key required.

## What this is / is not

**It is:**

- a deterministic price-action analysis engine;
- a multi-frequency event monitor;
- a structured briefing generator with a review rubric.

**It is not:**

- a trading executor;
- a prediction engine with a validated edge;
- investment advice.

## Scope and disclaimer

This is an analysis and monitoring toolkit, not a trading system. It does not execute orders and makes **no historical performance claims**. Outputs are technical readings of price action and are **not investment advice**.

## License and watermark

[PolyForm Noncommercial License 1.0.0](LICENSE) — source-available, **noncommercial use only**.
Core modules carry a traceable watermark (`WM: NKA-XXXXXXXX`, see [WATERMARK.md](WATERMARK.md)); removing it violates the license.

Required Notice: Copyright (c) 2026 William-Trader (https://github.com/William-Trader)

---

## 中文说明

**零依赖的价格行为（裸K）分析与多频监测工具包。**

- **`nakedk`**：确定性分析引擎（特征、状态、信号、评分、历史回放）。
- **`beagle`**：1m/5m 事件监测 + SQLite 状态 + 去重/冷却/限流 + 推送桥。
- **`knowledge`**：9 个价格行为模块（市场结构、逐K、Setup、主力、决策树、输出模板、OCR 提纯、Al Brooks 深度框架、评审标准）。

```bash
python3 -m unittest discover -s tests
python3 -m nakedk fetch BTCUSDT ETHUSDT
python3 -m nakedk signal BTCUSDT ETHUSDT
python3 -m beagle status
```

许可：PolyForm Noncommercial 1.0.0（非商用）。仅用于学习与技术分析，不构成投资建议；不声明任何历史业绩。