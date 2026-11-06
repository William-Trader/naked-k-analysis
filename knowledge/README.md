# 价格行为知识库（裸K / Price Action）

本目录是把 `交易/01-价格行为` 中的 Al Brooks、YTC、许佳聪、胡云生、崔海军、陈浩筹码分布等资料**蒸馏成可执行规则**的结果。

| 文件 | 内容 |
|---|---|
| 01-market-structure.md | 四支柱、市场周期、趋势/区间/通道、状态机 |
| 02-bar-reading.md | 信号K/入场K、K线类型、买压卖压、订单流 |
| 03-setups.md | H1-H4/L1-L4、DB/DT、楔形、最终旗形、MTR、头肩、BLSHS |
| 04-smart-money.md | 吸筹/派发、筹码形态、Stop run/吸收/背离、7 问 |
| 05-decision-tree.md | 9 步决策流程 + 置信度评分 + 禁止事项 |
| 06-output-template.md | 机器人输出模板 + 真实示例 |
| 07-ocr-distilled.md | 扫描书 OCR 提纯：崔海军/胡云生/许佳聪（异动、相对强弱、支撑质量、入场止损） |
| 08-albrooks-deep.md | Al Brooks 深度框架：周期/Always-In/Setup/概率/管理/12问 |
| 09-review-rubric.md | 输出评审标准（12项×5分=60） |
| 10-albrooks-taxonomy.md | Al Brooks 术语全集与引擎映射 |
| 11-risk-management.md | 交易者方程、止损、实际风险、订单类型（Video 30/32/33/34） |
| 12-swing-scalp.md | 波段 vs 剥头皮的量化画像 + 程序化交易认知（Video 31/5） |
| 13-quantitative-parameters.md | Brooks 实证概率数字全集（80%/70%/40%/60%…） |
| 14-pattern-details.md | 三角形/头肩/圆弧/窄幅组合/微通道细节补遗 |
| 15-position-sizing-and-portfolio.md | 头寸规模、单笔/总风险预算、相关性门禁、加仓减仓、破产风险直觉 |
| 16-multi-timeframe-confluence.md | 多周期嵌套规律、主周期与 1d/4h/1h 映射、多周期冲突处理 |
| 17-failed-breakouts-and-traps.md | 失败突破、2 腿/5 跳陷阱、趋势中旗形 vs 区间中反转 |
| 18-session-open-and-gaps.md | 开盘类型、时段与策略匹配、缺口规则、资金费率时点 |
| 19-evidence-and-backtest-method.md | 命中率/期望值/成本口径、Wilson 区间、走查方法、2026-11-06 审计实证 |
| 20-execution-and-psychology.md | 过度交易/报复交易/移动止损、连亏处理、记录与复盘 |
| playbook.json | 机器可读的规则/权重/概率参数摘要 + 2026-11 实测门禁 |

## 使用方式
- 机器人：先跑 `pa_fetch.py` 拿结构指标，再按 05 的流程、用 03 的 setup、04 的主力检查，最后按 06 输出。
- 人工：从 01 建立心智模型，02 练读K，03 认 setup，04 判主力，05 做决策。
- 覆盖自检：`python3 scripts/knowledge_coverage.py`（30 个主题 × 20 个模块，CI 强制 100%）。

## 覆盖矩阵（主题 → 主模块）

| 主题 | 主模块 | 辅模块 |
|---|---|---|
| 市场结构/四支柱/Always-In | 01 | 08 |
| 市场周期/趋势/区间/通道 | 01 | 08/14 |
| 单根K/信号K/入场K | 02 | 07/14 |
| Setup 全家桶（H1-H4/L1-L4/DB/DT/楔形/MTR/BLSHS） | 03 | 14 |
| 主力/筹码/订单流 | 04 | 07 |
| 决策流程/置信度 | 05 | 09 |
| 输出模板 | 06 | 09 |
| OCR 提纯（许/胡/崔） | 07 | 02/03 |
| Brooks 深度框架/12 问 | 08 | 10 |
| 评审 rubric | 09 | 06 |
| 术语与引擎映射 | 10 | 08 |
| 风险/止损/订单/实际风险 | 11 | 15/20 |
| 波段 vs 剥头皮 | 12 | 11 |
| 量化概率参数 | 13 | 08 |
| 形态细节/微通道 | 14 | 03/17 |
| 头寸规模/组合风险 | 15 | 11 |
| 多周期/时间框架 | 16 | 08 |
| 失败突破/陷阱 | 17 | 03/04 |
| 开盘/时段/缺口 | 18 | 16 |
| 证据/回测方法 | 19 | 13 |
| 执行/心理 | 20 | 11 |

矩阵由 `scripts/knowledge_coverage.py` 自动校验：任何主题缺关键词即退出码 1，CI 会拦住。

## 免责
仅用于学习与技术分析，不构成投资建议。
