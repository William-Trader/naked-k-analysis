# 裸K分析 · 价格行为机器人

[![License: PolyForm Noncommercial 1.0.0](https://img.shields.io/badge/License-PolyForm%20Noncommercial%201.0.0-blue.svg)](LICENSE)
[![Watermarked](https://img.shields.io/badge/code-watermarked%20(NKA)-orange.svg)](WATERMARK.md)

> ⚠️ **代码水印**：核心脚本内嵌追踪水印 `WM: NKA-XXXXXXXX`（见 [WATERMARK.md](WATERMARK.md)）。移除水印即违反本仓库许可证；水印用于**溯源**，不阻止复制。
> **License**: [PolyForm Noncommercial License 1.0.0](LICENSE) - source-available, noncommercial use only.

## 这是什么
把「裸K / 价格行为」（price action）分析自动化并推送到 IM 群聊的最小机器人：
- `pa_fetch.py` 拉取 Binance 真实 K线，生成紧凑数据摘要（无需 API Key）；
- 交给 LLM（DeepSeek）按固定框架做价格行为判读；
- 通过 OpenClaw 定时任务（cron）把简报送达 QQ 群。

## 目录
| 路径 | 作用 |
|---|---|
| `pa_fetch.py` | 拉 Binance 1h/4h K线 → 文本摘要 |
| `prompts/pa_agent_msg.txt` | 分析任务提示（市场结构→关键价位→情景推演→总结） |
| `scripts/pa_run.sh` | 手动触发一次分析（OpenClaw agent） |
| `scripts/pa_cron_setup.sh` | 注册每 4 小时的定时推送 |
| `config/openclaw.example.json` | OpenClaw 配置示例（凭据为占位符） |
| `docs/价格行为分析框架.md` | 分析框架与输出约束 |
| `WATERMARK.md` | 代码水印登记表 |

## 快速开始
```bash
python3 pa_fetch.py BTCUSDT ETHUSDT   # 打印价格行为数据摘要
```
把输出喂给任意 LLM；或部署到 OpenClaw：
```bash
cp config/openclaw.example.json ~/.openclaw/openclaw.json   # 填入自己的凭据
bash scripts/pa_cron_setup.sh                                # 注册每 4 小时推送
```

## 数据源
Binance 公共端点（data-api.binance.vision），公开数据、无需 API Key。

## 免责声明
仅供学习与技术交流；仅基于历史行情做技术面判读，**不构成投资建议**。

---

## English
**Naked-K / Price-Action Analyst Bot** - a minimal pipeline that pulls real Binance K-lines, asks an LLM to read price action (market structure to key levels to scenarios), and pushes a short briefing to a QQ group via OpenClaw cron. One Python script (no API key needed) plus a prompt and deploy scripts.

- `pa_fetch.py` - fetch Binance 1h/4h K-lines into a compact text summary
- `prompts/pa_agent_msg.txt` - the analysis prompt
- `scripts/` - manual run + 4-hourly cron registration
- `config/openclaw.example.json` - OpenClaw config example (placeholder credentials)
- `docs/价格行为分析框架.md` - the analysis framework and output constraints

**License**: PolyForm Noncommercial License 1.0.0 (source-available, **noncommercial only**). Core scripts carry a traceable watermark (`WM: NKA-XXXXXXXX`, see [WATERMARK.md](WATERMARK.md)); removing it violates the license. Historical data only; **not investment advice.**

Required Notice: Copyright (c) 2026 William-Trader (https://github.com/William-Trader)
