#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["requests<3"]
# ///

"""Poll Telegram Bot API getUpdates and optionally advance the offset.

Writes the raw JSON response to --out (default: /tmp/tg_updates.json).

Important: Telegram updates are queue-like. If you advance the offset, older
updates may no longer be retrievable via getUpdates.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

import requests


def _default_offset_file() -> Path:
    state = os.environ.get("XDG_STATE_HOME") or (Path.home() / ".local/state")
    return Path(state) / "telegram_bot_offset"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="/tmp/tg_updates.json", help="Output file for raw JSON")
    ap.add_argument(
        "--offset-file",
        default=str(_default_offset_file()),
        help="File storing the next offset (update_id) to fetch",
    )
    ap.add_argument("--timeout", type=int, default=30, help="Long-poll timeout seconds")
    ap.add_argument("--limit", type=int, default=100, help="Max updates to return")
    ap.add_argument(
        "--allowed-updates",
        default="",
        help='Comma-separated list, e.g. "message,edited_message,callback_query" (optional)',
    )
    ap.add_argument(
        "--consume",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Whether to advance the offset after fetching",
    )
    ap.add_argument(
        "--offset",
        type=int,
        default=None,
        help="Override offset (next update_id to fetch). If set, offset-file is ignored for reading.",
    )

    args = ap.parse_args()

    token = os.environ.get("TELEGRAM_BOT_TOKEN") or os.environ.get("TG_BOT_TOKEN")
    if not token:
        raise SystemExit("Missing TELEGRAM_BOT_TOKEN (or TG_BOT_TOKEN) in environment")

    base = f"https://api.telegram.org/bot{token}"
    url = f"{base}/getUpdates"

    offset_path = Path(args.offset_file)
    if args.offset is None:
        try:
            offset = int(offset_path.read_text().strip() or "0")
        except FileNotFoundError:
            offset = 0
    else:
        offset = args.offset

    params: dict[str, Any] = {
        "timeout": args.timeout,
        "limit": args.limit,
        "offset": offset,
    }
    if args.allowed_updates.strip():
        allowed = [s.strip() for s in args.allowed_updates.split(",") if s.strip()]
        params["allowed_updates"] = json.dumps(allowed)

    r = requests.get(url, params=params, timeout=args.timeout + 10)
    r.raise_for_status()
    payload = r.json()

    Path(args.out).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")

    updates = payload.get("result") or []
    if not updates:
        print("updates=0")
        return 0

    max_id = max(u.get("update_id", -1) for u in updates)
    print(f"updates={len(updates)}")
    print(f"min_update_id={updates[0].get('update_id')}")
    print(f"max_update_id={max_id}")

    if args.consume and max_id >= 0:
        offset_path.parent.mkdir(parents=True, exist_ok=True)
        offset_path.write_text(str(max_id + 1) + "\n")
        print(f"next_offset_written={max_id + 1}")
    else:
        print("consume=false (offset not advanced)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
