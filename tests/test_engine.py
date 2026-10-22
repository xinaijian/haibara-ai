"""对话引擎单元测试：响应解析容错、记忆瞬间归类、持久化往返。

不依赖网络与 API Key，只测纯逻辑。
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engine import ChatEngine, _memory_tag
from state import EmotionState
from store import load_state, save_state


class TestParse(unittest.TestCase):
    def test_whole_json(self):
        raw = ('{"reply":"哼，随便你。","favorability_delta":2,"mood_delta":5,'
               '"inner_voice":"倒也不是没意思。","memory":""}')
        text, patch = ChatEngine._parse(raw)
        self.assertEqual(text, "哼，随便你。")
        self.assertEqual(patch["favorability_delta"], 2)
        self.assertEqual(patch["mood_delta"], 5)
        self.assertEqual(patch["inner_voice"], "倒也不是没意思。")

    def test_state_tag_extraction(self):
        raw = '我最讨厌睡眠了。\n<STATE>{"favorability_delta":-1,"mood_delta":-3}</STATE>'
        text, patch = ChatEngine._parse(raw)
        self.assertEqual(text, "我最讨厌睡眠了。")
        self.assertEqual(patch["favorability_delta"], -1)
        self.assertEqual(patch["mood_delta"], -3)

    def test_embedded_json(self):
        raw = '好的。\n{"favorability_delta":1,"mood_delta":2}'
        text, patch = ChatEngine._parse(raw)
        self.assertEqual(text, "好的。")
        self.assertEqual(patch["favorability_delta"], 1)

    def test_bare_json_fragment(self):
        raw = '一些台词 {"favorability_delta":2}'
        text, patch = ChatEngine._parse(raw)
        self.assertEqual(text, "一些台词")
        self.assertEqual(patch["favorability_delta"], 2)

    def test_no_json_falls_back(self):
        raw = '完全没有结构化输出的情形'
        text, patch = ChatEngine._parse(raw)
        self.assertEqual(text, "……")
        self.assertEqual(patch["favorability_delta"], 0)


class TestSalvage(unittest.TestCase):
    def test_salvage_recovers_truncated_reply(self):
        patch = {"favorability_delta": 0, "mood_delta": 0,
                 "inner_voice": "", "memory": ""}
        raw = '{"reply":"我是没说完的台'
        text, _ = ChatEngine._salvage(raw, patch)
        self.assertEqual(text, "我是没说完的台")

    def test_salvage_recovers_inner_voice(self):
        patch = {"favorability_delta": 0, "mood_delta": 0,
                 "inner_voice": "", "memory": ""}
        raw = '{"reply":"xx", "inner_voice":"有点在意", "favorability_delta":1}'
        _, patch = ChatEngine._salvage(raw, patch)
        self.assertEqual(patch["inner_voice"], "有点在意")


class TestPartialReply(unittest.TestCase):
    def test_partial_reply(self):
        self.assertEqual(ChatEngine._partial_reply('{"reply":"你好吗"'), "你好吗")


class TestMemoryTag(unittest.TestCase):
    def test_tags(self):
        self.assertEqual(_memory_tag(-2, 0), "受伤")
        self.assertEqual(_memory_tag(0, -6), "难过")
        self.assertEqual(_memory_tag(3, 0), "心动")
        self.assertEqual(_memory_tag(2, 0), "温暖")
        self.assertEqual(_memory_tag(0, 7), "开心")

    def test_no_tag_when_calm(self):
        self.assertIsNone(_memory_tag(1, 1))


class TestPersist(unittest.TestCase):
    def test_store_roundtrip(self):
        state = EmotionState(favorability=42, mood=7)
        facts = ["他喜欢咖啡", "答应周五一起看展"]
        memories = [{"tag": "温暖", "note": "他递来的热可可"}]
        history = [{"role": "user", "content": "你好"},
                   {"role": "assistant", "content": "……有事？"}]
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "state.json"
            save_state(state, facts, memories, str(path), history)
            s2, f2, m2, h2 = load_state(str(path))
        self.assertEqual(s2, state)
        self.assertEqual(f2, facts)
        self.assertEqual(m2, memories)
        self.assertEqual(h2, history)

    def test_load_old_archive_without_history(self):
        """旧版存档没有 history 字段，读取时应兼容返回空列表。"""
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "old.json"
            path.write_text(
                json.dumps({"state": {"favorability": 30, "mood": 0},
                            "facts": [], "memories": []}, ensure_ascii=False),
                encoding="utf-8",
            )
            s, f, m, h = load_state(str(path))
        self.assertEqual(s.favorability, 30)
        self.assertEqual(h, [])

    def test_load_missing_file(self):
        with tempfile.TemporaryDirectory() as d:
            s, f, m, h = load_state(str(Path(d) / "nope.json"))
        self.assertIsNone(s)
        self.assertEqual((f, m, h), ([], [], []))

    def test_load_corrupt_file(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "bad.json"
            path.write_text("{ not json", encoding="utf-8")
            s, f, m, h = load_state(str(path))
        self.assertIsNone(s)

    def test_engine_save_and_load(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "state.json"
            eng = ChatEngine(store_path=str(path))
            eng.state.apply(2, 5)
            eng.facts.append("他救过的小猫")
            eng.history.append({"role": "user", "content": "今晚吃什么"})
            eng.history.append({"role": "assistant", "content": "……随便。"})
            eng.save()
            eng2 = ChatEngine(store_path=str(path))
            self.assertTrue(eng2.load())
            self.assertEqual(eng2.state, eng.state)
            self.assertEqual(eng2.facts, eng.facts)
            self.assertEqual(eng2.history, eng.history)


if __name__ == "__main__":
    unittest.main()