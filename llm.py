"""LLM 客户端：把消息列表发给大模型，返回助手回答。

只封装「发送 → 解析」这一件事，不掺任何业务逻辑。
换模型只需改 .env 里的 base_url / api_key / model 三行。
"""

from typing import Dict, List, Optional

import httpx

import config


def chat_raw(
    messages: List[Dict[str, str]],
    tools: Optional[List[Dict]] = None,
) -> Dict:
    """调用 OpenAI 兼容的 /chat/completions 接口，返回完整 message。

    完整 message 可能含 tool_calls（模型请求调用工具时），
    供上层 Agent 循环使用。
    """
    url = f"{config.BASE_URL}/chat/completions"
    headers = {"Authorization": f"Bearer {config.API_KEY}"}
    payload = {
        "model": config.MODEL,
        "messages": messages,
        "temperature": config.TEMPERATURE,
    }
    if tools:
        payload["tools"] = tools

    # 60 秒超时足够覆盖绝大多数问答；流式输出等进阶需求可后续加
    with httpx.Client(timeout=60.0) as client:
        resp = client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()

    return data["choices"][0]["message"]


def chat(messages: List[Dict[str, str]]) -> str:
    """只返回回答文本（不含工具调用），供纯问答场景使用。"""
    msg = chat_raw(messages)
    return msg.get("content") or ""
