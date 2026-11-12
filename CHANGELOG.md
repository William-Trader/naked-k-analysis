# Changelog

## 2.3.0 — 2026-11-12

新增**自适应时空分析体系**（`nakedk/spacetime.py`），不推倒、不替换现有分析链路。

### 新增
- 时间轴：从 1h 基础序列重聚合 1h/2h/4h/8h/1d，用「净位移/总路程」选 `dominant_scale`；**不再先验固定 15m 为执行框架**。
- 空间轴：40 根摆动区间分位、ATR 归一化速度/加速度、关键位触碰的时间衰减权重、UTC 时段、离散 `state_id`。
- 可解释性：`describe()` 一行中文结论；面板新增「时空状态」卡片，逐项展示尺度效率与状态。
- `build_state()` 在 4h bar 收盘时刻截断 1h 序列，**无未来函数**；`build_mask()` 支持历史重放。
- 可选开关 `NK_SPACETIME=1`（默认关闭、零额外请求）；payload 新增描述性 `spacetime` 字段。

### 验证与结论（不粉饰）
- 同一冻结快照、同一三段分割：v1 规则只产生 4 笔训练交易（样本不足）；修正「长尺度主导被误拒」的逻辑反转后 v2 达 87/26/46 笔。
- v2 在 validation 净 +0.1830%，但 test 转负 −0.1565%，**未超过 2.2.0 的 v22 champion（test +0.1162%）**。
- 更关键：v2 规则是在看过 v1 test 之后修改的，test 段已被使用两次，**不再构成干净的样本外验证**。继续按它调规则属于数据窥探。
- 因此时空体系**不晋升为交易门禁**，定位为描述性分析层；门禁仍以 v22 champion 为准（其 test 仅评估一次）。晋升需全新独立数据段做一次性验证。详见 [docs/SPACETIME.md](docs/SPACETIME.md) 与 `research/results/spacetime_2.3.0.json`。

### 兼容性
- 纯新增模块 + 可选环境变量；默认行为、API 响应结构（新增可空字段除外）、数据库 schema 均不变。
- 新增 `tests/test_spacetime.py` 覆盖无未来函数、尺度自适应、规则可解释性。

## 2.2.0 — 2026-11-12

工程化与生产 101 对齐，补齐代码级缺陷修复，并建立**冻结快照 + 三段式 walk-forward + 样本外压力验证**的可复现研究闭环。

### 修复
- 确认门与建计划门禁统一，消除两套口径不一致。
- trigger mode 在调用链中的传递修复。
- rearm 冷却按 symbol 维度生效。
- 两个 SQLite 数据孤岛统一：dashboard 与 beagle record/score/review 统一 `WorkingDirectory=/opt/apps/nakedk-dashboard`、显式 `BEAGLE_DB=/opt/apps/nakedk-dashboard/beagle.db`，老链路相对 `db_path` 由 `config/` 侧改动配合修正；路径以 [deploy/INVENTORY.md](deploy/INVENTORY.md) 为准。
- outbox 重试与幂等增强（重试去重、唯一约束）。
- dashboard 安全默认值（默认只绑 `127.0.0.1`，对外暴露需 `NK_DASH_HOST` + `NK_DASH_TOKEN`）与面板 XSS 修复。
- 配置强类型化（读取时校验类型，减少隐式字符串 / None）。
- systemd 模板与生产对齐（`/opt/apps/nakedk-dashboard`、`PORT=8081`、`User=root`），停用 unit 明确标注；`bootstrap.sh` 移除 `--delete-excluded`、排除 `state/` / 密钥 / `*.db`、发布前备份 `beagle.db` 并支持 `--dry-run`。

