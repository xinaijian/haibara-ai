"""Gradio 界面：左侧对话，右侧情感状态面板 + 内心独白 + 心里的余温。

用法：python app.py，浏览器打开 http://127.0.0.1:7860
"""

import gradio as gr

from avatar import render_avatar
from engine import ChatEngine

_TAG_EMOJI = {"心动": "💗", "温暖": "☕", "开心": "✨", "受伤": "🩹", "难过": "🌧️"}


def _badge(delta):
    """本轮变化徽章：▲2 / ▼3 / —"""
    if delta > 0:
        return f"**▲{delta}**"
    if delta < 0:
        return f"**▼{abs(delta)}**"
    return "—"


def _status_md(s, fav_d=0, mood_d=0):
    if s.next_stage:
        nxt, need = s.next_stage
        stage_line = f"关系：**{s.stage}** ｜ 再聊 **{need}** 点好感 → {nxt}"
    else:
        stage_line = f"关系：**{s.stage}**（已到最高阶段）"
    return (
        f"### 💗 好感度 {s.favorability} 　{_badge(fav_d)}\n"
        f"{stage_line}\n\n"
        f"### 🌗 心情 {s.mood_desc} {s.mood:+d} 　{_badge(mood_d)}"
    )


def _memories_md(memories):
    if not memories:
        return "**🍃 心里的余温**\n\n*还没有什么让她记住的瞬间……*"
    lines = ["**🍃 心里的余温**"]
    for m in memories[-6:]:
        lines.append(f"{_TAG_EMOJI.get(m['tag'], '·')} *（{m['tag']}）* {m['note']}")
    return "\n\n".join(lines)


def _error_text(e):
    """把底层异常翻译成用户能看懂的一句话。"""
    name = type(e).__name__
    msg = str(e)
    if isinstance(e, RuntimeError) and "API Key" in msg:
        return msg  # 缺 Key 的提示本身已足够友好
    if "Timeout" in name or "timed out" in msg.lower():
        return "她走神太久了（请求超时）……再发一次试试？"
    if "Connection" in name or "ConnectionError" in name or "connection" in msg.lower():
        return "网络不太稳定，没连上她的思绪。检查网络后再试一次。"
    if "RateLimit" in name or "429" in msg:
        return "她今天被问得有点多（接口限流）。稍等片刻再试，或在 .env 里把 LLM_MODEL 换成 glm-4-flash。"
    if "Authentication" in name or "401" in msg:
        return "API Key 无效或过期，请检查 .env 里的 LLM_API_KEY。"
    return f"出了点小状况：{msg}"


def respond(user_text, chat_history, engine):
    user_text = (user_text or "").strip()
    s = engine.state
    if not user_text:
        yield (chat_history, "", render_avatar(s), _status_md(s), s.favorability, "",
               _memories_md(engine.memories), engine)
        return
    # 第 0 帧：必须在任何网络调用之前 yield——消息立即上屏、输入框立即清空、
    # 她的气泡先显示思考占位（Gradio 6 会过滤空 content，占位必须非空）
    history = chat_history + [
        {"role": "user", "content": user_text},
        {"role": "assistant", "content": "……"},
    ]
    yield (history, "", gr.update(), gr.update(), gr.update(),
           gr.update(), gr.update(), engine)

    final = None
    try:
        for r in engine.reply_stream(user_text):
            if "partial" in r:
                # 流式阶段：思考占位被逐字台词替换，右侧面板保持不动
                history[-1]["content"] = r["partial"]
                yield (history, "", gr.update(), gr.update(), gr.update(),
                       gr.update(), gr.update(), engine)
            else:
                final = r
    except Exception as e:
        history[-1]["content"] = f"⚠️ {_error_text(e)}"
        yield (history, "", render_avatar(s), _status_md(s), s.favorability, "",
               _memories_md(engine.memories), engine)
        return
    s = final["state"]
    history[-1]["content"] = final["text"]
    engine.save()
    yield (history, "", render_avatar(s, final["fav_delta"], final["mood_delta"]),
           _status_md(s, final["fav_delta"], final["mood_delta"]), s.favorability,
           final["inner_voice"], _memories_md(engine.memories), engine)


def _start_engine():
    """启动/重置时新建引擎，并尝试载入本地存档。"""
    eng = ChatEngine()
    eng.load()
    return eng


def reset():
    """重置对话：清空聊天记录，但保留关系进度与长期记忆（立即落盘）。"""
    eng = _start_engine()
    eng.history = []
    eng.save()
    s = eng.state
    return [], eng, render_avatar(s), _status_md(s), s.favorability, "", _memories_md(eng.memories)


with gr.Blocks(title="灰原哀 · 情感智能体") as demo:
    _initial = _start_engine()
    engine = gr.State(_initial)

    gr.Markdown("# 灰原哀 · 情感状态智能体\n好感度与心情会随对话实时变化，每一次真诚的交流都会让她的防线松动一点。")

    with gr.Row():
        with gr.Column(scale=3):
            chatbot = gr.Chatbot(height=560, label="对话", value=_initial.history)
            msg = gr.Textbox(placeholder="说点什么……（回车发送）", show_label=False)
            with gr.Row():
                send = gr.Button("发送", variant="primary")
                clear = gr.Button("重置对话")

        with gr.Column(scale=1):
            avatar = gr.HTML(render_avatar(_initial.state))
            status = gr.Markdown(_status_md(_initial.state))
            fav = gr.Slider(0, 100, value=_initial.state.favorability, step=1,
                            label="好感度进度", interactive=False, show_label=True)
            inner = gr.Textbox(label="💭 内心独白", interactive=False, lines=5,
                               placeholder="她说出口的，不一定是心里想的……")
            membox = gr.Markdown(_memories_md(_initial.memories))

    outputs = [chatbot, msg, avatar, status, fav, inner, membox, engine]
    send.click(respond, [msg, chatbot, engine], outputs, show_progress="hidden")
    msg.submit(respond, [msg, chatbot, engine], outputs, show_progress="hidden")
    clear.click(reset, None, [chatbot, engine, avatar, status, fav, inner, membox],
                show_progress="hidden")

if __name__ == "__main__":
    demo.launch(inbrowser=True)  # 启动后自动打开浏览器
