<!-- SPDX-License-Identifier: LicenseRef-NKA-Personal-1.0 -->
# 生产环境清单 · INVENTORY（101 服务器）

> **本文件是全仓库生产路径的唯一权威清单。** 所有 `deploy/` systemd 模板、
> `bootstrap.sh` / `bootstrap-local.sh`、README 与各 `docs/` 文档应引用本文件，
> 不再各自硬编码路径。路径变更请先改这里。

## 1. 主机与发布方式

| 项 | 值 |
|---|---|
| 主机 | 101 服务器（生产） |
| 发布方式 | 文件级覆盖同步（`rsync`），**生产目录当前不是 git 仓库** |
| 发布前必做 | **先备份 `beagle.db`**（见 §6）；建议先 `bash bootstrap.sh --dry-run` 预演 |
| 运行用户 | `root`（生产 systemd unit 均为 `User=root`） |

## 2. 目录

| 用途 | 生产路径 | 说明 |
|---|---|---|
| 主链路 / dashboard | `/opt/apps/nakedk-dashboard` | `nakedk-dashboard.service` 的 `WorkingDirectory` / `PYTHONPATH`；全部 `beagle-*.service` 统一到此 cwd |
| 老链路（独立） | `/opt/apps/beagle-app` | 历史独立链路；通过 `PYTHONPATH` 第二段保留可导入能力 |
| systemd 单元目录 | `/etc/systemd/system/` | unit / timer 安装目标 |
| 运行时状态 | `/opt/apps/nakedk-dashboard/state/` | `settings.json` / `symbol_profiles.json` / `llm.key`，不入库、不同步 |
| 本地 LLM 配置 | `/opt/apps/nakedk-dashboard/config/llm.local.json` | 不入库、不同步 |

## 3. 端口 / 数据库 / 环境变量

| 项 | 值 |
|---|---|
| dashboard 端口 | `8081`（`Environment=PORT=8081`） |
| 主数据库（单库目标） | `/opt/apps/nakedk-dashboard/beagle.db` |
| 老链路历史库 | `/opt/apps/beagle-app/beagle.db`（由 `config/beagle.json` 相对 `db_path: "beagle.db"` 产生，曾造成两个 SQLite 数据孤岛，待合并/弃用） |

`nakedk-dashboard.service` 关键环境变量：

| 变量 | 值 |
|---|---|
| `PORT` | `8081` |
| `PYTHONPATH` | `/opt/apps/nakedk-dashboard` |
| `BEAGLE_DB` | `/opt/apps/nakedk-dashboard/beagle.db` |
| `NK_SETTINGS` | `/opt/apps/nakedk-dashboard/state/settings.json` |
| `NK_SYMBOL_PROFILES` | `/opt/apps/nakedk-dashboard/state/symbol_profiles.json` |
| `NK_LLM_KEY_FILE` | `/opt/apps/nakedk-dashboard/state/llm.key` |
| `NK_LLM_CONFIG` | `/opt/apps/nakedk-dashboard/config/llm.local.json` |

> **单库机制**：dashboard 与全部 `beagle-*.service`（record/score/review）统一
> `WorkingDirectory=/opt/apps/nakedk-dashboard`，并显式设置
> `Environment=BEAGLE_DB=/opt/apps/nakedk-dashboard/beagle.db`；老链路相对 `db_path`
> 由 `config/` 侧改动配合修正，双保险消除数据孤岛。

可选安全变量（`nakedk-dashboard.service` 内以注释形式给出，**禁止写入真实值**）：
`NK_DASH_HOST`（默认 `127.0.0.1`）、`NK_DASH_TOKEN`（空=不鉴权）、`NK_DASH_CORS_ORIGINS`。
对外暴露必须显式设置 `NK_DASH_HOST` 与 `NK_DASH_TOKEN`。

## 4. systemd unit / timer 清单

| 仓库模板 | 生产 unit | 类型 | 状态 |
|---|---|---|---|
| `deploy/nakedk-dashboard.service` | `nakedk-dashboard.service` | service | 启用（`PORT=8081`, `User=root`, `Restart=always`） |
| `deploy/beagle-record.service` | `beagle-record.service` | oneshot | 启用，由 `beagle-record.timer` 触发 |
| `deploy/beagle-score.service` | `beagle-score.service` | oneshot | 启用，由 `beagle-score.timer` 触发 |
| `deploy/beagle-review.service` | `beagle-review.service` | oneshot | 启用，由 `beagle-review.timer` 触发 |
| `deploy/beagle-monitor.service` | `beagle-monitor.service` | service | **2.1.1 起停用，勿 enable** |
| `deploy/beagle-push.service` | `beagle-push.service` | oneshot | **2.1.1 起停用，勿 enable** |
| `deploy/beagle-push.timer` | `beagle-push.timer` | timer | **2.1.1 起停用，勿 enable** |

timer：

| timer | 触发 | 状态 |
|---|---|---|
| `beagle-record.timer` | 每 4h 收盘后 5 分钟 | 启用 |
| `beagle-score.timer` | 每日 00:10 | 启用 |
| `beagle-review.timer` | 每周日 00:20 | 启用 |
| `beagle-push.timer` | 每 5 分钟 | **停用** |

## 5. 「仓库模板 → 生产」映射

| 仓库内 | 生产位置 | 备注 |
|---|---|---|
| `deploy/*.service`、`deploy/*.timer` | `/etc/systemd/system/` | 由 `bootstrap.sh` 复制；unit 内路径已对齐本清单 |
| 仓库代码根 | `/opt/apps/nakedk-dashboard/` | 纯覆盖同步（`--delete-excluded` / `--delete` 均已移除） |
| `config/*.example.*` | `/opt/apps/nakedk-dashboard/config/` | 仅示例；`*.local.json` / `.env*` 不入库、不同步 |
| `state/`（运行时） | `/opt/apps/nakedk-dashboard/state/` | 同步时排除，含 `llm.key` |
| `beagle.db` | `/opt/apps/nakedk-dashboard/beagle.db` | **同步时排除，发布前备份，绝不覆盖** |
| `research/data/*.json.gz`、`research/data/manifest.json` | 版本库内 | 回测冻结快照，需入库（`.gitignore` 已放行） |

## 6. 发布前检查清单

1. `bash bootstrap.sh --dry-run` 预演同步范围。
2. **备份 `beagle.db`**：`bootstrap.sh` 在真实同步前自动生成 `beagle.db.bak-<时间戳>`；手工发布请先自行 `cp -p`。
3. 确认 `state/`、`*.key`、`*.db`、`.env*`、`config/*.local.json` 未被同步覆盖。
4. `systemctl daemon-reload` 后仅启用 §4 标记为「启用」的 unit / timer；**不要** enable 任何「停用」项。
5. 核对 `PORT=8081` 与 `BEAGLE_DB` 指向主库。