### 研究（实测数字，均可复现）
- 冻结快照：`python3 research/fetch_history.py` 把 BTCUSDT/ETHUSDT 730 天的 4h+1h 行情写入 `research/data/*.json.gz`（含 sha256 manifest，入库）。
- 方法：train 50% / validation 25% / **test 25%（只评估一次）**，每段 4-fold walk-forward，12bp 往返成本，样本量 <30 不得参选，validation 连续 2 轮无改善即早停；`python3 research/run_backtest.py`。
- 样本外结果（test）：baseline 169 笔 / 平均净 −0.0125% / 命中 46.72% / 最大回撤 −12.33%；采纳 `v22` 门禁 + `adx_min=22, stop=1.5ATR, target=3ATR` 后 **51 笔 / +0.1162% / 56.88% / −5.11%**（净收益 +0.1287pp、命中 +10.16pp、回撤改善 7.22pp、交易数 −118）。
- 压力验证 `python3 research/verify_result.py`：成本 12/16/20/25bp、单标的、test 前后半段、参数邻域共 **12 组场景胜 11 组（91.7%）**，唯一失败为 test 后半段；结果见 `research/results/verification_2.2.0.json`。
- 落地方式：`NK_RESEARCH_GATE=1` 可选启用（`nakedk/research_gate.py`），**默认关闭**以保持兼容；历史模拟不构成正期望声明。
- 单测由 259 增至 **294 全绿**（+2 门禁对称性用例、+22 项审计回归、+11 项时空引擎用例；含 2.3.0 新增部分）。

### 兼容性
- 所有部署侧新行为都有环境变量开关或为纯文档 / 忽略规则，不删除既有功能。
- 生产目录不是 git 仓库，继续采用文件级覆盖同步；**发布前先备份 `beagle.db`**。
- 生产路径以 [deploy/INVENTORY.md](deploy/INVENTORY.md) 为唯一权威清单；`docs/ARCHITECTURE.md` 降级为 v2 时代历史文档。

## 2.1.1 — 2026-11-09

QQ 重复推送修复。

### 根因
- 触发价选到了错误方向（空单触发价低于现价），计划刚建立就触发/失效。
- 失效后没有再武装冷却，每 2 分钟重新建同方向同价位计划。
- outbox 只按 `plan_event_id` 去重，不同 plan id 的同一段文字仍会重复推送。
- 旧 `beagle-monitor` 仍在 qsp 运行，持续写旧事件。

### 修复
- `_choose_trigger` 只允许同向回踩/反抽；无可用位置时等 0.15 ATR 回踩，不再市价立即触发。
- 新增 `plan_rearm_cooldown_min`（默认 240 分钟）：同标的同方向 void 后 4 小时内不再建新计划。
- 新增 `push_dedupe_min`（默认 240 分钟）：outbox 按完整文案去重，即使 plan id 不同也抑制重复。
- qsp 旧 `beagle-monitor` 已停止并禁用；`beagle-push.timer` 保持 inactive/disabled。
- 新增回归测试：错误方向触发、内容去重、void 冷却。

### 验证
- 259 单测通过。
- qsp 新服务重启后 outbox 维持 105 条历史、无新增重复；最大 id 未增长。

## 2.1.0 — 2026-11-08

图表交互 + 多周期 + 标注/交易质量升级。

### 绘图
- 新增 `dashboard/app/drawing.js`：趋势线、射线、水平线、矩形、斐波那契、文字、测量、箭头、画笔、擦除、磁吸、锁定、撤销/重做、清空。
- 按 symbol + interval 持久化到 `drawings.json`（运行时状态，gitignored）；服务端新增 POST `/api/drawings`。

### 多周期
- 默认周期改为 **15m + 4h**；设置支持 15m/30m/1h/4h/1d 多选或单周期。
- 图表周期条动态生成；右侧新增「多周期矩阵」，所选周期全部显示并可点击切换详情。

### 标注
- 新增 FVG 失衡区、订单块、等高等低流动性；保留供需区、通道、ZigZag、HH/HL/LH/LL、形态/颈线/量度目标。

### 交易质量
- 计划新增 `confluence` 多周期共振评分（结构/次周期/形态/RR），低于阈值不出计划。
- 新增 `risk_pct` / `notional_pct`：按止损距离计算名义仓位，建议中明确风险与 R:R。

### 测试
- 255 单测通过；前端 JS `node --check`。

## 2.0.1 — 2026-11-08

QQ 推送重构 + 面板内 API Key。

### QQ 推送
- 推送文案改为「标的 · 周期 · 方向 / 状态 / 操作 / 触发止损目标 / 依据 / 风控 / 数据」的简单可执行格式，去掉冗长内部字段。
- `确认 / 目标一 / 目标二 / 止损 / 失效` 各自给出明确动作：轻仓、减半、移保本、了结、离场、放弃。
- 触发价到达后先自动重分析并过确认门，通过才推「可执行」；不通过推「结构失效」，不裸触发。
- 支持设置面板填写 QQ 群 target；新增新计划建立时可选推送；outbox 增加 30 分钟过期保护，避免补发旧计划。
- 本机无 qqbot 时可用 `push_ssh` 走远程已配置网关；旧的 qsp `beagle-push.timer` 已停止/禁用，避免旧格式继续发群。

