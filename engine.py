"""对话引擎：LLM 调用、响应解析、情绪状态机、长期记忆与情感瞬间记忆。

支持任意 OpenAI 兼容 API（智谱 GLM / DeepSeek / GPT-4o / 各类中转），
通过环境变量 LLM_API_KEY / LLM_BASE_URL / LLM_MODEL 配置。
"""

import json
import os
import re

from dotenv import load_dotenv

from character import build_system_prompt
from state import EmotionState
from store import DEFAULT_STORE, load_state, save_state

load_dotenv()

# 兼容旧格式：<STATE>{...}</STATE>（部分模型会把闭合标签误写成 <STATE>）
STATE_RE = re.compile(r"<STATE>\s*(\{.*?\})\s*(?:</STATE>|<STATE>|$)", re.S)
STATE_TAG_RE = re.compile(r"</?STATE>")

# 长期记忆提取 prompt：把溢出的旧对话压缩成事实清单
FACT_PROMPT = (
    "从以下对话中提取值得长期记住的事实（对方的个人信息、喜好、约定、重要事件），"
    "每条不超过15字，去重，只输出 JSON 字符串数组，没有则输出 []。"
)


def _memory_tag(fav_delta, mood_delta):
    """根据情绪增量给记忆瞬间归类。"""
    if fav_delta <= -2:
        return "受伤"
    if mood_delta <= -6:
        return "难过"
    if fav_delta >= 3:
        return "心动"
    if fav_delta >= 2:
        return "温暖"
    if mood_delta >= 7:
        return "开心"
    return None


