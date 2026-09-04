"""简单上下文处理：维护一个固定窗口的对话历史。

这是「简单上下文」的最小实现——一个内存列表，保留最近 N 轮。
后续要升级成 RAG 时，只需把「取历史」替换成「向量检索 + 历史」，
对外接口（to_messages / add / clear）保持不变，调用方无需改动。
"""

from typing import List, Dict


class ConversationMemory:
    """固定窗口的对话记忆。

    内部是一个消息列表 [{"role": "...", "content": "..."}, ...]，
    每次新增后若超出窗口上限，自动截断最旧的消息。
    """

    def __init__(self, max_turns: int = 6) -> None:
        # 1 轮 = user + assistant 两条，因此上限 = max_turns * 2
        self.max_turns = max_turns
        self._history: List[Dict[str, str]] = []

    def add(self, role: str, content: str) -> None:
        """追加一条消息，并截断到窗口上限。"""
        self._history.append({"role": role, "content": content})
        limit = self.max_turns * 2
        if len(self._history) > limit:
            self._history = self._history[-limit:]

    def to_messages(self) -> List[Dict[str, str]]:
        """返回当前历史（副本），供组装请求用。"""
        return list(self._history)

    def clear(self) -> None:
        """清空上下文。"""
        self._history.clear()

    def __len__(self) -> int:
        return len(self._history)
