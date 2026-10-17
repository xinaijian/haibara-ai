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


def respond(user_text, chat_history, engine):
    user_text = (user_text or "").strip()
    s = engine.state
    if not user_text:
        yield (chat_history, "", render_avatar(s), _status_md(s), s.favorability, "",
               _memories_md(engine.memories), engine)
        return
    history = chat_history + [
        {"role": "user", "content": user_text},
        {"role": "assistant", "content": ""},
    ]
    final = None
    try:
        for r in engine.reply_stream(user_text):
            if "partial" in r:
                # 流式阶段：只逐字更新对话气泡，右侧面板保持不动
                history[-1]["content"] = r["partial"]
                yield (history, "", gr.update(), gr.update(), gr.update(),
                       gr.update(), gr.update(), engine)
            else:
                final = r
    except Exception as e:
        history[-1]["content"] = f"⚠️ {e}"
        yield (history, "", render_avatar(s), _status_md(s), s.favorability, "",
               _memories_md(engine.memories), engine)
        return
    s = final["state"]
    history[-1]["content"] = final["text"]
    yield (history, "", render_avatar(s, final["fav_delta"], final["mood_delta"]),
           _status_md(s, final["fav_delta"], final["mood_delta"]), s.favorability,
           final["inner_voice"], _memories_md(engine.memories), engine)


def reset():
    eng = ChatEngine()
    s = eng.state
    return [], eng, render_avatar(s), _status_md(s), s.favorability, "", _memories_md([])


with gr.Blocks(title="灰原哀 · 情感智能体") as demo:
    engine = gr.State(ChatEngine())

    gr.Markdown("# 灰原哀 · 情感状态智能体\n好感度与心情会随对话实时变化，每一次真诚的交流都会让她的防线松动一点。")

    with gr.Row():
        with gr.Column(scale=3):
            chatbot = gr.Chatbot(height=560, label="对话")
            msg = gr.Textbox(placeholder="说点什么……（回车发送）", show_label=False)
            with gr.Row():
                send = gr.Button("发送", variant="primary")
                clear = gr.Button("重置对话")

        with gr.Column(scale=1):
            avatar = gr.HTML(render_avatar(ChatEngine().state))
            status = gr.Markdown(_status_md(ChatEngine().state))
            fav = gr.Slider(0, 100, value=10, step=1, label="好感度进度",
                            interactive=False, show_label=True)
            inner = gr.Textbox(label="💭 内心独白", interactive=False, lines=5,
                               placeholder="她说出口的，不一定是心里想的……")
            membox = gr.Markdown(_memories_md([]))

    outputs = [chatbot, msg, avatar, status, fav, inner, membox, engine]
    send.click(respond, [msg, chatbot, engine], outputs)
    msg.submit(respond, [msg, chatbot, engine], outputs)
    clear.click(reset, None, [chatbot, engine, avatar, status, fav, inner, membox])

if __name__ == "__main__":
    demo.launch()
