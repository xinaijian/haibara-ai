"""会话持久化：状态机与记忆落盘。

把"她"的长期状态（好感度/心情）、长期记忆、情感瞬间保存为本地 JSON，
重启后加载，让"长期记忆"名副其实。滚动对话窗口不落盘（那是短期上下文）。
"""

import json
from dataclasses import asdict
from pathlib import Path

from state import EmotionState

DEFAULT_STORE = "haibara_state.json"


def save_state(state, facts, memories, path=DEFAULT_STORE):
    """把长期状态写入 JSON 文件。"""
    payload = {
        "state": asdict(state),
        "facts": list(facts or []),
        "memories": list(memories or []),
    }
    Path(path).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def load_state(path=DEFAULT_STORE):
    """读取存档，返回 (state, facts, memories)。

    文件不存在或损坏时返回 (None, [], [])，由调用方决定是否回退到初始状态。
    """
    p = Path(path)
    if not p.exists():
        return None, [], []
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return None, [], []

    state_data = payload.get("state")
    state = EmotionState(**state_data) if isinstance(state_data, dict) else None
    facts = payload.get("facts", [])
    memories = payload.get("memories", [])
    if not isinstance(facts, list):
        facts = []
    if not isinstance(memories, list):
        memories = []
    return state, facts, memories