# 让服务器的 OpenClaw 完全对接价格行为系统

目标：服务器上的机器人不再“自由发挥”，所有行情分析都走同一套数据与规则。

## 一次性安装（在服务器执行）

```bash
cd /home/ubuntu/nakedk-dashboard
bash scripts/install_price_action_skill.sh
```

脚本做三件事，且是幂等的：
1. 把 `skills/price-action-analyst/SKILL.md` 复制到 `~/.openclaw/skills/price-action-analyst/`；
2. 在 `~/.openclaw/workspace/AGENTS.md` 末尾追加一段指针（已存在则跳过）；
3. 打印下一步命令。

## 更新 4h 简报 prompt

```bash
openclaw cron list --json | grep -n "价格行为简报"
openclaw cron edit <job-id> --prompt-file /home/ubuntu/nakedk-dashboard/prompts/pa_agent_msg.txt
openclaw cron get <job-id> | head -40
```

只改 prompt，不动 cron 表达式与投递目标。

> 仓库模板里的 `/opt/naked-k-analysis/...` 是规范部署路径；如果实际路径不同（例如 `/home/ubuntu/nakedk-dashboard`），先做一次替换再写入：
> ```bash
> sed 's#/opt/naked-k-analysis/nakedk-dashboard#/home/ubuntu/nakedk-dashboard#g' \
>   prompts/pa_agent_msg.txt > /tmp/live_prompt.txt
> openclaw cron edit <job-id> --message "$(cat /tmp/live_prompt.txt)"
> ```

## 验收

```bash
# 1) 技能可见
ls ~/.openclaw/skills/price-action-analyst/SKILL.md

# 2) 数据行完整（应看到 BAR/STRUCT/MTF/SIGBAR/FLOW/TRADES/BOOK/PLAN）
python3 pa_fetch.py BTCUSDT | grep -E "^(BAR|STRUCT|MTF|SIGBAR|FLOW|TRADES|BOOK|PLAN)\|"

# 3) 定时任务仍启用
openclaw cron list --json | grep -c "价格行为简报"
```

## 回滚

```bash
rm -rf ~/.openclaw/skills/price-action-analyst
# AGENTS.md 中的「价格行为系统」段落手工删除即可
```
