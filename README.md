# 裸K分析 · 价格行为引擎

[![ci](https://github.com/William-Trader/naked-k-analysis/actions/workflows/ci.yml/badge.svg)](https://github.com/William-Trader/naked-k-analysis/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![dependencies](https://img.shields.io/badge/dependencies-0-brightgreen.svg)](#zero-dependencies)
[![License: PolyForm Noncommercial 1.0.0](https://img.shields.io/badge/License-PolyForm%20Noncommercial%201.0.0-blue.svg)](LICENSE)
[![Watermarked](https://img.shields.io/badge/code-watermarked%20(NKA)-orange.svg)](WATERMARK.md)

> **零依赖、可回测、可闭环评分的 4h 价格行为（裸K）引擎。**
> A zero-dependency, backtested, closed-loop price-action engine.

## 为什么是它 / Why this one

大多数“价格行为机器人”只是把指标拼在一起，然后让 LLM 编一段看多看空。这个项目的做法相反：

1. **先有证据，再有规则。** 我们对机器人自己产出的 **201 条真实简报**（2026-09-13 ~ 10-20）对 Binance 真实 4h 价格做了回测。结果：24h 方向胜率只有 **40%**，唯一稳定的 edge 是 **4h 看空延续（66%）**。v2 的规则就是按这个结论写的，不是拍脑袋。见 [bench/RESULTS.md](bench/RESULTS.md)。
2. **确定性信号，LLM 可选。** `nakedk signal` 只用标准库和公开行情算出方向/置信度/止损/目标；没有 API key 也能跑。LLM 只负责写简报文案，不负责编数字。
3. **把亏损模式写进代码。** `pos20 < 0.30` 禁止看空、`pos20 > 0.70` 禁止看多、`ADX < 20` 不给趋势方向——直接掐掉回测里最亏钱的“区间边缘追单”。
4. **闭环评分。** 每条信号都有 `SIGNAL|...` 机器可读行；`nakedk score` 用真实价格回算命中率、平均收益和置信度校准，下一轮优化继续用数据说话。
5. **零依赖 + 测试 + CI + Docker。** 纯标准库，`unittest` 覆盖指标与风控规则，GitHub Actions 跑 3 个 Python 版本。

## 实测基准 / Benchmark

| 持有期 | 基准上涨率 | 看多命中 | 看空命中 | 方向合计 |
|---|---|---|---|---|
| +4h | 54.2% | 56% | **66%** | **61%** |
| +8h | 54.2% | 48% | 43% | 45% |
| +12h | 52.7% | 41% | 69% | 56% |
| +24h | 55.2% | 37% | 43% | **40%** |
| +48h | 49.8% | 44% | 43% | 44% |

样本：201 条真实简报 / BTCUSDT 4h / 2026-09-13 ~ 2026-10-20。完整方法与原始数据见 [bench/](bench/)。

### Walk-forward 现实检验 / Reality check

对 v2 引擎本身做 365 天 walk-forward（BTC/ETH 4h，无参数拟合）：

| 币 | 交易数 | 命中率 | 单笔均值 | 累计 | 最大回撤 |
|---|---|---|---|---|---|
| BTC | 446 | 49.3% | +0.006% | +1.13% | -15.72% |
| ETH | 392 | 48.2% | +0.010% | +0.60% | -19.16% |

**结论：没有找到稳健 alpha。** 9 个规则族 × 4 个周期 × 2 币 = 72 组，只有 1 组在训练/验证两段都为正（BTC 12h），符合随机噪声特征。所以本仓库不承诺收益，只承诺**可复现的证据与诚实的负结果**。详见 [bench/WALKFORWARD.md](bench/WALKFORWARD.md)。

## 快速开始 / Quickstart

```bash
# 不需要安装任何第三方包
python3 -m nakedk fetch BTCUSDT ETHUSDT   # 打印 4h 结构指标 + K线
python3 -m nakedk signal BTCUSDT ETHUSDT  # 输出确定性信号
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
| `nakedk score LEDGER.jsonl` | 用真实价格回算命中率/收益/校准 |
| `nakedk backtest SYMBOL... --days 365` | 对确定性引擎做 walk-forward 回测 |

## 架构 / Architecture

```
Binance public API (data-api.binance.vision)
        │
        ▼
nakedk.features   EMA/ADX/RSI/ATR/vol_z/swings/range-position
        │
        ▼
nakedk.signals    deterministic stance + guards + levels
        │
        ├──► TEXT briefing (LLM optional) ──► QQ / chat
        └──► SIGNAL|... ──► ledger.jsonl ──► nakedk.score
```

## 与同品类的位置 / Positioning

| | naked-k-analysis | TradingAgents | freqtrade | CryptoSignal |
|---|---|---|---|---|
| 定位 | 价格行为分析与信号 | 多智能体投研框架 | 交易执行/回测 | TA 指标信号 |
| 需要 LLM | 否（可选） | 是 | 否 | 否 |
| 价格行为结构特征 | 原生 | 部分 | 否 | 指标为主 |
| 真实产出回测 | **有（201 条）** | 无 | 策略回测 | 无 |
| 信号闭环评分 | **有** | 部分 | 无 | 无 |
| 第三方依赖 | **0** | 多 | 多 | 多 |

> 目标不是比谁的星多，而是在“价格行为”这个细分里，把**证据、可复现、零依赖**做到最好。

## 数据源 / Data

Binance 公共端点 `data-api.binance.vision`，无需 API Key。

## 免责声明 / Disclaimer

仅供学习与技术交流；仅基于历史行情做技术面判读，**不构成投资建议**。

---

## English

**Zero-dependency price-action engine for 4h crypto markets.**

- **Evidence first:** rules are derived from a backtest of 201 real briefings against Binance 4h prices. 24h directional calls scored **40%**; the only robust edge was **4h bearish continuation (66%)**.
- **Deterministic signals:** `nakedk signal` computes direction, confidence, stop and target with the standard library only. No API key, no LLM required.
- **Guards from losses:** no shorts when `pos20 < 0.30`, no longs when `pos20 > 0.70`, no trend call when `ADX < 20`.
- **Closed loop:** every signal carries a `SIGNAL|...` line; `nakedk score` replays it against real prices for hit rate, average return and confidence calibration.
- **Engineering:** stdlib only, `unittest`, GitHub Actions on Python 3.10/3.12/3.13, Dockerfile, Makefile.

```bash
python3 -m nakedk fetch BTCUSDT ETHUSDT
python3 -m nakedk signal BTCUSDT ETHUSDT
python3 -m nakedk score signals.jsonl
```

**License:** [PolyForm Noncommercial License 1.0.0](LICENSE) — source-available, **noncommercial use only**. Core modules carry a traceable watermark (`WM: NKA-XXXXXXXX`, see [WATERMARK.md](WATERMARK.md)); removing it violates the license. Historical data only; **not investment advice.**

Required Notice: Copyright (c) 2026 William-Trader (https://github.com/William-Trader)