# Agent setup (one-click)

This file is written for an AI agent. Follow it exactly.

## 1. Clone

    git clone https://github.com/William-Trader/naked-k-analysis.git
    cd naked-k-analysis

## 2. Bootstrap

    bash bootstrap.sh

## 3. QQ bot (default channel)

- Copy config/openclaw.example.json to ~/.openclaw/openclaw.json.
- Fill channels.qqbot.appId, channels.qqbot.clientSecret and gateway.auth.token.
- Fill /opt/naked-k-analysis/.beagle.env: BEAGLE_QQ_TARGET=group:<group_openid>.
- Restart: sudo systemctl restart beagle-push.

## 4. Chat route

Append the price-action section (below) to ~/.openclaw/workspace/AGENTS.md and TOOLS.md.

    ## QQ analysis route - price action
    On "分析X", "X怎么看", "深度分析X":
    1. python3 /opt/naked-k-analysis/pa_fetch.py {X}USDT
    2. read /opt/naked-k-analysis/knowledge/08-albrooks-deep.md and 09-review-rubric.md
    3. output the 06 template: market cycle + always-in, structure numbers,
       smart-money evidence, key levels, setup, signal-bar quality,
       trigger/invalidation/target, R:R, counter-scenario, 2 SIGNAL lines.

## 5. Charts cron (4h briefing)

Edit the group placeholder in scripts/pa_cron_setup.sh, then:

    bash scripts/pa_cron_setup.sh

## 6. Verify

    cd /opt/naked-k-analysis
    python3 -m beagle status
    curl -s localhost:8080/api/overview | head
    curl -s -o /dev/null -w '%{http_code}' localhost:8080/

## 7. Update

    cd /opt/naked-k-analysis && git pull && bash bootstrap.sh
