"""命令行入口：交互式问答 REPL。

用法：
    python main.py

命令：
    输入问题   开始一轮问答（自动携带最近 N 轮上下文）
    /clear    清空上下文
    /quit     退出
"""

import config
import memory
import qa


def main() -> None:
    if not config.is_ready():
        print("⚠️  配置不完整，请先复制 .env.example 为 .env 并填入：")
        print("    QA_LLM_BASE_URL / QA_LLM_API_KEY / QA_LLM_MODEL")
        return

    mem = memory.ConversationMemory(max_turns=config.MAX_TURNS)
    print(f"已启动通用问答 POC（模型：{config.MODEL}）")
    print("输入问题开始；/clear 清空上下文；/quit 退出。")
    print("可问「现在几点」「算一下 123*456」体验工具调用。\n")

    while True:
        try:
            question = input("你：").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not question:
            continue
        if question == "/quit":
            break
        if question == "/clear":
            mem.clear()
            print("[上下文已清空]\n")
            continue

        try:
            answer = qa.ask_with_tools(mem, question)
        except Exception as e:  # 网络/鉴权/超时等，报错但不断开循环
            print(f"[出错了] {e}\n")
            continue

        print(f"\n助手：{answer}\n")


if __name__ == "__main__":
    main()
