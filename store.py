"""会话持久化：状态机、记忆与对话历史落盘。

把"她"的长期状态（好感度/心情）、长期记忆、情感瞬间和对话历史保存为
本地 JSON，重启后完整恢复——关掉程序再打开，聊天记录和关系进度都还在。
"""

import json
from dataclasses import asdict
from pathlib import Path

from state import EmotionState

DEFAULT_STORE = "haibara_state.json"


def save_state(state, facts, memories, path=DEFAULT_STORE, history=None):
    """把长期状态与对话历史写入 JSON 文件。"""
    payload = {
        "state": asdict(state),
        "facts": list(facts or []),
        "memories": list(memories or []),
        "history": list(history or []),
    }
    Path(path).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def load_state(path=DEFAULT_STORE):
    """读取存档，返回 (state, facts, memories, history)。

    文件不存在或损坏时返回 (None, [], [], [])，由调用方决定是否回退到初始状态。
    旧版本存档没有 history 字段时返回空列表，兼容处理。
    """
    p = Path(path)
    if not p.exists():
        return None, [], [], []
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return None, [], [], []

    state_data = payload.get("state")
    state = EmotionState(**state_data) if isinstance(state_data, dict) else None
    facts = payload.get("facts", [])
    memories = payload.get("memories", [])
    history = payload.get("history", [])
    if not isinstance(facts, list):
        facts = []
    if not isinstance(memories, list):
        memories = []
    if not isinstance(history, list):
        history = []
    return state, facts, memories, history
