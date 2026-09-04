"""工具层：定义 Agent 可调用的工具 + 执行分发。

这是从「问答 POC」升级到「Agent」的关键一步——让模型不仅能说话，
还能在需要时「调用工具」拿回真实数据（时间、计算），再综合成答案。

新增工具只需三步：
1. 往 TOOLS 里加一段 function 定义；
2. 在 dispatch 的 handlers 里登记执行函数；
3. 完成。上层 Agent 循环会自动把新工具发给模型。
"""

import datetime
from typing import Any, Dict, List

# OpenAI 兼容的 tools 定义（function calling 格式）
TOOLS: List[Dict] = [
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "获取当前日期和时间。当用户询问「现在几点」「今天几号」「今天星期几」时调用。",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculator",
            "description": "计算数学表达式。当用户需要精确计算（如四则运算）时调用，避免模型心算出错。",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "要计算的数学表达式，例如 '123*456+78'",
                    }
                },
                "required": ["expression"],
            },
        },
    },
]


def _get_current_time() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _calculator(expression: str) -> str:
    # 白名单字符 + 空内建求值，防止任意代码注入
    allowed = set("0123456789.+-*/() ")
    if not expression or not all(c in allowed for c in expression):
        raise ValueError("表达式含非法字符，仅支持数字与 + - * / ( )")
    result = eval(expression, {"__builtins__": {}}, {})
    return str(result)


def dispatch(name: str, args: Dict[str, Any]) -> str:
    """按工具名执行，返回字符串结果。"""
    handlers = {
        "get_current_time": lambda: _get_current_time(),
        "calculator": lambda: _calculator(str(args.get("expression", ""))),
    }
    if name not in handlers:
        return f"[错误] 未知工具：{name}"
    try:
        return handlers[name]()
    except Exception as e:  # 工具执行异常也要回给模型，让它能感知失败
        return f"[工具执行出错] {e}"
