# 10 · Al Brooks 价格行为完整术语与判读（2026-10 更新）

> 来源：Wikipedia「Price action trading」条目（2026-10-21 抓取）与 brookspriceaction.com 官方论坛/文章索引。
> 本文只做知识整理与工程映射，不构成投资建议；术语以 Brooks 原意为准，中文为工程内统一译名。

## 1. 核心世界观

- **市场只有两种状态**：趋势（trend）与区间（trading range）；过渡态只是切换过程。
- **Always-In**：当下最可能延续的方向。只在「结构突破 + 跟随」时翻向，不因单根 K 线抖动。
- **两次尝试（two attempts）**：突破关键位通常要试两次；第二次失败才是高胜率反转。
- **被困交易者（trapped）**：突破后回落，追单者被套，其止损成为反向燃料。
- **信号必须收盘确认**：未收盘的形态只是「可能」，不允许据此入场。

## 2. 单根 K 线分类

| 类型 | 判据 | 含义 |
|---|---|---|
| 趋势K（trend bar） | 实体 ≥60% 全幅，收盘靠近极值 | 一方掌控 |
| 顺势趋势K | 方向与当前趋势一致 | 延续概率高 |
| 逆势趋势K | 方向与趋势相反 | 可能是回调第一根 |
| 高潮K（climactic） | 幅度 ≥2×ATR，量能 z ≥2 | 衰竭或启动，等下一根 |
| 光头K（shaved） | 一端几乎无影线 | 该方向无阻力 |
| 内包K（inside） | 高低于前一根之内 | 收缩，突破前兆 |
| 外包K（outside） | 高低均超出前一根 | 双向扫单，反转或加速 |
| 小K（small bar） | 幅度 <0.5×ATR | 无信息，等确认 |
| 十字星（doji） | 实体 ≤25% 全幅 | 犹豫，区间特征 |
| ii / iii | 连续两根/三根内包 | 突破前的压缩 |

## 3. 趋势结构

- **Spike and Channel**：急冲（spike）后进入窄通道，通道内回调浅、重叠低。
- **微趋势线（microtrend line）**：连接 2–3 根 K 线低/高点，破位常引出第一次回调。
- **趋势通道线（trend channel line）**：平行于趋势线的外轨；overshoot 后常见反转。
- **趋势线破（trend line break）**：只是「可能反转」，需再看 HL/LH 与强反转K。
- **腿（leg）**：相邻摆动点之间的一段；趋势成熟度按同向腿数计（1–4 腿）。

## 4. 突破与回调

| 概念 | 定义 | 交易含义 |
|---|---|---|
| Breakout | 收盘越过区间/前高前低 ≥0.2×ATR | 需跟随确认 |
| Breakout pullback | 突破后回踩突破位不破 | 高胜率二次入场 |
| Breakout failure | 突破后 1–3 根内收回区间 | 被困交易者出现 |
| Failed breakout failure | 失败突破后再次突破 | 最强延续信号之一 |
| Pullback | 趋势中的逆向 1–3 根 | H1/H2、L1/L2 的载体 |

## 5. 反转形态

- **反转K（reversal bar）**：长影线 + 收盘回到反向 1/3，且出现在极值。
- **高潮反转（climactic reversal）**：高潮K 后立刻反向趋势K。
- **双顶/双底（DT/DB）**：两高点/低点差 ≤0.25–0.5×ATR；**twin** 指几乎同价。
- **opposite twin**：先下后上（或先上后下）的两根同价 K，反转意味更强。
- **楔形（wedge）**：三推、动能收敛；楔形顶/底常以通道线 overshoot 结束。
- **头肩（HS/IHS）**：三推的特例，颈线突破需跟随。
- **MTR（major trend reversal）**：趋势线破 + HL/LH + 强反转K，三者缺一不可。
- **最终旗形（final flag）**：趋势末段的窄旗，突破后更容易失败。

## 6. 交易区间

- **Chop / barb wire**：重叠高、影线多、无连续趋势K；不在这里做突破。
- **区间边缘交易（BLSHS）**：只买下沿、卖上沿；中部不动。
- **区间突破**：需要「收盘 + 跟随 + 回踩确认」三件套。

## 7. Setup 清单（工程内 type 对应）

