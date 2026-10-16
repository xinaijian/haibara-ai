"""情绪状态机：把"情感"建模为可量化、可演化的状态变量。

- favorability: 好感度 0~100，长期缓慢变化，决定关系阶段
- mood: 心情 -100~100，短期波动，影响语气
"""

from dataclasses import dataclass

# (好感度下限, 阶段名, 该阶段的行为提示)
STAGES = [
    (0, "冷淡戒备", "保持疏离与礼貌的冷淡，回答简短，对私人话题直接回避或反问"),
    (20, "初步接纳", "愿意正常交谈，偶尔纠正对方，但不主动表露情绪"),
    (40, "毒舌熟人", "用讽刺和吐槽表达熟悉感，嘴上不饶人，但会认真回应对方的事"),
    (60, "有限信任", "偶尔透露真实想法，会用别扭的方式表达关心"),
    (80, "袒露内心", "愿意谈及过去、恐惧与温柔，语气明显柔软，但仍保留自尊"),
]

# (心情下限, 心情描述)
MOODS = [
    (-100, "糟糕"),
    (-60, "低落"),
    (-20, "平静"),
    (20, "不错"),
    (60, "很好"),
]

# 单轮变化量上限，防止一次对话就攻略成功
MAX_FAV_DELTA = 3
MAX_MOOD_DELTA = 10


def _clamp(value, lo, hi):
    return max(lo, min(hi, value))


@dataclass
class EmotionState:
    favorability: int = 10
    mood: int = 0

    def apply(self, fav_delta=0, mood_delta=0):
        fav_delta = _clamp(int(fav_delta), -MAX_FAV_DELTA, MAX_FAV_DELTA)
        mood_delta = _clamp(int(mood_delta), -MAX_MOOD_DELTA, MAX_MOOD_DELTA)
        self.favorability = _clamp(self.favorability + fav_delta, 0, 100)
        self.mood = _clamp(self.mood + mood_delta, -100, 100)

    @property
    def stage(self):
        return next(name for lo, name, _ in reversed(STAGES) if self.favorability >= lo)

    @property
    def stage_hint(self):
        return next(hint for lo, _, hint in reversed(STAGES) if self.favorability >= lo)

    @property
    def mood_desc(self):
        return next(name for lo, name in reversed(MOODS) if self.mood >= lo)
