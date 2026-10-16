"""对话引擎：LLM 调用、状态块解析、长期记忆压缩。

支持任意 OpenAI 兼容 API（DeepSeek / GPT-4o / 各类中转），
通过环境变量 LLM_API_KEY / LLM_BASE_URL / LLM_MODEL 配置。
"""

import json
import os
import re

from dotenv import load_dotenv

from character import build_system_prompt
from state import EmotionState

load_dotenv()

# 容错：部分模型会把闭合标签误写成 <STATE>，或漏掉闭合标签
STATE_RE = re.compile(r"<STATE>\s*(\{.*?\})\s*(?:</STATE>|<STATE>|$)", re.S)
STATE_TAG_RE = re.compile(r"</?STATE>")

# 长期记忆提取 prompt：把溢出的旧对话压缩成事实清单
FACT_PROMPT = (
    "从以下对话中提取值得长期记住的事实（对方的个人信息、喜好、约定、重要事件），"
    "每条不超过15字，去重，只输出 JSON 字符串数组，没有则输出 []。"
)


class ChatEngine:
    def __init__(self, window=24):
        self.state = EmotionState()
        self.history = []   # 近期对话 [{"role": ..., "content": ...}]
        self.facts = []     # 长期记忆：事实清单
        self.window = window
        self._client = None

    @property
    def client(self):
        # 懒加载，避免 gr.State 深拷贝时复制 httpx 客户端
        if self._client is None:
            from openai import OpenAI

            api_key = os.getenv("LLM_API_KEY", "")
            if not api_key:
                raise RuntimeError(
                    "还没有配置 API Key：请把 .env.example 复制为 .env，填入 LLM_API_KEY 后重启程序。"
                )
            self._client = OpenAI(
                api_key=api_key,
                base_url=os.getenv("LLM_BASE_URL", "https://api.deepseek.com"),
            )
        return self._client

    @property
    def model(self):
        return os.getenv("LLM_MODEL", "deepseek-chat")

    def _chat(self, messages, temperature=0.85, max_tokens=1500):
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return resp.choices[0].message.content

    # 兜底 2：模型彻底省略标签，直接在台词后输出裸 JSON（扁平结构，无嵌套花括号）
    FLAT_JSON_RE = re.compile(r'\{\s*"favorability_delta".*?\}', re.S)

    @staticmethod
    def _parse(raw):
        """把回复拆成 (台词正文, 状态增量)。状态块缺失或损坏时静默降级。"""
        patch = {"favorability_delta": 0, "mood_delta": 0, "inner_voice": ""}
        m = STATE_RE.search(raw)
        if m:
            block = m.group(1)
            text = raw[:m.start()] + raw[m.end():]
        else:
            fm = ChatEngine.FLAT_JSON_RE.search(raw)
            if not fm:
                return raw.strip(), patch
            block = fm.group(0)
            text = raw[:fm.start()] + raw[fm.end():]
        text = STATE_TAG_RE.sub("", text).strip()
        try:
            data = json.loads(block)
            patch["favorability_delta"] = int(data.get("favorability_delta", 0))
            patch["mood_delta"] = int(data.get("mood_delta", 0))
            patch["inner_voice"] = str(data.get("inner_voice", "")).strip()
        except (json.JSONDecodeError, ValueError, TypeError):
            # 兜底：至少把内心独白抠出来
            iv = re.search(r'"inner_voice"\s*:\s*"([^"]*)"', block)
            if iv:
                patch["inner_voice"] = iv.group(1).strip()
        return text, patch

    def reply(self, user_text):
        """完整跑一轮对话，返回 {text, inner_voice, state}。"""
        if not os.getenv("LLM_API_KEY"):
            return self._mock_reply(user_text)
        system = build_system_prompt(self.state, self.facts)
        messages = [{"role": "system", "content": system}]
        messages += self.history[-self.window:]
        messages.append({"role": "user", "content": user_text})

        raw = self._chat(messages)
        text, patch = self._parse(raw)
        self.state.apply(patch["favorability_delta"], patch["mood_delta"])

        self.history.append({"role": "user", "content": user_text})
        self.history.append({"role": "assistant", "content": text})
        self._consolidate()

        return {"text": text, "inner_voice": patch["inner_voice"], "state": self.state}

    # 无 API Key 时的演示回复：随对话轮次推进，好感度逐步上升
    _MOCK_SCRIPT = [
        ("……你好。有什么事吗？如果只是想闲聊，我劝你去找侦探团那帮小鬼。", 1, 0,
         "又是一个自来熟的家伙。"),
        ("哼，至少你比柯南那家伙有礼貌一点。（低头翻动书页）说吧，想聊什么？", 2, 5,
         "……倒也不讨厌。"),
        ("（停下手中的实验记录）你对化学感兴趣？……呵，难得。APTX 的事我不能多说，但普通的有机化学问题，我可以教你。", 3, 8,
         "认真地听人说话的感觉，久违了。"),
        ("叫我哀就行。（移开视线）……只是叫起来方便而已，别多想。", 3, 5,
         "心跳有点快……错觉吧。"),
        ("（轻声）如果早点遇到像你这样的人，也许一切都会不一样。……没什么，自言自语罢了。", 2, 5,
         "这样的日子，能持续下去就好了。"),
    ]

    def _mock_reply(self, user_text):
        idx = min(len(self.history) // 2, len(self._MOCK_SCRIPT) - 1)
        text, fav_d, mood_d, inner = self._MOCK_SCRIPT[idx]
        self.state.apply(fav_d, mood_d)
        self.history.append({"role": "user", "content": user_text})
        self.history.append({"role": "assistant", "content": text})
        return {"text": text, "inner_voice": inner + "（演示模式）", "state": self.state}

    def _consolidate(self):
        """旧对话溢出窗口时，压缩成长期记忆。"""
        overflow = len(self.history) - self.window
        if overflow < 12:
            return
        chunk = self.history[:12]
        self.history = self.history[12:]
        try:
            dialogue = "\n".join(f"{m['role']}: {m['content']}" for m in chunk)
            out = self._chat(
                [{"role": "system", "content": FACT_PROMPT},
                 {"role": "user", "content": dialogue}],
                temperature=0.3,
                max_tokens=300,
            )
            data = json.loads(out[out.find("["): out.rfind("]") + 1])
            if isinstance(data, list):
                for f in data:
                    f = str(f).strip()
                    if f and f not in self.facts:
                        self.facts.append(f)
                self.facts = self.facts[-20:]
        except Exception:
            # 记忆失败不影响对话本身
            pass
