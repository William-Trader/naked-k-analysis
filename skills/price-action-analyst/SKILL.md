---
name: "price-action-analyst"
description: "A股/加密价格行为（裸K）分析与监测：读 BAR/STRUCT/MTF/FLOW/TRADES/BOOK/PLAN 行，按一屏可执行格式输出，遵循 R:R≥1.5、MTF 门禁与相关性门禁。"
---

# 价格行为分析（本机部署）

任何「分析 BTC/ETH」「出简报」「复盘」「推送」请求，先按本技能执行，不要临场发明指标。

## 1. 数据入口（唯一）

```bash
python3 /home/ubuntu/nakedk-dashboard/pa_fetch.py BTCUSDT ETHUSDT
```

输出为机器可读行，按顺序：

| 行 | 含义 | 必读 |
|---|---|---|
| `BAR` | 单根K线编码（类型/质量/收盘位置/影线） | 是 |
| `STRUCT` | 结构状态 + BOS/CHoCH + 摆动位 | 是 |
| `MTF` | 1d/4h/1h 对齐，-3..+3 | 是 |
| `LOC` | 距摆动位 ATR、区间边缘、前日高低 | 是 |
| `VOLP` | VPOC/价值区、effort、背离 | 是 |
| `SIGBAR` | 信号K六维分数 + 缺失项 | 是 |
| `FLOW` | K线级 taker delta、累积 delta、背离 | 是 |
| `TRADES` | 最近 1000 笔逐笔 delta、均单、大单数 | 是 |
| `BOOK` | top-100 盘口失衡与价差 | 是 |
| `VOLS` | ATR 百分位、扩张/收缩、已实现波动 | 是 |
| `CROSS` | BTC/ETH 30d 相关、相对强弱、ETHBTC | 是 |
| `PLAN` | 可执行计划（entry/stop/target/rr/basis）或 reject 原因 | 是 |

## 2. 输出契约（不可改）

```
<币种> · 4h
结论：偏多/偏空/中性 · 置信 <0-100>
触发：<价格>（现价 <价格>）
止损：<价格>（<±%>）
目标：<价格>（R:R <数字> · <basis>）
仓位：风险 0.5% · 名义 <数字>%
失效：4h收盘 <价格> 或 <N> 小时未触发
依据：结构 <state/BOS> · <形态> · MTF <alignment> · 信号K <score>
数据：Binance · <时间> · 非投资建议
```

结尾两行严格 SIGNAL：

```
SIGNAL|BTC|<long|short|neutral>|4h|<0-100>|entry=<价>|stop=<价>|target=<价>
SIGNAL|ETH|<long|short|neutral>|4h|<0-100>|entry=<价>|stop=<价>|target=<价>
```

## 3. 硬规则（违反即返工）

- `MTF alignment >= +2` 不得做空，`<= -2` 不得做多；冲突写中性。
- `SIGBAR score < 40` 不得给方向，并写出 missing 项。
- `PLAN status=reject` 或缺失，一律中性，不得手写目标。
- `R:R < 1.5` 不做；不得用「看起来会到」代替数字。
- `FLOW div=bearish/bullish` 时，不得顺着背离方向开新仓。
- `CROSS corr30 > 0.8` 时 BTC/ETH 视为同一风险，不得同时给同向方向。
- 置信度上限 59；概率只写 40–60% 区间。
- 禁止 Markdown 表格；纯文本 ≤900 字。
- 必须写「非投资建议」。

## 4. 运维动作

```bash
# 记录当前 4h 信号（每根收盘后一次）
cd /home/ubuntu/beagle-app && PYTHONPATH=/home/ubuntu/nakedk-dashboard \
  python3 -m beagle record --config config/beagle.json

# 到期评分（MFE/MAE/盘中先触）
python3 -m beagle score --config config/beagle.json

# 周复盘 + 自适应权重
python3 -m beagle review --config config/beagle.json --apply

# 推送（加载 .beagle.env 中的 BEAGLE_QQ_TARGET）
python3 -m beagle push --config config/beagle.json --send
```

## 5. 知识库（必读）

- `knowledge/10-albrooks-taxonomy.md`：术语全集 + 引擎映射（遇到不认识的术语先查这里，不要自造）
- `knowledge/08-albrooks-deep.md`：12 问检查表
- `knowledge/05-decision-tree.md`：决策顺序
- `knowledge/09-review-rubric.md`：评审标准

形态必须写明 stage（forming / breakout / target / failed）；未突破只能写「形成中」。

## 6. 已知坑

- `openclaw` 不在 systemd PATH：push 已用 `cli_path()` 兜底；手工执行仍建议 `export PATH=$HOME/.npm-global/bin:$PATH`。
- `.beagle.env` 权限必须是 600，且 `BEAGLE_QQ_TARGET` 不能带引号包裹空格。
- Binance futures（fapi）在服务器不可达，funding/OI 走 Gate；不要把 fapi 当主源。
- SQLite 必须短连接 + 显式 close，禁用 `with sqlite3.connect()`。
- 只用已收盘 K 线；`closed_bars()` 会丢弃进行中的 bar。
- 数据源：`data-api.binance.vision`（现货）；`api.gateio.ws`（衍生品）。
