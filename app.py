"""Gradio 界面：左侧对话，右侧情感状态面板 + 内心独白。

用法：python app.py，浏览器打开 http://127.0.0.1:7860
"""

import gradio as gr

from engine import ChatEngine


def respond(user_text, chat_history, engine):
    user_text = (user_text or "").strip()
    s = engine.state
    if not user_text:
        return chat_history, "", s.favorability, s.stage, f"{s.mood_desc}({s.mood})", "", engine
    try:
        r = engine.reply(user_text)
    except Exception as e:
        chat_history = chat_history + [
            {"role": "user", "content": user_text},
            {"role": "assistant", "content": f"⚠️ {e}"},
        ]
        return chat_history, "", s.favorability, s.stage, f"{s.mood_desc}({s.mood})", "", engine
    chat_history = chat_history + [
        {"role": "user", "content": user_text},
        {"role": "assistant", "content": r["text"]},
    ]
    s = r["state"]
    return chat_history, "", s.favorability, s.stage, f"{s.mood_desc}({s.mood})", r["inner_voice"], engine


def reset():
    eng = ChatEngine()
    s = eng.state
    return [], eng, s.favorability, s.stage, f"{s.mood_desc}({s.mood})", ""


with gr.Blocks(title="灰原哀 · 情感智能体") as demo:
    engine = gr.State(ChatEngine())

    gr.Markdown("# 灰原哀 · 情感状态智能体\n好感度与心情会随对话实时变化，试着真正走进她的内心。")

    with gr.Row():
        with gr.Column(scale=3):
            chatbot = gr.Chatbot(height=520, label="对话")
            msg = gr.Textbox(placeholder="说点什么……（回车发送）", show_label=False)
            with gr.Row():
                send = gr.Button("发送", variant="primary")
                clear = gr.Button("重置对话")

        with gr.Column(scale=1):
            fav = gr.Slider(0, 100, value=10, label="好感度", interactive=False)
            stage = gr.Textbox(label="关系阶段", value="冷淡戒备", interactive=False)
            mood = gr.Textbox(label="心情", value="平静(0)", interactive=False)
            inner = gr.Textbox(label="内心独白", interactive=False, lines=6,
                               placeholder="她说出口的，不一定是心里想的……")

    outputs = [chatbot, msg, fav, stage, mood, inner, engine]
    send.click(respond, [msg, chatbot, engine], outputs)
    msg.submit(respond, [msg, chatbot, engine], outputs)
    clear.click(reset, None, [chatbot, engine, fav, stage, mood, inner])

if __name__ == "__main__":
    demo.launch()
