# LLM 配置 / LLM Configuration

项目只使用 OpenAI 兼容的 `/chat/completions`，不引入 SDK。所有配置都可以用环境变量覆盖；key 只从环境变量读取，**不写进仓库**。

## 0. 面板内直接输入（推荐）

打开 `http://127.0.0.1:8099/` → 右上角 `⚙` → 「LLM · 解读与参数迭代」→ 粘贴 API Key → **保存 Key**。

key 写入本机 `state/llm.key`（`chmod 600`），接口不回显、不写日志。保存后无需重启：下一次「生成解读」立即生效。「清除」可移除。

## 1. 最快可用（DeepSeek 示例）

仓库已带一份可直接改的示例：

```bash
cp config/llm.example.json config/llm.local.json
export DEEPSEEK_API_KEY='你的 key'
python3 scripts/llm_check.py --ping
PORT=8099 python3 dashboard/server.py
```

`config/llm.local.json` 已被 `.gitignore` 忽略。示例内容：

```json
{
  "base": "https://api.deepseek.com/v1",
  "model": "deepseek-chat",
  "api_key_env": "DEEPSEEK_API_KEY",
  "enabled": true,
  "require_key": true,
  "timeout": 45
}
```

## 2. 其他 provider

| Provider | base | model 示例 | key 环境变量 |
|---|---|---|---|
| DeepSeek | `https://api.deepseek.com/v1` | `deepseek-chat` | `DEEPSEEK_API_KEY` |
| OpenAI | `https://api.openai.com/v1` | `gpt-4o-mini` | `OPENAI_API_KEY` |
| 通义千问 / DashScope | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-plus` | `DASHSCOPE_API_KEY` |
| Moonshot | `https://api.moonshot.cn/v1` | `moonshot-v1-8k` | `MOONSHOT_API_KEY` |
| Ollama（本地） | `http://127.0.0.1:11434/v1` | `qwen2.5:7b` | 不需要 |

Ollama 示例：

```json
{
  "base": "http://127.0.0.1:11434/v1",
  "model": "qwen2.5:7b",
  "api_key_env": "",
  "enabled": true,
  "require_key": false,
  "timeout": 120
}
```

先 `ollama serve` 并 `ollama pull qwen2.5:7b`。本地端点不需要 key，`nakedk/llm.py` 会自动判定 `require_key=false`。

## 3. 字段说明

| 字段 | 说明 |
|---|---|
| `base` | OpenAI 兼容 base URL，末尾不要带 `/chat/completions` |
| `model` | 模型名 |
| `api_key_env` | 保存 key 的环境变量名；不要直接写 key |
| `require_key` | 缺 key 时是否视为未启用；localhost 默认 false |
| `enabled` | 总开关；false 时完全关闭 LLM |
| `timeout` | 单次请求超时秒数 |

优先级：**环境变量 > `NK_LLM_CONFIG` 指定的文件 > `config/llm.local.json` > 内置默认值**。

```bash
# 一次性覆盖，不写文件
NK_LLM_BASE=https://api.deepseek.com/v1 \
NK_LLM_MODEL=deepseek-chat \
NK_LLM_KEY=sk-... \
PORT=8099 python3 dashboard/server.py
```

## 4. 自检与界面

```bash
python3 scripts/llm_check.py          # 只看配置，不发送请求
python3 scripts/llm_check.py --ping   # 发一次最小请求
```

面板右上角 `⚙ → LLM` 会显示是否启用；右侧「AI 解读」卡的「生成解读」调用 `/api/llm/annotate`。未启用时按钮禁用，系统其余功能不受影响。

## 5. 安全边界

- key 不进入 git、日志、API 响应；`/api/llm/status` 只返回 `key_env` 名称。
- 配置文件建议 `chmod 600 config/llm.local.json`。
- LLM **不参与定价**：价位、计划、触发/止损/目标全部来自确定性引擎。
- 参数迭代只接受 `symbol_params.BOUNDS` 内的数字，单次最多 2 个键，样本不足直接返回空 patch。
- 未配置或请求失败时，评论卡显示原因，不阻断行情/计划/推送。

## 6. 常见问题

**`missing environment variable DEEPSEEK_API_KEY`** — 当前 shell 没导出 key，或服务启动时没有继承该环境变量。先 `echo $DEEPSEEK_API_KEY`，再重启服务。

**`HTTP 401`** — key 无效或 provider/base 不匹配。

**`HTTP 404`** — base 少了 `/v1`，或 provider 不支持 OpenAI 兼容路径。

**`llm_bad_json`** — 模型没有按要求输出 JSON。换更强的模型，或降低温度重试；引擎不会因此改变价位。

**本地 Ollama 很慢** — 把 `timeout` 调到 120，并优先使用已量化的 7B 模型。
