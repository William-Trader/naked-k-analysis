# beagle · 多频市场监测

零依赖的 1m/5m 事件监测器，配合 4h 简报使用。

## 命令

    python3 -m beagle once      # 扫描一次，输出新事件（JSON）
    python3 -m beagle monitor   # 常驻，每 60s 扫描
    python3 -m beagle status    # 心跳/队列/最近事件
    python3 -m beagle push      # 取出待推送 alerts（--mark-sent 标记已发）
    python3 -m beagle score     # 回填 SIGNAL 的 4h 结果并汇总

## 配置

    config/beagle.json

- symbols: 监测列表
- poll_seconds: 轮询间隔
- cooldown_min: P0/P1/P2 去重窗口
- quiet_hours: 静默时段
- rate_limit_per_hour/day: 全局限流
- thresholds: 价格冲击/量能/突破阈值

## 事件

| kind | severity | 条件 |
|---|---|---|
| price_shock | P1 | abs(Δ1m) ≥ 0.8×ATR14 |
| price_shock_extreme | P0 | abs(Δ1m) ≥ 2.0×ATR14 |
| volume_spike | P1 | vol_z ≥ 3 |
| range_break | P1 | 突破 r20 边界 + vol_z≥1 |
| state_shift | P2 | trend 状态切换 |
| funding_extreme | P2 | abs(funding) ≥ 0.1% |

## 部署

    rsync -az ... /tmp/nka/ ubuntu@host:/opt/naked-k-analysis/beagle-app/
    sudo cp deploy/beagle-monitor.service /etc/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl enable --now beagle-monitor

## 设计

完整架构见 [docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md)。
