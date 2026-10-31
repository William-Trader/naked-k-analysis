# naked-k-analysis

Zero-dependency price-action analysis and multi-frequency monitoring for crypto markets.

[![ci](https://github.com/William-Trader/naked-k-analysis/actions/workflows/ci.yml/badge.svg)](https://github.com/William-Trader/naked-k-analysis/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![version](https://img.shields.io/badge/version-1.0.1-blue.svg)](CHANGELOG.md)
[![dependencies](https://img.shields.io/badge/dependencies-0-brightgreen.svg)](#engineering)
[![License: Personal Use & Group Exchange](https://img.shields.io/badge/License-Personal%20Use%20%26%20Group%20Exchange-blue.svg)](LICENSE)
[![Watermarked](https://img.shields.io/badge/code-watermarked%20(NKA)-orange.svg)](WATERMARK.md)

> **许可 / License**: [Personal Use & Group Exchange License](LICENSE).
> **仅供个人使用与团体交流；禁止商业用途。**
> **For personal use and group exchange only. Commercial use is prohibited.**

---

## 关于本项目 / About

naked-k-analysis 把 Al Brooks 的价格行为（Price Action / 裸K）体系蒸馏成可执行的确定性规则，输出可审阅、可追溯、可评分的中立分析。它不执行交易、不承诺预测、不声明收益。

设计上坚持三条：

1. **确定性优先** — 能用规则算的（状态、结构、事件、防线、置信度）不交给大模型；模型只做叙述与综合。
2. **证据可复核** — 每条结论都落到机器可读的 `BAR / STRUCT / REGIME / POLICY / PLAN` 行，数字可回查。
3. **如实报告** — 回测没有正期望就写没有，不包装、不吹收益。

系统由三层组成：

- **`nakedk`**：确定性分析引擎（特征、趋势评分、状态、信号、评分、历史回放）。
- **`beagle`**：多频监测服务（1m/5m 事件、SQLite 状态、去重/冷却/限流、推送桥）。
- **`knowledge`**：价格行为知识模块（市场结构、逐K、Setup、主力、决策树、输出模板、OCR 提纯、Al Brooks 深度框架、评审标准、Al Brooks 术语全集与引擎映射）。

---

## 致谢 / Acknowledgments

本项目的价格行为方法论，源自以下作者与体系的公开著作。我们只做蒸馏与工程化，不声称发明这些方法；原著版权归原作者所有。

- **Al Brooks** — 价格行为交易三部曲（趋势篇 / 区间篇 / 反转篇），Always-In、Setup、市场周期与 12 问框架。本项目的方法主体与术语体系来自 Brooks。
- **YTC（Lance Beggs）** — 价格行为交易者方法（支撑阻力、时间框架、趋势方向）。
- **许佳聪** —《裸K线交易法》，Pinbar、关键位强弱、组合形态信号。
- **胡云生** —《裸K线技术分析与交易》，区间/趋势/突破结构分析、交易数学。
- **崔海军** —《裸K线操盘技法》系列，量能异动、同步/非同步性、分时相对性。
- **陈浩** — 筹码分布理论，吸筹/派发与主力行为。
- **Adam Grimes** —《技术分析的艺术与科学》，市场结构与交易策略。
- **Wyckoff** — 吸筹/派发、量价周期。

如果本项目帮助到了你，请向上述作者学习原作——本项目只是这些思想的一个可执行、可验证的实现。

---

## 功能

![仪表盘](docs/screenshots/dashboard.png)

- **六层分析链**：单根K线编码 → 结构标注（BOS/CHoCH）→ 位置上下文 → 量价关系 → 多周期共振 → 信号K质量，逐层输出机器可读行。
- **单根K线编码**：实体占比、收盘位置、上下影线、range/body 相对 ATR、与前一根重叠、bar 类型、0–100 清晰度。
- **结构标注**：ATR ZigZag 摆动点、HH/HL/LH/LL、BOS/CHoCH、结构状态机（up/down/range/transition）。
- **多周期对齐**：1d/4h/1h 三档，alignment −3…+3；方向与对齐冲突的形态直接降权。
- **量价与位置**：近似 VPOC/价值区/HVN、effort-vs-result、量价背离；距摆动位 ATR 距离、区间边缘分区、前日高低。
- **信号K六维打分**：收盘位置、实体、影线、前一根跟随、位置、量能；低于 40 视为无效信号K。
- **趋势评分 0–100**：EMA 排列 + ADX 强度 + 区间位置 + 24h 动量；输出 `TREND|...`。
- **多频监测与提醒**：1m/5m 价格冲击、量能异常、区间突破、状态切换、资金费率；P0/P1/P2 分级。
- **反馈闭环**：信号落库 → 到期评分（收益、命中、MFE/MAE、盘中先触止损还是目标）→ 分桶复盘 → 自适应权重。
- **仪表盘**：暗色终端 UI，三选项卡（行情 / 知识库 / 调参）。行情卡用 **TradingView Lightweight Charts** 渲染 K 线（蜡烛 + EMA20/50 + 支撑阻力 + 摆动点 + 形态标注，本地 vendor 零 CDN）；知识库卡内置 Markdown 渲染 + 模块目录，可在线阅读知识体系；调参卡可实时调节 stance/trend/信号K 阈值并持久化。
- **逐笔与盘口**：最近 1000 笔成交 delta、大单数，top-100 盘口失衡与价差（`TRADES` / `BOOK`）。
- **相关性门禁**：BTC/ETH 30 日相关 > 0.8 时视为同一风险，自动丢弃较弱一边（代码强制）。
- **推送防刷**：30 分钟有效期 + 冷却/限流 + 失败重试与死信。
- **OpenClaw 技能对接**：`skills/price-action-analyst` + 幂等安装脚本。
- **工程化**：零依赖、154 单测、GitHub Actions、Dockerfile、Makefile、systemd、一键部署。

### 趋势概率与形态共振

- `PROB`：按 `regime | ADX 档 | 位置档` 统计历史下一根 4h 的涨/跌/平分布；样本 <100 自动合并到 regime 池，仍不足只输出 `status=insufficient`。
- `PATTERN_MTF`：1d 形态与 4h 触发的一致性判断，对主形态做 ±8%/级的有界加权（最多 ±24%）。

### 回测结论（如实）

- 18 组参数 × 2 标的 × 8 折、含 1h 盘中路径与 12bp 成本：**0 组平均收益为正**。
- 最好一组 stop 1.5 / target 2.0 / ADX 22：平均 −0.034%，t = −0.66。
- 因此方向输出保留为**描述性判断**，不作为入场依据；详见 `docs/OPTIMIZE.md`。

---

## 快速开始

```bash
git clone https://github.com/William-Trader/naked-k-analysis.git
cd naked-k-analysis
bash bootstrap.sh
```

手动运行：

```bash
python3 -m unittest discover -s tests
python3 -m nakedk fetch BTCUSDT ETHUSDT
python3 -m nakedk signal BTCUSDT ETHUSDT
PYTHONPATH=. PORT=8080 python3 dashboard/server.py
```

### 六层分析链

| 层 | 模块 | 输出 |
|---|---|---|
| 单根K | `nakedk/bars.py` | `BAR` 行 |
| 结构 | `nakedk/structure.py` | `STRUCT` 行 |
| 多周期 | `nakedk/mtf.py` | `MTF` 行 |
| 位置 | `nakedk/location.py` | `LOC` 行 |
| 量价 | `nakedk/volume.py` | `VOLP` 行 |
| 信号K | `nakedk/signalbar.py` | `SIGBAR` 行 |

### 反馈闭环与自迭代

```bash
python -m beagle backfill --days 120   # 生成带标签的历史信号（source=engine_backfill）
python -m beagle score                 # 到期评分：收益/命中/MFE/MAE/盘中先触
python -m beagle review --apply        # 分桶复盘 + 写入自适应权重
```

实测（481 条回填样本，非实盘业绩）：

```
样本: 481 | 命中率 49.5% | Wilson [45.0, 53.9] | 期望 -0.009% | MFE 0.72 / MAE -0.66
multipliers: DB=0.9478 DT=1.0774 IHS=0.9244 L1=0.92 L2=1.0468
```

> 回填样本用于验证链路与统计方法，不代表任何实盘收益；自适应权重有界、可回滚。

---

## 自动分析与提醒

| 频率 | 任务 | 输出 |
|---|---|---|
| 1m | 价格冲击 / 量能异常 | P1/P2 事件 |
| 5m | 区间/关键位突破 | P1 事件 |
| 15m | 状态切换 / 主力迹象 | P2 事件 |
| 4h | 完整简报 | QQ 群 |
| 事件 | P0 极端行情 | 群 + 私聊 |

提醒策略：P0 立即；P1 5 分钟聚合；P2 只进 4h 简报；23:00–08:00 只推 P0；冷却 60/120/360 分钟；全局限流 6 条/小时、20 条/天。

### QQ 机器人（默认集成）

1. 复制 `config/openclaw.example.json` 到 `~/.openclaw/openclaw.json`，填入 `channels.qqbot.appId`、`channels.qqbot.clientSecret`、`gateway.auth.token`。
2. 在 `.beagle.env` 填 `BEAGLE_QQ_TARGET=group:<群 openid>`（600 权限，不进仓库）。
3. 4h 简报：`bash scripts/pa_cron_setup.sh`（先替换群 openid 占位符）。
4. 5 分钟事件推送：`beagle-push.timer`。
5. 聊天「分析BTC」：走 `pa_fetch` + `08/09` → `06` 模板。

---

## 系统组成

| 路径 | 作用 |
|---|---|
| `nakedk/features.py` | EMA、ADX、RSI、ATR、量能 z、摆动点、区间位置 |
| `nakedk/bars.py` | 单根K线编码 |
| `nakedk/structure.py` | ATR ZigZag、HH/HL/LH/LL、BOS/CHoCH、结构状态 |
| `nakedk/mtf.py` | 1d/4h/1h 多周期对齐 |
| `nakedk/signalbar.py` | 信号K六维打分 |
| `nakedk/volume.py` | VPOC/价值区、effort-vs-result、量价背离 |
| `nakedk/location.py` | 距摆动位 ATR、区间边缘、前日高低 |
| `nakedk/stats.py` | Wilson 区间、分桶统计、样本门槛 |
| `nakedk/calibration.py` | 置信度分桶校准 |
| `nakedk/trend.py` | 0–100 趋势评分 + Always-In |
| `nakedk/signals.py` | 确定性方向 + 防线 + 止损/目标 |
| `nakedk/fetch.py` | Binance 公共数据 + 文本摘要 + TREND 行 |
| `nakedk/score.py` | 信号结果回算 |
| `nakedk/backtest.py` | 历史回放（内部研究） |
| `beagle/detect.py` | 事件检测 |
| `beagle/monitor.py` | 快照 → 特征 → 事件 → SQLite |
| `beagle/push.py` | 待推送告警 → QQ |
| `beagle/review.py` | 分桶复盘 + 自适应权重写回 |
| `dashboard/` | 零依赖仪表盘 API + 暗色前端 |
| `knowledge/` | 价格行为知识模块 |
| `deploy/` | systemd 单元：monitor / push / dashboard |
| `bootstrap.sh` | 一键部署 |
| `AGENT-SETUP.md` | 给 Agent 的一键设置说明 |

---

## 扩展数据源

本工具的数据层与市场无关。价格行为交易者可以修改 `nakedk/fetch.py` 与 `beagle/config.py`，接入其他数据源（其他交易所、股票/期货/外汇 API）。

可行范围取决于：服务器性能（1m 轮询的品种数、K线回补会消耗 CPU/内存）与数据源强度（速率限制、历史深度、字段完整性与稳定性）。

建议先加一个市场、跑通 `nakedk fetch`，再逐步扩展 watchlist；不要把全市场一次性塞进 1m 轮询。

### 架构

```
L0 数据      Binance 1m/5m/15m/1h/4h/1d + 资金费率/FGI
L1 特征      EMA/ADX/RSI/ATR/量能 z/区间/摆动点
L2 事件      价格冲击/量能异常/区间突破/状态切换/资金费率
L3 分析      确定性 stance + 趋势评分 + 可选 LLM 叙述
L4 决策      P0/P1/P2 + entry/stop/target + 置信度
L5 投递      OpenClaw qqbot / 任意 webhook；去重/冷却/静默/限流
L6 反馈      SIGNAL → 结果评分 → 校准
```

完整设计：[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)。

### 工程化

- 零第三方依赖（Python 标准库 + SQLite）
- 195 个单测；GitHub Actions（3.10/3.12/3.13）
- Dockerfile、Makefile、systemd 单元
- `bootstrap.sh` 一键部署

### 许可与免责

- **Personal Use & Group Exchange License**：source-available，**仅供个人使用与团体交流**。
- **禁止商用**：不得转售、再许可、嵌入付费产品或用于任何商业服务。
- 本工具不执行交易，不构成投资建议；不声明任何历史业绩。

---

## English

### About

naked-k-analysis is a zero-dependency price-action analysis and multi-frequency monitoring toolkit. It does not execute trades, makes no prediction claims, and reports no hypothetical returns. It distils the Al Brooks framework into executable rules and produces structured, reviewable analysis.

Three layers:

- **`nakedk`** — deterministic analysis engine (features, trend score, stance, signals, scoring, replay).
- **`beagle`** — multi-frequency monitor (1m/5m events, SQLite state, cooldowns, push bridge).
- **`knowledge`** — price-action knowledge modules (market structure, bar reading, setups, smart money, decision tree, output template, OCR distillation, deep Al Brooks framework, review rubric, Al Brooks taxonomy).

### Acknowledgments

The price-action methodology is distilled from the published works of **Al Brooks** (the trading trilogy), **YTC (Lance Beggs)**, **许佳聪**, **胡云生**, **崔海军**, **陈浩** (chip distribution), **Adam Grimes**, and **Wyckoff**. We only distil and engineer these ideas; we do not claim to have invented them. All original works remain the property of their authors — please study the originals if this project helps you.

### Features

- **Deterministic first**: EMA/ADX/RSI/ATR/volume z/range position/swings are computed with rules; the LLM only narrates.
- **Trend score 0–100**: EMA alignment + ADX strength + range position + 24h momentum; emitted as `TREND|...`.
- **Multi-frequency monitoring**: 1m/5m price shocks, volume spikes, range breaks, state shifts, funding extremes.
- **Automatic alerts**: P0/P1/P2; cooldowns, quiet hours, rate limits.
- **Closed loop**: each signal carries a `SIGNAL|...` line; `nakedk score` replays it against real prices.
- **Engineering**: zero dependencies, 154 unit tests, GitHub Actions, Dockerfile, Makefile, systemd, one-click bootstrap.

### Quickstart

```bash
git clone https://github.com/William-Trader/naked-k-analysis.git
cd naked-k-analysis
bash bootstrap.sh
```

Manual:

```bash
python3 -m unittest discover -s tests
python3 -m nakedk fetch BTCUSDT ETHUSDT
python3 -m nakedk signal BTCUSDT ETHUSDT
PYTHONPATH=. PORT=8080 python3 dashboard/server.py
```

### License

**Personal Use & Group Exchange License** — source-available, for personal use and non-commercial group exchange only. Commercial use, resale, sublicensing, or incorporation into paid products is prohibited. This tool does not execute trades and does not constitute investment advice.
