"""情绪状态机单元测试：验证量化、钳制、余韵与阶段跃迁边界。"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from state import MAX_FAV_DELTA, MAX_MOOD_DELTA, EmotionState


class TestDefaults(unittest.TestCase):
    def test_default_values(self):
        s = EmotionState()
        self.assertEqual(s.favorability, 10)
        self.assertEqual(s.mood, 0)
        self.assertEqual(s.stage, "冷淡戒备")
        self.assertEqual(s.mood_desc, "平静")


class TestApply(unittest.TestCase):
    def test_positive_apply(self):
        s = EmotionState()
        s.apply(2, 5)
        self.assertEqual(s.favorability, 12)
        self.assertEqual(s.mood, 5)

    def test_fav_delta_clamped(self):
        s = EmotionState()
        s.apply(100, 0)
        self.assertEqual(s.favorability, 10 + MAX_FAV_DELTA)

    def test_mood_delta_clamped(self):
        s = EmotionState()
        s.apply(0, 100)
        self.assertEqual(s.mood, MAX_MOOD_DELTA)

    def test_favorability_never_below_zero(self):
        s = EmotionState(favorability=1, mood=0)
        s.apply(-MAX_FAV_DELTA, 0)
        self.assertEqual(s.favorability, 0)

    def test_favorability_never_above_hundred(self):
        s = EmotionState(favorability=99, mood=0)
        s.apply(MAX_FAV_DELTA, 0)
        self.assertEqual(s.favorability, 100)

    def test_mood_decays_toward_zero(self):
        """无新刺激时，心情保留四成并自然平复。"""
        s = EmotionState(mood=50)
        s.apply(0, 0)
        self.assertEqual(s.mood, 20)


class TestStages(unittest.TestCase):
    def test_stage_thresholds(self):
        cases = [(0, "冷淡戒备"), (20, "初步接纳"), (40, "毒舌熟人"),
                 (60, "有限信任"), (80, "袒露内心")]
        for fav, name in cases:
            with self.subTest(fav=fav):
                self.assertEqual(EmotionState(favorability=fav).stage, name)

    def test_stage_below_threshold(self):
        self.assertEqual(EmotionState(favorability=19).stage, "冷淡戒备")
        self.assertEqual(EmotionState(favorability=59).stage, "毒舌熟人")

    def test_next_stage(self):
        name, need = EmotionState(favorability=10).next_stage
        self.assertEqual((name, need), ("初步接纳", 10))

    def test_next_stage_maxed(self):
        self.assertIsNone(EmotionState(favorability=85).next_stage)


class TestMoodDesc(unittest.TestCase):
    def test_mood_boundaries(self):
        cases = [(-100, "糟糕"), (-60, "低落"), (-20, "平静"),
                 (20, "不错"), (60, "很好")]
        for mood, name in cases:
            with self.subTest(mood=mood):
                self.assertEqual(EmotionState(mood=mood).mood_desc, name)

    def test_mood_below_threshold(self):
        self.assertEqual(EmotionState(mood=-59).mood_desc, "低落")
        self.assertEqual(EmotionState(mood=59).mood_desc, "不错")


if __name__ == "__main__":
    unittest.main()