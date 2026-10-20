# 裸K分析 · 价格行为引擎

[![ci](https://github.com/William-Trader/naked-k-analysis/actions/workflows/ci.yml/badge.svg)](https://github.com/William-Trader/naked-k-analysis/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![dependencies](https://img.shields.io/badge/dependencies-0-brightgreen.svg)](#zero-dependencies)
[![License: PolyForm Noncommercial 1.0.0](https://img.shields.io/badge/License-PolyForm%20Noncommercial%201.0.0-blue.svg)](LICENSE)
[![Watermarked](https://img.shields.io/badge/code-watermarked%20(NKA)-orange.svg)](WATERMARK.md)

> **零依赖、知识驱动、可闭环评分的 4h 价格行为（裸K）分析与监测引擎。**
> A zero-dependency, knowledge-driven price-action analysis and monitoring engine.

## 为什么是它 / Why this one

1. **知识驱动**：把 Al Brooks、YTC、崔海军、胡云生、许佳聪、陈浩《筹码分布》、Wyckoff 等资料蒸馏成可执行规则（`knowledge/` 7 个模块）。
2. **确定性优先**：状态、防线、事件用规则算；LLM 只做叙述与综合，不负责编数字。
3. **把风险模式写进代码**：`pos20 < 0.30` 禁止看空、`pos20 > 0.70` 禁止看多、`ADX < 20` 不给趋势方向。
4. **闭环评分**：每条信号带 `SIGNAL|...` 行；`nakedk score` 用真实价格回算结果，供内部复盘。**不对外声明历史战绩。**
5. **多频监测**：`beagle` 在 1m/5m 做事件检测，4h 做完整简报，1d 做复盘；去重/冷却/静默/限流。
6. **工程化**：零依赖、22+ 单测、GitHub Actions、Dockerfile、Makefile、systemd 单元。

## 知识库 / Knowledge base

| 文件 | 内容 |
|---|---|
| `01-market-structure.md` | 四支柱、市场周期、趋势/区间/通道、状态机 |
| `02-bar-reading.md` | 信号K/入场K、K线类型、买压卖压、订单流 |
| `03-setups.md` | H1-H4/L1-L4、DB/DT、楔形、最终旗形、MTR、头肩、BLSHS |
| `04-smart-money.md` | 吸筹/派发、筹码形态、Stop run/吸收/背离、主力 7 问 |
| `05-decision-tree.md` | 9 步决策流程 + 置信度评分 + 硬规则 |
| `06-output-template.md` | 机器人输出模板 + 示例 |
| `07-ocr-distilled.md` | 扫描书 OCR 提纯：崔海军/胡云生/许佳聪 |

## 快速开始 / Quickstart

```bash
# 不需要安装任何第三方包
python3 -m nakedk fetch BTCUSDT ETHUSDT   # 4h 结构指标 + K线
python3 -m nakedk signal BTCUSDT ETHUSDT  # 确定性信号 + SIGNAL 行
python3 -m nakedk signal BTCUSDT --json   # 机器可读
```

部署到 OpenClaw（可选，用于 QQ/群推送）：

```bash
cp config/openclaw.example.json ~/.openclaw/openclaw.json  # 填入自己的凭据
bash scripts/pa_cron_setup.sh                               # 每 4 小时推送
```

## CLI

| 命令 | 作用 |
|---|---|
| `nakedk fetch SYMBOL...` | 4h 结构摘要（EMA/ADX/RSI/ATR/量能/区间/摆动点） |
| `nakedk signal SYMBOL...` | 确定性方向 + 置信度 + 止损/目标 + SIGNAL 行 |
| `nakedk score LEDGER.jsonl` | 用真实价格回算信号结果（内部复盘） |

## 架构 v2 / Architecture

- 设计推导与分层：[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- 多频监测服务：`beagle/`（1m/5m 事件 → SQLite → 4h 简报）
- 部署单元：`deploy/beagle-monitor.service`

## 与同品类的位置 / Positioning

| | naked-k-analysis | TradingAgents | freqtrade | CryptoSignal |
|---|---|---|---|---|
| 定位 | 价格行为分析与监测 | 多智能体投研框架 | 交易执行/回测 | TA 指标信号 |
| 需要 LLM | 否（可选） | 是 | 否 | 否 |
| 价格行为结构特征 | 原生 | 部分 | 否 | 指标为主 |
| 知识库蒸馏 | **7 模块** | 部分 | 否 | 否 |
| 信号闭环评分 | **有** | 部分 | 无 | 无 |
| 第三方依赖 | **0** | 多 | 多 | 多 |

> 目标不是比星数，而是在「价格行为」细分里，把知识、可复现、零依赖做到最好。

## 数据源 / Data

Binance 公共端点 `data-api.binance.vision`，无需 API Key。

## 免责声明 / Disclaimer

仅供学习与技术交流；仅基于历史行情做技术面判读，**不构成投资建议**。

---

## English

**Zero-dependency, knowledge-driven price-action engine for 4h crypto markets.**

- **Knowledge-driven:** distilled rules from Al Brooks, YTC, Cui Haijun, Hu Yunsheng, Xu Jiacong, chip-distribution and Wyckoff material (`knowledge/`, 7 modules).
- **Deterministic first:** state, guards and events are computed with rules; the LLM only narrates.
- **Risk patterns in code:** no shorts when `pos20 < 0.30`, no longs when `pos20 > 0.70`, no trend call when `ADX < 20`.
- **Closed loop:** every signal carries a `SIGNAL|...` line; `nakedk score` replays it against real prices for internal review. **No historical performance claims are made.**
- **Multi-frequency monitoring:** `beagle` detects 1m/5m events, writes a 4h briefing and a daily review, with cooldowns, quiet hours and rate limits.
- **Engineering:** stdlib only, 22+ unit tests, GitHub Actions, Dockerfile, Makefile, systemd unit.

```bash
python3 -m nakedk fetch BTCUSDT ETHUSDT
python3 -m nakedk signal BTCUSDT ETHUSDT
python3 -m nakedk score signals.jsonl
```

**License:** [PolyForm Noncommercial License 1.0.0](LICENSE) — source-available, **noncommercial use only**. Core modules carry a traceable watermark (`WM: NKA-XXXXXXXX`, see [WATERMARK.md](WATERMARK.md)); removing it violates the license. **Not investment advice.**

Required Notice: Copyright (c) 2026 William-Trader (https://github.com/William-Trader)