| Setup | 引擎 type | 必要条件 |
|---|---|---|
| H1 / H2 | `H1` / `H2` | 上升结构中的第 1/2 次更高低点 |
| L1 / L2 | `L1` / `L2` | 下降结构中的第 1/2 次更低高点 |
| 双底 / 双顶 | `DB` / `DT` | 两低/高点接近 + 颈线突破 |
| 头肩 | `HS` / `IHS` | 三推 + 颈线 |
| 楔形 | `WEDGE_TOP` / `WEDGE_BOTTOM` | 三推收敛 |
| 三角形 | `TRI_ASC` / `TRI_DESC` / `TRI_SYM` | 高低点收敛/走平 |
| 旗形 | `FLAG_BULL` / `FLAG_BEAR` | 冲击 ≥2.5ATR + 浅回调 |
| 最终旗形 | `FINAL_FLAG_*` | 成熟趋势（≥3 腿）+ 窄旗 |
| 测量移动 | `MM_UP` / `MM_DOWN` | 两段等长（误差 ≤25%） |
| 微型双底/顶 | `MICRO_DB` / `MICRO_DT` | 两根 K 线极值接近 |
| 三内包 | `III` | 连续三根内包 |
| 外包反转 | `OBR_BULL` / `OBR_BEAR` | 外包 + 收盘越过前极值 |
| 高潮反转 | `CLIMAX_BULL` / `CLIMAX_BEAR` | 2ATR + 量能 + 反向收盘 |

## 8. 判读规则（简报必须遵守）

1. 先定状态：趋势 / 区间 / 过渡（`REGIME`），再谈方向。
2. 方向必须有 **两条独立理由**（结构 + 信号K / 位置 / 量价）。
3. 信号K四项：收盘位置、实体、影线、跟随；缺两项即无效。
4. 位置优先：区间中部不做反转，边缘不做追突破。
5. 突破必须等收盘；未收盘只写「形成中」。
6. 失败突破出现时，禁止顺原突破方向追单。
7. R:R <1.5 不做；目标优先用测量移动，其次结构位，最后 ATR。

## 9. 与引擎输出的映射

| 知识概念 | 引擎行 | 说明 |
|---|---|---|
| 单根K分类 | `BAR` | type / quality / close_pos |
| 结构状态 | `STRUCT` | state / BOS / CHoCH |
| 市场状态 | `REGIME` | 1d+4h 结构仲裁 |
| Always-In | `AI` | 带滞回的状态机 |
| 失败突破 | `FAILED` | 突破后收回 |
| 跟随 | `FOLLOW` | 收盘越过前极值 |
| 信号K | `SIGBAR` | 六维分数 + 缺失项 |
| 形态阶段 | `PATTERN_STAGE` / `stage` | forming/breakout/target/failed |
| 腿与成熟度 | `LEGS` | 同向腿数、衰竭 |

## 10. 术语表（EN → 中文）

trend 趋势 · trading range 交易区间 · always-in 始终在场方向 · breakout 突破 ·
pullback 回调 · breakout pullback 突破回踩 · failed breakout 失败突破 · trapped 被困 ·
signal bar 信号K · entry bar 入场K · follow-through 跟随 · reversal bar 反转K ·
climax 高潮 · exhaustion 衰竭 · spike 急冲 · channel 通道 · microtrend line 微趋势线 ·
measured move 测量移动 · wedge 楔形 · double top/bottom 双顶/双底 · twin 同价双K ·
head and shoulders 头肩 · final flag 最终旗形 · barb wire 铁丝网（密集重叠）·
two attempts 两次尝试 · with-trend 顺势 · counter-trend 逆势 · shaved bar 光头K ·
inside bar 内包K · outside bar 外包K · ii/iii 两/三内包 · MTR 主要趋势反转

## 11. 常见误读（明确禁止）

- 把「趋势线破」直接当反转 → 必须等 HL/LH 与强反转K。
- 把「放量」当方向 → 放量只说明换手，方向看收盘。
- 在区间中部做反转 → 位置不对，胜率大幅下降。
- 用未收盘 K 线的形态下结论 → 只写「形成中」。
- 把多个形态简单叠加当共振 → 只在同向、同价位（≤0.5ATR）才算 confluence。

## 12. 与本地知识库的关系

- `05-decision-tree.md`：决策顺序；
- `08-albrooks-deep.md`：12 问检查表；
- `09-review-rubric.md`：评审标准；
- 本文（10）：术语全集与引擎映射，作为前两者的词典与对照表。
