#!/usr/bin/env python3
"""List / filter Telegram messages from a getUpdates JSON dump.

This does NOT fetch chat history from Telegram (Bot API can't do that).
It only inspects what your bot has received (polling/webhook) and what you saved.

Examples:
  # After fetching updates into /tmp/tg_updates.json
  ./list_messages.py /tmp/tg_updates.json --chat-id 123 --limit 20

  # Only messages from a particular sender inside the chat
  ./list_messages.py /tmp/tg_updates.json --chat-id 123 --from-id 777 --limit 50

  # Direct replies to a particular message_id
  ./list_messages.py /tmp/tg_updates.json --chat-id 123 --reply-to 456

  # Topic/thread (forum) messages
  ./list_messages.py /tmp/tg_updates.json --chat-id 123 --thread-id 999

Output:
  - default: one compact line per message
  - --json: print the raw message object as JSON (one per line)
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


DEFAULT_KINDS = "message,edited_message,channel_post,edited_channel_post"


def _iter_updates(payload: dict[str, Any]) -> Iterable[dict[str, Any]]:
    res = payload.get("result")
    if isinstance(res, list):
        for u in res:
            if isinstance(u, dict):
                yield u


def _iter_messages(
    payload: dict[str, Any],
    kinds: list[str],
) -> Iterable[dict[str, Any]]:
    for u in _iter_updates(payload):
        for k in kinds:
            m = u.get(k)
            if isinstance(m, dict):
                yield m


def _ts(sec: int | float | None) -> str:
    if not sec:
        return "-"
    dt = datetime.fromtimestamp(sec, tz=timezone.utc).astimezone()
    return dt.isoformat(timespec="seconds")


def _text_preview(m: dict[str, Any], width: int = 80) -> str:
    # text / caption are the common human-readable fields
    txt = m.get("text")
    if not isinstance(txt, str) or not txt.strip():
        txt = m.get("caption")
    if not isinstance(txt, str) or not txt.strip():
        # fall back to a rough type indicator
        if "photo" in m:
            txt = "<photo>"
        elif "document" in m:
            txt = "<document>"
        elif "sticker" in m:
            txt = "<sticker>"
        elif "voice" in m:
            txt = "<voice>"
        elif "video" in m:
            txt = "<video>"
        else:
            txt = "<non-text message>"

    one = " ".join(txt.split())
    if len(one) > width:
        one = one[: width - 1] + "…"
    return one


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("dump", help="Path to getUpdates JSON dump")
    ap.add_argument("--kind", default=DEFAULT_KINDS, help=f"Comma-separated fields (default: {DEFAULT_KINDS})")

    ap.add_argument("--chat-id", type=int, help="Filter by chat.id")
    ap.add_argument("--from-id", type=int, help="Filter by from.id (sender user id)")
    ap.add_argument("--thread-id", type=int, help="Filter by message_thread_id (topics/forums)")
    ap.add_argument("--reply-to", type=int, help="Filter messages that reply to this message_id")

    ap.add_argument("--limit", type=int, default=0, help="Keep only the most recent N messages (0 = no limit)")
    ap.add_argument("--json", action="store_true", help="Print raw message JSON (NDJSON)")

    args = ap.parse_args()

    payload = json.loads(Path(args.dump).read_text())
    kinds = [k.strip() for k in args.kind.split(",") if k.strip()]

    msgs: list[dict[str, Any]] = []
    for m in _iter_messages(payload, kinds):
        chat = m.get("chat")
        if not isinstance(chat, dict):
            continue
        if args.chat_id is not None and chat.get("id") != args.chat_id:
            continue

        if args.from_id is not None:
            frm = m.get("from")
            if not isinstance(frm, dict) or frm.get("id") != args.from_id:
                continue

        if args.thread_id is not None and m.get("message_thread_id") != args.thread_id:
            continue

        if args.reply_to is not None:
            rtm = m.get("reply_to_message")
            if not isinstance(rtm, dict) or rtm.get("message_id") != args.reply_to:
                continue

        msgs.append(m)

    # Sort by date/message_id for stable output
    msgs.sort(key=lambda x: (x.get("date") or 0, x.get("message_id") or 0))

    if args.limit and len(msgs) > args.limit:
        msgs = msgs[-args.limit :]

    if args.json:
        for m in msgs:
            print(json.dumps(m, ensure_ascii=False))
        return 0 if msgs else 1

    for m in msgs:
        chat = m.get("chat") or {}
        frm = m.get("from") or {}
        line = {
            "ts": _ts(m.get("date")),
            "chat_id": chat.get("id"),
            "message_id": m.get("message_id"),
            "from_id": frm.get("id"),
            "from": (frm.get("username") or "").strip() or (frm.get("first_name") or ""),
            "thread_id": m.get("message_thread_id"),
            "reply_to": (m.get("reply_to_message") or {}).get("message_id") if isinstance(m.get("reply_to_message"), dict) else None,
            "text": _text_preview(m),
        }
        # compact, grep-friendly
        print(
            f"{line['ts']} chat={line['chat_id']} msg={line['message_id']} from={line['from_id']}"
            f" thread={line['thread_id'] or '-'} reply_to={line['reply_to'] or '-'}"
            f" | {line['text']}"
        )

    return 0 if msgs else 1


if __name__ == "__main__":
    raise SystemExit(main())
