"""问答编排：问题输入 → 组装上下文 → 调用 LLM → 返回答案。

这是整个 POC 的核心流程，刻意保持清晰的分层结构。
纯问答用 ask()；带工具调用的 Agent 循环用 ask_with_tools()。
后续要加检索增强（RAG）时，改 build_messages 即可。
"""

import json
from typing import Dict, List

import config
import llm
import memory
import tools


def build_messages(mem: "memory.ConversationMemory", question: str) -> List[Dict[str, str]]:
    """把 system 提示 + 历史上下文 + 当前问题拼成一次请求的消息列表。"""
    return (
        [{"role": "system", "content": config.SYSTEM_PROMPT}]
        + mem.to_messages()
        + [{"role": "user", "content": question}]
    )


def ask(mem: "memory.ConversationMemory", question: str) -> str:
    """一次完整问答（不带工具）：返回答案，并把本轮问答写入上下文。"""
    messages = build_messages(mem, question)
    answer = llm.chat(messages)
    mem.add("user", question)
    mem.add("assistant", answer)
    return answer


def ask_with_tools(mem: "memory.ConversationMemory", question: str) -> str:
    """Agent 问答（带工具调用）：模型按需调用工具，多轮循环直到给出最终答案。

    循环逻辑：
    1. 发起请求，若模型返回 tool_calls，说明它想调用工具；
    2. 逐个执行工具，把结果以 role=tool 回填；
    3. 再次请求，让模型基于工具结果生成最终答案；
    4. 最多循环 MAX_AGENT_STEPS 次，防止死循环。
    """
    messages = build_messages(mem, question)
    answer = ""

    for _ in range(config.MAX_AGENT_STEPS):
        msg = llm.chat_raw(messages, tools=tools.TOOLS)

        # 模型没要调工具 → 直接拿文本答案，结束循环
        if not msg.get("tool_calls"):
            answer = msg.get("content") or ""
            break

        # 有 tool_calls → 把 assistant 消息原样加入，再逐个执行工具
        messages.append(msg)
        for tc in msg["tool_calls"]:
            fn = tc.get("function", {})
            name = fn.get("name", "")
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            result = tools.dispatch(name, args)
            messages.append({
                "role": "tool",
                "tool_call_id": tc.get("id", name),
                "content": result,
            })

    mem.add("user", question)
    mem.add("assistant", answer)
    return answer
