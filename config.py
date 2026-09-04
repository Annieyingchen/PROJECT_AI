"""配置加载：从 .env 文件 / 环境变量读取 LLM 配置。

设计原则：不引入 python-dotenv，用 20 行标准库解析 .env，
把第三方依赖压到只剩 httpx 一个。
"""

import os


def _load_env() -> None:
    """读取项目根目录下的 .env 文件（若存在），写入环境变量。

    只设置「尚未设置」的变量，即：真实环境变量 > .env 文件。
    每行格式：KEY=VALUE，支持 # 注释、空行。
    """
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


_load_env()

# ---- 必填配置：任意「OpenAI 兼容接口」都能跑 ----
# 通义千问 / DeepSeek / 豆包 / OpenAI 均走 /chat/completions 格式
BASE_URL = os.getenv("QA_LLM_BASE_URL", "").rstrip("/")
API_KEY = os.getenv("QA_LLM_API_KEY", "")
MODEL = os.getenv("QA_LLM_MODEL", "")

# ---- 可选配置 ----
SYSTEM_PROMPT = os.getenv(
    "QA_SYSTEM_PROMPT", "你是一个乐于助人的问答助手，回答简洁、准确。"
)
# 保留最近 N 轮对话（1 轮 = 1 次提问 + 1 次回答）
MAX_TURNS = int(os.getenv("QA_MAX_TURNS", "6"))
TEMPERATURE = float(os.getenv("QA_TEMPERATURE", "0.7"))
# Agent 工具调用最多循环多少轮（防止死循环）
MAX_AGENT_STEPS = int(os.getenv("QA_MAX_AGENT_STEPS", "4"))


def is_ready() -> bool:
    """三项必填是否齐全。"""
    return bool(BASE_URL and API_KEY and MODEL)
