"""终端试聊工具：不开界面，快速调试人设和状态机。

用法：python cli.py
"""

from engine import ChatEngine


def main():
    eng = ChatEngine()
    print("灰原哀 已上线（输入 exit 退出）\n")
    while True:
        try:
            q = input("你: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if q.lower() in ("exit", "quit"):
            break
        if not q:
            continue
        try:
            r = eng.reply(q)
        except Exception as e:
            print(f"[调用失败] {e}\n")
            continue
        s = r["state"]
        print(f"\n灰原哀: {r['text']}")
        if r["inner_voice"]:
            print(f"  (内心: {r['inner_voice']})")
        print(f"  [好感度 {s.favorability} | {s.stage} | 心情 {s.mood_desc}({s.mood})]")
        if eng.facts:
            print(f"  [记忆] {' / '.join(eng.facts)}")
        print()


if __name__ == "__main__":
    main()
