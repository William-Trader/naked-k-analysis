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
| playbook.json | 机器可读的规则/权重摘要 |

## 使用方式
- 机器人：先跑 `pa_fetch.py` 拿结构指标，再按 05 的流程、用 03 的 setup、04 的主力检查，最后按 06 输出。
- 人工：从 01 建立心智模型，02 练读K，03 认 setup，04 判主力，05 做决策。

## 免责
仅用于学习与技术分析，不构成投资建议。