class ChatEngine:
    def __init__(self, window=24, store_path=DEFAULT_STORE):
        self.state = EmotionState()
        self.history = []          # 近期对话 [{"role": ..., "content": ...}]
        self.facts = []            # 长期记忆：事实清单
        self.memories = []         # 情感瞬间：[{"tag": ..., "note": ...}]
        self.window = window
        self.store_path = store_path
        self._client = None

    # ---- 持久化：把长期状态和对话历史落盘，重启后"她"完整记得 ----
    def save(self):
        save_state(self.state, self.facts, self.memories, self.store_path,
                   self.history)

    def load(self):
        """从存档恢复长期状态与对话历史；无存档则保持初始态。返回是否成功。"""
        state, facts, memories, history = load_state(self.store_path)
        if state is None:
            return False
        self.state = state
        self.facts = facts
        self.memories = memories
        self.history = list(history)
        return True

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
                base_url=os.getenv("LLM_BASE_URL", "https://open.bigmodel.cn/api/paas/v4/"),
                timeout=60.0,   # 单次请求超时，避免网络卡住时对话永远停在"……"
                max_retries=1,  # 网络抖动自动重试一次
            )
        return self._client

    @property
    def model(self):
        return os.getenv("LLM_MODEL", "glm-5.3-flash")

    def _chat(self, messages, temperature=0.9, max_tokens=2000, json_mode=False):
        kwargs = dict(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        try:
            resp = self.client.chat.completions.create(**kwargs)
        except Exception:
            # 部分兼容端点不支持 response_format，自动降级重试
            if not json_mode:
                raise
            kwargs.pop("response_format", None)
            resp = self.client.chat.completions.create(**kwargs)
        return resp.choices[0].message.content

    def _chat_stream(self, messages, temperature=0.9, max_tokens=2000, json_mode=False):
        """流式调用：逐段 yield 增量文本。"""
        kwargs = dict(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        try:
            stream = self.client.chat.completions.create(**kwargs)
        except Exception:
            # 部分兼容端点不支持 response_format，自动降级重试
            if not json_mode:
                raise
            kwargs.pop("response_format", None)
            stream = self.client.chat.completions.create(**kwargs)
        for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta

    @staticmethod
    def _apply_patch(patch, data):
        try:
            patch["favorability_delta"] = int(data.get("favorability_delta", 0))
            patch["mood_delta"] = int(data.get("mood_delta", 0))
        except (ValueError, TypeError):
            pass
        for key in ("inner_voice", "memory"):
            val = data.get(key, "")
            if isinstance(val, str):
                patch[key] = val.strip()
        return str(data.get("reply") or data.get("text") or "").strip()

    @staticmethod
    def _parse(raw):
        """解析模型响应为 (台词, patch)。容错：整体JSON → 嵌入JSON → STATE标签 → 裸JSON。"""
        patch = {"favorability_delta": 0, "mood_delta": 0,
                 "inner_voice": "", "memory": ""}

        # 路径 1：整体即 JSON（JSON 模式的正常输出）
        stripped = raw.strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            try:
                data = json.loads(stripped)
                if isinstance(data, dict) and "favorability_delta" in data:
                    return ChatEngine._apply_patch(patch, data), patch
            except json.JSONDecodeError:
                pass

        # 路径 2：JSON 裹在台词/代码块中间
        start, end = raw.find("{"), raw.rfind("}")
        if start != -1 and end > start and (start > 0 or end < len(stripped) - 1):
            try:
                data = json.loads(raw[start:end + 1])
                if isinstance(data, dict) and "favorability_delta" in data:
                    ChatEngine._apply_patch(patch, data)
                    return STATE_TAG_RE.sub("", raw[:start] + raw[end + 1:]).strip(), patch
            except json.JSONDecodeError:
                pass

        # 路径 3/4：<STATE> 标签 或 裸 JSON（兼容老格式/其他模型）
        m = STATE_RE.search(raw)
        if m:
            block, text = m.group(1), raw[:m.start()] + raw[m.end():]
            text = STATE_TAG_RE.sub("", text).strip()
        else:
            fm = re.search(r'\{\s*"favorability_delta".*?\}', raw, re.S)
            if not fm:
                # 路径 5：JSON 被 max_tokens 截断——正则抢救各字段残片
                return ChatEngine._salvage(raw, patch)
            block, text = fm.group(0), (raw[:fm.start()] + raw[fm.end():]).strip()
        try:
            data = json.loads(block)
            if isinstance(data, dict):
                text = ChatEngine._apply_patch(patch, data) or text
        except json.JSONDecodeError:
            iv = re.search(r'"inner_voice"\s*:\s*"([^"]*)"', block)
            if iv:
                patch["inner_voice"] = iv.group(1).strip()
        return text, patch

    @staticmethod
    def _unescape(s):
        try:
            return json.loads(f'"{s}"')
        except json.JSONDecodeError:
            return s.replace('\\"', '"').replace("\\n", "\n").replace("\\'", "'")

    @staticmethod
    def _partial_reply(raw):
        """从（可能残缺的）流式 JSON 中实时截取 reply 台词前缀，供逐字显示。"""
        m = re.search(r'"reply"\s*:\s*"', raw)
        if not m:
            return ""
        s = raw[m.end():]
        # 截到第一个未转义的闭合引号（若已出现）
        i, end = 0, len(s)
        while i < len(s):
            if s[i] == "\\":
                i += 2
                continue
            if s[i] == '"':
                end = i
                break
            i += 1
        s = s[:end]
        # 末尾可能有残缺的转义序列，修掉以保证可解码
        trailing = len(s) - len(s.rstrip("\\"))
        if trailing % 2 == 1:
            s = s[:-1]
        s = re.sub(r"\\u[0-9a-fA-F]{0,3}$", "", s)
        return ChatEngine._unescape(s)

    @staticmethod
    def _salvage(raw, patch):
        """JSON 截断时的最后防线：把能捞到的字段残片捞回来。"""
        text = ""
        m = re.search(r'"reply"\s*:\s*"(.*?)"\s*[,}]', raw, re.S)
        if not m:
            m = re.search(r'"reply"\s*:\s*"(.+)$', raw, re.S)
        if m:
            text = ChatEngine._unescape(m.group(1)).strip()
        for key, name in (("inner_voice", "inner_voice"), ("memory", "memory")):
            mm = re.search(rf'"{key}"\s*:\s*"([^"]*)"', raw)
            if mm and mm.group(1).strip():
                patch[name] = ChatEngine._unescape(mm.group(1)).strip()
        for key, name in (("favorability_delta", "favorability_delta"),
                          ("mood_delta", "mood_delta")):
            mm = re.search(rf'"{key}"\s*:\s*(-?\d+)', raw)
            if mm:
                try:
                    patch[name] = int(mm.group(1))
                except ValueError:
                    pass
        return text or "……", patch

    def _build_messages(self, user_text):
        """组装本轮对话消息：System 人设 + 窗口内历史 + 用户输入。"""
        messages = [{"role": "system", "content": build_system_prompt(
            self.state, self.facts, self.memories)}]
        messages += self.history[-self.window:]
        messages.append({"role": "user", "content": user_text})
        return messages

    def _finalize(self, user_text, text, patch):
        """把本轮结果落到状态机、记忆和历史上，返回统一的结果 dict。"""
        if not text:
            text = "……"
        self.state.apply(patch["favorability_delta"], patch["mood_delta"])
        self._remember(patch)
        self.history.append({"role": "user", "content": user_text})
        self.history.append({"role": "assistant", "content": text})
        self._consolidate()
        return {
            "text": text,
            "inner_voice": patch["inner_voice"],
            "memory": patch["memory"],
            "fav_delta": patch["favorability_delta"],
            "mood_delta": patch["mood_delta"],
            "state": self.state,
        }

    def reply(self, user_text):
        """完整跑一轮对话，返回 {text, inner_voice, fav/mood_delta, memory, state}。"""
        if not os.getenv("LLM_API_KEY"):
            return self._mock_reply(user_text)

        # 单次调用：台词、内心、状态、记忆出自同一个"脑子"，才有口是心非的张力
        raw = self._chat(self._build_messages(user_text), json_mode=True)
        text, patch = self._parse(raw)
        return self._finalize(user_text, text, patch)

    def reply_stream(self, user_text):
        """流式版 reply：先逐字 yield {"partial": 台词前缀}，最后 yield 完整结果 dict。"""
        if not os.getenv("LLM_API_KEY"):
            r = self._mock_reply(user_text)
            yield {"partial": r["text"]}
            yield r
            return

        raw = ""
        last = ""
        for chunk in self._chat_stream(self._build_messages(user_text), json_mode=True):
            raw += chunk
            partial = self._partial_reply(raw)
            if partial != last:
                last = partial
                yield {"partial": partial}

        text, patch = self._parse(raw)
        if not text:
            text = last.strip()  # 兜底：解析失败就用流式期间已展示的台词
        yield self._finalize(user_text, text, patch)

    def _remember(self, patch):
        """高情绪波动的瞬间存入"心里的余温"，优先保留强烈记忆。"""
        note = patch.get("memory", "").strip()
        if not note:
            return
        tag = _memory_tag(patch["favorability_delta"], patch["mood_delta"])
        if tag is None:
            return  # 情绪波动不够强：不记录，避免记忆泛滥
        self.memories.append({"tag": tag, "note": note})
        self.memories = self.memories[-8:]

    # 无 API Key 时的演示回复：随对话轮次推进，好感度逐步上升
    _MOCK_SCRIPT = [
        ("……你好。有什么事吗？如果只是想闲聊，我劝你去找侦探团那帮小鬼。", 1, 2,
         "又是一个自来熟的家伙。", ""),
        ("哼，至少你比柯南那家伙有礼貌一点。（低头翻动书页）说吧，想聊什么？", 2, 5,
         "……倒也不讨厌。", "他认真说话的样子，倒不讨厌。"),
        ("（停下手中的实验记录）你对化学感兴趣？……呵，难得。普通的有机化学问题，我可以教你。", 2, 7,
         "认真地听人说话的感觉，久违了。", ""),
        ("叫我哀就行。（移开视线）……只是叫起来方便而已，别多想。", 3, 6,
         "心跳有点快……错觉吧。", "他递来热可可的那天，指尖碰过杯壁，温度留了很久。"),
        ("（轻声）如果早点遇到像你这样的人，也许一切都会不一样。……没什么，自言自语罢了。", 2, 5,
         "这样的日子，能持续下去就好了。", ""),
    ]

    def _mock_reply(self, user_text):
        idx = min(len(self.history) // 2, len(self._MOCK_SCRIPT) - 1)
        text, fav_d, mood_d, inner, memory_note = self._MOCK_SCRIPT[idx]
        self.state.apply(fav_d, mood_d)
        if memory_note:
            self.memories.append({"tag": "温暖", "note": memory_note})
            self.memories = self.memories[-8:]
        self.history.append({"role": "user", "content": user_text})
        self.history.append({"role": "assistant", "content": text})
        return {"text": text, "inner_voice": inner + "（演示模式）",
                "memory": memory_note, "fav_delta": fav_d, "mood_delta": mood_d,
                "state": self.state}

    def _consolidate(self):
        """旧对话溢出窗口时，压缩成长期事实记忆。"""
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
            start, end = out.find("["), out.rfind("]")
            if start == -1 or end <= start:
                return  # 模型没按格式返回数组，放弃本次提取
            data = json.loads(out[start:end + 1])
            if isinstance(data, list):
                for f in data:
                    f = str(f).strip()
                    if f and f not in self.facts:
                        self.facts.append(f)
                self.facts = self.facts[-20:]
        except Exception:
            # 记忆失败不影响对话本身
            pass
