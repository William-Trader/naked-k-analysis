# Changelog

## 3.1.0 — 2026-10-31

领域最强改造：多市场源基座、证据账本、条件 edge、知识检索、本地部署。

### 许可与文档
- 许可改为 **Personal Use & Group Exchange**（仅供个人使用与团体交流），SPDX 头 12 文件 + NOTICE + WATERMARK + README 徽章同步。
- README 去 AI 化重写：删掉营销腔，新增「致谢」章节，致敬 Al Brooks、YTC、许佳聪、胡云生、崔海军、陈浩、Adam Grimes、Wyckoff。

### 数据层（源基座）
- 新增 `nakedk/markets.py`：多市场源基座。XAU/白银/铂金（Yahoo 期货）、美股指数（SPX/NDX/DJI/RUT）、期货（ES/NQ/YM/CL）统一归一化到 Binance K 线格式，供引擎/回测/信号复用；实时 1m/5m 监测仍走加密主流（BTC/ETH）。
- `nakedk/http.py` 增加 SSL 信任回退（系统 CA 包），修复 python.org macOS 框架构建证书不完整导致的 HTTPS 失败。

### 回测（证据账本）
- 成本模型扩展：round-trip fee（cost_bps）+ 滑点（slippage_bps）+ 每 bar 资金费（funding_bps × horizon），贯穿 run / walk_forward / _simulate。

### 分析层（条件 edge）
- 新增 `nakedk/conditional.py`：订单流背离 / 资金费拥挤 / OI 背离三条件分类 + 基于订单流背离的经验概率表（OHLCV 可重建的部分），接入 fetch 输出 `COND|...` 行。

### 知识层（可检索 + 自检）
- 新增 `nakedk/knowledge.py`：知识库全文检索（`nakedk knowledge <query>`）+ 12 维 practitioner rubric 自动评分（`nakedk rubric <text>`），总分 60、可回溯到文件与行。

### 部署
- 新增 `bootstrap-local.sh` + `scripts/local_launchd_install.sh`：本地电脑（macOS/Linux）无 sudo / 无 systemd 部署，launchd 常驻。

### 测试
- 154 → 188 项全过；新增 markets / knowledge / conditional 三组测试。

## 3.0.1 — 2026-10-31


健壮性：网络层统一重试退避（评审缺口 #1）。

- 新增 `nakedk/http.py`：JSON GET 共享助手，429/418/5xx/超时/网络抖动做指数退避 + 抖动重试，其余 4xx 立即抛出，尊重 `Retry-After`。
- `nakedk/fetch.py`（ticker/klines/replay 主取数）、`nakedk/sources.py`（五源加权）、`beagle/monitor.py`（Gate 资金费率）全部改走该助手。
- 新增 `tests/test_http.py`（重试/退避/4xx 不重试/耗尽抛错）。

## 3.0.0 — 2026-10-27

大版本：数据可信度、形态覆盖与实时推送口径全面升级。

### 数据层
- 五源加权价格：Binance / Gate / OKX / KuCoin / Bitget，按 24h 成交额加权。
- 权重设计：`流动性份额 × 质量`（偏离中位数 ≤0.3% 为 1，≤1% 为 0.25，>1% 为 0），单源上限 60%。
- 输出 `effective_n` 与置信度 `high/medium/low`；偏差 >0.5% 附 `DATA_WARN`。
- W1 的 mihomo 代理模块迁移到本机运行（`mihomo.service`，127.0.0.1:7890），两台服务器不再互联。
- 多源快照按次落库 `state/multi_log.jsonl`，用于积累真实偏差分布。

### 分析层
- 形态扩展：旗形、最终旗形、测量移动、微型双底/顶、三内包、外包反转、高潮反转。
- 形态 `stage`（forming/breakout/target/failed）与家族质量校准。
- 多周期形态共振 `PATTERN_MTF`（1d 与 4h 一致性，±8%/级，最多 ±24%）。
- 趋势经验概率 `PROB`：按 regime/ADX/位置分桶，样本 <100 时合并或标 `insufficient`。
- 稳健量能：`log(volume)` + median/MAD，并输出真实倍数 `vol_ratio`。

### 推送
- 量能误报修复：`z≥5 且 ratio≥3` 双条件；`ratio<5` 降为 P2，不推送。
- P2 一律 `p2_deferred`，只进 4h 简报。
- 告警消息插入数据置信度：`多源：N源加权 · 偏差X% · 置信Y`。
- 30 分钟有效期 + 冷却 + 重试/死信。

### 反馈与回测
- 回测支持 1h 盘中路径（先触止损判定）、12bp 成本、参数网格与逐组落盘。
- 统计：有效样本量、Benjamini-Hochberg、setup×regime 单元。
- 结论（如实）：18 组参数在 240 天样本上 **0 组平均收益为正**；方向输出仅作描述。
- 蒙特卡洛验证权重：干净行情加权仅差 0.2bp，异常源场景好 7–43 倍。

### 工程
- 前端 gzip（约 24KB → 8KB）、隐藏标签页暂停轮询、事件节点上限。
- `analogs` 按 (symbol, bar) 缓存，重复调用不再重扫。
- 测试 148 个全过；CI 保持 JS 语法门禁。