### LLM
- 新增面板内 API Key 输入框，保存到 `state/llm.key`（0600），接口只返回是否配置，不回显 key。
- 本地 Ollama 端点无需 key；配置优先级 env > 配置文件 > 本地 key 文件。

### 前端修复
- `/api/analyze` 的 `force` 参数未传入 `_build`，手动分析一直返回缓存；现在强制重算，`as_of` 会推进。
- 手动分析增加完成/失败 toast 与最新分析时间；自动分析仍按 120s 强制刷新并走 SSE。
- 新增 force-refresh 回归测试。

### 测试
- 253 单测（+10）：QQ 文案/不追单/止盈止损语义、key 文件落盘与权限、QQ target 解析、force 缓存绕过。

## 2.0.0 — 2026-11-08

系统性重构：从「行情卡片 + 事件提醒」升级为「价格行为 AI 交易面板 + 计划生命周期」。

### 前端架构
- 拆分为原生 ES modules：`app/main.js`（启动/路由/SSE）、`chart.js`（LWC + Canvas 标注层）、`panels.js`（右侧模块）、`settings.js`（标的池/周期/自动化/参数库）、`api.js`/`store.js`/`format.js`；`index.html` 只保留壳。
- 专业双栏终端：左侧 K 线主图 + EMA/成交量，右侧 7 个模块（综合研判、交易计划、周期分析、关键价位、AI 解读、计划事件、数据与引擎）。
- 图表几何由服务端 `nakedk/annotations.py` 生成，Canvas 叠加绘制：ZigZag/HH-HL-LH-LL、支撑阻力聚类、趋势通道、供需区、双底/双顶/头肩/三角/楔形/旗形、颈线与量度目标、计划触发/止损/目标/风险区。
- SSE `/api/stream` 实时推送 symbol / plan / settings；25s 轮询兜底。

### 多市场
- 新增新浪财经国内期货 provider（RB0/HC0/I0/J0/JM0/CU0/AL0/AU0/AG0/SC0/MA0/TA0/M0/Y0/P0/CF0/SR0/FG0/SA0/RU0/BU0），统一归一化为 Binance K 线形状。
- 扩展大宗商品与海外期货标的；Yahoo 4h 由 1h 聚合；国内期货 4h 由 60m 聚合。
- 默认只分析 BTC/ETH；其他标的按需拉取，设置中可选最大同时分析数（默认 6，上限 24）。

### 分析引擎
- 新增 `nakedk/analysis.py`：单一分析路径，输出多周期 chart-ready payload。
- 新增 `nakedk/multi.py`：4h + 15m 联合研判；冲突降中性、4h 否决、置信度上限。
- 新增 `nakedk/symbol_params.py`：按标的独立参数库（JSON），带硬边界、版本、来源与回滚。
- 新增 `nakedk/plans.py`：计划状态机 armed → triggered → confirmed → managing → closed/void；纯函数、幂等键。
- 新增 `beagle/engine.py`：analysis / trigger 双循环；到价触发后自动重算并执行确认门；到价邻近关键位自动再分析；LLM 参数迭代受样本量与边界约束。
- `beagle/store.py` 新增 plans / plan_events / outbox 三表；`beagle/push.py` 新增 outbox 投递。
- 新增 `nakedk/llm.py`：OpenAI 兼容、无 key 自动关闭、评论与受限参数建议，缓存与边界校验。
- 新增 `config/llm.example.json` + `config/llm.local.json`（本地被 gitignore）+ `docs/LLM.md` + `scripts/llm_check.py`；支持环境变量/配置文件/本地 Ollama 三种入口，状态接口不返回 key。

### 工程
- 测试 237（+33）：计划状态机、多周期组合、标注几何、标的参数库、计划持久化/触发循环、引擎计划构建。
- README 重写为 v2.0 架构文档；仪表盘截图更新。
- 仍保持零第三方依赖、本地 vendor 图表、水印与许可证。

## 1.1.0 — 2026-11-06

准确度审计 + 引擎门禁 + 知识库全覆盖。

