# 比格交易员 Bot · 架构 v2（推导 + 设计）

> 目标：在「价格行为分析」这个细分里做到**分析最强、推送最稳、频率最合理**。
> 非目标：承诺收益。分析质量优先于 P&L。

---

## 0. 现状（v1）与 6 个结构性问题

v1 = 单个 OpenClaw cron（每 4h）→ 跑 pa_fetch.py → LLM 按提示词写简报 → qqbot announce 到群。

| # | 问题 | 后果 |
|---|---|---|
| 1 | **单频 4h** | 盘中急跌/放量/关键位破位，最多晚 4 小时才知道 |
| 2 | **无状态** | 同一事件反复推送，或该推的没推；无法去重/冷却 |
| 3 | **LLM 单点** | 402/超时/限流 → 静默失败（已实际发生 12 次） |
| 4 | **无反馈** | 置信度不校准，错在哪不知道 |
| 5 | **无健康监控** | 服务挂了没人知道 |
| 6 | **数据源单点** | Binance 故障即盲；无 fallback |

## 1. 设计原则

1. **确定性优先**：能用规则算的（状态、事件、防线、置信度）不交给 LLM；LLM 只做叙述与综合。
2. **频率分层**：检测高频、分析中频、推送低频；不是所有东西都 4h，也不是所有东西都 1m。
3. **状态即真相**：所有事件/信号/推送/结果落 SQLite；可追溯、可回放、可评分。
4. **失败可降级**：LLM 挂了走模板；数据源挂了走备源；推送失败进 outbox 重试。
5. **推送克制**：严重级别 + 去重 + 冷却 + 静默时段 + 全局限流。
6. **证据可验证**：每条结论带数字与来源；回测/评分可复现。

## 2. 分层架构

```
L0 数据层   Binance(1m/5m/15m/1h/4h/1d) + Gate/KuCoin fallback + funding/FGI/OI
              |
L1 特征层   nakedk.features: EMA20/50, ADX14, RSI14, ATR%, vol_z, range20/40, pos, swings
              |
L2 事件层   deterministic detectors: 价格冲击, 量能异常, 区间突破, 关键位破, 资金费率极端, OI 背离
              |
L3 分析层   确定性 stance（nakedk.signals）+ LLM 叙述（knowledge 05/06）+ 事实校验
              |
L4 决策层   severity P0/P1/P2 + trade plan（entry/stop/target）+ confidence 校准
              |
L5 投递层   OpenClaw/qqbot：定时简报 vs 事件警报；去重/冷却/静默/限流/路由
              |
L6 反馈层   outcome scoring（+4h/+24h）、calibration、weekly review
```

## 3. 频率矩阵（核心融合设计）

| 频率 | 任务 | 触发条件 | 输出 | 是否 LLM |
|---|---|---|---|---|
| **1m** | 价格冲击 / 量能异常 | abs(Δ1m) ≥ 0.8×ATR14 或 vol_z ≥ 3 | P1/P2 事件 | 否 |
| **5m** | 区间/关键位突破 | 收盘突破 r20 边界 + vol_z≥1 | P1 事件 | 否 |
| **15m** | 结构更新 / 主力迹象 | 状态切换（trend↔range）或扫单形态 | P2 事件 | 否 |
| **4h** | 完整简报 | 定时 00/04/08/12/16/20:05 | 群简报 | 是（叙述） |
| **1d** | 复盘 + 校准 | 每日 00:10 | 日报/内部 | 部分 |
| **事件** | 极端行情 | P0 阈值（±3×ATR、闪崩、放量破位） | 立即群+私聊 | 是（短） |

> 关键：**1m/5m 只做检测不做长文**；4h 才做完整分析。这样既不错过事件，也不刷屏。

## 4. 事件定义与严重级别

