#!/usr/bin/env python3
"""Extract raw Telegram update objects from a getUpdates dump.

Examples:
  ./extract_update.py /tmp/tg_updates.json --chat-id 567113516 --message-id 933
  ./extract_update.py /tmp/tg_updates.json --update-id 551691725

Prints matching update(s) as JSON (one per match).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable


def _iter_updates(payload: dict[str, Any]) -> Iterable[dict[str, Any]]:
    res = payload.get("result")
    if isinstance(res, list):
        for u in res:
            if isinstance(u, dict):
                yield u


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("dump", help="Path to getUpdates JSON dump")
    ap.add_argument("--update-id", type=int)
    ap.add_argument("--chat-id", type=int)
    ap.add_argument("--message-id", type=int)
    ap.add_argument(
        "--kind",
        default="message,edited_message,channel_post,edited_channel_post",
        help="Comma-separated fields to check for chat/message (default: common message kinds)",
    )

    args = ap.parse_args()

    payload = json.loads(Path(args.dump).read_text())

    kinds = [k.strip() for k in args.kind.split(",") if k.strip()]

    matches = []
    for u in _iter_updates(payload):
        if args.update_id is not None and u.get("update_id") != args.update_id:
            continue

        if args.chat_id is None and args.message_id is None:
            matches.append(u)
            continue

        found = False
        for k in kinds:
            m = u.get(k)
            if not isinstance(m, dict):
                continue
            chat = m.get("chat")
            if not isinstance(chat, dict):
                continue
            if args.chat_id is not None and chat.get("id") != args.chat_id:
                continue
            if args.message_id is not None and m.get("message_id") != args.message_id:
                continue
            found = True
            break

        if found:
            matches.append(u)

    for m in matches:
        print(json.dumps(m, ensure_ascii=False, indent=2))

    return 0 if matches else 1


if __name__ == "__main__":
    raise SystemExit(main())
