#!/usr/bin/env python3
"""
tools/queue_status.py
パイプラインキューの状態を表示する。
"""
import json
from pathlib import Path

QUEUE_PATH = Path(__file__).parent.parent / "workspace" / "pipeline_queue.json"

STATUS_ICON = {
    "done":        "✅",
    "in_progress": "🔄",
    "pending":     "⏳",
    "error":       "❌",
    "skip":        "⏭️",
}

def main():
    q = json.loads(QUEUE_PATH.read_text(encoding="utf-8"))
    print(f"\n{'='*55}")
    print(f"  調査パイプライン キュー状況")
    print(f"{'='*55}")
    for m in q["municipalities"]:
        icon = STATUS_ICON.get(m["status"], "?")
        done  = ", ".join(m.get("phases_done", [])) or "-"
        todo  = ", ".join(m.get("phases_todo", [])) or "-"
        print(f"\n{icon} {m['prefecture']} {m['name']}  [{m['status']}]")
        print(f"   完了: {done}")
        print(f"   残り: {todo}")
        if m.get("note"):
            print(f"   備考: {m['note']}")
    print(f"\n{'='*55}\n")

    next_m = next((m for m in q["municipalities"] if m["status"] in ("pending", "in_progress")), None)
    if next_m:
        print(f"▶ 次の処理対象: {next_m['prefecture']} {next_m['name']}")
        print(f"  次フェーズ: {next_m['phases_todo'][0] if next_m['phases_todo'] else '（全フェーズ完了）'}")
    else:
        print("🎉 全自治体の処理が完了しています。")
    print()

if __name__ == "__main__":
    main()
