# 通用问答 Agent POC

> 最小依赖（仅 httpx）的 AI 问答 Agent，支持多轮上下文记忆与工具调用（时间 / 计算器）。
> 任意 OpenAI 兼容接口均可接入（通义千问 / DeepSeek / 豆包 / OpenAI）。
>
> 这是一个从 0 手写的 Agent 骨架——没有 LangChain、没有向量库、没有 Docker，
> 用 600+ 行代码展示「分层设计 → 工具调用 → 上下文记忆」的完整链路。

---

## 3 分钟演示路径

### 方式一：Web 界面（推荐，面试演示用）

```bash
# 1. 克隆

git clone https://github.com/Annieyingchen/PROJECT_AI.git
cd PROJECT_AI

# 2. 配置（复制模板，填入你的 API key）
cp .env.example .env
# 编辑 .env：填入 QA_LLM_BASE_URL / QA_LLM_API_KEY / QA_LLM_MODEL

# 3. 安装依赖 + 启动 Web
pip install -r requirements.txt
python app.py
```

浏览器打开 http://localhost:7860 ，勾选「启用工具调用」，依次输入：

```
你：北京今天天气怎么样？
你：算一下 1024 * 768
你：现在几点
```

### 方式二：CLI（命令行）

```bash
pip install httpx   # 只装核心依赖
python main.py
```

然后依次输入：

```
你：北京今天天气怎么样？
你：算一下 1024 * 768
你：现在几点
```

观察：
- **多轮上下文**：第二轮不需要重复「北京」
- **工具调用**：计算器和时间是真实 API，不是模型心算
- **Agent 循环**：模型按需决定「是否需要调工具」，多轮循环直到给出最终答案

---

## 架构

```
┌─────────────────────────────────────────┐
│  main.py  CLI REPL 入口                 │
│  /quit /clear 交互命令                   │
├─────────────────────────────────────────┤
│  qa.py    问答编排层                     │
│  ask() → 纯问答                          │
│  ask_with_tools() → Agent 多轮循环       │
├──────────┬──────────────┬───────────────┤
│ llm.py   │ memory.py    │ tools.py      │
│ HTTP 调用│ 滑动窗口     │ 工具定义 +    │
│ 兼容任意 │ 上下文记忆   │ 执行分发      │
│ OpenAI   │              │               │
│ 接口     │              │               │
├──────────┴──────────────┴───────────────┤
│  config.py  配置加载（.env / 环境变量）   │
└─────────────────────────────────────────┘
```

| 模块 | 职责 | 关键设计 |
|---|---|---|
| `config.py` | 配置加载 | 20 行标准库解析 `.env`，不引入 `python-dotenv`，依赖压到仅剩 `httpx` |
| `llm.py` | LLM 调用 | 统一封装 `chat()` + `chat_raw()`，兼容任意 `/chat/completions` 接口 |
| `memory.py` | 上下文记忆 | 固定 N 轮滑动窗口，超限时自动丢弃最早对话，防止 token 溢出 |
| `qa.py` | 问答编排 | 纯问答 `ask()` + Agent 循环 `ask_with_tools()`，后续扩展 RAG 时只改 `build_messages()` |
| `tools.py` | 工具层 | 新增工具只需「定义 + 执行函数」两步，Agent 循环自动接管 |
| `main.py` | CLI 入口 | REPL 交互，支持 `/clear` `/quit`，含配置校验提示 |
| `app.py` | Web 界面 | Gradio 封装，复用 qa/memory 层，浏览器 30 秒体验 |

---

## 核心特性

- **零框架**：没有 LangChain、LlamaIndex、FastAPI——只有 `httpx` 一个第三方依赖
- **OpenAI 兼容**：任意走 `/chat/completions` 的接口（通义千问 / DeepSeek / 豆包 / OpenAI）均可接入
- **多轮记忆**：固定 N 轮滑动窗口，上下文自动维护
- **工具调用（Agent 雏形）**：模型按需调用真实工具，多轮循环直到给出最终答案
- **易扩展**：新增工具、接入 RAG、改记忆策略——均只需改动 1 个文件

---

## 设计决策

| 决策 | 选择 | 理由 |
|---|---|---|
| 框架 | 无 | 面试官想知道的是「你理解底层」，不是「你会调 API」。600 行手写代码 > 两行 import |
| 依赖 | 仅 `httpx` | 单依赖 = 单点问题暴露，也降低新人上手门槛 |
| 接口兼容 | OpenAI 协议 | 国内主流模型（千问 / 豆包 / DeepSeek）均已兼容，切换模型改 1 个环境变量 |
| 记忆策略 | 滑动窗口 | 简单可控，后续可升级为 token 计数 / 摘要压缩 |
| 工具调用 | function calling | 行业通用标准，模型原生支持 |

---

## 快速启动

```bash
# 1. 克隆项目
git clone https://github.com/Annieyingchen/PROJECT_AI.git
cd PROJECT_AI

# 2. 安装依赖（只有一个 httpx）
pip install -r requirements.txt

# 3. 配置 API

cp .env.example .env
# 编辑 .env，填入你的 base_url / api_key / model
# 示例（火山方舟豆包）：
# QA_LLM_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
# QA_LLM_API_KEY=sk-xxxxxxxx
# QA_LLM_MODEL=doubao-seed-2-1-turbo-260628

# 4. 运行
python main.py
```

---

## 扩展路线图

| 方向 | 改动点 | 复杂度 |
|---|---|---|
| **RAG 检索增强** | `qa.py` 的 `build_messages()` 前加文档检索 → 检索结果注入 system prompt | 中 |
| **新增工具** | `tools.py` 加 function 定义 + handler 函数，`qa.py` 无感知 | 低 |
| **记忆升级** | `memory.py` 滑动窗口 → token 计数 / 摘要压缩 | 中 |
| **Web 界面** | ✅ 已实现（`app.py`，Gradio） | — |
| **多模型路由** | `llm.py` 加 provider 分发，按任务自动切换模型 | 中 |

---

## 技术栈

- Python 3.10+
- [httpx](https://www.python-httpx.org/)（唯一第三方依赖）
- 任意 OpenAI 兼容 LLM API

---

## License

MIT