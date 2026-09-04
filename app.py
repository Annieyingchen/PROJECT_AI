"""Gradio Web 界面：基于 qa.py 的问答 Agent。

这是从「CLI REPL」升级到「产品级 demo」的关键一步——
让非技术面试官 / HR 也能在浏览器里 30 秒体验项目。

启动：python app.py
访问：浏览器打开 http://localhost:7860

核心逻辑完全复用 qa.py / memory.py，Web 层只负责输入输出。
"""

import gradio as gr

import config
import memory
import qa


def init_state() -> memory.ConversationMemory:
    return memory.ConversationMemory(max_turns=config.MAX_TURNS)


def respond(
    user_input: str,
    history: list,
    state: memory.ConversationMemory,
    use_tools: bool,
) -> tuple:
    """处理一次问答：调用 qa 层 → 追加到历史 → 返回新历史。"""
    if state is None:
        state = init_state()
    if not user_input or not user_input.strip():
        return "", history, state

    try:
        if use_tools:
            answer = qa.ask_with_tools(state, user_input)
        else:
            answer = qa.ask(state, user_input)
    except Exception as exc:  # noqa: BLE001 — 兜底所有错误给用户
        answer = f"⚠️ 出错了：{exc}"

    history = (history or []) + [[user_input, answer]]
    return "", history, state


def clear_context() -> tuple:
    """清空上下文：重置 memory + 聊天记录。"""
    return None, [], init_state()


# ---- UI 构建 ----

if not config.is_ready():
    raise SystemExit(
        "⚠️ 配置不完整：请先复制 .env.example 为 .env 并填入 "
        "QA_LLM_BASE_URL / QA_LLM_API_KEY / QA_LLM_MODEL"
    )

with gr.Blocks(title="通用问答 Agent POC", theme=gr.themes.Soft()) as demo:
    gr.Markdown(
        f"""
# 🤖 通用问答 Agent POC

> **模型**：`{config.MODEL}` ｜ **记忆窗口**：最近 {config.MAX_TURNS} 轮
> 可选启用工具调用（时间 / 计算器）— 让模型在需要时拿真实数据。

**演示路径**：① 启用工具调用 → ② 问「现在几点」/「算一下 1024*768」 ③ 体验多轮上下文
        """
    )

    state = gr.State(value=init_state())

    with gr.Row():
        use_tools = gr.Checkbox(
            label="启用工具调用（Agent 模式）", value=True
        )
        turns_info = gr.Markdown(value="已用轮数：0 / " + str(config.MAX_TURNS))

    chatbot = gr.Chatbot(
        label="对话区", height=400, show_label=False, avatar_images=(None, "🤖")
    )
    msg = gr.Textbox(
        label="输入问题（Enter 发送）", placeholder="例如：北京今天天气怎么样？"
    )

    with gr.Row():
        submit_btn = gr.Button("发送", variant="primary")
        clear_btn = gr.Button("清空上下文")

    # ---- 事件绑定 ----

    def on_submit(user_input, history, state, use_tools):
        new_msg, new_history, new_state = respond(user_input, history, state, use_tools)
        turns = len(new_state) // 2
        turns_md = f"已用轮数：{turns} / {config.MAX_TURNS}"
        return new_msg, new_history, new_state, turns_md

    msg.submit(
        on_submit,
        inputs=[msg, chatbot, state, use_tools],
        outputs=[msg, chatbot, state, turns_info],
    )
    submit_btn.click(
        on_submit,
        inputs=[msg, chatbot, state, use_tools],
        outputs=[msg, chatbot, state, turns_info],
    )
    clear_btn.click(clear_context, inputs=[], outputs=[state, chatbot, turns_info])


if __name__ == "__main__":
    demo.launch(server_name="127.0.0.1", server_port=7860, share=False)