### 审计（真实行情，可复现）
- 新增 `scripts/accuracy_audit.py`：按方向 / ADX / 重叠 / 量能 / 位置分桶，输出命中率、Wilson 95% 下界、扣 12bp 净收益、三折一致性。
- BTC/ETH 近 150 天基线：命中 38.6% / 42.2%，平均净 −0.105% / −0.078%，3 折全负。
- 定位两个最差桶：`overlap ≥0.70`（31.6% / 25.9%）与无成交量确认的趋势入场。
- 修复审计脚本分折计算：原先用行数当折宽、与 bar 索引不匹配，导致所有折为 `None`（已有回归测试）。

### 引擎
- `stance()` 新增高重叠硬否决（`stance_overlap_max=0.70`）与量能确认（`stance_min_vol_z=0.0`），两项均由实测驱动。
- 置信度由固定 56–64 改为 35–60 的质量分级，新增 `grade` / `evidence` 字段；高 ADX 过热扣分。
- 门禁后同口径：命中 47.6% / 54.1%，平均净 −0.033% / +0.206%，正收益折 2/3，仍不宣称正期望。

### 知识库
- 新增 15 头寸规模与组合风险、16 多周期、17 失败突破与陷阱、18 开盘时段缺口、19 证据与回测方法、20 执行与心理。
- 新增 `scripts/knowledge_coverage.py`：30 主题 × 20 模块关键词审计，CI 强制 100%。
- 更新 `knowledge/README.md` 覆盖矩阵与 `playbook.json` 的实测门禁/审计数据。

### 测试
- 204 单测（+9），全部通过。

## 1.0.1 — 2026-10-31

修复仪表盘空白与加载慢。

### 修复
- `dashboard/server.py` 自行把仓库根加入 `sys.path`，`python3 dashboard/server.py` 在任意 cwd 下都能导入 `nakedk` / `beagle`，不再直接抛 `ModuleNotFoundError` 导致整页空白。

### 性能
- 行情抓取改为并发：两个标的的 ticker / K 线 / 多周期 / 日线一次并发取回（本地冷启动约 25s → 约 4s）。
- 多周期的 1d/4h/1h K 线并入同一批并发请求，`mtf_alignment` 不再串行取数（远端冷构建 31s → 约 15s，取决于链路）。
- 最近一次 payload 落盘 `state/overview_<tf>.json`，重启后首个请求直接命中磁盘缓存（实测 3ms），后台再刷新。
- 缓存策略改为 fresh 60s + stale-while-revalidate（15 分钟内直接返回旧数据并后台刷新），前端轮询基本 0 等待（热请求约 2ms）。
- 启动时后台预热 4h/1h/1d，首个访问不再等冷构建。
- 前端图表不再每次轮询销毁重建：复用 Lightweight Charts 实例，只 `setData` 更新；`autoSize` 自适应容器；K 线与摆动点/形态标注合并为一次 `setMarkers`；请求可中断（AbortController），切换周期不再堆积响应。

### 文档
- README 仪表盘截图更新为修复后的真实渲染。

## 1.0.0 — 2026-10-31

版本统一 v1.0.0：前端升级 + 工程优化。此版本起以 v1.0 为准。

### 前端（dashboard）
- **TradingView Lightweight Charts™** 渲染 K 线（蜡烛 + EMA20/50 + 支撑阻力 + 摆动点 + 形态标注），本地 vendor（`dashboard/vendor/lwc.js`）零 CDN / 零网络依赖。
- **三选项卡**：行情 / 知识库 / 调参。
- **知识库选项卡**：内置 Markdown 渲染 + 模块目录（`/api/knowledge`），可在线阅读全部知识模块。
- **调参选项卡**：实时调节 stance / trend / 信号K 阈值（`/api/params` GET/POST），持久化到 `state/params.json`。
- 服务端新增静态资源服务（vendor JS）。

### 工程
- 新增 `nakedk/params.py`：运行时可调决策阈值（stance 的 ADX/位置/止损目标 ATR、trend 标签阈值、信号K质量门槛），默认值即历史行为。
- `signals.stance` / `trend.trend_score` 支持 `params` 覆盖（默认不改行为，测试全绿）。

### 消息易读性
- `beagle.detect.alert_text` 重写为中文可读格式：`[P0·需要立刻看] BTC · 极端价格冲击 · +9.00% · 0.9×ATR · price=…`。

### 测试
- 195 个全过；新增 test_params（调参）、test_detect 消息格式更新。

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