| 事件 | 条件 | 级别 |
|---|---|---|
| 价格冲击 | abs(Δ1m) ≥ 0.8×ATR14(4h) | P1 |
| 极端冲击 | abs(Δ5m) ≥ 2.0×ATR14 或 abs(Δ1h) ≥ 3% | P0 |
| 量能异常 | vol_z(1m/5m) ≥ 3 且 abs(Δ) ≥ 0.3×ATR | P1 |
| 区间突破 | 5m 收盘 > r20_hi 或 < r20_lo，且 vol_z≥1 | P1 |
| 关键位破 | 突破前高/前低/EMA50 且跟随 | P1 |
| 状态切换 | trend↔range、ADX 上/下穿 20/25 | P2 |
| 资金费率极端 | abs(funding) ≥ 0.1%/8h | P2 |
| OI 背离 | 价涨 OI 跌 / 价跌 OI 涨 | P2 |
| 数据源故障 | 主源连续 3 次失败 | P1（运维） |
| LLM 故障 | 连续 2 次失败 | P1（运维） |

## 5. 推送策略（防刷屏）

- **路由**：P0 → 群 + 私聊；P1 → 群；P2 → 只进 4h 简报汇总。
- **去重**：同一 (symbol, event, direction) 在 **cooldown** 内只推一次：P0 60m，P1 120m，P2 360m。
- **静默**：23:00–08:00 只推 P0；其余进 08:00 汇总。
- **限流**：全局 ≤ 6 条/小时，≤ 20 条/天；超限进 outbox。
- **聚合**：5m 内同一 symbol 的多个 P1 合并为一条。
- **可追溯**：每条推送写 alerts 表（event_id、severity、payload、sent_at、status）。

## 6. 可靠性 / 降级

| 故障 | 降级 |
|---|---|
| LLM 402/超时 | 用 nakedk.signals 的确定性模板生成；标注「降级模式」 |
| Binance 失败 | 切 Gate/KuCoin；仍失败 → 运维 P1 |
| 推送失败 | 重试 3 次（指数退避）→ outbox；次日汇总 |
| 服务崩溃 | systemd Restart=always；health 表 heartbeat |
| 重复发送 | event_id 幂等键 + alerts 唯一约束 |

## 7. 反馈闭环（分析质量）

1. 每条 SIGNAL 落 signals 表（ts/symbol/direction/confidence/entry/stop/target）。
2. +4h / +24h 自动回填真实价格 → outcomes。
3. 计算：命中率、平均 signed return、置信度分箱校准（Brier）。
4. 每周复盘：哪些 setup 有效、哪些状态误判、哪些事件噪声大。
5. 只根据**样本量足够**的结论调整提示词/权重；不做单次调参。

## 8. 工程化

- 零第三方依赖（stdlib + SQLite）。
- 目录：beagle/{config,store,detect,monitor,score,cli}.py；测试 tests/。
- 部署：beagle-monitor.service（常驻，1m 轮询）+ OpenClaw cron（4h 简报 / 每日复盘）。
- 观测：status（心跳、最后事件、队列深度、错误率）；日志结构化 JSON。
- CI：unittest + compileall；Docker 可选。

## 9. 验证计划

1. **事件检测**：用 1m/5m 历史回放，统计 precision/recall（人工标注 50 个事件）。
2. **分析一致性**：同一数据跑 3 次，方向一致率应 ≥90%；数字必须来自 SIG 行。
3. **延迟**：1m 事件从发生到入库 ≤ 5s；P0 从入库到推送 ≤ 60s。
4. **可用性**：monitor 心跳 ≥99%；推送成功率 ≥99%（含重试）。
5. **回放**：历史简报 → 校准曲线（内部研究，不对外声明）。

## 10. 迁移步骤（v1 → v2）

1. 部署 beagle 包与 SQLite（不动现有 4h cron）。
2. 启动 beagle-monitor（只写事件，不推送）→ 观察 24h 噪声。
3. 接入 beagle-push（先 dry-run，再群推送）。
4. 保留 4h 简报，改为读取 beagle 的最新 state。
5. 上线每日复盘/评分；观察一周后调阈值。

## 11. 取舍

- **不做**：高频交易执行、杠杆/仓位管理、全市场 400 币 1m 轮询（成本高、噪声大）。
- **先做**：BTC/ETH + Top 10 关注列表的 1m/5m 监测；4h 全分析。
- **宁可漏报，不可刷屏**：P2 默认只进简报。

---

*本文件是 v2 的设计基线；实现进度见仓库 beagle/。*